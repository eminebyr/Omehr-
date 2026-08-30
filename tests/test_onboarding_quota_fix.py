from __future__ import annotations

"""Self-servis kayıt (onboarding.py) — regresyon testleri.

Önceden register_tenant(), plan ismini create_tenant()'a geçiriyordu
ama KOTA DEĞERLERİNİ geçmiyordu — bu yüzden 'standart'/'kurumsal'
plan seçmenin kota açısından hiçbir etkisi yoktu (her zaman
varsayılan 10 şube/5 kullanıcı kotası kullanılıyordu).
"""


def test_register_tenant_applies_correct_plan_quota(tmp_path, monkeypatch):
    monkeypatch.setenv("OMEHR_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.setenv("OMEHR_DB_BACKEND", "sqlite")
    (tmp_path / "data").mkdir()

    from services.onboarding import register_tenant

    sonuc = register_tenant("KOTATEST", "Kota Test Firması", plan="standart")
    assert sonuc["sube_kotasi"] == 50, (
        f"REGRESYON: 'standart' plan seçildi ama kota hâlâ varsayılan "
        f"({sonuc['sube_kotasi']}) — plan seçiminin kota üzerinde etkisi yok."
    )
    assert sonuc["kullanici_kotasi"] == 100


def test_full_self_service_onboarding_chain_end_to_end(tmp_path, monkeypatch):
    """3-adımlı self-servis kayıt akışının (firma kaydı → ilk admin →
    Excel içe aktarma → doğru KPI) TAM olarak çalıştığını doğrular."""
    monkeypatch.setenv("OMEHR_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.setenv("OMEHR_DB_BACKEND", "sqlite")
    monkeypatch.setenv("OMEHR_INPUT_SOURCE", "db")
    monkeypatch.setenv("OMEHR_TENANT", "TAMZINCIR")
    (tmp_path / "data").mkdir()

    from services.onboarding import register_tenant, register_first_admin, import_initial_data
    from services.security import authenticate

    register_tenant("TAMZINCIR", "Tam Zincir Test A.Ş.", plan="kurumsal")
    register_first_admin("TAMZINCIR", "admin1", "GucluSifre2026!", "admin@test.com")

    giris_sonucu = authenticate("admin1", "GucluSifre2026!", tenant_id="TAMZINCIR")
    assert giris_sonucu[0] is True, "REGRESYON: yeni oluşturulan admin hesabıyla giriş başarısız."

    sonuc = import_initial_data("TAMZINCIR", "ORNEK_VERI_GUVENLI/OMEHR_AI_NORM_TRANSFER_INPUT.xlsx")
    basarili = sum(1 for v in sonuc.values() if v.get("durum") == "OK")
    assert basarili == 64

    from services.input_data_access import read_all_sheets
    from src.state_engine import state
    from src.kpi_engine import kpis

    sheets = read_all_sheets()
    st, detail = state(sheets["Fact_Norm"], sheets["Fact_Mevcut"], sheets)
    kp = kpis(st)
    assert kp["Aktif Mevcut"] == 596
    assert kp["Toplam Norm"] == 607


def test_deneme_plan_quota_blocks_oversized_import_as_designed(tmp_path, monkeypatch):
    """'Deneme' planının düşük kotasının, GERÇEKTEN büyük bir veri
    yüklemesini engellediğini (bilinçli bir koruma olduğunu)
    doğrular — bu bir hata değil, tasarım kararıdır."""
    monkeypatch.setenv("OMEHR_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.setenv("OMEHR_DB_BACKEND", "sqlite")
    (tmp_path / "data").mkdir()

    from services.onboarding import register_tenant, register_first_admin, import_initial_data
    from services.tenant_quota import KotaAsimiHatasi

    register_tenant("DENEMEKOTA", "Deneme Kota Test", plan="deneme")
    register_first_admin("DENEMEKOTA", "admin1", "GucluSifre2026!")

    try:
        import_initial_data("DENEMEKOTA", "ORNEK_VERI_GUVENLI/OMEHR_AI_NORM_TRANSFER_INPUT.xlsx")
        assert False, "REGRESYON: deneme planı kota aşımını engellemiyor."
    except KotaAsimiHatasi:
        pass
