from __future__ import annotations

"""Immutable audit trail for critical business writes.

The runtime DB is append-only: UPDATE/DELETE are blocked by SQLite triggers.
Payloads store before/after snapshots (JSON) so a production incident can be
reconstructed without relying on application logs.
"""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from services.runtime_paths import runtime_root


def _db_path():
    return runtime_root() / "data" / "business_audit.db"


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=30)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS business_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_key TEXT,
            before_json TEXT,
            after_json TEXT,
            metadata_json TEXT
        )
        """
    )
    con.execute(
        """CREATE TRIGGER IF NOT EXISTS business_audit_no_update
        BEFORE UPDATE ON business_audit
        BEGIN SELECT RAISE(ABORT, 'business_audit immutable: UPDATE denied'); END;"""
    )
    con.execute(
        """CREATE TRIGGER IF NOT EXISTS business_audit_no_delete
        BEFORE DELETE ON business_audit
        BEGIN SELECT RAISE(ABORT, 'business_audit immutable: DELETE denied'); END;"""
    )
    con.commit()
    return con


def _json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)


def record(
    *,
    actor: str,
    action: str,
    entity_type: str,
    entity_key: str = "",
    before: Any = None,
    after: Any = None,
    metadata: Any = None,
) -> None:
    con = _connect()
    try:
        con.execute(
            """INSERT INTO business_audit
            (created_at, actor, action, entity_type, entity_key, before_json, after_json, metadata_json)
            VALUES (?,?,?,?,?,?,?,?)""",
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                actor or "system",
                action,
                entity_type,
                entity_key or "",
                _json(before),
                _json(after),
                _json(metadata),
            ),
        )
        con.commit()
    finally:
        con.close()


def recent(limit: int = 200) -> list[dict]:
    con = _connect()
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT * FROM business_audit ORDER BY id DESC LIMIT ?", (max(1, int(limit)),)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()
