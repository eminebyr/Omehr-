from __future__ import annotations

"""İsteğe bağlı Railway -> Supabase sonuç senkronizasyonu.

Bu modül ana motor hesaplarını değiştirmez. Yalnızca başarılı bir motor
çalıştırmasının sonunda oluşmuş KPI özetini Supabase'e yazar.

Güvenlik davranışı:
- Varsayılan olarak KAPALIDIR (OMEHR_SUPABASE_SYNC=1 olmadıkça hiçbir şey yapmaz).
- Secret key yalnız ortam değişkeninden okunur; kaynak koda yazılmaz.
- Ağ/Supabase hataları çağıran tarafa istisna fırlatmaz; False döner.
"""

import json
import os
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _enabled() -> bool:
    return os.getenv("OMEHR_SUPABASE_SYNC", "0").strip().lower() in {"1", "true", "yes", "on"}


def _clean_url(value: str) -> str:
    return value.strip().rstrip("/")


def sync_kpi_snapshot(kpis: dict, *, engine_version: str = "") -> bool:
    """Başarılı motor KPI'larını Supabase'e ekler.

    Yeni `sb_secret_...` anahtarları JWT değildir; Supabase'in güncel önerisine
    uygun olarak yalnız `apikey` başlığında gönderilir.
    """
    if not _enabled():
        return False

    base_url = _clean_url(os.getenv("OMEHR_SUPABASE_URL", ""))
    secret_key = os.getenv("OMEHR_SUPABASE_SECRET_KEY", "").strip()
    if not base_url or not secret_key:
        return False

    payload = {
        "tenant_id": os.getenv("OMEHR_TENANT_ID", "basdas").strip() or "basdas",
        "active_current": int(kpis.get("Aktif Mevcut", 0) or 0),
        "total_norm": int(kpis.get("Toplam Norm", 0) or 0),
        "norm_deficit": int(kpis.get("Norm Eksiği", 0) or 0),
        "norm_surplus": int(kpis.get("Norm Fazlası", 0) or 0),
        "net_need": int(kpis.get("Net İhtiyaç", 0) or 0),
        "engine_version": engine_version or None,
        "calculated_at": datetime.now(timezone.utc).isoformat(),
    }

    request = Request(
        f"{base_url}/rest/v1/omehr_kpi_snapshot",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "apikey": secret_key,
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
            "User-Agent": "OMEHR-Railway-Sync/1.0",
        },
    )

    try:
        with urlopen(request, timeout=8) as response:
            return 200 <= int(getattr(response, "status", 0)) < 300
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return False
