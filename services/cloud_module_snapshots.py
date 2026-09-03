from __future__ import annotations

"""Streamlit ekranlarının Railway'de üretilen salt-okunur veri sözleşmesi.

Bu katman hesaplama yapmaz. Resmî motorun zaten ürettiği DataFrame ve rapor
dosyalarını JSON'a uygun modül snapshot'larına çevirir. Böylece Vercel arayüzü
Streamlit ile aynı kaynağı gösterir; ikinci bir iş kuralı oluşmaz.
"""

from pathlib import Path
from typing import Any

import pandas as pd

from services.real_staffing_need import build_real_staffing_need


def _records(frame: pd.DataFrame | None, *, limit: int = 1500) -> list[dict[str, Any]]:
    if frame is None or frame.empty:
        return []
    view = frame.head(limit).copy()
    for column in view.columns:
        if pd.api.types.is_datetime64_any_dtype(view[column]):
            view[column] = view[column].dt.strftime("%Y-%m-%d")
        else:
            view[column] = view[column].map(
                lambda value: value.isoformat() if hasattr(value, "isoformat") else value
            )
    view = view.where(pd.notnull(view), None)
    return view.to_dict(orient="records")


def _sheet(sheets: dict[str, pd.DataFrame], *names: str) -> pd.DataFrame:
    for name in names:
        value = sheets.get(name)
        if isinstance(value, pd.DataFrame) and not value.empty:
            return value
    return pd.DataFrame()


def _excel_sheet(path: Path, *names: str) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame()
    for name in names:
        try:
            value = pd.read_excel(path, sheet_name=name)
            if not value.empty:
                return value
        except Exception:
            continue
    return pd.DataFrame()


def _snapshot(title: str, rows: list[dict], *, description: str = "") -> dict:
    return {"title": title, "description": description, "rows": rows}


def build_module_snapshots(
    *,
    sheets: dict[str, pd.DataFrame],
    staff: pd.DataFrame,
    store_title_detail: pd.DataFrame,
    scenarios: Any,
    output_dir: Path,
) -> dict[str, dict]:
    """Vercel'deki her bilgi ekranı için kaynak snapshot'ı oluşturur."""
    personnel_columns = [
        c for c in (
            "PersonelID", "Sicil No", "İsim Soyisim", "Mağaza", "Unvan",
            "Departman", "İşe Giriş", "İşten Çıkış", "Durum", "Açıklama",
        ) if c in staff.columns
    ]
    personnel = staff[personnel_columns].copy() if personnel_columns else pd.DataFrame()

    transfer_rows: list[dict] = []
    if isinstance(scenarios, dict):
        for scenario_name, frame in scenarios.items():
            if isinstance(frame, pd.DataFrame) and not frame.empty:
                data = frame.copy()
                # DÜZELTME: .insert(0, "Senaryo", ...) bazı senaryo
                # DataFrame'lerinde ZATEN "Senaryo" adlı bir sütun varsa
                # "cannot insert Senaryo, already exists" hatasıyla
                # çöküyordu (canlıda /api/run-engine üzerinden gözlendi).
                # Doğrudan atama, sütun var/yok fark etmeksizin güvenli:
                # varsa üzerine yazar, yoksa oluşturur.
                data["Senaryo"] = str(scenario_name)
                transfer_rows.extend(_records(data, limit=500))

    forecast_path = output_dir / "OMEHR_Magaza_Unvan_Isgucu_Tahmini.xlsx"
    ai_path = output_dir / "V19_AI_Norm_Sonuclari.xlsx"
    analytics_path = output_dir / "OMEHR_Gelismis_Analitik.xlsx"

    report_rows = []
    if output_dir.is_dir():
        for path in sorted(output_dir.rglob("*")):
            if path.is_file() and path.suffix.lower() in {".pdf", ".xlsx", ".xls"}:
                report_rows.append({
                    "Rapor": path.name,
                    "Tür": path.suffix.lstrip(".").upper(),
                    "Klasör": str(path.parent.relative_to(output_dir)),
                    "Boyut (KB)": round(path.stat().st_size / 1024, 1),
                })

    detail = store_title_detail.copy()
    detail_aliases = {
        "Norm Kadro": "Norm", "Aktif Mevcut": "Mevcut",
        "Norm Eksiği": "Eksik", "Norm Fazlası": "Fazla",
    }
    detail = detail.rename(columns={k: v for k, v in detail_aliases.items() if k in detail.columns and v not in detail.columns})

    need_rows, need_kpis = build_real_staffing_need(store_title_detail, sheets=sheets)

    return {
        "personnel": _snapshot("Personel Kartları", _records(personnel), description="Aktif ve geçmiş personel görünümü"),
        "store_title": _snapshot("Mağaza–Ünvan Detayı", _records(detail), description="Hangi mağazada hangi pozisyonda kaç kişi eksik/fazla"),
        "performance": _snapshot("Personel Performansı", _records(_sheet(sheets, "Personel_Performans_Endeksi"))),
        "forecast": _snapshot("İş Gücü Tahmini", _records(_excel_sheet(forecast_path, "Mağaza_Unvan_Tahmini"))),
        "forecast_summary": _snapshot("Tahmin Yönetici Özeti", _records(_excel_sheet(forecast_path, "Yönetici Özeti"))),
        "transfer": _snapshot("Transfer Optimizasyonu", transfer_rows),
        "ai_norm": _snapshot("AI Norm ve Operasyon Önerileri", _records(_excel_sheet(ai_path, "AI_Norm_Sonuclari"))),
        "model_comparison": _snapshot("Model Karşılaştırması", _records(_excel_sheet(analytics_path, "Model_Karsilastirma"))),
        "operations": _snapshot("Operasyon Görselleri", _records(_sheet(sheets, "Aylık Operasyon KPI", "Aylik Operasyon KPI"))),
        "daily_operations": _snapshot("Günlük Operasyon", _records(_sheet(sheets, "Günlük Operasyon", "Gunluk Operasyon"))),
        "hourly_density": _snapshot("Saatlik Yoğunluk", _records(_sheet(sheets, "Saatlik Yoğunluk", "Saatlik Yogunluk"))),
        "register_usage": _snapshot("Kasa Kullanımı", _records(_sheet(sheets, "Kasa Kullanımı", "Kasa Kullanimi"))),
        "online_orders": _snapshot("Online Sipariş", _records(_sheet(sheets, "Online Sipariş", "Online Siparis"))),
        "goods_receipt": _snapshot("Mal Kabul", _records(_sheet(sheets, "Mal Kabul"))),
        "waste_returns": _snapshot("Fire ve İade", _records(_sheet(sheets, "Fire ve İade", "Fire ve Iade"))),
        "productivity": _snapshot("Verimlilik Görselleri", _records(_sheet(sheets, "İş Yükü Endeksi", "Is Yuku Endeksi"))),
        "overtime": _snapshot("Fazla Mesai", _records(_sheet(sheets, "Fazla Mesai"))),
        "absence": _snapshot("Devamsızlık", _records(_sheet(sheets, "Devamsızlık"))),
        "store_performance": _snapshot("Mağaza Performansı", _records(_sheet(sheets, "Performans"))),
        "real_staffing_need": {
            **_snapshot(
                "Gerçek Personel İhtiyacı",
                _records(need_rows),
                description="Norm açığını transfer, geçici açık, norm incelemesi ve gerçek işe alım ihtiyacına ayıran açıklanabilir karar desteği",
            ),
            "kpis": need_kpis,
        },
        "reports": _snapshot("Rapor Merkezi", report_rows),
    }
