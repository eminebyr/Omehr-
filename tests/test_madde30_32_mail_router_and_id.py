from __future__ import annotations

"""Madde 30-32 — Mail Router, Mail ID, ve önceden var olan bir hatanın
düzeltmesi (regresyon testleri).

KRİTİK BULGU: web/accounts.py::admin_copy_email_list() önceden HİÇBİR
ZAMAN eşleşmeyen bir regex kullanıyordu (küçük harfli+boşluklu desen,
gerçek Rol değerleri büyük harfli+alt çizgili) — yani "şirket geneli
Norm/AI raporu İK+yönetime gitsin" (Madde 27-28) sessizce hiç
çalışmıyordu. Bu test dosyası hem bu düzeltmeyi hem yeni Mail
Router/Mail ID altyapısını kapsar.
"""

import pandas as pd


def test_admin_copy_email_list_matches_real_role_format():
    """REGRESYON: HR_DIRECTOR/ADMIN gibi büyük harfli, alt çizgili
    gerçek rol değerleriyle eşleşmeli — önceden hiç eşleşmiyordu."""
    from web.accounts import admin_copy_email_list
    acc = pd.DataFrame([
        {"Rol": "HR_DIRECTOR", "E-posta": "ik1@test.com"},
        {"Rol": "ADMIN", "E-posta": "admin1@test.com"},
        {"Rol": "REGION", "E-posta": "bolge@test.com"},
    ])
    r = admin_copy_email_list(acc)
    assert "ik1@test.com" in r, "REGRESYON: HR_DIRECTOR rolü eşleşmiyor."
    assert "admin1@test.com" in r, "REGRESYON: ADMIN rolü eşleşmiyor."
    assert "bolge@test.com" not in r, "REGION rolü admin kopyası almamalı."


def test_mail_router_company_report_reaches_management():
    from services.mail_router import resolve_recipients
    sheets = {"Mail_Listesi": pd.DataFrame([
        {"Rol": "HR_DIRECTOR", "E-posta": "ik@test.com", "Yetki Kapsamı": "ALL"},
    ])}
    r = resolve_recipients(event_type="COMPANY_NORM_REPORT", scope="ALL", sheets=sheets)
    assert "ik@test.com" in r


def test_mail_router_region_report_only_own_region():
    """Madde 29: bölge müdürüne şirket geneli değil, yalnız kendi
    bölgesinin raporu gitmeli."""
    from services.mail_router import resolve_recipients
    sheets = {"Mail_Listesi": pd.DataFrame([
        {"Rol": "REGION", "E-posta": "ertan@test.com", "Yetki Kapsamı": "ERTAN"},
        {"Rol": "REGION", "E-posta": "cuneyt@test.com", "Yetki Kapsamı": "CUNEYT"},
    ])}
    r = resolve_recipients(event_type="REGION_NORM_REPORT", scope="ERTAN", sheets=sheets)
    assert "ertan@test.com" in r
    assert "cuneyt@test.com" not in r


def test_mail_id_generated_and_unique(tmp_path, monkeypatch):
    monkeypatch.setenv("OMEHR_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.setenv("OMEHR_MAIL_DRY_RUN", "1")
    from services.mail_idempotency import send_idempotent, stats
    send_idempotent("TEST1", "Konu 1", "Gövde", ["a@test.com"])
    send_idempotent("TEST2", "Konu 2", "Gövde", ["b@test.com"])
    kayitlar = stats()
    mail_idler = [k["mail_id"] for k in kayitlar]
    assert all(m and m.startswith("MAIL-") for m in mail_idler)
    assert len(set(mail_idler)) == len(mail_idler)


def test_mail_id_migration_does_not_crash_on_old_schema(tmp_path, monkeypatch):
    """REGRESYON: ALTER TABLE ADD COLUMN sütunu SONA ekler — pozisyonel
    INSERT bunu hesaba katmazsa eski (göç edilmiş) veritabanlarında
    çöker. Sütun adları açıkça belirtilerek bu önlendi."""
    import sqlite3
    monkeypatch.setenv("OMEHR_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.setenv("OMEHR_MAIL_DRY_RUN", "1")
    (tmp_path / "data").mkdir(exist_ok=True)
    con = sqlite3.connect(tmp_path / "data" / "mail_idempotency.db")
    con.execute("""CREATE TABLE mail_sends (
        idempotency_key TEXT PRIMARY KEY, report_type TEXT NOT NULL, run_id TEXT NOT NULL,
        recipients TEXT NOT NULL, subject TEXT, attachment_hash TEXT, status TEXT NOT NULL,
        attempts INTEGER NOT NULL DEFAULT 0, last_result TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    )""")
    con.commit()
    con.close()

    from services.mail_idempotency import send_idempotent
    sonuc = send_idempotent("TEST_GOC", "Konu", "Gövde", ["x@test.com"])
    assert sonuc.startswith("SENT")
