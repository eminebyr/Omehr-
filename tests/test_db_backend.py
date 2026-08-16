"""SQLite/PostgreSQL VERİTABANI SOYUTLAMASI — testler (services/db_backend.py).

SQLite testleri HER ZAMAN çalışır (varsayılan backend, ek kurulum
gerektirmez). PostgreSQL testleri yalnız BASDAS_TEST_POSTGRES_DSN ortam
değişkeni tanımlıysa çalışır, aksi halde nazikçe ATLANIR — bu, geliştirme
ortamında gerçek bir PostgreSQL'e karşı doğrulanmış (bkz. DEGISIKLIK_OZETI),
ama teslim edilen pakette PostgreSQL zorunlu kılınmayan bir tasarımdır.
"""
from __future__ import annotations

import pytest

from services.exceptions import ConfigurationError


def test_default_backend_is_sqlite(monkeypatch):
    from services.db_backend import backend_name

    monkeypatch.delenv("BASDAS_DB_BACKEND", raising=False)
    assert backend_name() == "sqlite"


def test_invalid_backend_name_raises_configuration_error(monkeypatch):
    from services.db_backend import backend_name

    monkeypatch.setenv("BASDAS_DB_BACKEND", "mongodb")
    with pytest.raises(ConfigurationError):
        backend_name()


def test_sqlite_connect_execute_and_row_access(tmp_path, monkeypatch):
    monkeypatch.delenv("BASDAS_DB_BACKEND", raising=False)
    from services.db_backend import connect, ddl_for_backend

    con = connect(tmp_path / "test.db")
    con.execute(ddl_for_backend(
        "CREATE TABLE t(id INTEGER PRIMARY KEY AUTOINCREMENT, ad TEXT)",
        "CREATE TABLE t(id SERIAL PRIMARY KEY, ad TEXT)",
    ))
    con.execute("INSERT INTO t(ad) VALUES (?)", ("test",))
    con.commit()
    row = con.execute("SELECT * FROM t").fetchone()
    assert row["ad"] == "test"
    assert row[1] == "test"  # indeksle erişim de çalışmalı
    con.close()


def test_sqlite_lastrowid_works(tmp_path, monkeypatch):
    monkeypatch.delenv("BASDAS_DB_BACKEND", raising=False)
    from services.db_backend import connect

    con = connect(tmp_path / "test.db")
    con.execute("CREATE TABLE t(id INTEGER PRIMARY KEY AUTOINCREMENT, ad TEXT)")
    cur = con.execute("INSERT INTO t(ad) VALUES (?)", ("birinci",))
    con.commit()
    assert cur.lastrowid == 1
    cur2 = con.execute("INSERT INTO t(ad) VALUES (?)", ("ikinci",))
    con.commit()
    assert cur2.lastrowid == 2


# ------------------------------------------------------------------
# Aşağıdaki testler GERÇEK bir PostgreSQL sunucusu gerektirir; sunucu
# yoksa postgres_dsn fixture'ı testi otomatik atlar.
# ------------------------------------------------------------------

def test_postgres_connect_execute_and_row_access(postgres_dsn, monkeypatch):
    monkeypatch.setenv("BASDAS_DB_BACKEND", "postgres")
    monkeypatch.setenv("BASDAS_POSTGRES_DSN", postgres_dsn)
    from services.db_backend import connect, ddl_for_backend

    con = connect("/unused")
    con.execute("DROP TABLE IF EXISTS basdas_test_t")
    con.execute(ddl_for_backend(
        "CREATE TABLE basdas_test_t(id INTEGER PRIMARY KEY AUTOINCREMENT, ad TEXT)",
        "CREATE TABLE basdas_test_t(id SERIAL PRIMARY KEY, ad TEXT)",
    ))
    con.commit()
    con.execute("INSERT INTO basdas_test_t(ad) VALUES (?)", ("test",))
    con.commit()
    row = con.execute("SELECT * FROM basdas_test_t").fetchone()
    assert row["ad"] == "test"
    assert row[1] == "test"
    con.execute("DROP TABLE basdas_test_t")
    con.commit()
    con.close()


def test_postgres_lastrowid_via_returning(postgres_dsn, monkeypatch):
    monkeypatch.setenv("BASDAS_DB_BACKEND", "postgres")
    monkeypatch.setenv("BASDAS_POSTGRES_DSN", postgres_dsn)
    from services.db_backend import connect

    con = connect("/unused")
    con.execute("DROP TABLE IF EXISTS basdas_test_t2")
    con.execute("CREATE TABLE basdas_test_t2(id SERIAL PRIMARY KEY, ad TEXT)")
    con.commit()
    cur = con.execute("INSERT INTO basdas_test_t2(ad) VALUES (?) RETURNING id", ("birinci",))
    con.commit()
    assert cur.lastrowid == 1
    con.execute("DROP TABLE basdas_test_t2")
    con.commit()
    con.close()


def test_postgres_immutability_trigger_blocks_update_and_delete(postgres_dsn, monkeypatch):
    """REGRESYON/KANIT testi: 6. maddede SQLite için eklenen 'değiştirilemez
    audit tablosu' deseninin PostgreSQL'de de (farklı trigger sözdizimiyle)
    çalıştığını kanıtlar."""
    monkeypatch.setenv("BASDAS_DB_BACKEND", "postgres")
    monkeypatch.setenv("BASDAS_POSTGRES_DSN", postgres_dsn)
    from services.db_backend import connect

    con = connect("/unused")
    con.execute("DROP TABLE IF EXISTS basdas_test_immutable")
    con.execute("CREATE TABLE basdas_test_immutable(id SERIAL PRIMARY KEY, deger TEXT)")
    con.execute("""CREATE OR REPLACE FUNCTION basdas_test_immutable_fn() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'degistirilemez: % reddedildi', TG_OP;
END;
$$ LANGUAGE plpgsql""")
    con.execute("DROP TRIGGER IF EXISTS basdas_test_immutable_upd ON basdas_test_immutable")
    con.execute("CREATE TRIGGER basdas_test_immutable_upd BEFORE UPDATE ON basdas_test_immutable FOR EACH ROW EXECUTE FUNCTION basdas_test_immutable_fn()")
    con.commit()

    con.execute("INSERT INTO basdas_test_immutable(deger) VALUES (?)", ("orijinal",))
    con.commit()

    with pytest.raises(Exception):
        con.execute("UPDATE basdas_test_immutable SET deger='hacklendi' WHERE id=1")
        con.commit()
    con.rollback()

    row = con.execute("SELECT deger FROM basdas_test_immutable WHERE id=1").fetchone()
    assert row["deger"] == "orijinal"

    con.execute("DROP TABLE basdas_test_immutable")
    con.commit()
    con.close()
