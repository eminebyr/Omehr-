from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from services.runtime_paths import runtime_root

DB = runtime_root() / "data" / "jobs.db"


def connect() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""CREATE TABLE IF NOT EXISTS jobs(
        id INTEGER PRIMARY KEY AUTOINCREMENT, tenant TEXT NOT NULL, job_type TEXT NOT NULL,
        payload TEXT NOT NULL, status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT, result TEXT, error TEXT)""")
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
