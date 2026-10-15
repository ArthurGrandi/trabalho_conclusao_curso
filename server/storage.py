"""Small SQLite document store. No upload bytes or credentials are persisted."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Callable


class Store:
    def __init__(self, directory: str | Path | None = None):
        self.directory = Path(directory or os.getenv("TCC_DATA_DIR", "/workspace/.tcc-data"))
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "platform.sqlite3"
        self._lock = threading.RLock()
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS batches (id INTEGER PRIMARY KEY AUTOINCREMENT, body TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS dictionary_edits (id INTEGER PRIMARY KEY AUTOINCREMENT, body TEXT NOT NULL)")

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=30)
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def create(self, body: dict) -> dict:
        with self._lock, self._connect() as db:
            cursor = db.execute("INSERT INTO batches(body) VALUES (?)", ("{}",))
            body = {**body, "id": cursor.lastrowid}
            db.execute("UPDATE batches SET body=? WHERE id=?", (json.dumps(body, ensure_ascii=False), body["id"]))
        return body

    def get(self, batch_id: int) -> dict | None:
        with self._connect() as db:
            row = db.execute("SELECT body FROM batches WHERE id=?", (batch_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def all(self) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("SELECT body FROM batches ORDER BY id DESC").fetchall()
        return [json.loads(row[0]) for row in rows]

    def update(self, batch_id: int, change: Callable[[dict], None]) -> dict | None:
        with self._lock, self._connect() as db:
            row = db.execute("SELECT body FROM batches WHERE id=?", (batch_id,)).fetchone()
            if row is None:
                return None
            body = json.loads(row[0])
            change(body)
            db.execute("UPDATE batches SET body=? WHERE id=?", (json.dumps(body, ensure_ascii=False), batch_id))
        return body

    def dictionary_edits(self) -> list[dict]:
        with self._connect() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT body FROM dictionary_edits ORDER BY id")]

    def add_dictionary_edit(self, edit: dict) -> dict:
        with self._lock, self._connect() as db:
            db.execute("INSERT INTO dictionary_edits(body) VALUES (?)", (json.dumps(edit, ensure_ascii=False),))
        return edit
