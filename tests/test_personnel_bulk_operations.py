"""services/personnel_exit.py — toplu işe giriş / toplu işten çıkış
gerçek fonksiyonel testleri (FAST V9 entegrasyonu).
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from services.personnel_exit import (
    load_personnel_view, add_personnel_bulk, process_exits_bulk, is_active,
)


@pytest.fixture
def ornek_input(tmp_path):
    yol = tmp_path / "input.xlsx"
    staff = pd.DataFrame([
        {"İsim Soyisim": "AYŞE VAR", "MağazaID": "M1", "Mağaza": "TEST MAĞAZA",
         "UnvanID": "U1", "Unvan": "KASİYER", "Departman": "KASİYER",
         "İşe Giriş": "2025-01-01", "İşten Çıkış": None, "Çıkış Kodu": None,
         "CikisNedeniID": None, "Çıkış Nedeni": None, "Açıklama": None},
        {"İsim Soyisim": "MEHMET VAR", "MağazaID": "M1", "Mağaza": "TEST MAĞAZA",
         "UnvanID": "U2", "Unvan": "MANAV", "Departman": "MANAV",
         "İşe Giriş": "2025-02-01", "İşten Çıkış": None, "Çıkış Kodu": None,
         "CikisNedeniID": None, "Çıkış Nedeni": None, "Açıklama": None},
    ])
    magaza = pd.DataFrame([{"MağazaID": "M1", "Mağaza": "TEST MAĞAZA", "Bölge Sorumlusu": "TEST BÖLGE"}])
    unvan = pd.DataFrame([{"UnvanID": "U1", "Unvan": "KASİYER"}, {"UnvanID": "U2", "Unvan": "MANAV"}])
    norm = pd.DataFrame([
        {"MağazaID": "M1", "UnvanID": "U1", "Norm Kadro": 2},
        {"MağazaID": "M1", "UnvanID": "U2", "Norm Kadro": 2},
    ])
    cikis = pd.DataFrame([
        {"CikisNedeniID": 1, "CikisNedeni": "İstifa - Ücret", "CikisGrubu": "İstifa", "AnalizKategorisi": "Ücret"},
        {"CikisNedeniID": 2, "CikisNedeni": "İşveren feshi - Performans", "CikisGrubu": "İşveren feshi", "AnalizKategorisi": "Performans"},
    ])
    with pd.ExcelWriter(yol, engine="openpyxl") as w:
        staff.to_excel(w, sheet_name="Fact_Mevcut", index=False)
        magaza.to_excel(w, sheet_name="Dim_Magaza", index=False)
        unvan.to_excel(w, sheet_name="Dim_Unvan", index=False)
        norm.to_excel(w, sheet_name="Fact_Norm", index=False)
        cikis.to_excel(w, sheet_name="Dim_CikisNedeni", index=False)
    return yol, tmp_path


def test_add_personnel_bulk_adds_multiple_people_in_one_write(ornek_input, monkeypatch):
    yol, root = ornek_input
    staff, magaza, unvan, _ = load_personnel_view(yol)
    yeni_kayitlar = [
        {c: None for c in staff.columns} | {
            "İsim Soyisim": "CAN YENİ", "MağazaID": "M1", "Mağaza": "TEST MAĞAZA",
            "UnvanID": "U1", "Unvan": "KASİYER", "Departman": "KASİYER", "İşe Giriş": "2026-08-09",
        },
        {c: None for c in staff.columns} | {
            "İsim Soyisim": "DENİZ YENİ", "MağazaID": "M1", "Mağaza": "TEST MAĞAZA",
            "UnvanID": "U2", "Unvan": "MANAV", "Departman": "MANAV", "İşe Giriş": "2026-08-09",
        },
    ]
    sonuc = add_personnel_bulk(input_path=yol, root=root, staff=staff, yeni_kayitlar=yeni_kayitlar, username="test")
    assert sonuc == {"durum": "OK", "eklenen": 2}

    guncel, *_ = load_personnel_view(yol)
    assert len(guncel) == 4
    assert "CAN YENİ" in guncel["İsim Soyisim"].values
    assert "DENİZ YENİ" in guncel["İsim Soyisim"].values


def test_process_exits_bulk_each_person_keeps_own_code_and_reason(ornek_input):
    """FAST V9'un asıl istediği davranış: aynı toplu işlemde bir kişi
    İstifa, başka bir kişi İşveren feshi ile çıkabilmeli."""
    yol, root = ornek_input
    staff, _, _, cikis_nedeni = load_personnel_view(yol)
    ayse_idx = staff.index[staff["İsim Soyisim"] == "AYŞE VAR"][0]
    mehmet_idx = staff.index[staff["İsim Soyisim"] == "MEHMET VAR"][0]

    cikislar = [
        {"index": ayse_idx, "cikis_tarihi": date(2026, 8, 9), "cikis_kodu": "İstifa",
         "cikis_nedeni_id": 1, "cikis_nedeni_metni": "İstifa - Ücret"},
        {"index": mehmet_idx, "cikis_tarihi": date(2026, 8, 9), "cikis_kodu": "İşveren feshi",
         "cikis_nedeni_id": 2, "cikis_nedeni_metni": "İşveren feshi - Performans"},
    ]
    sonuc = process_exits_bulk(input_path=yol, root=root, cikislar=cikislar, kullanici="test")
    assert sonuc["durum"] == "OK"
    assert sonuc["guncellenen_satir"] == 2
    assert sonuc["basarisiz_satir"] == 0

    guncel, *_ = load_personnel_view(yol)
    ayse = guncel.loc[guncel["İsim Soyisim"] == "AYŞE VAR"].iloc[0]
    mehmet = guncel.loc[guncel["İsim Soyisim"] == "MEHMET VAR"].iloc[0]

    assert ayse["Çıkış Kodu"] == "İstifa"
    assert ayse["Çıkış Nedeni"] == "İstifa - Ücret"
    assert mehmet["Çıkış Kodu"] == "İşveren feshi"
    assert mehmet["Çıkış Nedeni"] == "İşveren feshi - Performans"
    assert not is_active(ayse.to_dict())
    assert not is_active(mehmet.to_dict())


def test_process_exits_bulk_rejects_already_exited_person(ornek_input):
    """DÜZELTME (Madde 15 — her satır bağımsız): zaten çıkmış personel
    için 2. deneme artık istisna fırlatmaz — satır başarısız sayılıp
    ayrı raporlanır."""
    yol, root = ornek_input
    staff, _, _, _ = load_personnel_view(yol)
    idx = staff.index[staff["İsim Soyisim"] == "AYŞE VAR"][0]
    cikislar = [{"index": idx, "cikis_tarihi": date(2026, 8, 9), "cikis_kodu": "İstifa",
                 "cikis_nedeni_id": 1, "cikis_nedeni_metni": "İstifa - Ücret"}]
    process_exits_bulk(input_path=yol, root=root, cikislar=cikislar, kullanici="test")

    staff2, *_ = load_personnel_view(yol)
    idx2 = staff2.index[staff2["İsim Soyisim"] == "AYŞE VAR"][0]
    sonuc2 = process_exits_bulk(
        input_path=yol, root=root,
        cikislar=[{"index": idx2, "cikis_tarihi": date(2026, 8, 9), "cikis_kodu": "İstifa",
                   "cikis_nedeni_id": 1, "cikis_nedeni_metni": "İstifa - Ücret"}],
        kullanici="test",
    )
    assert sonuc2["guncellenen_satir"] == 0
    assert sonuc2["basarisiz_satir"] == 1
    assert "zaten kayıtlı" in sonuc2["hatalar"][0]["hata"]


def test_process_exits_bulk_empty_list_raises(ornek_input):
    yol, root = ornek_input
    with pytest.raises(ValueError, match="seçilmedi"):
        process_exits_bulk(input_path=yol, root=root, cikislar=[], kullanici="test")
