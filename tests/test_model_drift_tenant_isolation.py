"""MODEL DRIFT GEÇMİŞİ — ÇOK KİRACILI İZOLASYON regresyon testi.

Denetim bulgusu: services/model_drift.py, runtime_root() üzerinden TÜM
kiracılar arasında paylaşılan tek bir model_drift_gecmisi.csv dosyasını
kiracı ayrımı YAPMADAN okuyup yazıyordu. Bu yalnız bir gizlilik sorunu
değil, gerçek bir İŞ MANTIĞI hatasıydı: drift_kontrolu() referans MAE'yi
gecmis()'ten hesaplar — kiracı karışırsa bir firmanın drift alarmı başka
bir firmanın geçmiş model performansına göre yanlış tetiklenir/susar.
"""
from __future__ import annotations


def test_iki_kiracinin_model_gecmisi_karismaz(isolated_root, monkeypatch):
    from services.model_drift import kaydet, gecmis

    monkeypatch.setenv("OMEHR_TENANT", "KIRACI_A")
    kaydet("RandomForest", cv_mae=1.5, cv_r2=0.8, egitim_sayisi=100)

    monkeypatch.setenv("OMEHR_TENANT", "KIRACI_B")
    kaydet("GradientBoosting", cv_mae=99.9, cv_r2=0.1, egitim_sayisi=5)

    gecmis_a = gecmis(tenant_id="KIRACI_A")
    gecmis_b = gecmis(tenant_id="KIRACI_B")

    assert len(gecmis_a) == 1 and gecmis_a[0]["Model"] == "RandomForest"
    assert len(gecmis_b) == 1 and gecmis_b[0]["Model"] == "GradientBoosting"
    assert not any(s["Model"] == "GradientBoosting" for s in gecmis_a), \
        "KRİTİK SIZINTI: KIRACI_A, KIRACI_B'nin model geçmişini görüyor!"


def test_drift_referansi_baska_kiracidan_ETKILENMEZ(isolated_root, monkeypatch):
    """B'nin çok farklı (yüksek MAE) geçmişi, A'nın referansını
    bozmamalı — A yalnız KENDİ geçmişine göre drift tespit etmeli.

    kaydet() aynı takvim gününde tek satır tuttuğu için (bkz. FIELDS
    dedup anahtarı Kiracı+Tarih), geçmişi geçmiş TARİHLİ satırlarla
    doğrudan dosyaya yazarak simüle ediyoruz — tıpkı üretimde günlük
    main.py çalıştırmalarının biriktirdiği gibi."""
    from services.runtime_paths import runtime_root
    import csv
    from datetime import date, timedelta

    drift_dosya = runtime_root() / "data" / "model_drift_gecmisi.csv"
    drift_dosya.parent.mkdir(parents=True, exist_ok=True)
    satirlar = []
    for i in range(3):
        gun = (date.today() - timedelta(days=10 - i)).isoformat()
        satirlar.append({"Kiracı": "KIRACI_A", "Tarih": gun, "Model": f"A{i}", "CV_MAE": "1.0", "CV_R2": "0.9", "Egitim_Sayisi": "100"})
        satirlar.append({"Kiracı": "KIRACI_B", "Tarih": gun, "Model": f"B{i}", "CV_MAE": "500.0", "CV_R2": "0.1", "Egitim_Sayisi": "100"})
    with open(drift_dosya, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Kiracı", "Tarih", "Model", "CV_MAE", "CV_R2", "Egitim_Sayisi"])
        writer.writeheader()
        writer.writerows(satirlar)

    from services.model_drift import kaydet, drift_kontrolu

    monkeypatch.setenv("OMEHR_TENANT", "KIRACI_A")
    kaydet("ModelSon", cv_mae=1.0, cv_r2=0.9, egitim_sayisi=100)

    sonuc = drift_kontrolu()
    assert sonuc["yeterli_gecmis"] is True
    assert sonuc["referans_mae"] == 1.0, \
        "KRİTİK SIZINTI: A'nın drift referansı B'nin (500.0 MAE) geçmişinden etkileniyor!"
