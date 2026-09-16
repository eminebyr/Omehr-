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


def _varsayilan_kiraci() -> str:
    from services.tenant_context import current_tenant_id
    return current_tenant_id()


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
    # DÜZELTME (KRİTİK — çapraz kiracı sızıntısı): tek süreç birden fazla
    # kiracıya hizmet ettiğinde bu tablo (personel before/after JSON
    # anlık görüntüleri DAHİL) runtime_root() üzerinden TÜM kiracılar
    # arasında PAYLAŞILIYORDU ve tenant sütunu yoktu. security.py/
    # job_queue.py'nin izlediği desen uygulanır.
    mevcut_sutunlar = {row[1] for row in con.execute("PRAGMA table_info(business_audit)").fetchall()}
    if "tenant" not in mevcut_sutunlar:
        con.execute("ALTER TABLE business_audit ADD COLUMN tenant TEXT NOT NULL DEFAULT 'OMEHR'")
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
    tenant: str | None = None,
) -> None:
    con = _connect()
    try:
        con.execute(
            """INSERT INTO business_audit
            (created_at, actor, action, entity_type, entity_key, before_json, after_json, metadata_json, tenant)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                actor or "system",
                action,
                entity_type,
                entity_key or "",
                _json(before),
                _json(after),
                _json(metadata),
                (tenant or _varsayilan_kiraci()).strip().upper(),
            ),
        )
        con.commit()
    finally:
        con.close()


def recent(limit: int = 200, tenant: str | None = None) -> list[dict]:
    """ÇAĞIRANIN kiracısına ait son N denetim kaydını döndürür — başka
    kiracıların kayıtları (ve içindeki before/after kişisel veri
    anlık görüntüleri) asla dönmez."""
    con = _connect()
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT * FROM business_audit WHERE tenant = ? ORDER BY id DESC LIMIT ?",
            ((tenant or _varsayilan_kiraci()).strip().upper(), max(1, int(limit))),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()
