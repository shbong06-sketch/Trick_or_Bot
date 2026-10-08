"""웹캠 검출 + car_locator 통합 시나리오 테스트 (사람이 car를 움직이고, 판정은 이 도구가 한다).

webcam_detector, car_locator가 켜진 상태에서 실행한다. 시나리오마다 할 일을 안내 → Enter → 측정 →
✅/❌ 판정을 출력한다. 시작·끝은 /webcam/test_marker (String)로 발행해 rosbag에도 남긴다.

시나리오: S0 기본 점검(자동) / S1 빈 경기장 / S2 dummy만 / S3 car 놓기 / S4 car 이동 / S5 순간 가림 /
          S6 car 치우기 / S7 car+dummy / S8 손·다리 오검출

사용법:
  ros2 run detection_alert scenario_test [--only S3,S4,S6] [--out result.txt]
"""
import argparse
import json
import math
import statistics
import sys
import threading
import time

import rclpy
from rclpy.executors import SingleThreadedExecutor
from geometry_msgs.msg import PointStamped
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String

LATCHED = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                     durability=DurabilityPolicy.TRANSIENT_LOCAL)
ON_LATENCY_MAX = 0.8    # 내 차가 처음 보인 뒤 알림 ON까지 (초)
OFF_LATENCY_MAX = 1.2   # 마지막으로 내 차가 보인 뒤 알림 OFF까지 (초) = off_sec 0.7 + 여유
FINAL_ERR_MAX = 0.07    # 멈춘 뒤 마지막 car_point와 실제 추정 위치 차이 (m)


class Recorder(Node):
    def __init__(self):
        super().__init__('scenario_test')
        self.dets, self.points, self.raws = [], [], []
        self.create_subscription(String, '/webcam/detections', self.on_det, 10)
        self.create_subscription(PointStamped, '/webcam/car_point', lambda m: self.on_pt(self.points, m), LATCHED)
        self.create_subscription(PointStamped, '/webcam/car_point_raw', lambda m: self.on_pt(self.raws, m), 10)
        self.marker = self.create_publisher(String, '/webcam/test_marker', 10)

    def on_det(self, msg):
        d = json.loads(msg.data)
        cars = [x for x in d['detections'] if x['class'] == 'car']
        mine_ids = {x['track_id'] for x in cars if x.get('mine')}
        self.dets.append({
            't': d['stamp'], 'alert': d['car_alert'], 'my_id': d.get('my_id'),
            'n_car': len(cars), 'n_dummy': sum(x['class'] == 'dummy' for x in d['detections']),
            'mine': sum(bool(x.get('mine')) for x in cars),
            'black': [x['black'] for x in cars if x.get('black') is not None],
            'id_ok': d.get('my_id') is not None and d.get('my_id') in mine_ids,
            'head': {k: d.get(k) for k in ('image_w', 'image_h', 'src_w', 'src_h', 'crop_offset', 'crop_scale')},
        })

    @staticmethod
    def on_pt(store, m):
        store.append((m.header.stamp.sec + m.header.stamp.nanosec / 1e9, m.point.x, m.point.y))

    def window(self, t0, t1):
        f = lambda items, key: [i for i in items if t0 <= key(i) <= t1]
        return (f(self.dets, lambda i: i['t']), f(self.points, lambda i: i[0]), f(self.raws, lambda i: i[0]))


def transitions(D):
    """알림 상태가 바뀐 시각 [(t, 새 상태)]."""
    out, prev = [], None
    for d in D:
        if prev is not None and d['alert'] != prev:
            out.append((d['t'], d['alert']))
        prev = d['alert']
    return out


def fmt_black(D):
    b = [v for d in D for v in d['black']]
    return f"car bbox 검정 비율 최소/최대 {min(b):.2f}/{max(b):.2f}" if b else "car 검출 없음"


# ---- 판정: 각 함수는 (D, P, R) → [(ok, 설명)] -------------------------------------------------
def check_s0(D, P, R, rate):
    if not D:
        return [(False, '/webcam/detections가 안 들어옴 → webcam_detector가 켜져 있나?')]
    h = D[-1]['head']
    out = [(h['image_w'] == 640 and h['image_h'] == 640, f"검출 영상 640x640: {h['image_w']}x{h['image_h']}")]
    exp = h['src_h'] / 640 if h['src_w'] >= h['src_h'] else h['src_w'] / 640
    out.append((h['crop_scale'] is not None and abs(h['crop_scale'] - exp) < 1e-3,
                f"crop_scale {h['crop_scale']} (기대 {exp:.3f}), 원본 {h['src_w']}x{h['src_h']}, crop_offset {h['crop_offset']}"))
    hz = (len(D) - 1) / max(D[-1]['t'] - D[0]['t'], 1e-6)
    out.append((0.8 * rate <= hz <= 1.2 * rate, f"검출 발행 주기 {hz:.1f} Hz (기대 {rate} ±20%)"))
    return out


def check_empty(D, P, R, rate):
    out = [(not any(d['alert'] for d in D), f"알림이 한 번도 안 켜짐 (검출 {len(D)}프레임)"),
           (len(P) == 0, f"car_point 발행 {len(P)}개 (0이어야 함)")]
    out.append((True, f"참고: dummy 보인 프레임 {sum(d['n_dummy'] > 0 for d in D)}, {fmt_black(D)}, 내 차 판정 {sum(d['mine'] for d in D)}프레임"))
    return out


def check_s3(D, P, R, rate):
    fm = next((d for d in D if d['mine']), None)
    if fm is None:
        return [(False, f"내 차로 검출된 프레임이 없음 ({fmt_black(D)}) → black-min / 조명 확인")]
    fa = next((d for d in D if d['alert']), None)
    lat = None if fa is None else max(fa['t'] - fm['t'], 0.0)
    out = [(lat is not None and lat <= ON_LATENCY_MAX,
            f"내 차가 처음 보인 뒤 알림 ON까지 {'없음' if lat is None else f'{lat:.2f} s'} (≤ {ON_LATENCY_MAX} s)"),
           (1 <= len(P) <= 2, f"car_point {len(P)}개 (정지 car는 1~2개: 처음 + 멈춤 확정)")]
    if len(R) >= 5:
        xs, ys = [r[1] for r in R[-15:]], [r[2] for r in R[-15:]]
        out.append((True, f"참고: 정지 car 좌표 흔들림 σx={statistics.pstdev(xs):.3f} σy={statistics.pstdev(ys):.3f} m, {fmt_black(D)}"))
    return out


def check_s4(D, P, R, rate):
    if len(R) < 20:
        return [(False, f"car_point_raw {len(R)}개 → 측정 구간에 car가 거의 안 보임")]
    # 시작·끝 위치는 구간 안 car_point(처음 보낸 점은 구간 이전일 수 있음)가 아니라 raw 좌표의 처음·마지막 1초 중앙값
    head = [r for r in R if r[0] <= R[0][0] + 1.0]
    tail = [r for r in R if r[0] >= R[-1][0] - 1.0]
    start = (statistics.median(r[1] for r in head), statistics.median(r[2] for r in head))
    end = (statistics.median(r[1] for r in tail), statistics.median(r[2] for r in tail))
    moved = math.dist(start, end)
    path = sum(math.dist(R[i][1:], R[i + 1][1:]) for i in range(len(R) - 1))
    out = [(moved >= 0.5, f"시작→끝 위치 거리 {moved:.2f} m (테스트 유효: ≥ 0.5 m), 움직인 경로 길이 {path:.2f} m")]
    if len(P) < 1:
        return out + [(False, "car_point 0개 → 이동이 감지되지 않음")]
    # 이동 중에는 0.3 m마다 다시 보내므로, 경로 길이 / 0.3 + 3 개를 넘으면 안 됨
    limit = math.ceil(path / 0.3) + 3
    out.append((len(P) <= limit, f"car_point {len(P)}개 (≤ 경로 {path:.1f} m ÷ 0.3 + 3 = {limit}개)"))
    err = math.dist(P[-1][1:], end)
    out.append((err <= FINAL_ERR_MAX, f"멈춘 뒤 마지막 car_point와 실제 위치 차이 {err:.3f} m (≤ {FINAL_ERR_MAX})"))
    return out


def check_s5(D, P, R, rate):
    offs = [t for t, a in transitions(D) if not a]
    miss = sum(d['mine'] == 0 for d in D)
    return [(not offs, f"알림 OFF {len(offs)}회 (0이어야 함). 내 차 못 본 프레임 {miss}/{len(D)}"),
            (len(P) <= 1, f"car_point {len(P)}개 (≤ 1: 순간 가림은 이동이 아님)")]


def check_s6(D, P, R, rate):
    seen = [d for d in D if d['mine']]
    if not seen:
        return [(False, "시작할 때 car가 안 보임 → car가 놓여 있는 상태에서 시작해야 함")]
    last = seen[-1]['t']
    off = next((d for d in D if d['t'] > last and not d['alert']), None)
    if off is None:
        return [(False, "car를 치웠는데 알림이 안 꺼짐")]
    lat = off['t'] - last
    return [(lat <= OFF_LATENCY_MAX, f"마지막으로 보인 뒤 알림 OFF까지 {lat:.2f} s (≤ {OFF_LATENCY_MAX} s)")]


def check_s7(D, P, R, rate):
    ids = {d['my_id'] for d in D if d['my_id'] is not None}
    on = [d for d in D if d['alert']]
    ok_frac = sum(d['id_ok'] for d in on) / len(on) if on else 0.0
    return [(bool(on), f"알림 ON 프레임 {len(on)}/{len(D)}"),
            (len(ids) <= 2, f"내 차 ID 종류 {sorted(ids)} (≤ 2: ID가 자주 바뀌면 추적 불안정)"),
            (ok_frac >= 0.95, f"알림 중 my_id가 car(내 차)를 가리킨 비율 {ok_frac:.0%} (≥ 95%)"),
            (True, f"참고: dummy 보인 프레임 {sum(d['n_dummy'] > 0 for d in D)}/{len(D)}, car_point {len(P)}개")]


SCENARIOS = {
    'S0': ('기본 점검 (자동, car 없어도 됨)', '아무것도 하지 않아도 됨', 5, check_s0),
    'S1': ('빈 경기장', '경기장에서 car·dummy·손을 모두 치운다', 15, check_empty),
    'S2': ('dummy만', 'dummy만 경기장 안에 놓는다 (car 없음)', 15, check_empty),
    'S3': ('car 정지', '🔴 Enter 후 5초 안에 car를 놓고 손을 뺀다. 그 뒤 건드리지 않는다 (dummy 없음)', 20, check_s3),
    'S4': ('car 이동', '🔴 car가 놓인 상태에서 Enter → 5초 뒤부터 car를 손으로 1 m 이상 천천히 밀어 옮기고 놓는다 → 그대로 둔다', 25, check_s4),
    'S5': ('순간 가림', 'car가 놓인 상태에서 Enter → 손바닥으로 car를 0.2초만 가렸다 빼기를 3번 (5초 간격)', 20, check_s5),
    'S6': ('car 치우기', '🔴 car가 놓인 상태에서 Enter → 3초 뒤 car를 손으로 집어 경기장 밖으로 치운다', 10, check_s6),
    'S7': ('car + dummy', 'car와 dummy를 함께 놓는다 (서로 떨어뜨려서) → 손을 뺀다', 20, check_s7),
    'S8': ('손·다리 오검출', 'car 없이 손을 넣어 흔들고, 다리가 경기장 가장자리를 지나가게 한다', 15, check_empty),
}


def main():
    ap = argparse.ArgumentParser(description='웹캠 검출 + car_locator 통합 시나리오 테스트')
    ap.add_argument('--rate', type=float, default=15.0, help='기대 처리 주기 Hz (S0 주기 검사용, 15Hz 고정이라 보통 안 바꿈)')
    ap.add_argument('--only', default='', help='실행할 시나리오만 쉼표로 (예: S3,S4,S6)')
    args = ap.parse_args()
    names = [n.strip() for n in args.only.split(',') if n.strip()] or list(SCENARIOS)
    if any(n not in SCENARIOS for n in names):
        ap.error(f'시나리오는 {list(SCENARIOS)} 중에서')

    rclpy.init()
    node = Recorder()
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    spinner = threading.Thread(target=executor.spin)
    spinner.start()
    results = []
    try:
        for n in names:
            title, todo, dur, fn = SCENARIOS[n]
            print(f"\n{'=' * 60}\n[{n}] {title}  ({dur}초)\n  할 일: {todo}")
            if n != 'S0':
                ans = input('  준비되면 Enter (s=건너뜀, q=종료) > ').strip().lower()
                if ans == 'q':
                    break
                if ans == 's':
                    results.append((n, None))
                    continue
            t0 = time.time()
            node.marker.publish(String(data=f'{n} start'))
            for left in range(dur, 0, -1):
                if left % 5 == 0 or left == dur:
                    print(f"  측정 중… {left}초 남음", flush=True)
                time.sleep(1)
            t1 = time.time()
            node.marker.publish(String(data=f'{n} end'))
            time.sleep(0.3)
            D, P, R = node.window(t0, t1)
            checks = fn(D, P, R, args.rate)
            ok = all(c[0] for c in checks)
            for c_ok, text in checks:
                print(f"  {'✅' if c_ok else '❌'} {text}")
            print(f"  → [{n}] {'✅ 통과' if ok else '❌ 실패 — 이 로그를 Claude에게 보여줄 것'}")
            results.append((n, ok))
    except (KeyboardInterrupt, EOFError):
        print('\n중단')
    print(f"\n{'=' * 60}\n요약: " + '  '.join(f"{n}={'통과' if ok else '건너뜀' if ok is None else '실패'}" for n, ok in results))
    executor.shutdown()
    spinner.join()
    node.destroy_node()
    rclpy.try_shutdown()
    sys.exit(0 if all(ok in (True, None) for _, ok in results) else 1)


if __name__ == '__main__':
    main()
