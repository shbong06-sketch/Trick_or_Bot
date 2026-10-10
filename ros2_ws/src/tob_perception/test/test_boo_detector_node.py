"""DESIGN_TEMP 6-10: real compressed input, messages, QoS and DDS output."""

# 실행: python -m pytest -q <이 파일 경로>
# 촬영 시각·박스·미탐지·오류 격리·압축 디버그·QoS·CLI를 실제 JPEG와 ROS 통신으로 검증한다.
# Detector만 대체한다. 지도 좌표·이동 명령·게임 사건 생성은 이 노드의 범위 밖이다.
# DDS는 domain 173, LOCALHOST, 고유 토픽 사용. 입력 중단 검사는 0.5초이며 장기 검증은 별도다.

from pathlib import Path
import time
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import cv2
import numpy as np
import pytest
import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy,
)
from sensor_msgs.msg import CompressedImage
from tob_interfaces.msg import TargetObservation


def spin_until(executor, condition, timeout=5.0):
    end = time.monotonic() + timeout
    while not condition() and time.monotonic() < end:
        executor.spin_once(timeout_sec=0.02)
    assert condition(), 'DDS condition not satisfied before test deadline'


@pytest.fixture
def ros_session(monkeypatch):
    # Use a separate ROS domain and unique topics, never a live robot's graph.
    monkeypatch.setenv('ROS_AUTOMATIC_DISCOVERY_RANGE', 'LOCALHOST')
    yield
    if rclpy.ok():
        rclpy.shutdown()


@pytest.fixture
def graph_factory(ros_session, package_environment, node_module, monkeypatch):
    graphs = []

    def create(debug=False, extra_parameters=(), load_error=None):
        root = '/perception_test_' + uuid4().hex
        topics = SimpleNamespace(
            image=root + '/image/compressed',
            detection=root + '/detection',
            debug=root + '/debug/image/compressed',
        )
        arguments = [
            '--ros-args', '--params-file',
            str(package_environment / 'config/detectors.yaml'),
            '-p', 'image_topic:=' + topics.image,
            '-p', 'detection_topic:=' + topics.detection,
            '-p', 'debug_image_topic:=' + topics.debug,
        ]
        for parameter in extra_parameters:
            arguments.extend(['-p', parameter])
        rclpy.init(args=arguments, domain_id=173)
        inference = Mock()
        inference._model = SimpleNamespace(names={0: 'pumpkin'})
        inference.detect.return_value = []
        loader = Mock(return_value=inference)
        loader.side_effect = load_error
        monkeypatch.setattr(node_module, 'Detector', loader)
        node = node_module.BooDetectorNode(debug=debug)
        peer = Node('perception_test_peer', use_global_arguments=False)
        executor = SingleThreadedExecutor()
        executor.add_node(node)
        executor.add_node(peer)
        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST, depth=1,
        )
        observations, images = [], []
        output_sub = peer.create_subscription(
            TargetObservation, topics.detection, observations.append, qos,
        )
        debug_sub = peer.create_subscription(
            CompressedImage, topics.debug, images.append, qos,
        )
        input_pub = peer.create_publisher(CompressedImage, topics.image, qos)
        graph = SimpleNamespace(
            node=node, peer=peer, executor=executor, inference=inference,
            loader=loader, topics=topics, observations=observations,
            images=images, input_pub=input_pub,
        )
        graphs.append(graph)
        spin_until(executor, lambda: all((
            input_pub.get_subscription_count() > 0,
            output_sub.get_publisher_count() > 0,
            not debug or debug_sub.get_publisher_count() > 0,
        )))
        return graph

    yield create
    for graph in graphs:
        graph.executor.shutdown()
        graph.node.destroy_node()
        graph.peer.destroy_node()


def frame(stamp=101, data=None):
    message = CompressedImage()
    message.header.frame_id = 'test_camera_optical_frame'
    message.header.stamp.sec = stamp
    message.header.stamp.nanosec = 123456
    message.format = 'bgr8; jpeg compressed bgr8'
    if data is None:
        success, encoded = cv2.imencode(
            '.jpg', np.full((120, 200, 3), 50, dtype=np.uint8),
        )
        assert success
        data = encoded.tobytes()
    message.data = data
    return message


def assert_observation_header_and_scope(observation, message):
    assert observation.header == message.header
    assert observation.source == 'boo_camera'
    assert observation.map_valid is False
    assert observation.target_position == TargetObservation().target_position
    assert observation.distance_m == 0.0


@pytest.mark.parametrize('debug', [False, True])
def test_detection_selects_best_and_normalizes_original_coordinates(
    debug, graph_factory, detector_module,
):
    graph = graph_factory(debug=debug)
    graph.inference.detect.return_value = [
        detector_module.Detection((10, 10, 30, 30), 0, 0.7),
        detector_module.Detection((20, 30, 80, 90), 0, 0.9),
    ]
    message = frame()
    graph.input_pub.publish(message)
    spin_until(graph.executor, lambda: (
        len(graph.observations) == 1 and (not debug or len(graph.images) == 1)
    ))
    observation = graph.observations[0]
    assert_observation_header_and_scope(observation, message)
    assert observation.detected is True
    assert observation.confidence == pytest.approx(0.9)
    assert (
        observation.bbox_center_x, observation.bbox_center_y,
        observation.bbox_width, observation.bbox_height,
    ) == pytest.approx((0.25, 0.5, 0.3, 0.5))
    # The backend receives decoded pixels, not the JPEG bytes.
    image = graph.inference.detect.call_args.args[0]
    assert image.shape == (120, 200, 3) and image.dtype == np.uint8
    assert np.max(np.abs(image.astype(int) - 50)) <= 2
    endpoints = graph.peer.get_publishers_info_by_topic(graph.topics.debug)
    assert bool(endpoints) is debug
    if debug:
        output = graph.images[0]
        assert output.header == message.header
        assert output.format == 'bgr8; jpeg compressed bgr8'
        decoded = cv2.imdecode(np.frombuffer(output.data, np.uint8), cv2.IMREAD_COLOR)
        assert decoded is not None and decoded.shape == image.shape
        assert not np.array_equal(decoded, image), 'Annotation missing'
        blue, green, red = decoded[60, 20].astype(int)
        assert green > blue + 60 and green > red + 60, 'Box drawn at wrong location'


def test_absence_after_detection_clears_previous_result(graph_factory, detector_module):
    graph = graph_factory(debug=True)
    graph.inference.detect.side_effect = [
        [detector_module.Detection((20, 30, 80, 90), 0, 0.9)], [],
    ]
    first, second = frame(101), frame(102)
    graph.input_pub.publish(first)
    spin_until(graph.executor, lambda: len(graph.images) == 1)
    graph.input_pub.publish(second)
    spin_until(graph.executor, lambda: len(graph.images) == 2)
    assert len(graph.observations) == 2
    observation = graph.observations[-1]
    assert_observation_header_and_scope(observation, second)
    assert observation.detected is False
    assert observation.confidence == 0.0
    assert (observation.bbox_center_x, observation.bbox_center_y,
            observation.bbox_width, observation.bbox_height) == (0, 0, 0, 0)
    assert graph.images[-1].header == second.header
    decoded = cv2.imdecode(np.frombuffer(graph.images[-1].data, np.uint8), cv2.IMREAD_COLOR)
    assert decoded is not None and np.max(np.abs(decoded.astype(int) - 50)) <= 2


@pytest.mark.parametrize('failure', ['empty', 'corrupt', 'inference'])
def test_processing_failure_logs_and_publishes_neither_result(
    failure, graph_factory, monkeypatch,
):
    graph = graph_factory(debug=True)
    logger = Mock()
    monkeypatch.setattr(graph.node, 'get_logger', lambda: logger)
    if failure == 'inference':
        graph.inference.detect.side_effect = RuntimeError('inference failed')
        message = frame()
    else:
        message = frame(data=b'' if failure == 'empty' else b'invalid JPEG')
    graph.input_pub.publish(message)
    spin_until(graph.executor, lambda: logger.error.called)
    end = time.monotonic() + 0.2
    while time.monotonic() < end:
        graph.executor.spin_once(timeout_sec=0.02)
    assert graph.observations == [] and graph.images == []
    if failure != 'inference':
        graph.inference.detect.assert_not_called()


@pytest.mark.parametrize('bbox', [
    (80, 30, 20, 90), (20, 30, 20, 90),
    (float('nan'), 30, 80, 90),
])
def test_invalid_detection_never_becomes_a_valid_observation(
    bbox, graph_factory, detector_module, monkeypatch,
):
    graph = graph_factory(debug=True)
    logger = Mock()
    monkeypatch.setattr(graph.node, 'get_logger', lambda: logger)
    graph.inference.detect.return_value = [detector_module.Detection(bbox, 0, 0.9)]
    graph.input_pub.publish(frame())
    spin_until(graph.executor, lambda: logger.error.called)
    assert graph.observations == [] and graph.images == []


def test_debug_failure_does_not_suppress_detection(graph_factory, monkeypatch):
    graph = graph_factory(debug=True)
    message = frame()
    logger = Mock()
    monkeypatch.setattr(graph.node, 'get_logger', lambda: logger)
    monkeypatch.setattr(cv2, 'imencode', lambda *args, **kwargs: (False, None))
    graph.input_pub.publish(message)
    spin_until(graph.executor, lambda: len(graph.observations) == 1)
    assert graph.observations[0].detected is False
    assert graph.images == []
    assert logger.error.called


def test_camera_silence_does_not_republish_old_observations(graph_factory):
    graph = graph_factory(debug=True)
    graph.input_pub.publish(frame())
    spin_until(graph.executor, lambda: len(graph.images) == 1)
    end = time.monotonic() + 0.5
    while time.monotonic() < end:
        graph.executor.spin_once(timeout_sec=0.02)
    assert len(graph.observations) == 1 and len(graph.images) == 1


def test_installed_config_is_applied_and_qos_matches_design(
    graph_factory, package_environment,
):
    graph = graph_factory(debug=True)
    configured_model = package_environment / 'models/yolo11n_boo.pt'
    assert Path(graph.loader.call_args.kwargs['model_path']) == configured_model
    assert configured_model.is_file()
    for topic in (graph.topics.detection, graph.topics.debug):
        endpoints = graph.peer.get_publishers_info_by_topic(topic)
        assert len(endpoints) == 1
        qos = endpoints[0].qos_profile
        assert qos.reliability == ReliabilityPolicy.RELIABLE
        assert qos.durability == DurabilityPolicy.VOLATILE
    # DDS discovery does not expose history/depth in every RMW implementation.
    # Verify those on the actual local endpoints instead of accepting UNKNOWN.
    endpoints = [
        *[pub for pub in graph.node.publishers if pub.topic_name in {
            graph.topics.detection, graph.topics.debug,
        }],
        *[sub for sub in graph.node.subscriptions if sub.topic_name == graph.topics.image],
    ]
    assert len(endpoints) == 3
    for endpoint in endpoints:
        qos = endpoint.qos_profile
        assert qos.reliability == ReliabilityPolicy.RELIABLE
        assert qos.durability == DurabilityPolicy.VOLATILE
        assert qos.history == HistoryPolicy.KEEP_LAST and qos.depth == 1
    subscriptions = graph.peer.get_subscriptions_info_by_topic(graph.topics.image)
    assert len(subscriptions) == 1
    assert subscriptions[0].qos_profile.reliability == ReliabilityPolicy.RELIABLE
    # The detector node must not publish movement, map positions or game events.
    published_topics = {
        name for name, _ in graph.peer.get_publisher_names_and_types_by_node(
            'boo_detector_node', '/',
        )
    }
    assert published_topics - {'/rosout', '/parameter_events'} == {
        graph.topics.detection, graph.topics.debug,
    }


@pytest.mark.parametrize('failure', [
    ValueError('invalid model'), RuntimeError('CUDA unavailable'),
])
def test_model_startup_failure_stops_node(failure, graph_factory):
    with pytest.raises(type(failure)):
        graph_factory(load_error=failure)


@pytest.mark.parametrize('parameter', [
    'model_path:=""', 'image_topic:=""', 'detection_topic:=""',
    'source:=""', 'debug_image_topic:=""',
])
def test_empty_required_settings_rejected(parameter, graph_factory):
    with pytest.raises(ValueError):
        graph_factory(extra_parameters=[parameter])


def test_external_model_absolute_path_is_preserved(tmp_path, graph_factory):
    model = tmp_path / 'external.pt'
    model.write_bytes(b'backend model loading is replaced in ROS tests')
    graph = graph_factory(extra_parameters=['model_path:=' + str(model)])
    assert Path(graph.loader.call_args.kwargs['model_path']) == model


def test_main_reports_startup_failure_and_shuts_down(node_module, monkeypatch):
    startup = Mock(side_effect=RuntimeError('model load failed'))
    logger = Mock()
    monkeypatch.setattr(node_module, 'BooDetectorNode', startup)
    monkeypatch.setattr(node_module.rclpy.logging, 'get_logger', lambda name: logger)
    assert node_module.main(args=[]) == 1
    assert logger.warning.called
    assert not rclpy.ok()


@pytest.mark.parametrize('debug_args', [[], ['--debug']])
def test_debug_cli_and_ros_arguments_are_independent(
    debug_args, node_module, monkeypatch,
):
    node = Mock()
    startup = Mock(return_value=node)
    monkeypatch.setattr(node_module, 'BooDetectorNode', startup)
    monkeypatch.setattr(node_module.rclpy, 'spin', lambda instance: None)
    node_module.main(args=[*debug_args, '--ros-args', '-p', 'use_sim_time:=false'])
    startup.assert_called_once_with(debug=bool(debug_args))
    node.destroy_node.assert_called_once()
    assert not rclpy.ok()
