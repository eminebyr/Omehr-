from __future__ import annotations

import json
import logging
import os
import platform
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from services.runtime_paths import runtime_root

def _log_dir():
    from services.runtime_paths import runtime_root
    return runtime_root() / "logs"


def get_logger(name: str = "basdas") -> logging.Logger:
    _log_dir().mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(os.getenv("OMEHR_LOG_LEVEL", "INFO").upper())
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler = RotatingFileHandler(
        _log_dir() / "BASDAS_CURRENT.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(formatter)
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(handler)
    logger.addHandler(console)
    logger.propagate = False
    return logger


def write_runtime_status(status: str, **details) -> Path:
    _log_dir().mkdir(parents=True, exist_ok=True)
    target = _log_dir() / "CURRENT_Runtime_Status.json"
    temp = target.with_suffix(".json.tmp")
    payload = {
        "status": status,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "platform": platform.platform(),
        "pid": os.getpid(),
        **details,
    }
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(temp, target)
    return target
