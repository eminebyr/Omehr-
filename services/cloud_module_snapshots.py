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


def _normalize_embedded_headers(frame: pd.DataFrame | None) -> pd.DataFrame:
    """Promote a report's embedded header row when pandas produced Unnamed columns."""
    if frame is None or frame.empty:
        return pd.DataFrame() if frame is None else frame

    columns = [str(column).strip() for column in frame.columns]
    unnamed = sum(column.casefold().startswith("unnamed:") for column in columns)
    if unnamed < max(2, len(columns) // 2):
        return frame

    first_row = frame.iloc[0]
    labels = [
        "" if pd.isna(value) else str(value).strip()
        for value in first_row.tolist()
    ]
    meaningful = [label for label in labels if label and label.casefold() != "nan"]
    header_terms = ("isim", "personel", "mağaza", "magaza", "unvan", "puan", "tarih", "norm", "sınıf", "sinif")
    if len(meaningful) < 2 or not any(
        any(term in label.casefold() for term in header_terms) for label in meaningful
    ):
        return frame

    view = frame.iloc[1:].copy().reset_index(drop=True)
    promoted: list[str] = []
    counts: dict[str, int] = {}
    for index, label in enumerate(labels):
        base = label if label and label.casefold() != "nan" else columns[index]
        if base.casefold().startswith("unnamed:"):
            base = f"Kolon {index + 1}"
        counts[base] = counts.get(base, 0) + 1
        promoted.append(base if counts[base] == 1 else f"{base} ({counts[base]})")
    view.columns = promoted

    removable = [
        column for column in view.columns
        if column.startswith("Kolon ") and view[column].isna().all()
    ]
    return view.drop(columns=removable)


def _records(frame: pd.DataFrame | None, *, limit: int = 1500) -> list[dict[str, Any]]:
    if frame is None or frame.empty:
        return []
    view = _normalize_embedded_headers(frame).head(limit).copy()
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


def _snapshot(
    title: str,
    rows: list[dict],
    *,
    description: str = "",
    source: str = "",
    empty_message: str = "Kaynak veri henüz oluşmadı.",
    status: str | None = None,
) -> dict:
    resolved_status = status or ("READY" if rows else "SOURCE_MISSING")
    return {
        "title": title,
        "description": description,
        "rows": rows,
        "status": resolved_status,
        "status_message": "" if rows and resolved_status == "READY" else empty_message,
        "source": source,
    }


def _forecast_frames(sheets: dict[str, pd.DataFrame], output_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """Hafif tahmin motorunu güncel sheet sözlüğünden her çalıştırmada üretir."""
    path = output_dir / "OMEHR_Magaza_Unvan_Isgucu_Tahmini.xlsx"
    detail = pd.DataFrame()
    summary = pd.DataFrame()
    try:
        from services.workforce_forecast import run as run_workforce_forecast

        output_dir.mkdir(parents=True, exist_ok=True)
        outcome = run_workforce_forecast(sheets, output_dir)
        if outcome.get("status") == "SUCCESS":
            detail = _excel_sheet(path, "Mağaza_Unvan_Tahmini")
            summary = _excel_sheet(path, "Yönetici Özeti")
        if not detail.empty or not summary.empty:
            return detail, summary, ""
        reason = str(outcome.get("reason") or "Tahmin motoru veri üretemedi")
        missing = outcome.get("missing") or []
        if missing:
            reason += ": " + ", ".join(map(str, missing))
        return detail, summary, reason
    except Exception as exc:
        return detail, summary, f"Tahmin motoru çalıştırılamadı: {type(exc).__name__}"


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

    ai_path = output_dir / "V19_AI_Norm_Sonuclari.xlsx"
    analytics_path = output_dir / "V19_Istatistik_ML_Operasyon_Analizi.xlsx"

    forecast_detail, forecast_summary, forecast_message = _forecast_frames(sheets, output_dir)
    ai_frame = _excel_sheet(ai_path, "AI_Norm_Sonuclari")
    ai_status = "READY"
    ai_message = ""
    if ai_frame.empty and not store_title_detail.empty:
        try:
            from src.ai_norm import ai_norm_table

            ai_frame = ai_norm_table(sheets, store_title_detail, scenarios)
            if (
                "Veri Durumu" in ai_frame.columns
                and ai_frame["Veri Durumu"].astype(str).str.contains("AI kaydı yok", case=False).all()
            ):
                ai_status = "REFERENCE_ONLY"
                ai_message = "AI eğitim çıktısı henüz yok; güncel resmî norm güvenli referans olarak gösteriliyor."
        except Exception as exc:
            ai_status = "ENGINE_ERROR"
            ai_message = f"AI norm görünümü üretilemedi: {type(exc).__name__}"

    model_frame = _excel_sheet(analytics_path, "Model_Karsilastirma")

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
        "personnel": _snapshot("Personel Kartları", _records(personnel), description="Aktif ve geçmiş personel görünümü", source="Fact_Mevcut", empty_message="Fact_Mevcut içinde gösterilebilir personel kaydı bulunamadı."),
        "store_title": _snapshot("Mağaza–Ünvan Detayı", _records(detail), description="Hangi mağazada hangi pozisyonda kaç kişi eksik/fazla", source="Fact_Norm + Fact_Mevcut", empty_message="Mağaza–ünvan norm/mevcut detayı üretilemedi."),
        "performance": _snapshot("Personel Performansı", _records(_sheet(sheets, "Personel_Performans_Endeksi")), source="Personel_Performans_Endeksi", empty_message="Personel_Performans_Endeksi sayfasında veri bulunamadı."),
        "forecast": _snapshot("İş Gücü Tahmini", _records(forecast_detail), source="İş gücü tahmin motoru", empty_message=forecast_message or "İş gücü tahmini henüz oluşmadı."),
        "forecast_summary": _snapshot("Tahmin Yönetici Özeti", _records(forecast_summary), source="İş gücü tahmin motoru", empty_message=forecast_message or "Tahmin yönetici özeti henüz oluşmadı."),
        "transfer": _snapshot("Transfer Optimizasyonu", transfer_rows),
        "ai_norm": _snapshot("AI Norm ve Operasyon Önerileri", _records(ai_frame), source="AI norm motoru", empty_message=ai_message or "AI norm motoru henüz sonuç üretmedi.", status=ai_status if not ai_frame.empty or ai_status == "ENGINE_ERROR" else None),
        "model_comparison": _snapshot("Model Karşılaştırması", _records(model_frame), source="V19_Istatistik_ML_Operasyon_Analizi.xlsx / Model_Karsilastirma", empty_message="Model karşılaştırma raporu henüz üretilmedi veya eğitim için yeterli tarihsel veri yok."),
        "operations": _snapshot("Operasyon Görselleri", _records(_sheet(sheets, "Aylık Operasyon KPI", "Aylik Operasyon KPI")), source="Aylık Operasyon KPI", empty_message="Aylık Operasyon KPI sayfasında veri bulunamadı."),
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
        "sales_targets": _snapshot("Satış Hedefleri", _records(_sheet(sheets, "Satış Hedefi", "Satis Hedefi")), source="Satış Hedefi", empty_message="Satış Hedefi sayfası henüz doldurulmadı."),
        "inflation": _snapshot("Enflasyon", _records(_sheet(sheets, "Enflasyon")), source="Enflasyon", empty_message="Enflasyon sayfası henüz doldurulmadı."),
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
