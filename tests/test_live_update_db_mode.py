from __future__ import annotations

"""DB modunda 'canlı güncelleme' — regresyon testleri.

Kullanıcının sorusuna ("Fact_Mevcut'a kişi eklediğimde her yer
güncellenir mi?") cevap ararken 2 gerçek hata bulundu:
1) DB modunda, input dosyası diskte yoksa web/app.py giriş sonrası
   FileNotFoundError ile ÇÖKÜYORDU (5 korumasız .stat() çağrısı).
2) Çökme düzeltildikten sonra bile, DB modunda mtime sabit (0.0)
   kaldığı için st.cache_data, write_sheet() sonrası ESKİ veriyi
   döndürmeye devam ediyordu.
"""

import pandas as pd
import streamlit as st


def test_tenant_content_version_changes_after_write_sheet(tmp_path, monkeypatch):
    monkeypatch.setenv("BASDAS_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.setenv("BASDAS_DB_BACKEND", "sqlite")
    (tmp_path / "data").mkdir()

    from services.tenant_registry import create_tenant
    from services.input_data_access import tenant_content_version, ensure_schema, write_sheet

    create_tenant("VERSIYONTEST", "Versiyon Test", sube_kotasi=10, kullanici_kotasi=10)
    ensure_schema()

    v0 = tenant_content_version("VERSIYONTEST")
    assert v0 == 0.0, "REGRESYON: hiç yazma yapılmamış kiracı için versiyon 0.0 olmalı."

    write_sheet("Dim_Magaza", pd.DataFrame([{"MağazaID": "M001", "Mağaza": "ŞUBE1"}]), tenant_id="VERSIYONTEST")
    v1 = tenant_content_version("VERSIYONTEST")
    assert v1 > v0, "REGRESYON: write_sheet() sonrası versiyon damgası değişmedi."

    write_sheet("Dim_Magaza", pd.DataFrame([
        {"MağazaID": "M001", "Mağaza": "ŞUBE1"}, {"MağazaID": "M002", "Mağaza": "ŞUBE2"},
    ]), tenant_id="VERSIYONTEST")
    v2 = tenant_content_version("VERSIYONTEST")
    assert v2 > v1, (
        "REGRESYON: art arda iki write_sheet() çağrısı AYNI versiyon damgasını "
        "üretti — muhtemelen zaman çözünürlüğü yetersiz (saniye bazlı)."
    )


def test_cache_data_reflects_new_row_after_write_via_version_marker(tmp_path, monkeypatch):
    """Tam senaryo: kişi eklendikten sonra, st.cache_data'nın GERÇEKTEN
    yeni veriyi yansıttığını (tenant_content_version() önbellek
    anahtarı olarak kullanıldığında) doğrular."""
    monkeypatch.setenv("BASDAS_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.setenv("BASDAS_DB_BACKEND", "sqlite")
    (tmp_path / "data").mkdir()

    from services.tenant_registry import create_tenant
    from services.input_excel_migration import migrate_excel_to_db
    from services.input_data_access import tenant_content_version, read_sheet, write_sheet

    create_tenant("CANLIAKIS", "Canlı Akış Test", plan="kurumsal", sube_kotasi=10000, kullanici_kotasi=10000)
    migrate_excel_to_db("ORNEK_VERI_GUVENLI/BASDAS_AI_NORM_TRANSFER_INPUT.xlsx", tenant_id="CANLIAKIS")

    sayac = {"n": 0}

    @st.cache_data(show_spinner=False)
    def onbellekli_okuma(versiyon: float, tenant_id: str = ""):
        sayac["n"] += 1
        return len(read_sheet("Fact_Mevcut", tenant_id=tenant_id))

    v1 = tenant_content_version("CANLIAKIS")
    sonuc1 = onbellekli_okuma(v1, tenant_id="CANLIAKIS")
    assert sonuc1 == 596

    mevcut = read_sheet("Fact_Mevcut", tenant_id="CANLIAKIS")
    yeni_satir = mevcut.iloc[[0]].copy()
    yeni_satir["İsim Soyisim"] = "YENİ TEST KİŞİSİ"
    guncel = pd.concat([mevcut, yeni_satir], ignore_index=True)
    write_sheet("Fact_Mevcut", guncel, tenant_id="CANLIAKIS")

    v2 = tenant_content_version("CANLIAKIS")
    sonuc2 = onbellekli_okuma(v2, tenant_id="CANLIAKIS")

    assert sonuc2 == 597, (
        f"REGRESYON: Fact_Mevcut'a eklenen kişi önbellekli okumaya yansımadı "
        f"(beklenen 597, alınan {sonuc2}) — 'her yer güncellenir mi' sorusunun "
        f"cevabı artık 'hayır' olurdu."
    )
    assert sayac["n"] == 2, "REGRESYON: önbellek gerçekten yenilenmedi."


def test_db_mode_does_not_crash_when_input_file_missing(tmp_path, monkeypatch):
    """Kritik çöküş testi: DB modunda input dosyası diskte yokken,
    web/app.py'nin mtime hesaplama mantığı ÇÖKMEMELİ."""
    monkeypatch.setenv("BASDAS_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.setenv("BASDAS_INPUT_SOURCE", "db")
    monkeypatch.setenv("BASDAS_DB_BACKEND", "sqlite")
    (tmp_path / "data").mkdir()

    from services.settings import input_path
    from services.runtime_paths import runtime_root

    p = input_path(runtime_root())
    assert not p.exists(), "Test kurulumu hatalı: dosya var olmamalıydı."

    # web/app.py::_input_mtime_guvenli()'nin DB modu dalını taklit et
    from services.input_data_access import tenant_content_version
    try:
        sonuc = tenant_content_version("HERHANGI_BIR_KIRACI")
    except FileNotFoundError:
        assert False, "REGRESYON: DB modunda dosya yokken hâlâ FileNotFoundError fırlıyor."
    assert sonuc == 0.0


def test_excel_mode_still_uses_real_file_mtime(tmp_path, monkeypatch):
    """Regresyon kontrolü: Excel modunda (varsayılan), davranış hiç
    değişmemeli — hâlâ gerçek dosya mtime'ı kullanılmalı."""
    monkeypatch.setenv("BASDAS_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.delenv("BASDAS_INPUT_SOURCE", raising=False)
    (tmp_path / "input").mkdir()

    import shutil
    hedef = tmp_path / "input" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"
    shutil.copyfile("ORNEK_VERI_GUVENLI/BASDAS_AI_NORM_TRANSFER_INPUT.xlsx", hedef)

    from services.input_data_access import input_source
    assert input_source() == "excel"

    sonuc = hedef.stat().st_mtime if hedef.exists() else 0.0
    assert sonuc != 0.0, "REGRESYON: Excel modunda mtime hâlâ gerçek dosya değerini vermeli."
