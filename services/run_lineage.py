from __future__ import annotations

"""
RUN LINEAGE VE MANIFEST (P1 — reviewer önerisi)
====================================================
"Raporun hangi veriyle ve hangi kodla üretildiği tam olarak izlenemiyor"
sorununu çözer. Her main.py çalıştırmasında şunlar kaydedilir:

    - çalıştırma kimliği (run_id)
    - input dosyası SHA-256
    - kullanılan sayfalar ve satır sayıları
    - model adı ve model versiyonu
    - feature listesi
    - alias/config dosyalarının hash'i
    - Python ve scikit-learn sürümü
    - uygulama sürümü / Git commit (varsa)
    - başlangıç ve bitiş zamanı
    - durum (SUCCESS/FAILED)

Sonuç, logs/run_lineage/{run_id}.json dosyasına yazılır — böylece "bu rapor
hangi veriyle üretildi?" sorusuna her zaman kesin bir cevap verilebilir.
"""

import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from services.runtime_paths import runtime_root
from services.version import APP_VERSION
from services.safe_exec import log_swallowed

def _lineage_dir():
    return runtime_root() / "logs" / "run_lineage"


APPLICATION_VERSION = APP_VERSION  # geriye dönük uyumluluk için aynı isimle de erişilebilir


def _sha256_dosya(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for parca in iter(lambda: f.read(1 << 20), b""):
            h.update(parca)
    return h.hexdigest()


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=runtime_root(),
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() or None
    except Exception as _exc:
        log_swallowed("services.run_lineage._git_commit: beklenmeyen hata", _exc)
        return None


def _paket_surumu(paket: str) -> str | None:
    try:
        import importlib
        return getattr(importlib.import_module(paket), "__version__", None)
    except Exception as _exc:
        log_swallowed("services.run_lineage._paket_surumu: beklenmeyen hata", _exc)
        return None


def yeni_run_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_") + hashlib.sha256(str(datetime.now()).encode()).hexdigest()[:6]


def baslat(input_path: Path) -> dict:
    """Bir çalıştırmanın BAŞINDA çağrılır; run_id ve temel bilgileri içeren
    bir lineage kaydı oluşturur (henüz SÜREN durumda)."""
    _lineage_dir().mkdir(parents=True, exist_ok=True)
    kayit = {
        "run_id": yeni_run_id(),
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "application_version": APPLICATION_VERSION,
        "git_commit": _git_commit(),
        "python_version": sys.version.split()[0],
        "package_versions": {
            "pandas": _paket_surumu("pandas"),
            "numpy": _paket_surumu("numpy"),
            "scikit-learn": _paket_surumu("sklearn"),
            "openpyxl": _paket_surumu("openpyxl"),
        },
        "input_file": str(input_path),
        "input_sha256": _sha256_dosya(Path(input_path)),
        "config_hashes": {
            adi: _sha256_dosya(runtime_root() / adi)
            for adi in ("config_features.json", "config_magaza_yoneticileri.json")
            if (runtime_root() / adi).is_file()
        },
        "status": "RUNNING",
    }
    return kayit


def sayfa_ozetini_ekle(kayit: dict, sheets: dict) -> None:
    """Kullanılan sayfalar ve satır sayılarını lineage kaydına ekler."""
    kayit["input_sheets"] = {
        ad: int(len(df)) for ad, df in (sheets or {}).items() if hasattr(df, "__len__")
    }


def model_bilgisini_ekle(kayit: dict, model_adi: str, model_versiyonu: str = "", feature_listesi: list | None = None) -> None:
    """Kullanılan modelin adı/versiyonu/feature listesini kaydeder."""
    kayit.setdefault("models", []).append({
        "name": model_adi,
        "version": model_versiyonu,
        "features": list(feature_listesi or []),
    })


def bitir(kayit: dict, status: str, kpis: dict | None = None, hata: str | None = None) -> Path:
    """Çalıştırmanın SONUNDA çağrılır; durumu günceller ve manifest'i
    logs/run_lineage/{run_id}.json dosyasına kalıcı olarak yazar."""
    kayit["finished_at"] = datetime.now().isoformat(timespec="seconds")
    kayit["status"] = status
    if kpis is not None:
        kayit["kpis"] = kpis
    if hata:
        kayit["error"] = hata
    try:
        baslangic = datetime.fromisoformat(kayit["started_at"])
        bitis = datetime.fromisoformat(kayit["finished_at"])
        kayit["duration_seconds"] = round((bitis - baslangic).total_seconds(), 2)
    except Exception as _exc:
        log_swallowed("services.run_lineage.bitir: beklenmeyen hata", _exc)
        pass

    _lineage_dir().mkdir(parents=True, exist_ok=True)
    hedef = _lineage_dir() / f"{kayit['run_id']}.json"
    hedef.write_text(json.dumps(kayit, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    # En son çalıştırmaya işaret eden, kolay erişilebilir bir kısayol da tutulur.
    (_lineage_dir() / "SON_CALISTIRMA.json").write_text(
        json.dumps(kayit, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return hedef


def son_calistirmalar(n: int = 20) -> list[dict]:
    """Denetim/gözlemlenebilirlik için en son N çalıştırmanın lineage
    kayıtlarını (en yeniden en eskiye) döndürür."""
    if not _lineage_dir().is_dir():
        return []
    dosyalar = sorted(
        (p for p in _lineage_dir().glob("*.json") if p.name != "SON_CALISTIRMA.json"),
        key=lambda p: p.stat().st_mtime, reverse=True,
    )
    sonuc = []
    for p in dosyalar[:n]:
        try:
            sonuc.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception as _exc:
            log_swallowed("services.run_lineage.son_calistirmalar: beklenmeyen hata", _exc)
            continue
    return sonuc
