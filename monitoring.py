from __future__ import annotations

import json
import shutil
from datetime import datetime

from services.job_queue import metrics as job_metrics
from services.runtime_paths import runtime_root, tenant_code
from services.safe_exec import log_swallowed

def _root():
    return runtime_root()


def _is_kpileri_oku() -> dict:
    """logs/CURRENT_Runtime_Status.json'daki en son başarılı çalıştırmanın
    resmi KPI'larını okur (P1 — Prometheus iş metrikleri)."""
    runtime_file = _root() / "logs" / "CURRENT_Runtime_Status.json"
    if not runtime_file.is_file():
        return {}
    try:
        data = json.loads(runtime_file.read_text(encoding="utf-8"))
        return data.get("kpis") or {}
    except Exception as _exc:
        log_swallowed("services.monitoring._is_kpileri_oku: beklenmeyen hata", _exc)
        return {}


def _model_bilgisini_oku() -> dict:
    """En son çalıştırmanın (services/run_lineage.py) hangi modeli
    kullandığını, süresini ve durumunu okur (P1 — Prometheus model
    metrikleri)."""
    lineage_file = _root() / "logs" / "run_lineage" / "SON_CALISTIRMA.json"
    if not lineage_file.is_file():
        return {}
    try:
        data = json.loads(lineage_file.read_text(encoding="utf-8"))
        modeller = data.get("models") or []
        return {
            "best_model": modeller[0]["name"] if modeller else None,
            "overfitting_status": modeller[0].get("version") if modeller else None,
            "duration_seconds": data.get("duration_seconds"),
            "status": data.get("status"),
            "run_id": data.get("run_id"),
        }
    except Exception as _exc:
        log_swallowed("services.monitoring._model_bilgisini_oku: beklenmeyen hata", _exc)
        return {}


def snapshot() -> dict:
    runtime_file = _root() / "logs" / "CURRENT_Runtime_Status.json"
    runtime = json.loads(runtime_file.read_text(encoding="utf-8")) if runtime_file.exists() else {"status": "NOT_RUN"}
    disk = shutil.disk_usage(_root())
    jobs = job_metrics()
    alerts = []
    if runtime.get("status") == "FAILED":
        alerts.append({"severity": "critical", "code": "ENGINE_FAILED", "message": runtime.get("error", "Motor başarısız")})
    if jobs.get("FAILED", 0):
        alerts.append({"severity": "warning", "code": "FAILED_JOBS", "message": f"{jobs['FAILED']} görev başarısız"})
    free_ratio = disk.free / disk.total if disk.total else 0
    if free_ratio < 0.10:
        alerts.append({"severity": "critical", "code": "LOW_DISK", "message": f"Boş disk %{free_ratio*100:.1f}"})

    is_kpileri = _is_kpileri_oku()
    model_bilgisi = _model_bilgisini_oku()
    return {
        "tenant": tenant_code(),
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "runtime": runtime,
        "jobs": jobs,
        "disk": {"total": disk.total, "used": disk.used, "free": disk.free, "free_ratio": free_ratio},
        "alerts": alerts,
        "healthy": not any(item["severity"] == "critical" for item in alerts),
        "business_kpis": is_kpileri,       # P1: Norm Eksiği/Fazlası/Net İhtiyaç vb.
        "model": model_bilgisi,             # P1: en son kullanılan model + süre + durum
    }


def prometheus_text() -> str:
    data = snapshot()
    statuses = ("PENDING", "RUNNING", "SUCCESS", "FAILED")
    rows = [
        "# HELP basdas_health Application health (1 healthy, 0 unhealthy)",
        "# TYPE basdas_health gauge",
        f'basdas_health{{tenant="{data["tenant"]}"}} {1 if data["healthy"] else 0}',
        "# HELP basdas_disk_free_ratio Free disk ratio",
        "# TYPE basdas_disk_free_ratio gauge",
        f'basdas_disk_free_ratio{{tenant="{data["tenant"]}"}} {data["disk"]["free_ratio"]:.6f}',
    ]
    for status in statuses:
        rows.append(f'basdas_jobs_total{{tenant="{data["tenant"]}",status="{status}"}} {data["jobs"].get(status,0)}')
    rows.append(f'basdas_alerts_total{{tenant="{data["tenant"]}"}} {len(data["alerts"])}')

    # --- P1: İŞ METRİKLERİ (business_kpis) ---
    bk = data.get("business_kpis") or {}
    if bk:
        rows.append("# HELP basdas_norm_eksigi Şirket geneli toplam norm eksiği (kişi)")
        rows.append("# TYPE basdas_norm_eksigi gauge")
        rows.append(f'basdas_norm_eksigi{{tenant="{data["tenant"]}"}} {bk.get("Norm Eksiği", 0)}')
        rows.append("# HELP basdas_norm_fazlasi Şirket geneli toplam norm fazlası (kişi)")
        rows.append("# TYPE basdas_norm_fazlasi gauge")
        rows.append(f'basdas_norm_fazlasi{{tenant="{data["tenant"]}"}} {bk.get("Norm Fazlası", 0)}')
        rows.append("# HELP basdas_net_ihtiyac Net pozisyon farkı (fazla-eksik)")
        rows.append("# TYPE basdas_net_ihtiyac gauge")
        rows.append(f'basdas_net_ihtiyac{{tenant="{data["tenant"]}"}} {bk.get("Net İhtiyaç", 0)}')
        rows.append("# HELP basdas_aktif_mevcut Toplam aktif personel sayısı")
        rows.append("# TYPE basdas_aktif_mevcut gauge")
        rows.append(f'basdas_aktif_mevcut{{tenant="{data["tenant"]}"}} {bk.get("Aktif Mevcut", 0)}')

    # --- P1: MODEL METRİKLERİ ---
    mb = data.get("model") or {}
    if mb.get("duration_seconds") is not None:
        rows.append("# HELP basdas_last_run_duration_seconds Son çalıştırmanın süresi (saniye)")
        rows.append("# TYPE basdas_last_run_duration_seconds gauge")
        rows.append(f'basdas_last_run_duration_seconds{{tenant="{data["tenant"]}"}} {mb["duration_seconds"]}')
    if mb.get("status"):
        rows.append("# HELP basdas_last_run_status Son çalıştırma durumu (1 SUCCESS, 0 diğer)")
        rows.append("# TYPE basdas_last_run_status gauge")
        rows.append(f'basdas_last_run_status{{tenant="{data["tenant"]}",model="{mb.get("best_model","yok")}"}} {1 if mb["status"]=="SUCCESS" else 0}')

    return "\n".join(rows) + "\n"
