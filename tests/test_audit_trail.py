"""KALICI VE DEĞİŞTİRİLEMEZ AUDIT KAYDI — testler.

Kapsam:
1. action_log (services/web_runtime.py) ve audit_log (services/management_center.py)
   tablolarının SQLite TRIGGER'larla gerçekten UPDATE/DELETE'e kapalı olduğu.
2. services/backup.py'nin başarılı her input yedeklemesini action_log'a
   "INPUT_BACKUP" olarak, doğru actor (kullanıcı adı) ile yazdığı.
3. services/backup.py'nin artık runtime_root() kullandığı (bkz. bu turdaki
   bug düzeltmesi — önceden her zaman kod köküne yazıyordu, çoklu kiracı
   izolasyonunu bozuyordu).
"""
from __future__ import annotations

import sqlite3

import pytest


def test_action_log_rejects_update(isolated_root):
    from services.web_runtime import connect_web_db, log_web_action

    con = connect_web_db()
    log_web_action("test_user", "LOGIN", "ilk kayit")
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("UPDATE action_log SET action='HACKED' WHERE id=1")
    con.close()


def test_action_log_rejects_delete(isolated_root):
    from services.web_runtime import connect_web_db, log_web_action

    con = connect_web_db()
    log_web_action("test_user", "LOGIN", "ilk kayit")
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("DELETE FROM action_log WHERE id=1")
    # Satır hâlâ mevcut olmalı (silme gerçekten engellendi).
    row = con.execute("SELECT * FROM action_log WHERE id=1").fetchone()
    assert row is not None
    con.close()


def test_audit_log_rejects_update_and_delete(isolated_root):
    from services.management_center import init_db, connect, log_action

    init_db()
    log_action("ik_direktoru", "TRANSFER_REQUEST_CREATE", "test")
    con = connect()
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("UPDATE audit_log SET action='HACKED' WHERE id=1")
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("DELETE FROM audit_log WHERE id=1")
    con.close()


def test_backup_writes_immutable_audit_entry_with_correct_actor(isolated_root):
    import openpyxl
    from services.backup import backup_input_file
    from services.web_runtime import connect_web_db

    input_dir = isolated_root / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    dosya = input_dir / "ORNEK.xlsx"
    wb = openpyxl.Workbook()
    wb.active["A1"] = "test"
    wb.save(dosya)

    sonuc = backup_input_file(dosya, actor="ik_direktoru")
    assert sonuc is not None

    con = connect_web_db()
    row = con.execute(
        "SELECT username, action, detail FROM action_log WHERE action='INPUT_BACKUP'"
    ).fetchone()
    con.close()
    assert row is not None
    assert row[0] == "ik_direktoru"
    assert row[1] == "INPUT_BACKUP"
    assert "ORNEK.xlsx" in row[2]


def test_backup_defaults_to_system_actor_when_not_specified(isolated_root):
    import openpyxl
    from services.backup import backup_input_file
    from services.web_runtime import connect_web_db

    input_dir = isolated_root / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    dosya = input_dir / "ORNEK2.xlsx"
    wb = openpyxl.Workbook()
    wb.active["A1"] = "test"
    wb.save(dosya)

    backup_input_file(dosya)  # actor verilmedi

    con = connect_web_db()
    row = con.execute(
        "SELECT username FROM action_log WHERE action='INPUT_BACKUP'"
    ).fetchone()
    con.close()
    assert row is not None
    assert row[0] == "sistem"


def test_backup_respects_isolated_runtime_root_not_code_root(isolated_root):
    """REGRESYON TESTİ: services/backup.py önceden ROOT'u her zaman kod
    köküne sabitliyordu (Path(__file__).resolve().parent.parent), bu da
    çoklu kiracı / izole çalışma zamanı senaryosunda TÜM kiracıların
    yedeklerinin aynı paylaşılan klasöre karışmasına yol açıyordu."""
    from services import backup

    assert str(backup._backup_dir()).startswith(str(isolated_root))
    assert str(backup._restore_audit_log()).startswith(str(isolated_root))
