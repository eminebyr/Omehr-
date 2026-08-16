from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from services.runtime_paths import runtime_root

def _output():
    return runtime_root() / "output"


def _logs():
    return runtime_root() / "logs"


def _resolve_excel(result: dict) -> Path:
    candidates = []
    if isinstance(result, dict) and result.get("excel"):
        candidates.append(Path(result["excel"]))
    candidates += [
        _output() / "BASDAS_Executive_Data.xlsx",
        _output() / "V19_Executive_Data.xlsx",
        _output() / "BASDAS_Executive_Data.xlsx",
    ]
    candidates += sorted(_output().glob("*_Executive_Data.xlsx"), key=lambda x: x.stat().st_mtime if x.exists() else 0, reverse=True)
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError("Yönetici Excel raporu üretilemedi; output klasöründe *_Executive_Data.xlsx bulunamadı.")


def validate_report_schema(result: dict) -> dict:
    """Üretilen gerçek raporu doğrular; eski OMEHR adına sabitlenmez.

    Bazı üretim sürümlerinde ayrıntı sayfa adları/sütunları farklı olabilir.
    Kritik dosyanın açılabilirliği ve temel sayfalar doğrulanır; sürüme özgü
    ayrıntılar varsa ayrıca kontrol edilir, yoksa rapor motoru gereksiz yere
    durdurulmaz.
    """
    path = _resolve_excel(result)
    book = pd.ExcelFile(path)
    names = set(book.sheet_names)
    if not names:
        raise RuntimeError("Yönetici Excel raporunda hiç sayfa yok.")

    preferred = next((n for n in ("Mağaza-Unvan Bazlı", "Magaza-Unvan Bazli", "Genel Özet", "Genel_Ozet") if n in names), book.sheet_names[0])
    frame = pd.read_excel(path, sheet_name=preferred)
    if frame.empty:
        raise RuntimeError(f"Yönetici Excel raporundaki '{preferred}' sayfası boş.")

    checks = {"status": "SUCCESS", "file": str(path), "sheet_count": len(book.sheet_names), "validated_sheet": preferred}
    # Ayrıntılı eski sözleşme yalnız ilgili sayfalar gerçekten varsa uygulanır.
    if {"Mağaza-Unvan Bazlı", "Norm Eksikleri", "Norm Fazlaları"}.issubset(names):
        title = pd.read_excel(path, sheet_name="Mağaza-Unvan Bazlı")
        deficit = pd.read_excel(path, sheet_name="Norm Eksikleri")
        surplus = pd.read_excel(path, sheet_name="Norm Fazlaları")
        expected_people = int((result.get("kpis") or {}).get("Aktif Mevcut", 0))
        if expected_people and "Personel Adı Soyadı" in title.columns:
            actual = int(title["Personel Adı Soyadı"].notna().sum())
            if actual != expected_people:
                raise RuntimeError(f"Mağaza-Unvan sayfasında {expected_people} yerine {actual} personel adı bulundu.")
        if "Personel Adı Soyadı" in deficit.columns:
            raise RuntimeError("Norm Eksikleri sayfasında personel adı olmamalıdır.")
        checks["detailed_schema"] = True
        checks["surplus_rows"] = int(len(surplus))
    else:
        checks["detailed_schema"] = False
    return checks


def write_audit(payload: dict) -> None:
    _output().mkdir(exist_ok=True)
    _logs().mkdir(exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    for target in (_logs() / "CURRENT_Run_Audit.json", _output() / "CURRENT_latest.json"):
        temp = target.with_suffix(target.suffix + ".tmp")
        temp.write_text(text, encoding="utf-8")
        os.replace(temp, target)
