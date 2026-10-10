import sqlite3
import threading
import time
from pathlib import Path

from .settings import BACKEND_DIR

DB_PATH = BACKEND_DIR / "data" / "records.db"


class Records:
    """클리어 기록 (SQLite). 기록 시간은 서버가 판정한 값만 저장한다."""

    def __init__(self, path: Path = DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lv INTEGER NOT NULL,
                nickname TEXT NOT NULL,
                time_s REAL NOT NULL,
                created_at REAL NOT NULL
            )""")
        self._db.execute("CREATE INDEX IF NOT EXISTS records_lv_time ON records (lv, time_s)")
        self._db.commit()

    def add(self, lv: int, nickname: str, time_s: float) -> int:
        with self._lock:
            cur = self._db.execute("INSERT INTO records (lv, nickname, time_s, created_at) VALUES (?, ?, ?, ?)",
                                   (lv, nickname, time_s, time.time()))
            self._db.commit()
            return cur.lastrowid

    def top(self, lv: int, limit: int = 10) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT id, nickname, time_s FROM records WHERE lv = ? ORDER BY time_s, id LIMIT ?", (lv, limit)).fetchall()
        return [{"rank": i + 1, "id": r[0], "nickname": r[1], "time": r[2]} for i, r in enumerate(rows)]

    def close(self) -> None:
        self._db.close()
