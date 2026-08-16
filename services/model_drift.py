from __future__ import annotations

"""
MODEL DRIFT VE PERFORMANS İZLEME (P2 — reviewer önerisi)
==============================================================
Sadece "şu anki güven skoru dağılımı" yeterli değildir — model zaman
içinde SAPABİLİR (veri değişir, iş yükü kalıpları değişir). Bu modül her
main.py çalıştırmasında model performansını (CV MAE) kalıcı bir geçmişe
kaydeder ve REFERANS (ilk N çalıştırmanın ortalaması) ile karşılaştırır.

Alarm örneği (reviewer): "Son 30 günde mağaza bazlı MAE, referans MAE'nin
%25 üzerine çıktı." — bu modül tam olarak bunu üretir.
"""

import csv
from datetime import datetime

from services.runtime_paths import runtime_root
from services.safe_exec import log_swallowed

def _drift_history_file():
    from services.runtime_paths import runtime_root
    return runtime_root() / "data" / "model_drift_gecmisi.csv"
FIELDS = ["Tarih", "Model", "CV_MAE", "CV_R2", "Egitim_Sayisi"]
UYARI_ESIGI_ORAN = 0.25  # reviewer örneği: referansın %25 üzerine çıkarsa uyar


def kaydet(model_adi: str, cv_mae: float, cv_r2: float, egitim_sayisi: int = 0) -> None:
    """Bugünün model performansını geçmiş dosyasına ekler/günceller.
    Hata durumunda ana akışı bozmadan sessizce başarısız olur."""
    try:
        _drift_history_file().parent.mkdir(parents=True, exist_ok=True)
        bugun = datetime.now().strftime("%Y-%m-%d")
        satirlar = []
        if _drift_history_file().is_file():
            with open(_drift_history_file(), "r", encoding="utf-8", newline="") as f:
                satirlar = list(csv.DictReader(f))
        satirlar = [s for s in satirlar if s.get("Tarih") != bugun]
        satirlar.append({
            "Tarih": bugun, "Model": model_adi,
            "CV_MAE": round(float(cv_mae), 4), "CV_R2": round(float(cv_r2), 4),
            "Egitim_Sayisi": int(egitim_sayisi),
        })
        satirlar.sort(key=lambda s: s.get("Tarih", ""))
        with open(_drift_history_file(), "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(satirlar)
    except Exception:
        from services.safe_exec import log_swallowed
        import sys
        log_swallowed("model_drift.kaydet: geçmiş dosyasına yazılamadı", sys.exc_info()[1] or Exception("bilinmeyen"))


def gecmis() -> list[dict]:
    """Kayıtlı tüm model performans geçmişini (eskiden yeniye) döndürür."""
    if not _drift_history_file().is_file():
        return []
    try:
        with open(_drift_history_file(), "r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))
    except Exception as _exc:
        log_swallowed("services.model_drift.gecmis: beklenmeyen hata", _exc)
        return []


def drift_kontrolu() -> dict:
    """Bugünkü (en son) model performansını, geçmişteki İLK N çalıştırmanın
    ortalaması olan REFERANS ile karşılaştırır. Referans MAE'den %25+ kötüyse
    (daha yüksek MAE = daha kötü) 'drift_tespit_edildi'=True döner.

    Yeterli geçmiş (en az 2 kayıt) yoksa nötr bir sonuç döner — henüz
    karşılaştırma yapılamaz, bu NORMALdir (uydurma referans üretilmez)."""
    kayitlar = gecmis()
    if len(kayitlar) < 2:
        return {
            "yeterli_gecmis": False,
            "mesaj": "Model drift karşılaştırması için henüz yeterli geçmiş birikmedi (en az 2 çalıştırma gerekir).",
        }

    referans_sayisi = max(1, min(5, len(kayitlar) - 1))  # ilk 5 (veya daha az) çalıştırma referanstır
    referans_kayitlar = kayitlar[:referans_sayisi]
    referans_mae = sum(float(k["CV_MAE"]) for k in referans_kayitlar) / len(referans_kayitlar)
    son_kayit = kayitlar[-1]
    son_mae = float(son_kayit["CV_MAE"])

    oran_degisim = (son_mae - referans_mae) / referans_mae if referans_mae else 0
    drift_var = oran_degisim > UYARI_ESIGI_ORAN

    return {
        "yeterli_gecmis": True,
        "referans_mae": round(referans_mae, 4),
        "son_mae": son_mae,
        "son_model": son_kayit.get("Model"),
        "son_tarih": son_kayit.get("Tarih"),
        "oran_degisim": round(oran_degisim, 4),
        "drift_tespit_edildi": drift_var,
        "mesaj": (
            f"⚠️ MODEL DRIFT TESPİT EDİLDİ: {son_kayit.get('Tarih')} tarihli çalıştırmada CV MAE "
            f"({son_mae:.3f}) referans ortalamanın (%{referans_mae:.3f}) %{oran_degisim*100:.0f} üzerinde — "
            f"model performansı kötüleşmiş olabilir, veri/model incelenmeli."
        ) if drift_var else "Model performansı referans aralığında, drift tespit edilmedi.",
    }
