from __future__ import annotations

"""
KPI GEÇMİŞ TAKİP MODÜLÜ
==========================
CEO Özet Ekranı'nda "son 30 günlük değişim" gösterebilmek için, sistemin
GERÇEK bir zaman serisi geçmişine ihtiyacı var. Bu modül, `main.py` her
çalıştığında (günde bir kez, zamanlayıcı ile veya manuel) o anki resmi
KPI'ları `data/kpi_gecmisi.csv` dosyasına bir satır olarak ekler.

Aynı gün içinde birden fazla çalıştırma olursa, o güne ait satır GÜNCELLENİR
(tekrar eklenmez) — böylece dosya sınırsız büyümez ve "günlük" bir seri
oluşur. Geçmiş, sistem ilk kez bu haliyle çalıştırıldığı andan itibaren
birikir; geriye dönük tarihler için veri YOKTUR (uydurulamaz).
"""

import csv
from datetime import datetime, timedelta

from services.runtime_paths import runtime_root


def _history_file():
    from services.runtime_paths import runtime_root
    return runtime_root() / "data" / "kpi_gecmisi.csv"


def _varsayilan_kiraci() -> str:
    from services.tenant_context import current_tenant_id
    return current_tenant_id()


FIELDS = ["Kiracı", "Tarih", "Aktif Mevcut", "Toplam Norm", "Norm Eksiği", "Norm Fazlası", "Net İhtiyaç"]


def log_kpi_snapshot(kpi: dict, tenant_id: str | None = None) -> None:
    """Bugünün KPI'sını geçmiş dosyasına ekler/günceller. Hata durumunda
    sessizce başarısız olur — ana rapor akışını asla bozmaz.

    Supabase senkronizasyonu da burada, ana motor tamamen başarıyla bittikten
    sonra ve yalnız OMEHR_SUPABASE_SYNC=1 ise denenir. Senkronizasyon hatası
    yerel KPI geçmişini veya ana rapor motorunu etkilemez.
    """
    try:
        # DÜZELTME (KRİTİK — çapraz kiracı sızıntısı): tek süreç birden
        # fazla kiracıya hizmet ettiğinde (web girişinde firma seçimi /
        # self-servis kayıt), bu dosya runtime_root() üzerinden TÜM
        # kiracılar arasında PAYLAŞILIYORDU ve kiracı sütunu yoktu — bir
        # firmanın günlük KPI yazımı diğerininkinin üzerine yazabiliyor,
        # CEO Özeti "son 30 gün" trendinde başka bir firmanın rakamları
        # görünebiliyordu. Artık her satır kiracıya damgalanır ve
        # okuma/yazma ÇAĞIRANIN kiracısıyla sınırlanır.
        kiraci = (tenant_id or _varsayilan_kiraci()).strip().upper()
        _history_file().parent.mkdir(parents=True, exist_ok=True)
        bugun = datetime.now().strftime("%Y-%m-%d")
        satirlar = []
        if _history_file().is_file():
            with open(_history_file(), "r", encoding="utf-8", newline="") as f:
                satirlar = list(csv.DictReader(f))
        for s in satirlar:
            if not s.get("Kiracı"):
                s["Kiracı"] = "OMEHR"  # eski dosya: kiracı sütunundan önceki satırlar
        satirlar = [s for s in satirlar if not (s.get("Kiracı") == kiraci and s.get("Tarih") == bugun)]
        yeni_satir = {"Kiracı": kiraci, "Tarih": bugun}
        for alan in FIELDS[2:]:
            yeni_satir[alan] = kpi.get(alan, "")
        satirlar.append(yeni_satir)
        satirlar.sort(key=lambda s: (s.get("Kiracı", ""), s.get("Tarih", "")))
        with open(_history_file(), "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(satirlar)

        # İZOLE KÖPRÜ: ana motorun hesaplama/rapor üretim yoluna dokunmaz.
        # Varsayılan kapalıdır ve hata halinde yalnız False döner.
        try:
            from services.supabase_sync import sync_kpi_snapshot
            from services.version import APP_VERSION
            sync_kpi_snapshot(kpi, engine_version=APP_VERSION)
        except Exception as _sync_exc:
            from services.safe_exec import log_swallowed
            log_swallowed("log_kpi_snapshot: Supabase senkronizasyonu atlandı", _sync_exc)
    except Exception as _exc:
        from services.safe_exec import log_swallowed
        log_swallowed("log_kpi_snapshot: bugünün KPI'sı geçmiş dosyasına kaydedilemedi", _exc)


def load_history(tenant_id: str | None = None) -> list[dict]:
    """ÇAĞIRANIN kiracısına ait geçmişi (eskiden yeniye sıralı) döndürür —
    başka kiracıların satırları asla dönmez. Dosya yoksa boş liste döner."""
    if not _history_file().is_file():
        return []
    try:
        kiraci = (tenant_id or _varsayilan_kiraci()).strip().upper()
        with open(_history_file(), "r", encoding="utf-8", newline="") as f:
            satirlar = list(csv.DictReader(f))
        return [s for s in satirlar if (s.get("Kiracı") or "OMEHR") == kiraci]
    except Exception as _exc:
        from services.safe_exec import log_swallowed
        log_swallowed("load_history: kpi_gecmisi.csv okunamadı", _exc)
        return []


def snapshot_n_days_ago(n: int = 30, tenant_id: str | None = None) -> dict | None:
    """Yaklaşık N gün önceki (en yakın tarihli) kaydı döndürür; hiç kayıt
    yoksa veya yeterli geçmiş birikmemişse None döndürür."""
    gecmis = load_history(tenant_id=tenant_id)
    if not gecmis:
        return None
    hedef_tarih = (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d")
    uygun = [s for s in gecmis if s.get("Tarih", "") <= hedef_tarih]
    return uygun[-1] if uygun else None
