"""Build and apply the deployment contract instead of comparing source text."""

# 실행: python -m pytest -q <이 파일 경로>
# 외부 동작을 대체하지 않고 실제 colcon 설치 후 YAML·모델 경로·파일 무결성을 검증한다.
# 배포 설정은 개발 PC의 절대 경로에 의존하지 않아야 한다. GPU 로딩은 별도 테스트 대상이다.

import hashlib
from pathlib import Path

import yaml

from conftest import PACKAGE_DIR


def test_configured_model_is_installed_and_unchanged(installed_package):
    share = installed_package / 'share/tob_perception'
    config = yaml.safe_load((share / 'config/detectors.yaml').read_text())
    params = config['boo_detector_node']['ros__parameters']
    relative = Path(params['model_path'])
    assert not relative.is_absolute(), 'Deployment config must be portable'
    installed = share / relative
    original = PACKAGE_DIR / relative
    assert installed.is_file() and original.is_file()
    assert hashlib.sha256(installed.read_bytes()).digest() == (
        hashlib.sha256(original.read_bytes()).digest()
    )
    assert type(params['device']) is int and params['device'] >= 0
    assert type(params['target_class_id']) is int and params['target_class_id'] >= 0
    assert 0 <= params['confidence_threshold'] <= 1
    assert params['use_sim_time'] is False
