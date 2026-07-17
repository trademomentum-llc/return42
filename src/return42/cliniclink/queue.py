from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import PatientHandoff


class SyncQueue:
    """Persists handoffs that need to be forwarded or replayed after outage."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, check_same_thread=False)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sync_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    direction TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    done INTEGER NOT NULL DEFAULT 0
                )
                """
            )

    def enqueue(self, handoff: PatientHandoff, direction: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sync_queue (direction, payload, created_at, done) VALUES (?, ?, ?, 0)",
                (direction, json.dumps(handoff.to_payload()), datetime.now(timezone.utc).isoformat()),
            )

    def dequeue(self, direction: str) -> list[dict]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, payload FROM sync_queue WHERE direction = ? AND done = 0 ORDER BY created_at",
                (direction,),
            ).fetchall()
        return [{"id": row["id"], "payload": json.loads(row["payload"])} for row in rows]

    def mark_done(self, record_id: int) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE sync_queue SET done = 1 WHERE id = ?", (record_id,))
