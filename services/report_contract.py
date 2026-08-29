from __future__ import annotations

"""Yönetici rapor setinin dosya-adı düzeyindeki zorunlu sözleşmesi."""

from pathlib import Path
from typing import Iterable, Mapping

import pandas as pd


BASE_REPORTS = (
    "OMEHR_AI_Karar_Analizi.pdf",
    "OMEHR_Admin_Maliyet_ve_Operasyon.xlsx",
    "OMEHR_Admin_Norm_ve_Aksiyonlar.xlsx",
    "OMEHR_Admin_Yonetici_Ozeti.pdf",
    "OMEHR_Executive_Data.xlsx",
    "OMEHR_Kutucuklu_Yonetici_Raporu.xlsx",
    "OMEHR_Magaza_Unvan_Isgucu_Tahmini.xlsx",
    "OMEHR_Maliyet_Analizi.pdf",
    "OMEHR_Operasyon_Verimlilik_Analizi.pdf",
    "OMEHR_Veri_Kalitesi_Raporu.xlsx",
    "OMEHR_Yonetici_Raporu.pdf",
    "OMEHR_Yonetici_Raporu.xlsx",
    "V19_AI_Norm_Sonuclari.xlsx",
    "V19_Istatistik_ML_Operasyon_Analizi.xlsx",
)


def safe_region_name(region: object) -> str:
    return "".join(c if c.isalnum() else "_" for c in str(region)).strip("_")


def regions_from_sheets(sheets: Mapping[str, pd.DataFrame]) -> list[str]:
    regions: set[str] = set()
    used_store_ids: set[str] = set()
    for sheet_name in ("Fact_Norm", "Fact_Mevcut"):
        frame = sheets.get(sheet_name, pd.DataFrame())
        if "MağazaID" in frame:
            used_store_ids.update(frame["MağazaID"].dropna().astype(str).str.strip())
        for column in ("Bölge Sorumlusu", "Bolge Sorumlusu", "Bölge"):
            if column in frame:
                regions.update(v.strip() for v in frame[column].dropna().astype(str) if v.strip())

    stores = sheets.get("Dim_Magaza", pd.DataFrame())
    if "MağazaID" in stores:
        stores = stores[stores["MağazaID"].astype(str).str.strip().isin(used_store_ids)]
    for column in ("Bölge Sorumlusu", "Bolge Sorumlusu", "Bölge"):
        if column in stores:
            regions.update(v.strip() for v in stores[column].dropna().astype(str) if v.strip())
    return sorted(regions)


def required_report_paths(regions: Iterable[str]) -> tuple[Path, ...]:
    paths = [Path(name) for name in BASE_REPORTS]
    for region in sorted(set(regions)):
        safe = safe_region_name(region)
        paths.extend(
            (
                Path("Bolge_Raporlari") / f"OMEHR_Bolge_{safe}.pdf",
                Path("Bolge_Raporlari") / f"OMEHR_Bolge_{safe}.xlsx",
                Path("Bolge_Raporlari") / f"OMEHR_Bolge_{safe}_Sade.pdf",
            )
        )
    return tuple(paths)


def validate_report_set(output: Path, sheets: Mapping[str, pd.DataFrame]) -> dict:
    regions = regions_from_sheets(sheets)
    required = required_report_paths(regions)
    missing = [str(path) for path in required if not (output / path).is_file()]
    return {
        "status": "SUCCESS" if not missing else "FAILED",
        "expected": len(required),
        "present": len(required) - len(missing),
        "regions": regions,
        "missing": missing,
    }


def validate_current_report_set(output: Path) -> dict:
    from common_veri_okuma import read_all

    return validate_report_set(output, read_all())
