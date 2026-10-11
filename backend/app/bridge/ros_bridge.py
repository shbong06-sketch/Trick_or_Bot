import asyncio
import math
import threading

import rclpy
from geometry_msgs.msg import TwistStamped
from rclpy.duration import Duration
from rclpy.executors import ExternalShutdownException, SingleThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from rclpy.signals import SignalHandlerOptions
from rclpy.time import Time
from sensor_msgs.msg import CameraInfo, CompressedImage
from tf2_ros import Buffer, ExtrapolationException, TransformException, TransformListener
from tob_interfaces.msg import GameState
from tob_interfaces.srv import GameCommand

from ..protocol import Pose7
from ..settings import ROBOT
from .base import Bridge, VideoSink

COMMAND_TIMEOUT_S = 2.0  # game_manager 서비스 응답을 기다리는 최대 시간

IMAGE_QOS = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, history=HistoryPolicy.KEEP_LAST, depth=1)
# docs/interfaces.md 10.1 상태 메시지 권장 QoS
STATE_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE,
                       history=HistoryPolicy.KEEP_LAST, depth=1)


class RosBridge(Bridge):
    """rclpy 노드를 별도 스레드 executor로 돌린다."""

    remote_game = True

    def __init__(self):
        cfg = ROBOT["pumpkin"]
        self._map_frame = cfg["map_frame"]
        self._base_frame = cfg["base_frame"]
        self._camera_frame = cfg.get("camera_frame") or None  # 비우면 영상 header.frame_id 사용
        self._tf_timeout = Duration(seconds=float(cfg["tf_timeout_s"]))
        self._sink: VideoSink | None = None
        self._tf_fail = 0

        # 시그널은 uvicorn이 받는다. rclpy가 먼저 종료하면 마지막 정지 명령을 못 보낸다
        rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
        # Gazebo에서는 시뮬레이션 시간을 써야 이동 요청 시각이 pumpkin_controller와 맞는다
        sim_time = [Parameter("use_sim_time", value=bool(ROBOT.get("use_sim_time", False)))]
        self._node = Node("trick_or_bot_game_server", parameter_overrides=sim_time)
        # 이동 요청은 pumpkin_controller → velocity_gate를 거쳐 로봇 cmd_vel이 된다 (직접 발행하지 않는다)
        self._cmd_pub = self._node.create_publisher(TwistStamped, cfg["cmd_request_topic"], 10)
        # 회차 시작은 game_manager가 판정한다 (docs/interfaces.md 5.6 GameCommand)
        self._game_cmd = self._node.create_client(GameCommand, "/tob/game/command")
        self._game_state: dict | None = None
        self._node.create_subscription(GameState, "/tob/game/state", self._on_game_state, STATE_QOS)
        self._node.create_subscription(CompressedImage, cfg["image_topic"], self._on_image, IMAGE_QOS)
        # 카메라 내부 파라미터: camera_info가 오면 그 값, 아직 없으면 자리표시 값
        self._cam: dict | None = None
        if cfg.get("camera_info_topic"):
            self._node.create_subscription(CameraInfo, cfg["camera_info_topic"], self._on_camera_info, IMAGE_QOS)

        # TF는 로봇마다 전용 노드·스레드에서 받는다. 영상 콜백이 TF 도착을 잠깐 기다려도 막히지 않게 하기 위함
        # 로봇 TF가 네임스페이스 아래(/robot2/tf)에 있으면 /tf를 리매핑한다
        self._tf_buffer, self._tf_node, self._tf_listener = self._make_tf("trick_or_bot_tf_pumpkin", cfg)
        boo = ROBOT["boo"]
        self._boo_map, self._boo_base = boo["map_frame"], boo["base_frame"]
        self._boo_tf, self._boo_tf_node, self._boo_tf_listener = self._make_tf("trick_or_bot_tf_boo", boo)

        self._executor = SingleThreadedExecutor()
        self._executor.add_node(self._node)
        self._thread = threading.Thread(target=self._spin, daemon=True)

    @staticmethod
    def _make_tf(name: str, cfg: dict):
        node = Node(name, cli_args=[
            "--ros-args", "-r", f"/tf:={cfg['tf_topic']}", "-r", f"/tf_static:={cfg['tf_static_topic']}"])
        buffer = Buffer()
        return buffer, node, TransformListener(buffer, node, spin_thread=True)

    def _spin(self) -> None:
        try:
            self._executor.spin()
        except ExternalShutdownException:
            pass

    def start(self) -> None:
        self._thread.start()
        cfg = ROBOT["pumpkin"]
        self._node.get_logger().info(
            f"이동 요청 → {self._cmd_pub.topic_name}, "
            f"image ← {cfg['image_topic']}, tf ← {cfg['tf_topic']}")

    def stop(self) -> None:
        self.send_cmd(0.0, 0.0)
        self._executor.shutdown()
        for listener, node in ((self._tf_listener, self._tf_node), (self._boo_tf_listener, self._boo_tf_node)):
            listener.unregister()
            node.destroy_node()
        self._node.destroy_node()
        rclpy.try_shutdown()

    def set_video_sink(self, sink: VideoSink) -> None:
        self._sink = sink

    def camera_info(self) -> dict:
        return dict(self._cam) if self._cam else dict(ROBOT["camera_placeholder"])

    def _on_camera_info(self, msg: CameraInfo) -> None:
        if self._cam is None:
            self._node.get_logger().info(f"camera_info 수신: {msg.width}×{msg.height}, fx={msg.k[0]:.1f}, frame={msg.header.frame_id}")
        self._cam = {"w": msg.width, "h": msg.height, "fx": msg.k[0], "fy": msg.k[4], "cx": msg.k[2], "cy": msg.k[5],
                     "frame": msg.header.frame_id, "src": "camera_info"}

    def send_cmd(self, lin: float, ang: float) -> None:
        msg = TwistStamped()
        msg.header.stamp = self._node.get_clock().now().to_msg()
        msg.header.frame_id = self._base_frame
        msg.twist.linear.x = lin
        msg.twist.angular.z = ang
        self._cmd_pub.publish(msg)

    def _on_game_state(self, msg: GameState) -> None:
        # executor 스레드에서 dict 하나로 바꿔 끼운다. 게임 루프(asyncio)는 game_state()로 읽기만 한다
        self._game_state = {
            "round_id": msg.round_id, "level": msg.level, "phase": msg.phase,
            "elapsed_s": float(msg.elapsed_s), "remaining_s": float(msg.remaining_s),
            "hp": msg.hp, "max_hp": msg.max_hp, "candy_total": msg.candy_total,
            "collected": list(msg.collected_candy_ids), "exit_enabled": msg.exit_enabled,
            "reason": msg.reason,
        }

    def game_state(self) -> dict | None:
        return self._game_state

    async def request_start(self, level: int) -> tuple[bool, str]:
        return await self._game_command(GameCommand.Request.START, level, "")

    async def request_reset(self, round_id: str) -> tuple[bool, str]:
        return await self._game_command(GameCommand.Request.RESET, 0, round_id)

    async def _game_command(self, command: int, level: int, round_id: str) -> tuple[bool, str]:
        name = {GameCommand.Request.START: "START", GameCommand.Request.RESET: "RESET"}.get(command, str(command))
        if not self._game_cmd.service_is_ready():
            return False, "게임 관리자(game_manager)에 연결되지 않았습니다"
        req = GameCommand.Request(command=command, level=level, round_id=round_id)
        # rclpy 응답은 executor 스레드에서 오므로 asyncio 쪽 future로 옮겨 기다린다
        loop = asyncio.get_running_loop()
        done = loop.create_future()
        ros_future = self._game_cmd.call_async(req)
        ros_future.add_done_callback(
            lambda f: loop.call_soon_threadsafe(lambda: done.done() or done.set_result(f.result())))
        try:
            res = await asyncio.wait_for(done, COMMAND_TIMEOUT_S)
        except asyncio.TimeoutError:
            self._game_cmd.remove_pending_request(ros_future)
            return False, "게임 관리자 응답이 없습니다"
        if res is None:
            return False, "게임 관리자 응답이 없습니다"
        self._node.get_logger().info(
            f"{name} {'수락' if res.accepted else '거절'}: round_id={res.round_id or '-'} phase={res.phase} {res.message}")
        return res.accepted, res.message

    @staticmethod
    def _latest_pose(buffer: Buffer, map_frame: str, base_frame: str):
        """가장 최근 TF의 map → base_link (x, y, yaw). 아직 위치추정 전이면 None."""
        try:
            tf = buffer.lookup_transform(map_frame, base_frame, Time())
        except TransformException:
            return None
        t, q = tf.transform.translation, tf.transform.rotation
        yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
        return t.x, t.y, yaw

    def pumpkin_pose(self):
        return self._latest_pose(self._tf_buffer, self._map_frame, self._base_frame)

    def boo_pose(self):
        return self._latest_pose(self._boo_tf, self._boo_map, self._boo_base)

    # ---- 영상 ----
    def _on_image(self, msg: CompressedImage) -> None:
        sink = self._sink
        if sink is None or not sink.want_frame():
            return  # fps 제한·시청자 없음: TF 조회도 하지 않고 버린다
        stamp = msg.header.stamp
        pose = self._camera_pose(msg.header.frame_id, stamp)
        # JPEG 바이트를 그대로 넘긴다 (디코딩·재인코딩 없음)
        sink.push(stamp.sec + stamp.nanosec * 1e-9, pose, bytes(msg.data))

    def _camera_pose(self, image_frame: str, stamp) -> Pose7 | None:
        """촬영 시각의 map → 카메라 광학 프레임 변환. 실패하면 None (그 프레임은 AR을 그리지 않는다)."""
        source, t = self._camera_frame or image_frame, Time.from_msg(stamp)
        try:
            try:
                tf = self._tf_buffer.lookup_transform(self._map_frame, source, t)
            except ExtrapolationException:
                # 영상이 TF보다 먼저 도착한 경우만 잠깐 기다린다. 프레임 자체가 없으면 기다리지 않는다
                tf = self._tf_buffer.lookup_transform(self._map_frame, source, t, self._tf_timeout)
        except TransformException as e:
            self._tf_fail += 1
            if self._tf_fail in (1, 10, 100) or self._tf_fail % 1000 == 0:
                self._node.get_logger().warning(f"TF 조회 실패 {self._tf_fail}회: {e}")
            return None
        t, q = tf.transform.translation, tf.transform.rotation
        return t.x, t.y, t.z, q.x, q.y, q.z, q.w
