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


def _tenant_id() -> str:
    """Supabase RLS sözleşmesindeki kiracıyı çalışma zamanı adından ayırır."""
    return os.getenv("OMEHR_SUPABASE_TENANT_ID", "OMEHR_MAIN").strip() or "OMEHR_MAIN"


def _connection() -> tuple[str, str] | None:
    if not _enabled():
        return None
    base_url = _clean_url(os.getenv("OMEHR_SUPABASE_URL", ""))
    secret_key = os.getenv("OMEHR_SUPABASE_SECRET_KEY", "").strip()
    if not base_url or not secret_key:
        return None
    return base_url, secret_key


def _post_rows(table: str, payload: dict | list[dict], *, upsert: bool = False) -> bool:
    connection = _connection()
    if connection is None:
        return False
    base_url, secret_key = connection
    prefer = "return=minimal"
    suffix = ""
    if upsert:
        prefer = "resolution=merge-duplicates,return=minimal"
        conflicts = {
            "omehr_store_summary": "tenant_id,store_name",
            "omehr_title_summary": "tenant_id,title_name",
            "omehr_module_snapshots": "tenant_id,module_key",
        }
        conflict = conflicts.get(table, "tenant_id")
        suffix = f"?on_conflict={conflict}"
    request = Request(
        f"{base_url}/rest/v1/{table}{suffix}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "apikey": secret_key,
            "Content-Type": "application/json",
            "Prefer": prefer,
            "User-Agent": "OMEHR-Railway-Sync/1.0",
        },
    )
    try:
        with urlopen(request, timeout=12) as response:
            return 200 <= int(getattr(response, "status", 0)) < 300
    except HTTPError as exc:
        # DÜZELTME (görünürlük): bu hata daha önce TAMAMEN sessiz
        # yutuluyordu — örn. Supabase'de ilgili tablo/migration henüz
        # uygulanmamışsa (404) veya RLS politikası reddederse (401/403),
        # webhook_server.py yine de 200 dönüyordu ve hiçbir log basılmıyordu.
        # Artık en azından Railway loglarında görünür.
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            detail = ""
        print(
            f"[supabase_sync] '{table}' tablosuna yazma başarısız: "
            f"HTTP {exc.code} {exc.reason} — {detail}",
            flush=True,
        )
        return False
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        print(f"[supabase_sync] '{table}' tablosuna yazma başarısız: {exc}", flush=True)
        return False


def fetch_sales_targets() -> list[dict]:
    """Streamlit için aynı kiracının satış hedeflerini salt okunur getirir."""
    connection = _connection()
    if connection is None:
        return []
    base_url, secret_key = connection
    tenant = _tenant_id()
    request = Request(
        f"{base_url}/rest/v1/omehr_sales_targets?tenant_id=eq.{tenant}&select=period,store_id,store_name,sales_target,explanation,action_plan,owner_name,updated_at",
        method="GET",
        headers={"apikey": secret_key, "User-Agent": "OMEHR-Railway-Sync/1.0"},
    )
    try:
        with urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return payload if isinstance(payload, list) else []
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        return []


def sync_kpi_snapshot(kpis: dict, *, engine_version: str = "") -> bool:
    """Başarılı motor KPI'larını Supabase'e ekler.

    Yeni `sb_secret_...` anahtarları JWT değildir; Supabase'in güncel önerisine
    uygun olarak yalnız `apikey` başlığında gönderilir.
    """
    payload = {
        "tenant_id": _tenant_id(),
        "active_current": int(kpis.get("Aktif Mevcut", 0) or 0),
        "total_norm": int(kpis.get("Toplam Norm", 0) or 0),
        "norm_deficit": int(kpis.get("Norm Eksiği", 0) or 0),
        "norm_surplus": int(kpis.get("Norm Fazlası", 0) or 0),
        "net_need": int(kpis.get("Net İhtiyaç", 0) or 0),
        "engine_version": engine_version or None,
        "calculated_at": datetime.now(timezone.utc).isoformat(),
    }

    return _post_rows("omehr_kpi_snapshot", payload)


def sync_dashboard_summaries(summary: dict) -> dict[str, bool]:
    """Başarılı motor çalışmasından mağaza ve ünvan özetlerini kalıcılaştırır."""
    tenant_id = _tenant_id()
    calculated_at = datetime.now(timezone.utc).isoformat()
    stores = [
        {
            "tenant_id": tenant_id,
            "region_name": str(row.get("bolge_sorumlusu") or ""),
            "store_id": str(row.get("magaza") or ""),
            "store_name": str(row.get("magaza") or ""),
            "active_current": int(row.get("mevcut") or 0),
            "total_norm": int(row.get("norm") or 0),
            "norm_deficit": int(row.get("eksik") or 0),
            "norm_surplus": int(row.get("fazla") or 0),
            "calculated_at": calculated_at,
        }
        for row in summary.get("magaza_bazli", [])
        if row.get("magaza")
    ]
    titles = [
        {
            "tenant_id": tenant_id,
            "title_name": str(row.get("unvan") or ""),
            "active_current": int(row.get("mevcut") or 0),
            "total_norm": int(row.get("norm") or 0),
            "norm_deficit": int(row.get("eksik") or 0),
            "norm_surplus": int(row.get("fazla") or 0),
            "calculated_at": calculated_at,
        }
        for row in summary.get("unvan_bazli", [])
        if row.get("unvan")
    ]
    modules = [
        {
            "tenant_id": tenant_id,
            "module_key": str(key),
            "payload": value,
            "calculated_at": calculated_at,
        }
        for key, value in (summary.get("modules") or {}).items()
    ]
    return {
        "stores": bool(stores) and _post_rows("omehr_store_summary", stores, upsert=True),
        "titles": bool(titles) and _post_rows("omehr_title_summary", titles, upsert=True),
        "modules": bool(modules) and _post_rows("omehr_module_snapshots", modules, upsert=True),
    }