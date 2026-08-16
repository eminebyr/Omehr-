"""VERİTABANI ARKA UCU SOYUTLAMASI — SQLite (varsayılan) / PostgreSQL (seçenek).

Amaç: Tek şirket / az kullanıcı için SQLite yeterlidir ve varsayılan olarak
kalır — hiçbir ek kurulum gerekmez. Ürün birden fazla firmaya veya aynı
anda çok kullanıcıya satılacaksa, kod tabanını YENİDEN YAZMADAN, yalnız
ortam değişkenleriyle PostgreSQL'e geçilebilir:

    BASDAS_DB_BACKEND=postgres
    BASDAS_POSTGRES_DSN=postgresql://kullanici:parola@sunucu:5432/basdas

Tasarım kararı: Var olan tüm modüller `?` yer tutucularıyla (sqlite3
tarzı) ve sqlite3.Row benzeri sözlük-erişimli satırlarla yazılmıştı. Bu
modül, backend PostgreSQL olduğunda `?`'yi otomatik olarak `%s`'ye çeviren
ve satırları HER İKİ backend'de de aynı şekilde (hem indeksle hem isimle,
`row["sutun"]` ve `row[0]`) erişilebilir hale getiren bir bağlantı/cursor
SARMALAYICISI sağlar. Böylece mevcut modüller (services/web_runtime.py,
services/management_center.py, ...) `import sqlite3` yerine
`from services.db_backend import connect` yazıp SQL sorgularını
DEĞİŞTİRMEDEN iki backend'de de çalıştırabilir.

BİLEREK YAPILMAYAN (dürüstçe kapsam dışı — bkz. DEGISIKLIK_OZETI):
Bu modül TEMELİ kurar ve KANIT olarak `services/web_runtime.py` ile
`services/management_center.py`'yi bu temele taşır (gerçek bir PostgreSQL
sunucusuna karşı test edildi). `services/security.py`,
`services/job_queue.py`, `services/mail_idempotency.py`,
`services/download_audit.py`, `services/transfer_lifecycle.py` HENÜZ
taşınmadı — aynı desen uygulanarak taşınabilir ama bu, ayrı, dikkatli
test gerektiren bir iştir (özellikle security.py — parola verisi).
"""
from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import Any

from services.exceptions import ConfigurationError


def backend_name() -> str:
    """'sqlite' (varsayılan) veya 'postgres' döner."""
    value = os.environ.get("BASDAS_DB_BACKEND", "sqlite").strip().lower()
    if value not in {"sqlite", "postgres"}:
        raise ConfigurationError(
            f"Geçersiz BASDAS_DB_BACKEND: '{value}'. 'sqlite' veya 'postgres' olmalı."
        )
    return value


_PLACEHOLDER_RE = re.compile(r"\?")


class _PgRowWrapper:
    """psycopg2 satırlarını (tuple) sqlite3.Row gibi HEM isimle HEM
    indeksle erişilebilir yapar — mevcut kodda yaygın olan
    `row["sutun"]` ve `row[0]` kullanımlarının ikisi de bozulmadan
    çalışsın diye."""

    __slots__ = ("_data", "_columns")

    def __init__(self, data: tuple, columns: list[str]):
        self._data = data
        self._columns = columns

    def __getitem__(self, key):
        if isinstance(key, str):
            return self._data[self._columns.index(key)]
        return self._data[key]

    def keys(self):
        return list(self._columns)

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def __repr__(self):
        return f"<Row {dict(zip(self._columns, self._data))}>"


class _PgCursorWrapper:
    """psycopg2 cursor'ını sqlite3 cursor arayüzüne (execute ile `?` yer
    tutucu, .lastrowid, satır sonuçlarında isim+indeks erişimi) benzetir."""

    def __init__(self, cursor):
        self._cursor = cursor
        self.lastrowid = None

    def execute(self, sql: str, params: tuple | list = ()):
        pg_sql = _PLACEHOLDER_RE.sub("%s", sql)
        # ÖNEMLİ: params boşsa None geçilir (boş tuple DEĞİL). psycopg2,
        # vars=None olduğunda SQL içindeki '%' karakterlerine hiç
        # dokunmaz; boş bir tuple bile verilse "%" formatlama modunu
        # devreye sokar ve örn. PL/pgSQL "RAISE EXCEPTION '...%...'"
        # gibi DDL'lerdeki literal '%' karakterinde IndexError'a yol açar.
        self._cursor.execute(pg_sql, tuple(params) if params else None)
        # sqlite3'teki cursor.lastrowid davranışını taklit eder: sadece
        # "INSERT ... RETURNING id" biçimindeki sorgularda doldurulur.
        if pg_sql.strip().upper().startswith("INSERT") and self._cursor.description:
            try:
                self.lastrowid = self._cursor.fetchone()[0]
            except Exception:
                self.lastrowid = None
        return self

    def executescript(self, sql: str):
        # sqlite3'e özgü bir kolaylık metodudur; PostgreSQL'de birden
        # fazla deyimi tek execute() çağrısıyla çalıştırmak yeterlidir.
        self._cursor.execute(sql)
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        columns = [d[0] for d in self._cursor.description]
        return _PgRowWrapper(row, columns)

    def fetchall(self):
        rows = self._cursor.fetchall()
        if not rows:
            return []
        columns = [d[0] for d in self._cursor.description]
        return [_PgRowWrapper(r, columns) for r in rows]

    @property
    def rowcount(self):
        return self._cursor.rowcount


class _PgConnectionWrapper:
    """psycopg2 bağlantısını sqlite3.Connection arayüzüne benzetir."""

    def __init__(self, pg_conn):
        self._conn = pg_conn

    def execute(self, sql: str, params: tuple | list = ()):
        cur = _PgCursorWrapper(self._conn.cursor())
        return cur.execute(sql, params)

    def executescript(self, sql: str):
        cur = _PgCursorWrapper(self._conn.cursor())
        return cur.executescript(sql)

    def cursor(self):
        return _PgCursorWrapper(self._conn.cursor())

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False


def connect(sqlite_path: Path | str) -> Any:
    """Backend'e göre SQLite veya PostgreSQL bağlantısı döner.

    sqlite_path: yalnız sqlite backend'inde kullanılır (PostgreSQL'de tüm
    modüller AYNI veritabanına, BASDAS_POSTGRES_DSN ile bağlanır — dosya
    yolu kavramı yoktur, parametre yalnız arayüz uyumluluğu için tutulur).
    """
    if backend_name() == "sqlite":
        path = Path(sqlite_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(path, timeout=30)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA busy_timeout=30000")
        con.row_factory = sqlite3.Row
        return con

    try:
        import psycopg2
    except ImportError as exc:
        raise ConfigurationError(
            "BASDAS_DB_BACKEND=postgres ayarlanmış ama psycopg2 kurulu değil. "
            "'pip install psycopg2-binary' ile kurun."
        ) from exc

    dsn = os.environ.get("BASDAS_POSTGRES_DSN", "").strip()
    if not dsn:
        raise ConfigurationError(
            "BASDAS_DB_BACKEND=postgres ayarlanmış ama BASDAS_POSTGRES_DSN tanımlı değil."
        )
    pg_conn = psycopg2.connect(dsn)
    return _PgConnectionWrapper(pg_conn)


def ddl_for_backend(sqlite_ddl: str, postgres_ddl: str) -> str:
    """Bir CREATE TABLE/TRIGGER deyiminin backend'e göre doğru sürümünü
    döner. Her iki backend'in DDL sözdizimi (AUTOINCREMENT/SERIAL, trigger
    tanımı vb.) yeterince farklı olduğu için bu, tabloyu tanımlayan her
    modülde İKİ sürüm yazmayı gerektirir — otomatik çeviri yerine
    (hataya çok açık olurdu) açıkça iki DDL istenir."""
    return postgres_ddl if backend_name() == "postgres" else sqlite_ddl
