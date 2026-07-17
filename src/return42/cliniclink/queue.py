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
                    done INTEGER NOT NULL DEFAULT 0,
                    handoff_id TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_sync_queue_direction_done_created
                ON sync_queue (direction, done, created_at)
                """
            )
            # Migrate older tables that did not store handoff_id.
            columns = {
                row[1] for row in conn.execute("PRAGMA table_info(sync_queue)").fetchall()
            }
            if "handoff_id" not in columns:
                conn.execute("ALTER TABLE sync_queue ADD COLUMN handoff_id TEXT")
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_sync_queue_handoff_direction
                ON sync_queue (handoff_id, direction)
                """
            )

    def enqueue(self, handoff: PatientHandoff, direction: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO sync_queue
                    (handoff_id, direction, payload, created_at, done)
                VALUES (?, ?, ?, ?, 0)
                """,
                (
                    handoff.handoff_id,
                    direction,
                    json.dumps(handoff.to_payload()),
                    datetime.now(timezone.utc).isoformat(),
                ),
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
