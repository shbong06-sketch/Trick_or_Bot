"""일반 YAML 레벨을 읽고 회차에서 사용할 독립적인 설정을 검증한다."""

import math
from pathlib import Path

import yaml


class LevelConfigError(ValueError):
    """경로와 설정 키를 포함하는 레벨 오류."""


def config_path(path, config_file=None):
    """상대 경로는 명시한 설정 파일의 부모를 기준으로 해석한다."""
    result = Path(path).expanduser()
    if not result.is_absolute():
        if config_file is None or not Path(config_file).is_absolute():
            raise LevelConfigError(f'{path}: 경로: 상대 경로에는 절대 설정 파일 경로가 필요합니다')
        result = Path(config_file).parent / result
    return result.resolve()


def load_level(path, config_file=None):
    """필수 값과 Level 1 범위를 검사하고 새 딕셔너리 스냅샷을 반환한다."""
    path = config_path(path, config_file)

    def fail(key, message):
        raise LevelConfigError(f'{path}: {key}: {message}')

    try:
        with path.open(encoding='utf-8') as stream:
            data = yaml.safe_load(stream)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        fail('YAML', f'설정 파일을 읽을 수 없습니다 ({exc})')

    def value(key, expected=None):
        item = data
        for part in key.split('.'):
            if not isinstance(item, dict) or part not in item:
                fail(key, '필수 키가 없습니다')
            item = item[part]
        if item is None:
            fail(key, 'null인 필수 값은 설정 미완성입니다')
        if expected is not None and type(item) is not expected:
            fail(key, '자료형이 올바르지 않습니다')
        return item

    def number(item, key, positive=False, maximum=None):
        if type(item) not in (int, float):
            fail(key, 'bool이 아닌 숫자가 필요합니다')
        try:
            finite = math.isfinite(item)
        except OverflowError:
            finite = False
        if not finite:
            fail(key, '유한한 값이 필요합니다')
        if positive and item <= 0:
            fail(key, '양수여야 합니다')
        if maximum is not None and item > maximum:
            fail(key, '메시지의 표현 범위를 초과했습니다')

    def position(item, key, yaw=False):
        if not isinstance(item, dict):
            fail(key, '좌표 딕셔너리가 필요합니다')
        for axis in ('x', 'y', 'yaw_rad') if yaw else ('x', 'y'):
            if axis not in item or item[axis] is None:
                fail(f'{key}.{axis}', '필수 좌표가 없거나 null입니다')
            number(item[axis], f'{key}.{axis}')

    if not isinstance(data, dict):
        fail('YAML', '최상위 딕셔너리가 필요합니다')
    if value('level', int) != 1:
        fail('level', '지원하는 레벨은 1뿐입니다')
    for key in ('name', 'frame_id'):
        if not value(key, str).strip():
            fail(key, '빈 문자열은 사용할 수 없습니다')
    for key in ('rules.time_limit_s', 'rules.candy.pickup_radius_m',
                'rules.capture.distance_m', 'rules.capture.hold_s',
                'rules.capture.cooldown_s', 'layout.exit_zone.radius_m'):
        number(value(key), key, positive=True, maximum=3.4028234663852886e38)
    for key in ('rules.initial_hp', 'rules.capture.damage_hp'):
        if not 1 <= value(key, int) <= 65535:
            fail(key, 'uint16 범위의 양의 정수(1~65535)가 필요합니다')
    priority = value('rules.simultaneous_result_priority', str)
    if priority not in ('failed', 'cleared'):
        fail('rules.simultaneous_result_priority', 'failed 또는 cleared가 필요합니다')
    for robot in ('pumpkin', 'boo'):
        key = f'layout.start_poses.{robot}'
        position(value(key, dict), key, yaw=True)
    position(value('layout.exit_zone.position', dict), 'layout.exit_zone.position')
    candies = value('layout.candies', list)
    if not 1 <= len(candies) <= 4294967295:
        fail('layout.candies', '비어 있지 않고 uint32로 셀 수 있는 목록이 필요합니다')
    ids = set()
    for index, candy in enumerate(candies):
        key = f'layout.candies[{index}]'
        if not isinstance(candy, dict):
            fail(key, '사탕 딕셔너리가 필요합니다')
        candy_id = candy.get('id')
        if not isinstance(candy_id, str) or not candy_id.strip():
            fail(f'{key}.id', '비어 있지 않은 문자열 ID가 필요합니다')
        if candy_id in ids:
            fail(f'{key}.id', f'중복된 사탕 ID입니다: {candy_id}')
        ids.add(candy_id)
        position(candy.get('position'), f'{key}.position')
    return data
