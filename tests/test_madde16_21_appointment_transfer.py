from __future__ import annotations

"""OMEHR hızlandırma şartnamesi Madde 16-21 — regresyon testleri."""

import re
import shutil
from datetime import date, timedelta


def test_appointment_no_format_and_sequence(tmp_path, monkeypatch):
    monkeypatch.setenv("BASDAS_RUNTIME_ROOT", str(tmp_path))
    from services.appointment_lifecycle import yeni_atama_no
    no1 = yeni_atama_no()
    assert re.match(r"^ATM-\d{8}-\d{5}$", no1)


def test_transfer_no_format_and_sequence(tmp_path, monkeypatch):
    monkeypatch.setenv("BASDAS_RUNTIME_ROOT", str(tmp_path))
    from services.web_runtime import yeni_transfer_no, connect_web_db
    no1 = yeni_transfer_no()
    assert re.match(r"^TRF-\d{8}-\d{5}$", no1)
    con = connect_web_db()
    con.execute("INSERT INTO transfers(transfer_no, status) VALUES(?, 'BEKLIYOR')", (no1,))
    con.commit()
    con.close()
    no2 = yeni_transfer_no()
    assert no2.endswith("00002")


def test_appointment_today_applies_immediately_and_future_stays_planned(tmp_path, monkeypatch):
    monkeypatch.setenv("BASDAS_RUNTIME_ROOT", str(tmp_path))
    (tmp_path / "input").mkdir()
    shutil.copyfile("ORNEK_TEST_VERISI/BASDAS_AI_NORM_TRANSFER_INPUT.xlsx", tmp_path / "input" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx")
    hedef = tmp_path / "input" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"

    from services.appointment_lifecycle import create_appointment
    from services.personnel_exit import load_personnel_view

    staff, magaza, unvan, _ = load_personnel_view(hedef)
    kisi = staff[staff["İşten Çıkış"].isna()].iloc[0]
    eski_magaza = kisi["Mağaza"]
    yeni_magaza = magaza[magaza["Mağaza"] != eski_magaza]["Mağaza"].iloc[0]

    sonuc = create_appointment(
        input_path=hedef, root=tmp_path, person_name=str(kisi["İsim Soyisim"]), staff_index=kisi.name,
        staff_df=staff, magaza_df=magaza, unvan_df=unvan, source_store=eski_magaza, source_title=kisi["Unvan"],
        target_store=yeni_magaza, target_title=kisi["Unvan"], planned_date=date.today(), created_by="test",
    )
    assert sonuc["status"] == "APPLIED"
    staff2, *_ = load_personnel_view(hedef)
    assert staff2.loc[kisi.name, "Mağaza"] == yeni_magaza, "REGRESYON: bugünkü atama Fact_Mevcut'a uygulanmadı."

    kisi2 = staff2[staff2["İşten Çıkış"].isna()].iloc[1]
    sonuc2 = create_appointment(
        input_path=hedef, root=tmp_path, person_name=str(kisi2["İsim Soyisim"]), staff_index=kisi2.name,
        staff_df=staff2, magaza_df=magaza, unvan_df=unvan, source_store=kisi2["Mağaza"], source_title=kisi2["Unvan"],
        target_store=yeni_magaza, target_title=kisi2["Unvan"], planned_date=date.today() + timedelta(days=10), created_by="test",
    )
    assert sonuc2["status"] == "PLANNED"
    staff3, *_ = load_personnel_view(hedef)
    assert staff3.loc[kisi2.name, "Mağaza"] == kisi2["Mağaza"], "REGRESYON: gelecek tarihli atama erken uygulanmış."


def test_report_registry_prevents_duplicate_physical_generation(tmp_path):
    from services.report_registry import get_or_build
    sayac = {"n": 0}

    def uret():
        sayac["n"] += 1
        f = tmp_path / f"r{sayac['n']}.txt"
        f.write_text("x")
        return f

    for _ in range(3):
        get_or_build(tmp_path, report_type="T", scope_type="S", scope_id="1", data_version="V1", template_version="V1", format="PDF", builder=uret)
    assert sayac["n"] == 1, "REGRESYON: aynı anahtarla rapor tekrar tekrar üretiliyor."


def test_transfer_recipients_deduplicate_same_region_manager():
    from web.accounts import transfer_recipients
    import pandas as pd
    acc = pd.DataFrame([{"E-posta": "bolge@test.com", "Yetki Kapsamı": "AYNI BOLGE"}])
    satir = {"region": "AYNI BOLGE", "target_region": "AYNI BOLGE", "source_store": "A", "target_store": "B"}
    alicilar = transfer_recipients(acc, satir, {})
    assert len(alicilar) == len(set(alicilar)), "REGRESYON: aynı bölge müdürü mükerrer ekleniyor."
