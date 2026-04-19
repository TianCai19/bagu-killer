from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


class Database:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    @contextmanager
    def connect(self) -> Iterator[Any]:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError("psycopg is required. Install project dependencies in the aicoder environment.") from exc
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            yield conn

    def init_db(self, sql_path: Path) -> None:
        script = sql_path.read_text(encoding="utf-8")
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(script)
            conn.commit()
