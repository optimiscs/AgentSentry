from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections import deque
from contextlib import contextmanager
from pathlib import Path

from cryptography.fernet import Fernet

from agentsentry.context.scanner import redact
from agentsentry.schemas import Session, canonical, uid


class Store:
    """Single-writer SQLite store. Private execution/memory blobs are encrypted."""

    def __init__(self, path: Path, key: str, buffer_limit: int = 256):
        self.path = path
        self.crypto = Fernet(key.encode())
        self.lock = threading.RLock()
        self.buffer = deque(maxlen=buffer_limit)
        self.dropped = 0
        self.degraded = False
        self.db = sqlite3.connect(
            path, check_same_thread=False, isolation_level=None, timeout=10
        )
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, owner TEXT NOT NULL, payload TEXT NOT NULL, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS contexts(id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id), payload TEXT NOT NULL, private BLOB NOT NULL, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, trace_id TEXT NOT NULL, session_id TEXT NOT NULL, span_id TEXT NOT NULL, parent_span_id TEXT, kind TEXT NOT NULL, payload TEXT NOT NULL, created REAL NOT NULL, seq INTEGER NOT NULL);
        CREATE INDEX IF NOT EXISTS events_trace ON events(trace_id,seq);
        CREATE INDEX IF NOT EXISTS events_sequence ON events(seq);
        CREATE INDEX IF NOT EXISTS contexts_session ON contexts(session_id,created);
        CREATE TABLE IF NOT EXISTS actions(id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id), request_key TEXT NOT NULL, request_hash TEXT NOT NULL, status TEXT NOT NULL, private BLOB NOT NULL, result TEXT, created REAL NOT NULL, UNIQUE(session_id,request_key));
        CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY, action_id TEXT UNIQUE NOT NULL REFERENCES actions(id), owner TEXT NOT NULL, status TEXT NOT NULL, binding TEXT NOT NULL, signature TEXT NOT NULL, epoch TEXT NOT NULL, expires REAL NOT NULL, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS memories(id TEXT PRIMARY KEY, owner TEXT NOT NULL, name TEXT NOT NULL, private BLOB NOT NULL, metadata TEXT NOT NULL, status TEXT NOT NULL, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS executions(id INTEGER PRIMARY KEY AUTOINCREMENT, action_id TEXT NOT NULL, tool TEXT NOT NULL, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS sink_receipts(id INTEGER PRIMARY KEY AUTOINCREMENT, action_id TEXT NOT NULL, destination TEXT NOT NULL, digest TEXT NOT NULL, bytes INTEGER NOT NULL, created REAL NOT NULL);
        """)
        path.chmod(0o600)

    @contextmanager
    def transaction(self):
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield self.db
            except Exception:
                self.db.execute("ROLLBACK")
                raise
            else:
                self.db.execute("COMMIT")

    def seal(self, obj) -> bytes:
        return self.crypto.encrypt(canonical(obj).encode())

    def open(self, data):
        return json.loads(self.crypto.decrypt(data))

    def recover(self):
        # A fresh process invalidates approvals; in-flight side effects are NOT retried.
        with self.transaction() as db:
            db.execute(
                "UPDATE approvals SET status='expired' WHERE status IN ('pending','approved')"
            )
            db.execute(
                "UPDATE actions SET status='cancelled' WHERE status IN ('pending','approved','ready')"
            )
            db.execute(
                "UPDATE actions SET status='unknown' WHERE status IN ('executing','dispatched')"
            )

    def save_session(self, s: Session):
        with self.lock:
            self.db.execute(
                "INSERT INTO sessions VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                (
                    s.session_id,
                    s.owner,
                    canonical(redact(s.model_dump(mode="json"))),
                    s.created_at,
                ),
            )

    def session(self, id: str) -> Session:
        with self.lock:
            row = self.db.execute(
                "SELECT payload FROM sessions WHERE id=?", (id,)
            ).fetchone()
        if row is None:
            raise KeyError("SESSION_NOT_FOUND")
        return Session.model_validate_json(row["payload"])

    def sessions(self, owner: str):
        with self.lock:
            return [
                json.loads(r[0])
                for r in self.db.execute(
                    "SELECT payload FROM sessions WHERE owner=? ORDER BY created DESC LIMIT 200",
                    (owner,),
                )
            ]

    def save_context(self, id: str, session_id: str, payload: dict, raw: str):
        with self.lock:
            self.db.execute(
                "INSERT INTO contexts VALUES(?,?,?,?,?)",
                (
                    id,
                    session_id,
                    canonical(redact(payload)),
                    self.seal({"text": raw}),
                    time.time(),
                ),
            )

    def context_text(self, id: str, session_id: str):
        with self.lock:
            row = self.db.execute(
                "SELECT private FROM contexts WHERE id=? AND session_id=?",
                (id, session_id),
            ).fetchone()
        if row is None:
            raise KeyError("CONTEXT_NOT_FOUND")
        return self.open(row[0])["text"]

    def contexts(self, session_id: str):
        with self.lock:
            rows = self.db.execute(
                "SELECT id, json_extract(payload,'$.source_type'), json_extract(payload,'$.source_id'), json_extract(payload,'$.labels'), json_extract(payload,'$.source_refs') FROM contexts WHERE session_id=? ORDER BY created",
                (session_id,),
            ).fetchall()
            return [
                {
                    "chunk_id": r[0],
                    "source_type": r[1],
                    "source_id": r[2],
                    "labels": json.loads(r[3]),
                    "source_refs": json.loads(r[4]),
                }
                for r in rows
            ]

    def _append(self, event: dict):
        with self.lock:
            sequence = self.db.execute(
                "SELECT COALESCE(MAX(seq),0)+1 FROM events"
            ).fetchone()[0]
            self.db.execute(
                "INSERT OR IGNORE INTO events VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    event["event_id"],
                    event["trace_id"],
                    event["session_id"],
                    event["span_id"],
                    event.get("parent_span_id"),
                    event["event_type"],
                    canonical(redact(event)),
                    event["timestamp"],
                    sequence,
                ),
            )

    def emit(
        self,
        session: Session,
        kind: str,
        payload: dict,
        span: str | None = None,
        parent: str | None = None,
    ) -> tuple[dict, bool]:
        event = {
            **redact(payload),
            "event_id": uid("evt"),
            "trace_id": session.trace_id,
            "session_id": session.session_id,
            "agent_id": session.agent_id,
            "span_id": span or uid("sp"),
            "parent_span_id": parent,
            "event_type": kind,
            "timestamp": time.time(),
        }
        # Reserved identity/structure cannot be supplied through untrusted payloads.
        event.update(
            trace_id=session.trace_id,
            session_id=session.session_id,
            agent_id=session.agent_id,
            event_type=kind,
        )
        try:
            while self.buffer:
                self._append(self.buffer[0])
                self.buffer.popleft()
            self._append(event)
            self.degraded = False
            return event, True
        except sqlite3.Error:
            self.degraded = True
            if len(self.buffer) == self.buffer.maxlen:
                self.dropped += 1
            self.buffer.append(event)
            return event, False

    def events(self, trace_id: str):
        with self.lock:
            return [
                json.loads(r[0])
                for r in self.db.execute(
                    "SELECT payload FROM events WHERE trace_id=? ORDER BY seq",
                    (trace_id,),
                )
            ]

    def add_action(self, id, session_id, key, request_hash, private, result):
        with self.lock:
            self.db.execute(
                "INSERT INTO actions VALUES(?,?,?,?,?,?,?,?)",
                (
                    id,
                    session_id,
                    key,
                    request_hash,
                    "pending",
                    self.seal(private),
                    canonical(redact(result)),
                    time.time(),
                ),
            )

    def action_by_key(self, session_id, key):
        with self.lock:
            return self.db.execute(
                "SELECT * FROM actions WHERE session_id=? AND request_key=?",
                (session_id, key),
            ).fetchone()

    def action(self, id):
        with self.lock:
            row = self.db.execute("SELECT * FROM actions WHERE id=?", (id,)).fetchone()
        if row is None:
            raise KeyError("ACTION_NOT_FOUND")
        return row

    def finish(self, id, status, result):
        with self.lock:
            self.db.execute(
                "UPDATE actions SET status=?,result=? WHERE id=?",
                (status, canonical(redact(result)), id),
            )

    def claim(self, id, expected="pending") -> bool:
        with self.transaction() as db:
            return (
                db.execute(
                    "UPDATE actions SET status=? WHERE id=? AND status=?",
                    ("executing", id, expected),
                ).rowcount
                == 1
            )

    def execution(self, action_id, tool):
        with self.lock:
            self.db.execute(
                "INSERT INTO executions(action_id,tool,created) VALUES(?,?,?)",
                (action_id, tool, time.time()),
            )

    def execution_count(self, action_id=None):
        with self.lock:
            if action_id:
                return self.db.execute(
                    "SELECT COUNT(*) FROM executions WHERE action_id=?", (action_id,)
                ).fetchone()[0]
            return self.db.execute("SELECT COUNT(*) FROM executions").fetchone()[0]

    def sink(self, action_id, destination, text):
        import hashlib

        with self.lock:
            self.db.execute(
                "INSERT INTO sink_receipts(action_id,destination,digest,bytes,created) VALUES(?,?,?,?,?)",
                (
                    action_id,
                    destination,
                    hashlib.sha256(text.encode()).hexdigest(),
                    len(text.encode()),
                    time.time(),
                ),
            )

    def sink_count(self):
        with self.lock:
            return self.db.execute("SELECT COUNT(*) FROM sink_receipts").fetchone()[0]

    def purge(self, days: int):
        if days < 1:
            raise ValueError("Retention must be positive")
        cutoff = time.time() - days * 86400
        with self.transaction() as db:
            for table in ["events", "contexts", "sink_receipts", "executions"]:
                db.execute(f"DELETE FROM {table} WHERE created < ?", (cutoff,))
            db.execute("DELETE FROM approvals WHERE created < ?", (cutoff,))
            db.execute(
                "DELETE FROM actions WHERE created < ? AND status NOT IN ('executing')",
                (cutoff,),
            )
            db.execute("DELETE FROM memories WHERE created < ?", (cutoff,))
            db.execute(
                "DELETE FROM sessions WHERE created < ? AND id NOT IN (SELECT session_id FROM actions) AND id NOT IN (SELECT session_id FROM contexts)",
                (cutoff,),
            )

    def close(self):
        with self.lock:
            self.db.close()
