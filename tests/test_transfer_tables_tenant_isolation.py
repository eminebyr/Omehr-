"""transfers / appointments / action_log — ÇOK KİRACILI İZOLASYON regresyonu.

Denetim bulgusu: services/web_runtime.py::connect_web_db() ile açılan
v16_management.db (transfers, appointments, action_log tabloları —
GERÇEK personel adı, mağaza, transfer gerekçesi, karar notu içerir),
tek süreç birden fazla kiracıya hizmet ettiğinde (web girişinde firma
seçimi) TÜM kiracılar arasında paylaşılıyordu ve HİÇ tenant sütunu
yoktu. Bu, hem bir GİZLİLİK sızıntısıydı (bir firmanın transfer
taleplerini/karar notlarını başka bir firma görebilirdi) hem de bir
İŞ MANTIĞI hatasıydı (apply_due_appointments/reconcile_transfer_requests
gibi otomatik işlemler başka bir kiracının kaydını YANLIŞLIKLA
uygulayabilirdi).
"""
from __future__ import annotations

import shutil
from datetime import date, timedelta

import sqlite3


def _hazirla(tmp_path):
    (tmp_path / "input").mkdir()
    shutil.copyfile(
        "ORNEK_TEST_VERISI/OMEHR_AI_NORM_TRANSFER_INPUT.xlsx",
        tmp_path / "input" / "OMEHR_AI_NORM_TRANSFER_INPUT.xlsx",
    )
    return tmp_path / "input" / "OMEHR_AI_NORM_TRANSFER_INPUT.xlsx"


def test_apply_due_appointments_bir_kiracinin_calismasi_digerini_UYGULAMAZ(tmp_path, monkeypatch):
    """KRİTİK: A kiracısı için apply_due_appointments() çağrıldığında,
    AYNI paylaşılan veritabanındaki B kiracısının vadesi gelmiş PLANNED
    ataması hiçbir şekilde uygulanmamalı (Fact_Mevcut'u da etkilememeli)."""
    monkeypatch.setenv("OMEHR_RUNTIME_ROOT", str(tmp_path))
    from services.personnel_exit import load_personnel_view
    from services.appointment_lifecycle import create_appointment, apply_due_appointments
    from services.web_runtime import connect_web_db

    hedef = _hazirla(tmp_path)
    staff, magaza, unvan, _ = load_personnel_view(hedef)
    aktifler = staff[staff["İşten Çıkış"].isna()]
    kisi_a = aktifler.iloc[0]
    kisi_b = aktifler.iloc[1]
    hedef_magaza_a = magaza[magaza["Mağaza"] != kisi_a["Mağaza"]].iloc[0]
    hedef_magaza_b = magaza[magaza["Mağaza"] != kisi_b["Mağaza"]].iloc[0]

    monkeypatch.setenv("OMEHR_TENANT", "KIRACI_A")
    create_appointment(
        input_path=hedef, root=tmp_path, person_name=kisi_a["İsim Soyisim"], staff_index=kisi_a.name,
        staff_df=staff, magaza_df=magaza, unvan_df=unvan, source_store=kisi_a["Mağaza"], source_title=kisi_a["Unvan"],
        target_store=hedef_magaza_a["Mağaza"], target_title=kisi_a["Unvan"],
        planned_date=date.today() + timedelta(days=10), created_by="test_a",
    )

    monkeypatch.setenv("OMEHR_TENANT", "KIRACI_B")
    create_appointment(
        input_path=hedef, root=tmp_path, person_name=kisi_b["İsim Soyisim"], staff_index=kisi_b.name,
        staff_df=staff, magaza_df=magaza, unvan_df=unvan, source_store=kisi_b["Mağaza"], source_title=kisi_b["Unvan"],
        target_store=hedef_magaza_b["Mağaza"], target_title=kisi_b["Unvan"],
        planned_date=date.today() + timedelta(days=10), created_by="test_b",
    )

    # her iki ataman ın da tarihi "bugüne" gelmiş gibi simüle et
    con = connect_web_db()
    con.execute("UPDATE appointments SET planned_date=? WHERE status='PLANNED'", (date.today().isoformat(),))
    con.commit()
    con.close()

    monkeypatch.setenv("OMEHR_TENANT", "KIRACI_A")
    uygulanan = apply_due_appointments(input_path=hedef, root=tmp_path)

    assert len(uygulanan) == 1, (
        f"KRİTİK SIZINTI: KIRACI_A'nın çalışması {len(uygulanan)} atama uyguladı, "
        f"1 bekleniyordu (KIRACI_B'nin ataması da uygulanmış olabilir)."
    )
    assert uygulanan[0]["person_name"] == kisi_a["İsim Soyisim"]

    staff_sonra, *_ = load_personnel_view(hedef)
    assert staff_sonra.loc[kisi_a.name, "Mağaza"] == hedef_magaza_a["Mağaza"], "A'nın kendi ataması uygulanmalı."
    assert staff_sonra.loc[kisi_b.name, "Mağaza"] == kisi_b["Mağaza"], (
        "KRİTİK SIZINTI: KIRACI_A'nın çalışması KIRACI_B'nin personelini taşımış!"
    )

    con = connect_web_db()
    con.row_factory = sqlite3.Row
    b_kaydi = con.execute(
        "SELECT status FROM appointments WHERE tenant='KIRACI_B'"
    ).fetchone()
    con.close()
    assert b_kaydi["status"] == "PLANNED", (
        "KRİTİK SIZINTI: KIRACI_B'nin ataması KIRACI_A'nın çalışması tarafından APPLIED yapılmış!"
    )


def test_transfers_ve_action_log_tenant_sutunu_ile_goc_eder(tmp_path, monkeypatch):
    """connect_web_db() ve services.management_center.connect() AYNI
    dosyayı açar. connect_web_db() tabloları oluşturur (management_center.
    connect() bunu varsaymaya devam eder — davranış değişmedi); asıl
    kanıtlanan şey, management_center.connect()'in DE tenant göçünü
    (idempotent biçimde, hata vermeden) uygulayabilmesidir."""
    monkeypatch.setenv("OMEHR_RUNTIME_ROOT", str(tmp_path))
    from services.management_center import connect as mc_connect
    from services.web_runtime import connect_web_db

    con0 = connect_web_db()
    con0.close()

    con = mc_connect()  # tabloyu OLUŞTURMAZ ama tenant sütununu göçürebilmeli, hatasız
    con.execute(
        "INSERT INTO transfers(created_at,status,tenant) VALUES(?,?,?)",
        ("2026-01-01", "İK Onayladı", "KIRACI_A"),
    )
    con.commit()
    con.close()

    con2 = connect_web_db()
    con2.row_factory = sqlite3.Row
    satirlar = {row["tenant"] for row in con2.execute("SELECT tenant FROM transfers").fetchall()}
    con2.close()
    assert satirlar == {"KIRACI_A"}
