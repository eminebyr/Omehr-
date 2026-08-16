from __future__ import annotations

"""Excel Verisi Yükle ekranı — regresyon testi.

Kalıcı dosya sisteminin olmadığı dağıtımlarda (ücretsiz bulut
barındırma), ana Excel dosyasının web arayüzünden yüklenip
veritabanına aktarılabildiğini doğrular — bu özellik olmadan
BASDAS_INPUT_SOURCE=db modunda hiçbir veri sisteme giremezdi.
"""


def test_full_chain_upload_migrate_read_produces_correct_kpis(tmp_path, monkeypatch):
    monkeypatch.setenv("BASDAS_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.setenv("BASDAS_DB_BACKEND", "sqlite")
    monkeypatch.setenv("BASDAS_INPUT_SOURCE", "db")
    monkeypatch.setenv("BASDAS_MAIL_DRY_RUN", "1")
    (tmp_path / "data").mkdir()

    from services.input_excel_migration import migrate_excel_to_db
    from services.runtime_paths import tenant_code
    from services.tenant_registry import create_tenant

    create_tenant(tenant_code(), "Test Firması", plan="standart", sube_kotasi=200, kullanici_kotasi=100)
    sonuc = migrate_excel_to_db(
        "ORNEK_TEST_VERISI/BASDAS_AI_NORM_TRANSFER_INPUT.xlsx",
        kullanici="test", tenant_id=tenant_code(),
    )
    basarili = sum(1 for v in sonuc.values() if v.get("durum") == "OK")
    assert basarili == 64, f"REGRESYON: yalnız {basarili}/64 sayfa aktarıldı."

    from services.input_data_access import read_all_sheets
    from src.state_engine import state
    from src.kpi_engine import kpis

    sheets = read_all_sheets()
    st, detail = state(sheets["Fact_Norm"], sheets["Fact_Mevcut"], sheets)
    kp = kpis(st)
    assert kp["Aktif Mevcut"] == 596, (
        f"REGRESYON: DB-tabanlı okuma sonrası yanlış KPI: {kp}"
    )
    assert kp["Toplam Norm"] == 607


def test_ayarlar_upload_section_uses_correct_migration_signature():
    """ayarlar.py'nin migrate_excel_to_db()'yi doğru parametrelerle
    çağırdığını kod incelemesiyle doğrular (regresyon: fonksiyon imzası
    değişirse bu test fark eder)."""
    kaynak = open("web/tab_modules/ayarlar.py", encoding="utf-8").read()
    assert "migrate_excel_to_db(" in kaynak
    assert "tenant_id=tenant_code()" in kaynak
