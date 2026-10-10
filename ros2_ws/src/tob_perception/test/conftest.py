"""Run contracts against production modules and real ROS message types."""

# 공통 준비: ROS 2 Jazzy와 빌드된 tob_interfaces 환경을 source한 뒤 venv를 활성화한다.
# 필요 라이브러리: pytest, PyYAML, numpy, OpenCV, torch, ultralytics. 누락은 오류로 처리한다.
# 설정·모델 설치는 임시 경로에서 실제 colcon 빌드로 확인한다.

import importlib
import os
from pathlib import Path
import subprocess
import sys

import pytest


PACKAGE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_DIR))


def pytest_addoption(parser):
    """Keep hardware validation explicit, with independent labelled images."""
    parser.addoption('--run-gpu', action='store_true', default=False)
    parser.addoption('--gpu-cases', help='JSON manifest with images and GT boxes')


def pytest_configure(config):
    """Register the marker for hardware acceptance tests."""
    config.addinivalue_line('markers', 'gpu: real CUDA/model/image validation')


@pytest.fixture(scope='session')
def detector_module():
    """Import the production detector with its real library dependencies."""
    return importlib.import_module('tob_perception.detector')


@pytest.fixture(scope='session')
def node_module():
    """Import the production ROS node with generated message types."""
    return importlib.import_module('tob_perception.boo_detector_node')


@pytest.fixture(scope='session')
def installed_package(tmp_path_factory):
    """Exercise setup.py by installing into a separate test workspace."""
    staging = tmp_path_factory.mktemp('perception-install')
    result = subprocess.run([
        'colcon', '--log-base', str(staging / 'log'), 'build',
        '--paths', str(PACKAGE_DIR), '--packages-select', 'tob_perception',
        '--build-base', str(staging / 'build'),
        '--install-base', str(staging / 'install'),
    ], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    return staging / 'install/tob_perception'


@pytest.fixture
def package_environment(monkeypatch, installed_package):
    """Make the staged package discoverable through the ament index."""
    monkeypatch.setenv('AMENT_PREFIX_PATH', os.pathsep.join([
        str(installed_package), os.environ.get('AMENT_PREFIX_PATH', ''),
    ]))
    return installed_package / 'share/tob_perception'
