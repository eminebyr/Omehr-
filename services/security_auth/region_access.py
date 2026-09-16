from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Iterable

import pandas as pd
from services.runtime_paths import runtime_root
from services.safe_exec import log_swallowed

def _output_dir():
    from services.runtime_paths import runtime_root
    return runtime_root() / "output"


def _region_dir():
    return _output_dir() / "Bolge_Raporlari"


def safe_text(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception as _exc:
        log_swallowed("services.region_access.safe_text: beklenmeyen hata", _exc)
        pass
    return str(value).strip()


def yes(value: object) -> bool:
    return safe_text(value).casefold() in {"evet", "e", "yes", "1", "true", "aktif"}


def slug(value: object) -> str:
    text = safe_text(value).casefold().replace("ı", "i")
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", text)


def load_contacts(input_file: Path) -> pd.DataFrame:
    if not input_file.is_file():
        return pd.DataFrame()
    try:
        df = pd.read_excel(input_file, sheet_name="Mail_Listesi")
    except Exception as _exc:
        from services.safe_exec import log_swallowed
        log_swallowed(f"load_contacts: '{input_file}' içindeki Mail_Listesi okunamadı", _exc, level="ERROR")
        return pd.DataFrame()
    df.columns = [safe_text(c) for c in df.columns]
    return df


def _existing(paths: Iterable[Path]) -> list[Path]:
    unique: dict[str, Path] = {}
    for p in paths:
        p = Path(p).resolve()
        if p.is_file() and p.stat().st_size > 0:
            unique[str(p).casefold()] = p
    return list(unique.values())


def region_report_paths(region: str, add_pdf: bool = True, add_excel: bool = True) -> list[Path]:
    wanted = slug(region)
    if not wanted or wanted in {"tumu", "tum", "all", "test", "genel"}:
        paths=[]
        if add_pdf: paths.append(_output_dir() / "OMEHR_Yonetici_Raporu.pdf")
        if add_excel: paths.append(_output_dir() / "OMEHR_Executive_Data.xlsx")
        return _existing(paths)

    paths=[]
    if _region_dir().is_dir():
        for p in sorted(_region_dir().iterdir()):
            if not p.is_file() or wanted not in slug(p.stem):
                continue
            if p.suffix.lower()=='.pdf' and add_pdf: paths.append(p)
            elif p.suffix.lower()=='.xlsx' and add_excel: paths.append(p)
    return _existing(paths)


def is_global_scope(region: object, send_type: object = "") -> bool:
    return slug(region) in {"tumu","tum","all","test","genel"} or slug(send_type) in {"tumu","tum","all","test","genel"}
