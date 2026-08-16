from __future__ import annotations

"""Atama yaşam döngüsü — Madde 16-18 (regresyon testleri).

Bulunan ve düzeltilen gerçek hatalar:
1. create_appointment() "APPLIED" durumunu hesaplıyordu ama Fact_Mevcut'u
   GERÇEKTEN güncellemiyordu.
2. Atama belgesi her tıklamada yeniden üretiliyordu (dedup yoktu).
3. ATAMA_NO hiç üretilmiyordu.
"""

import shutil
from datetime import date, timedelta


def _hazirla(tmp_path):
    (tmp_path / "input").mkdir()
    shutil.copyfile(
        "ORNEK_TEST_VERISI/BASDAS_AI_NORM_TRANSFER_INPUT.xlsx",
        tmp_path / "input" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx",
    )
    return tmp_path / "input" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"


def test_appointment_gets_unique_atama_no(tmp_path, monkeypatch):
    monkeypatch.setenv("BASDAS_RUNTIME_ROOT", str(tmp_path))
    from services.personnel_exit import load_personnel_view
    from services.appointment_lifecycle import create_appointment

    hedef = _hazirla(tmp_path)
    staff, magaza, unvan, _ = load_personnel_view(hedef)
    kisi = staff[staff["İşten Çıkış"].isna()].iloc[0]
    hedef_magaza = magaza[magaza["Mağaza"] != kisi["Mağaza"]].iloc[0]

    sonuc = create_appointment(
        input_path=hedef, root=tmp_path, person_name=kisi["İsim Soyisim"], staff_index=kisi.name,
        staff_df=staff, magaza_df=magaza, unvan_df=unvan, source_store=kisi["Mağaza"], source_title=kisi["Unvan"],
        target_store=hedef_magaza["Mağaza"], target_title=kisi["Unvan"], planned_date=date.today(), created_by="test",
    )
    assert sonuc["atama_no"].startswith("ATM-")


def test_today_dated_appointment_actually_updates_fact_mevcut(tmp_path, monkeypatch):
    """REGRESYON: önceden APPLIED hesaplanıyordu ama Fact_Mevcut hiç
    güncellenmiyordu."""
    monkeypatch.setenv("BASDAS_RUNTIME_ROOT", str(tmp_path))
    from services.personnel_exit import load_personnel_view
    from services.appointment_lifecycle import create_appointment

    hedef = _hazirla(tmp_path)
    staff, magaza, unvan, _ = load_personnel_view(hedef)
    kisi = staff[staff["İşten Çıkış"].isna()].iloc[0]
    hedef_magaza = magaza[magaza["Mağaza"] != kisi["Mağaza"]].iloc[0]

    sonuc = create_appointment(
        input_path=hedef, root=tmp_path, person_name=kisi["İsim Soyisim"], staff_index=kisi.name,
        staff_df=staff, magaza_df=magaza, unvan_df=unvan, source_store=kisi["Mağaza"], source_title=kisi["Unvan"],
        target_store=hedef_magaza["Mağaza"], target_title=kisi["Unvan"], planned_date=date.today(), created_by="test",
    )
    assert sonuc["status"] == "APPLIED"
    staff2, *_ = load_personnel_view(hedef)
    assert staff2.loc[kisi.name, "Mağaza"] == hedef_magaza["Mağaza"], (
        "REGRESYON: APPLIED atama Fact_Mevcut'a gerçekten yazılmamış."
    )


def test_future_dated_appointment_does_not_touch_fact_mevcut(tmp_path, monkeypatch):
    monkeypatch.setenv("BASDAS_RUNTIME_ROOT", str(tmp_path))
    from services.personnel_exit import load_personnel_view
    from services.appointment_lifecycle import create_appointment

    hedef = _hazirla(tmp_path)
    staff, magaza, unvan, _ = load_personnel_view(hedef)
    kisi = staff[staff["İşten Çıkış"].isna()].iloc[0]
    eski_magaza = kisi["Mağaza"]
    hedef_magaza = magaza[magaza["Mağaza"] != eski_magaza].iloc[0]

    sonuc = create_appointment(
        input_path=hedef, root=tmp_path, person_name=kisi["İsim Soyisim"], staff_index=kisi.name,
        staff_df=staff, magaza_df=magaza, unvan_df=unvan, source_store=eski_magaza, source_title=kisi["Unvan"],
        target_store=hedef_magaza["Mağaza"], target_title=kisi["Unvan"],
        planned_date=date.today() + timedelta(days=10), created_by="test",
    )
    assert sonuc["status"] == "PLANNED"
    staff2, *_ = load_personnel_view(hedef)
    assert staff2.loc[kisi.name, "Mağaza"] == eski_magaza, "REGRESYON: gelecek tarihli atama anında uygulanmış."


def test_apply_due_appointments_activates_when_date_arrives(tmp_path, monkeypatch):
    monkeypatch.setenv("BASDAS_RUNTIME_ROOT", str(tmp_path))
    from services.personnel_exit import load_personnel_view
    from services.appointment_lifecycle import create_appointment, apply_due_appointments
    from services.web_runtime import connect_web_db

    hedef = _hazirla(tmp_path)
    staff, magaza, unvan, _ = load_personnel_view(hedef)
    kisi = staff[staff["İşten Çıkış"].isna()].iloc[0]
    eski_magaza = kisi["Mağaza"]
    hedef_magaza = magaza[magaza["Mağaza"] != eski_magaza].iloc[0]

    create_appointment(
        input_path=hedef, root=tmp_path, person_name=kisi["İsim Soyisim"], staff_index=kisi.name,
        staff_df=staff, magaza_df=magaza, unvan_df=unvan, source_store=eski_magaza, source_title=kisi["Unvan"],
        target_store=hedef_magaza["Mağaza"], target_title=kisi["Unvan"],
        planned_date=date.today() + timedelta(days=10), created_by="test",
    )
    # tarihi "bugüne" çekerek vadesi gelmiş gibi simüle et
    con = connect_web_db()
    con.execute("UPDATE appointments SET planned_date=? WHERE status='PLANNED'", (date.today().isoformat(),))
    con.commit(); con.close()

    uygulanan = apply_due_appointments(input_path=hedef, root=tmp_path)
    assert len(uygulanan) == 1
    staff2, *_ = load_personnel_view(hedef)
    assert staff2.loc[kisi.name, "Mağaza"] == hedef_magaza["Mağaza"]


def test_report_registry_prevents_duplicate_document_generation(tmp_path):
    """REGRESYON: aynı ATAMA_NO için belge iki kez fiziksel olarak
    üretilmemeli (Madde 18)."""
    from services.report_registry import get_or_build

    uretim_sayaci = {"n": 0}

    def uret():
        uretim_sayaci["n"] += 1
        p = tmp_path / f"belge_{uretim_sayaci['n']}.pdf"
        p.write_text("içerik")
        return p

    yol1, yeniden1 = get_or_build(
        tmp_path, report_type="ATAMA_BILDIRIMI", scope_type="ATAMA_NO", scope_id="ATM-20260811-00001",
        data_version="v1", template_version="V1", format="PDF", builder=uret,
    )
    yol2, yeniden2 = get_or_build(
        tmp_path, report_type="ATAMA_BILDIRIMI", scope_type="ATAMA_NO", scope_id="ATM-20260811-00001",
        data_version="v1", template_version="V1", format="PDF", builder=uret,
    )
    assert yol1 == yol2
    assert yeniden1 is True
    assert yeniden2 is False
    assert uretim_sayaci["n"] == 1
