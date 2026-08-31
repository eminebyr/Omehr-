from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from services.runtime_paths import runtime_root


def _db_path():
    # DÜZELTME (path doubling / stale DB kaynağı): DB yolu önceden modül
    # importunda BİR KEZ (DB = runtime_root()/"data"/"jobs.db") sabitleniyordu.
    # Bu, projedeki TÜM diğer veritabanı erişimcilerinin (security.py,
    # web_runtime.py, download_audit.py, vb.) izlediği "her çağrıda taze
    # runtime_root() çöz" kuralını bozan tek istisnaydı. Eğer bu modül,
    # OMEHR_RUNTIME_ROOT ortam değişkeni işlem içinde henüz tam oturmadan
    # import edilirse, jobs.db o andaki (yanlış) köke SÜRESİZ sabitlenir —
    # diğer tüm DB'ler /app/data/data/ altında doğru yola giderken, jobs.db
    # farklı/eski bir konumda kalmaya devam eder. Artık her çağrıda taze
    # hesaplanıyor, diğer modüllerle tutarlı.
    return runtime_root() / "data" / "jobs.db"


def connect() -> sqlite3.Connection:
    db = _db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""CREATE TABLE IF NOT EXISTS jobs(
        id INTEGER PRIMARY KEY AUTOINCREMENT, tenant TEXT NOT NULL, job_type TEXT NOT NULL,
        payload TEXT NOT NULL, status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT, result TEXT, error TEXT,
        scheduled_key TEXT)""")
    existing = {row[1] for row in con.execute("PRAGMA table_info(jobs)").fetchall()}
    if "scheduled_key" not in existing:
        con.execute("ALTER TABLE jobs ADD COLUMN scheduled_key TEXT")
    con.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_jobs_scheduled_key "
        "ON jobs(scheduled_key) WHERE scheduled_key IS NOT NULL"
    )
    con.commit()
    return con


def enqueue(job_type: str, payload: dict | None = None, tenant: str = "OMEHR") -> int:
    with connect() as con:
        cur = con.execute(
            "INSERT INTO jobs(tenant,job_type,payload,status,created_at) VALUES(?,?,?,?,?)",
            (tenant, job_type, json.dumps(payload or {}, ensure_ascii=False, default=str), "PENDING",
             datetime.now().isoformat(timespec="seconds")),
        )
        return int(cur.lastrowid)


def enqueue_scheduled_once(
    job_type: str,
    payload: dict | None,
    tenant: str,
    scheduled_key: str,
) -> int | None:
    """Aynı kiracı/zaman dilimi için görevi yalnız bir kez oluşturur."""
    key = f"{tenant.strip().upper()}:{job_type}:{scheduled_key}"
    with connect() as con:
        try:
            cur = con.execute(
                """INSERT INTO jobs(tenant,job_type,payload,status,created_at,scheduled_key)
                   VALUES(?,?,?,?,?,?)""",
                (
                    tenant.strip().upper(), job_type,
                    json.dumps(payload or {}, ensure_ascii=False, default=str),
                    "PENDING", datetime.now().isoformat(timespec="seconds"), key,
                ),
            )
        except sqlite3.IntegrityError:
            return None
        return int(cur.lastrowid)


def claim() -> dict | None:
    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT * FROM jobs WHERE status='PENDING' ORDER BY id LIMIT 1").fetchone()
        if row is None:
            return None
        con.execute(
            "UPDATE jobs SET status='RUNNING',attempts=attempts+1,started_at=? WHERE id=?",
            (datetime.now().isoformat(timespec="seconds"), row["id"]),
        )
        result = dict(row)
        result["payload"] = json.loads(result["payload"])
        return result


def finish(job_id: int, result: dict) -> None:
    with connect() as con:
        con.execute(
            "UPDATE jobs SET status='SUCCESS',finished_at=?,result=? WHERE id=?",
            (datetime.now().isoformat(timespec="seconds"), json.dumps(result, ensure_ascii=False, default=str), job_id),
        )


def fail(job_id: int, error: str) -> None:
    with connect() as con:
        con.execute(
            "UPDATE jobs SET status='FAILED',finished_at=?,error=? WHERE id=?",
            (datetime.now().isoformat(timespec="seconds"), error[-8000:], job_id),
        )


def status(job_id: int) -> dict | None:
    with connect() as con:
        row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None


def metrics() -> dict[str, int]:
    with connect() as con:
        return {row["status"]: int(row["count"]) for row in con.execute(
            "SELECT status,COUNT(*) count FROM jobs GROUP BY status"
        )}