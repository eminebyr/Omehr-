"""MONITORING SERVER — 127.0.0.1:9108 üzerinde çalışan, sistemin canlılığını
ve son çalıştırma durumunu gösteren minimal bir FastAPI servisi.

Çalıştırma: uvicorn monitoring_server:app --host 127.0.0.1 --port 9108
(BASDAS_CURRENT_BASLAT.bat/.sh ve docker-compose.production.yml tarafından
bu şekilde çağrılır.)

Kapsam BİLEREK küçük tutuldu: bu bir tam APM/metrik toplama sistemi değil,
"servis ayakta mı, en son main.py ne zaman/nasıl çalıştı, kaç yutulan hata
var" sorularına hızlı, bağımlılıksız bir cevap veren bir sağlık ucu.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI

app = FastAPI(title="OMEHR Monitoring", version="19.21.2")


@app.get("/health")
def health():
    """Servisin ayakta olduğunu ve kritik dosya yollarının erişilebilir
    olduğunu doğrulayan basit bir uç nokta."""
    from services.runtime_paths import runtime_root

    root = runtime_root()
    return {
        "status": "ok",
        "runtime_root": str(root),
        "input_dir_exists": (root / "input").is_dir(),
        "output_dir_exists": (root / "output").is_dir(),
    }


@app.get("/status")
def status():
    """En son çalışma zamanı durumunu (services.observability.write_runtime_status
    tarafından yazılan CURRENT_Runtime_Status.json) döndürür."""
    import json
    from services.runtime_paths import runtime_root

    path = runtime_root() / "logs" / "CURRENT_Runtime_Status.json"
    if not path.is_file():
        return {"status": "unknown", "reason": "Henüz bir durum kaydı yok."}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "error", "reason": f"{type(exc).__name__}: {exc}"}


@app.get("/recent-errors")
def recent_errors(n: int = 20):
    """services.safe_exec.recent_swallowed_errors() üzerinden son 'yutulan
    hata' kayıtlarını döndürür — bkz. Bölüm 16 (denetim/gözlemlenebilirlik)."""
    from services.safe_exec import recent_swallowed_errors

    return {"errors": recent_swallowed_errors(n)}
