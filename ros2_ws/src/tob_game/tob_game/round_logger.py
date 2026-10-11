"""확정된 회차 결과만 JSONL로 기록한다."""

import json
from pathlib import Path


class RoundLogger:
    """회차별로 한 번만 기록을 시도하며 실패를 호출자에게 전달한다."""

    def __init__(self, path, forbidden_roots=()):
        """운영 파일은 절대 경로로 지정하고 소스·설치 경로를 제외한다."""
        self.path = Path(path).expanduser()
        if not self.path.is_absolute():
            raise ValueError('결과 로그 경로는 절대 경로여야 합니다')
        self.path = self.path.resolve()
        roots = (Path(__file__).resolve().parents[1], *forbidden_roots)
        if any(self.path.is_relative_to(Path(root).resolve()) for root in roots):
            raise ValueError('소스 또는 설치 디렉터리에 운영 로그를 저장할 수 없습니다')
        self._attempted = set()

    def write(self, result):
        """이미 처리한 ID는 건너뛴다. 실패한 쓰기를 자동 재시도하지 않는다."""
        round_id = result['round_id']
        if not isinstance(round_id, str) or not round_id:
            raise ValueError('결과 기록에는 비어 있지 않은 round_id가 필요합니다')
        if round_id in self._attempted:
            return False
        self._attempted.add(round_id)
        try:
            line = json.dumps(result, ensure_ascii=False, allow_nan=False)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open('a', encoding='utf-8') as stream:
                stream.write(line + '\n')
        except (OSError, ValueError, TypeError) as exc:
            raise OSError(f'{self.path}: 회차 {round_id} 결과 기록 실패 ({exc})') from exc
        return True
