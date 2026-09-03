from __future__ import annotations

"""Açıklanabilir gerçek personel ihtiyacı karar katmanı.

Resmî normu değiştirmez. Mağaza-unvan norm açığını transfer, geçici kapasite,
norm incelemesi, işe alım ve veri açığı sınıflarına ayıran karar desteği üretir.
Yetersiz tarihçe bulunduğunda kesin işe alım veya norm revizyonu yayımlamaz.
"""

from collections import defaultdict
from typing import Any

import pandas as pd


MIN_DAILY_OBSERVATIONS = 30
MIN_MONTHLY_PERIODS = 3


def _number(value: Any) -> float | None:
    try:
        result = float(value)
        return result if pd.notna(result) else None
    except (TypeError, ValueError):
        return None


def _sheet(sheets: dict[str, pd.DataFrame], *names: str) -> pd.DataFrame:
    for name in names:
        frame = sheets.get(name)
        if isinstance(frame, pd.DataFrame) and not frame.empty:
            return frame.copy()
    return pd.DataFrame()


def _store_key(row: pd.Series | dict) -> str:
    for name in ("MağazaID", "MagazaID", "Mağaza", "Magaza"):
        value = row.get(name)
        if pd.notna(value) and str(value).strip():
            return str(value).strip()
    return ""


def _title(row: pd.Series | dict) -> str:
    return str(row.get("Unvan") or row.get("Ünvan") or "").strip()


def _latest_by_store(frame: pd.DataFrame) -> dict[str, pd.Series]:
    if frame.empty:
        return {}
    return {_store_key(row): row for _, row in frame.iterrows() if _store_key(row)}


def _metric(row: pd.Series | None, *names: str) -> float | None:
    if row is None:
        return None
    for name in names:
        if name in row.index:
            value = _number(row.get(name))
            if value is not None:
                return value
    return None


def _history_coverage(sheets: dict[str, pd.DataFrame], store: str) -> tuple[int, int]:
    daily = _sheet(sheets, "Günlük Operasyon", "Gunluk Operasyon")
    monthly = _sheet(sheets, "Aylık Operasyon KPI", "Aylik Operasyon KPI")

    def count(frame: pd.DataFrame, columns: tuple[str, ...]) -> int:
        if frame.empty:
            return 0
        subset = frame[frame.apply(_store_key, axis=1).eq(store)]
        for column in columns:
            if column in subset.columns:
                return int(subset[column].dropna().astype(str).str[:10].nunique())
        return 0

    return count(daily, ("Tarih", "Gün", "Gun")), count(monthly, ("Ay", "Dönem", "Donem", "Tarih"))


def build_real_staffing_need(
    detail: pd.DataFrame,
    *,
    sheets: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Mağaza-unvan açığını birbirini dışlayan karar sınıflarına ayırır."""
    output_columns = [
        "Bölge Sorumlusu", "Mağaza", "Unvan", "Norm", "Mevcut", "Norm Eksiği",
        "Transferle Kapatılabilir", "Geçici Operasyonel Açık", "Norm Revizyonu Adayı",
        "Gerçek İşe Alım İhtiyacı", "Kararsız Veri Açığı", "Karar", "Güven Puanı",
        "Güven Düzeyi", "Veri Kapsamı", "Neden",
    ]
    if detail is None or detail.empty:
        return pd.DataFrame(columns=output_columns), _totals([])

    overtime = _latest_by_store(_sheet(sheets, "Fazla Mesai"))
    absence = _latest_by_store(_sheet(sheets, "Devamsızlık"))
    workload = _latest_by_store(_sheet(sheets, "İş Yükü Endeksi", "Is Yuku Endeksi"))
    operations = _latest_by_store(_sheet(sheets, "Aylık Operasyon KPI", "Aylik Operasyon KPI"))

    available: dict[str, int] = defaultdict(int)
    for _, row in detail.iterrows():
        available[_title(row)] += max(0, int(_number(row.get("Norm Fazlası", row.get("Fazla"))) or 0))

    rows: list[dict[str, Any]] = []
    deficits = detail.copy()
    deficit_column = "Norm Eksiği" if "Norm Eksiği" in deficits.columns else "Eksik"
    deficits["_gap"] = pd.to_numeric(deficits.get(deficit_column, 0), errors="coerce").fillna(0)
    deficits = deficits[deficits["_gap"].gt(0)].sort_values("_gap", ascending=False)

    for _, source in deficits.iterrows():
        store, title = _store_key(source), _title(source)
        gap = int(source["_gap"])
        transfer = min(gap, available[title])
        available[title] -= transfer
        remaining = gap - transfer

        daily_count, monthly_count = _history_coverage(sheets, store)
        enough_history = daily_count >= MIN_DAILY_OBSERVATIONS or monthly_count >= MIN_MONTHLY_PERIODS
        overtime_hours = _metric(overtime.get(store), "Fazla Mesai Saat", "Fazla Mesai Saati")
        lost_fte = _metric(absence.get(store), "Fiili Kayıp FTE", "Kayıp FTE")
        workload_index = _metric(workload.get(store), "İş Yükü Endeksi")
        if workload_index is None:
            workload_index = _metric(operations.get(store), "İş Yükü Endeksi")
        target_rate = _metric(operations.get(store), "Hedef Gerçekleşme %", "Satış Hedef Gerçekleşme %")

        temporary = min(remaining, max(0, int(round(lost_fte or 0)))) if enough_history else 0
        remaining -= temporary
        high_pressure = sum((
            (overtime_hours or 0) > 0,
            (workload_index or 0) >= 70,
            (target_rate or 0) >= 95,
        ))

        revision = 0
        hiring = 0
        undecided = 0
        if not enough_history:
            undecided = remaining
            decision = "VERİ YETERSİZ — TRANSFER/İŞE ALIM ADAYI"
        elif remaining and high_pressure >= 1:
            hiring = remaining
            decision = "ACİL İŞE ALIM" if high_pressure >= 2 and remaining >= 2 else "İŞE ALIM"
        elif remaining:
            revision = remaining
            decision = "NORM REVİZYONU İNCELEMESİ"
        elif temporary:
            decision = "GEÇİCİ OPERASYONEL ÇÖZÜM"
        else:
            decision = "TRANSFER"

        coverage_points = min(40, daily_count) if daily_count else min(40, monthly_count * 12)
        signal_count = sum(value is not None for value in (overtime_hours, lost_fte, workload_index, target_rate))
        confidence = min(100, 20 + coverage_points + signal_count * 10)
        if not enough_history:
            confidence = min(confidence, 49)
        level = "Yüksek" if confidence >= 75 else "Orta" if confidence >= 50 else "Düşük"

        reasons = [f"Norm eksiği {gap} kişi."]
        if transfer:
            reasons.append(f"Aynı unvanda diğer mağazalarda {transfer} kişilik fazla kadro transfer adayıdır.")
        if temporary:
            reasons.append(f"Kayıp kapasitenin {temporary} FTE'si geçici devamsızlık/operasyon etkisiyle ilişkilidir.")
        if overtime_hours is not None:
            reasons.append(f"Fazla mesai {overtime_hours:g} saattir.")
        if workload_index is not None:
            reasons.append(f"İş yükü endeksi {workload_index:g} seviyesindedir.")
        if target_rate is not None:
            reasons.append(f"Satış hedef gerçekleşmesi %{target_rate:g} seviyesindedir.")
        if not enough_history:
            reasons.append(f"Yalnız {daily_count} günlük/{monthly_count} aylık dönem bulunduğu için kesin karar yayımlanmadı.")

        rows.append({
            "Bölge Sorumlusu": str(source.get("Bölge Sorumlusu") or source.get("bolge_sorumlusu") or ""),
            "Mağaza": store, "Unvan": title,
            "Norm": int(_number(source.get("Norm Kadro", source.get("Norm"))) or 0),
            "Mevcut": int(_number(source.get("Aktif Mevcut", source.get("Mevcut"))) or 0),
            "Norm Eksiği": gap, "Transferle Kapatılabilir": transfer,
            "Geçici Operasyonel Açık": temporary, "Norm Revizyonu Adayı": revision,
            "Gerçek İşe Alım İhtiyacı": hiring, "Kararsız Veri Açığı": undecided,
            "Karar": decision, "Güven Puanı": confidence, "Güven Düzeyi": level,
            "Veri Kapsamı": f"{daily_count} günlük / {monthly_count} aylık dönem",
            "Neden": " ".join(reasons),
        })

    return pd.DataFrame(rows, columns=output_columns), _totals(rows)


def _totals(rows: list[dict[str, Any]]) -> dict[str, int]:
    def total(key: str) -> int:
        return sum(int(row.get(key, 0) or 0) for row in rows)

    result = {
        "Norm Eksiği": total("Norm Eksiği"),
        "Transferle Kapatılabilir": total("Transferle Kapatılabilir"),
        "Geçici Operasyonel Açık": total("Geçici Operasyonel Açık"),
        "Norm Revizyonu Gerektiren": total("Norm Revizyonu Adayı"),
        "Gerçek İşe Alım İhtiyacı": total("Gerçek İşe Alım İhtiyacı"),
        "Kararsız Veri Açığı": total("Kararsız Veri Açığı"),
    }
    result["Sınıflandırılan Açık"] = sum(result[key] for key in (
        "Transferle Kapatılabilir", "Geçici Operasyonel Açık", "Norm Revizyonu Gerektiren",
        "Gerçek İşe Alım İhtiyacı", "Kararsız Veri Açığı",
    ))
    return result
