"""SQLite -> PostgreSQL VERİ TAŞIMA ARACI — testler (services/db_migration.py).

PostgreSQL sunucusu yoksa BASDAS_TEST_POSTGRES_DSN tanımlı olmadığı için
bu dosyadaki tüm testler nazikçe atlanır (bkz. tests/conftest.py
postgres_dsn fixture'ı).
"""
from __future__ import annotations

import sqlite3


def _ornek_sqlite_db(path):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE action_log(id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, username TEXT, action TEXT)")
    con.execute("INSERT INTO action_log(created_at, username, action) VALUES ('2026-01-01','ik_direktoru','LOGIN')")
    con.execute("INSERT INTO action_log(created_at, username, action) VALUES ('2026-01-02','bolge_muduru','TRANSFER_CREATE')")
    con.commit()
    con.close()


def test_migrate_database_copies_all_rows(tmp_path, postgres_dsn):
    import psycopg2
    from services.db_migration import migrate_database

    db_path = tmp_path / "test.db"
    _ornek_sqlite_db(db_path)

    con = psycopg2.connect(postgres_dsn)
    con.cursor().execute("DROP TABLE IF EXISTS action_log")
    con.commit()
    con.close()

    sonuc = migrate_database(db_path, postgres_dsn, tables=["action_log"])
    assert sonuc["action_log"]["sqlite_satir"] == 2
    assert sonuc["action_log"]["postgres_satir"] == 2
    assert sonuc["action_log"]["eslesti"] is True


def test_migrate_database_preserves_actual_content(tmp_path, postgres_dsn):
    import psycopg2
    from services.db_migration import migrate_database

    db_path = tmp_path / "test.db"
    _ornek_sqlite_db(db_path)

    con = psycopg2.connect(postgres_dsn)
    con.cursor().execute("DROP TABLE IF EXISTS action_log")
    con.commit()
    con.close()

    migrate_database(db_path, postgres_dsn, tables=["action_log"])

    con = psycopg2.connect(postgres_dsn)
    cur = con.cursor()
    cur.execute("SELECT username, action FROM action_log ORDER BY id")
    satirlar = cur.fetchall()
    con.close()
    assert satirlar == [("ik_direktoru", "LOGIN"), ("bolge_muduru", "TRANSFER_CREATE")]


def test_migrate_database_is_safely_rerunnable(tmp_path, postgres_dsn):
    """Aynı taşımayı iki kez çalıştırmak veri ÇOĞALTMAMALI (ON CONFLICT
    DO NOTHING) — kesintili bir taşımanın güvenle tekrar denenebilmesi
    için önemli."""
    import psycopg2
    from services.db_migration import migrate_database

    db_path = tmp_path / "test.db"
    _ornek_sqlite_db(db_path)

    con = psycopg2.connect(postgres_dsn)
    con.cursor().execute("DROP TABLE IF EXISTS action_log")
    con.commit()
    con.close()

    migrate_database(db_path, postgres_dsn, tables=["action_log"])
    sonuc2 = migrate_database(db_path, postgres_dsn, tables=["action_log"])

    assert sonuc2["action_log"]["postgres_satir"] == 2  # 4 değil, hâlâ 2


def test_migrate_database_reports_missing_table(tmp_path, postgres_dsn):
    from services.db_migration import migrate_database

    db_path = tmp_path / "test.db"
    _ornek_sqlite_db(db_path)

    sonuc = migrate_database(db_path, postgres_dsn, tables=["hic_olmayan_tablo"])
    assert "hata" in sonuc["hic_olmayan_tablo"]
