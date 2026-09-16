"""KPI GEÇMİŞİ — ÇOK KİRACILI İZOLASYON regresyon testi.

Denetim bulgusu: tek süreç birden fazla kiracıya hizmet ettiğinde
(web girişinde firma seçimi), services/kpi_history.py, runtime_root()
üzerinden TÜM kiracılar arasında paylaşılan tek bir kpi_gecmisi.csv
dosyasını kiracı ayrımı YAPMADAN okuyup yazıyordu — bir firmanın günlük
KPI yazımı diğerininkinin üzerine yazılabiliyor, CEO Özeti "son 30 gün"
trendinde başka bir firmanın rakamları görünebiliyordu.
"""
from __future__ import annotations


def test_iki_kiracinin_kpi_gecmisi_karismaz(isolated_root, monkeypatch):
    from services.kpi_history import log_kpi_snapshot, load_history

    monkeypatch.setenv("OMEHR_TENANT", "KIRACI_A")
    log_kpi_snapshot({"Aktif Mevcut": 100, "Toplam Norm": 110, "Norm Eksiği": 10,
                       "Norm Fazlası": 0, "Net İhtiyaç": -10})

    monkeypatch.setenv("OMEHR_TENANT", "KIRACI_B")
    log_kpi_snapshot({"Aktif Mevcut": 999, "Toplam Norm": 999, "Norm Eksiği": 0,
                       "Norm Fazlası": 0, "Net İhtiyaç": 0})

    gecmis_a = load_history(tenant_id="KIRACI_A")
    gecmis_b = load_history(tenant_id="KIRACI_B")

    assert len(gecmis_a) == 1 and gecmis_a[0]["Aktif Mevcut"] == "100"
    assert len(gecmis_b) == 1 and gecmis_b[0]["Aktif Mevcut"] == "999"
    assert not any(s["Aktif Mevcut"] == "999" for s in gecmis_a), \
        "KRİTİK SIZINTI: KIRACI_A, KIRACI_B'nin KPI kaydını görüyor!"


def test_ayni_gun_ayni_kiraci_tek_satira_gunceller(isolated_root, monkeypatch):
    from services.kpi_history import log_kpi_snapshot, load_history

    monkeypatch.setenv("OMEHR_TENANT", "KIRACI_A")
    log_kpi_snapshot({"Aktif Mevcut": 100, "Toplam Norm": 110, "Norm Eksiği": 10,
                       "Norm Fazlası": 0, "Net İhtiyaç": -10})
    log_kpi_snapshot({"Aktif Mevcut": 105, "Toplam Norm": 110, "Norm Eksiği": 5,
                       "Norm Fazlası": 0, "Net İhtiyaç": -5})

    gecmis = load_history(tenant_id="KIRACI_A")
    assert len(gecmis) == 1
    assert gecmis[0]["Aktif Mevcut"] == "105"


def test_eski_kiracisiz_satirlar_varsayilan_kiraciya_ait_sayilir(isolated_root, monkeypatch):
    """Göç öncesi (kiracı sütunu eklenmeden önce) yazılmış CSV satırları,
    varsayılan 'OMEHR' kiracısına ait sayılır ve başka bir kiracıya SIZMAZ."""
    from services.runtime_paths import runtime_root
    from services.kpi_history import load_history

    eski_dosya = runtime_root() / "data" / "kpi_gecmisi.csv"
    eski_dosya.parent.mkdir(parents=True, exist_ok=True)
    eski_dosya.write_text(
        "Tarih,Aktif Mevcut,Toplam Norm,Norm Eksiği,Norm Fazlası,Net İhtiyaç\n"
        "2026-01-01,50,60,10,0,-10\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("OMEHR_TENANT", "OMEHR")
    assert len(load_history(tenant_id="OMEHR")) == 1

    monkeypatch.setenv("OMEHR_TENANT", "KIRACI_A")
    assert load_history(tenant_id="KIRACI_A") == []
