from __future__ import annotations

"""Madde 13/76 — Gelecek tarihli çıkış kuralı (regresyon testleri).

İş kuralı DEĞİŞTİRİLDİ (kullanıcı ile açıkça netleştirildi): önceden
resmi İşten Çıkış alanına HERHANGİ bir tarih (gelecekte olsa bile)
yazılması kişiyi ANINDA pasif yapıyordu. Artık kişi ÇIKIŞ TARİHİNE
KADAR aktif kalır. Bu, hem services/personnel_status.py (web paneli)
hem de src/data_loading.py (main.py'nin resmi KPI motoru) için AYNI
şekilde geçerlidir — ikisi artık TEK, merkezi fonksiyonu kullanır.
"""

import shutil
from datetime import date, timedelta

import pandas as pd
import pytest


def test_iso_date_string_parsed_correctly_not_swapped():
    """KRİTİK: dayfirst=True ISO tarihleri (2026-08-10) yanlışlıkla
    10 Ekim olarak ayrıştırıyordu — bizzat bulunup düzeltildi."""
    from services.personnel_status import exit_is_recorded
    bugun = pd.Timestamp("2026-08-10")
    # Ekim ayı olsaydı bugünden SONRA olurdu (aktif kalırdı) — Ağustos
    # doğru ayrıştırılırsa bugünle AYNI gün olur (pasif olur).
    assert exit_is_recorded("2026-08-10", bugun=bugun) is True


@pytest.fixture
def _hazirlanmis_dizin(tmp_path):
    for d in ("input", "templates", "reference", "assets/fonts"):
        (tmp_path / d).mkdir(parents=True)
    shutil.copyfile("ORNEK_TEST_VERISI/BASDAS_AI_NORM_TRANSFER_INPUT.xlsx", tmp_path / "input" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx")
    from pathlib import Path
    for f in Path("templates").glob("*.docx"):
        shutil.copyfile(f, tmp_path / "templates" / f.name)
    for f in Path("assets/fonts").glob("*.ttf"):
        shutil.copyfile(f, tmp_path / "assets" / "fonts" / f.name)
    for f in Path("reference").glob("*"):
        if f.is_file():
            shutil.copyfile(f, tmp_path / "reference" / f.name)
    return tmp_path


def test_future_dated_exit_keeps_official_kpi_active_count_unchanged(_hazirlanmis_dizin, monkeypatch):
    """Uçtan uca: main.py'nin RESMİ KPI motoru (data_loading.py üzerinden),
    gelecek tarihli bir çıkışı Aktif Mevcut sayısından DÜŞÜRMEMELİ."""
    monkeypatch.setenv("BASDAS_RUNTIME_ROOT", str(_hazirlanmis_dizin))
    from services.personnel_exit import load_personnel_view, process_exit
    from src.data_loading import load
    from pathlib import Path

    hedef = _hazirlanmis_dizin / "input" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"
    staff, magaza, unvan, cikis_nedeni = load_personnel_view(hedef)
    _, _, _, staff_onceki, _ = load(prepare=False)
    onceki_aktif_sayisi = len(staff_onceki)
    kisi = staff[staff["İşten Çıkış"].isna()].iloc[0]
    neden = cikis_nedeni.iloc[0]

    process_exit(
        input_path=hedef, root=_hazirlanmis_dizin, isim_soyisim=str(kisi["İsim Soyisim"]), magaza_id=str(kisi["MağazaID"]),
        staff_index=kisi.name, cikis_tarihi=date.today() + timedelta(days=30), cikis_kodu=str(neden["CikisGrubu"]),
        cikis_nedeni_id=neden["CikisNedeniID"], cikis_nedeni_metni=str(neden["CikisNedeni"]), kullanici="test",
    )

    _, sheets, norm, staff2, _ = load(prepare=False)
    assert len(staff2) == onceki_aktif_sayisi, (
        "REGRESYON: gelecek tarihli çıkış, main.py'nin resmi KPI motorunda "
        "kişiyi yanlışlıkla aktiften düşürüyor."
    )


def test_past_dated_exit_reduces_official_kpi_active_count(_hazirlanmis_dizin, monkeypatch):
    """Karşı senaryo: geçmiş tarihli çıkış GERÇEKTEN düşürmeli."""
    monkeypatch.setenv("BASDAS_RUNTIME_ROOT", str(_hazirlanmis_dizin))
    from services.personnel_exit import load_personnel_view, process_exit
    from src.data_loading import load

    hedef = _hazirlanmis_dizin / "input" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"
    staff, magaza, unvan, cikis_nedeni = load_personnel_view(hedef)
    # DÜZELTME: "önceki" sayı, DOĞRULANACAK aynı load() mekanizmasıyla
    # hesaplanır (staff["İşten Çıkış"].isna() gibi ESKİ, tarih-duyarsız
    # bir sayımla KARIŞTIRILMAZ — ikisi farklı kural kullandığı için
    # test verisinde başka bir gelecek-tarihli kayıt varsa yanlışlıkla
    # tutarsız görünebilirdi).
    _, _, _, staff_onceki, _ = load(prepare=False)
    onceki_aktif_sayisi = len(staff_onceki)
    kisi = staff[staff["İşten Çıkış"].isna()].iloc[0]
    neden = cikis_nedeni.iloc[0]

    process_exit(
        input_path=hedef, root=_hazirlanmis_dizin, isim_soyisim=str(kisi["İsim Soyisim"]), magaza_id=str(kisi["MağazaID"]),
        staff_index=kisi.name, cikis_tarihi=date.today() - timedelta(days=5), cikis_kodu=str(neden["CikisGrubu"]),
        cikis_nedeni_id=neden["CikisNedeniID"], cikis_nedeni_metni=str(neden["CikisNedeni"]), kullanici="test",
    )
    # TEŞHİS: doğrudan Excel'i (hiçbir önbellek olmadan) oku, process_exit'in
    # GERÇEKTEN yazıp yazmadığını doğrula.
    import pandas as pd
    ham = pd.read_excel(hedef, sheet_name="Fact_Mevcut")
    yazilan_satir = ham[ham["İsim Soyisim"].astype(str).str.strip() == str(kisi["İsim Soyisim"]).strip()]
    assert not yazilan_satir.empty, "process_exit satırı hiç yazmamış olabilir"
    assert pd.notna(yazilan_satir.iloc[0]["İşten Çıkış"]), (
        f"TEŞHİS: process_exit çalıştı ama Excel'e İşten Çıkış tarihi YAZILMAMIŞ! "
        f"Satır: {yazilan_satir.iloc[0].to_dict()}"
    )

    _, sheets, norm, staff2, _ = load(prepare=False)
    assert len(staff2) == onceki_aktif_sayisi - 1, (
        "REGRESYON: geçmiş tarihli çıkış artık kişiyi doğru şekilde düşürmüyor."
    )
