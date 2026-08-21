from __future__ import annotations

"""Tahmin motoru için geriye dönük doğrulama ve hata ölçümleri.

Bu modül tahmin sonucunu resmî norma bağlamaz. Yeterli tarihsel veri varsa
rolling-origin backtest yapar; yoksa neden doğrulama yapılamadığını açıkça
yazar. Ölçüler: MAE, RMSE, MAPE, WAPE ve yanlılık (bias).
"""

from pathlib import Path
from typing import Any
import unicodedata

import numpy as np
import pandas as pd


def _norm(value: Any) -> str:
    text = str(value or "").strip().upper()
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _find_col(df: pd.DataFrame, *tokens: str) -> str | None:
    wanted = [_norm(t) for t in tokens]
    for c in df.columns:
        n = _norm(c)
        if all(t in n for t in wanted):
            return c
    return None


def _clean(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    unnamed = sum(str(c).startswith("Unnamed") for c in out.columns) / max(1, len(out.columns))
    if unnamed >= 0.4 and len(out):
        out.columns = [str(x).strip() if pd.notna(x) else f"Kolon_{i+1}" for i, x in enumerate(out.iloc[0].tolist())]
        out = out.iloc[1:].copy()
    return out.dropna(how="all").reset_index(drop=True)


def _sheet(sheets: dict[str, pd.DataFrame], *names: str) -> pd.DataFrame:
    direct = {k: v for k, v in sheets.items()}
    normalized = {_norm(k): k for k in sheets}
    for name in names:
        if name in direct:
            return _clean(direct[name])
        hit = normalized.get(_norm(name))
        if hit:
            return _clean(direct[hit])
    return pd.DataFrame()


def _metrics(actual: pd.Series, predicted: pd.Series) -> dict[str, float]:
    a = pd.to_numeric(actual, errors="coerce")
    p = pd.to_numeric(predicted, errors="coerce")
    mask = a.notna() & p.notna()
    a, p = a[mask].astype(float), p[mask].astype(float)
    if a.empty:
        return {"MAE": np.nan, "RMSE": np.nan, "MAPE %": np.nan, "WAPE %": np.nan, "Bias": np.nan, "Gözlem": 0}
    err = p - a
    abs_err = err.abs()
    nonzero = a.abs() > 1e-9
    mape = float((abs_err[nonzero] / a[nonzero].abs()).mean() * 100) if nonzero.any() else np.nan
    denom = float(a.abs().sum())
    return {
        "MAE": float(abs_err.mean()),
        "RMSE": float(np.sqrt((err ** 2).mean())),
        "MAPE %": mape,
        "WAPE %": float(abs_err.sum() / denom * 100) if denom else np.nan,
        "Bias": float(err.mean()),
        "Gözlem": int(len(a)),
    }


def _naive_forecast(series: pd.Series, horizon: int = 1) -> float:
    """Temkinli kısa dönem tahmini: son 3 ay ortalaması + sınırlı trend."""
    s = pd.to_numeric(series, errors="coerce").dropna().astype(float)
    if len(s) < 3:
        return float(s.iloc[-1]) if len(s) else np.nan
    recent = float(s.tail(3).mean())
    if len(s) >= 6:
        prev = float(s.iloc[-6:-3].mean())
        trend = 0.0 if prev == 0 else recent / prev - 1.0
    else:
        trend = 0.0
    trend = max(-0.15, min(0.20, trend))
    return recent * (1 + trend * horizon / 3.0)


def operational_backtest(sheets: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    op = _sheet(sheets, "Aylık Operasyon KPI", "Operasyon", "Fact_Operasyon", "Operasyon_KPI", "Günlük Operasyon")
    if op.empty:
        return pd.DataFrame(), pd.DataFrame([{"Durum": "SKIPPED", "Açıklama": "Operasyon geçmişi bulunamadı."}])
    sid = _find_col(op, "magaza", "id")
    date = _find_col(op, "ay") or _find_col(op, "tarih") or _find_col(op, "donem")
    metrics = {
        "Ciro": _find_col(op, "ciro"),
        "Fiş": _find_col(op, "fis"),
        "Online Sipariş": _find_col(op, "online", "siparis"),
    }
    metrics = {k: v for k, v in metrics.items() if v}
    if not sid or not date or not metrics:
        return pd.DataFrame(), pd.DataFrame([{"Durum": "SKIPPED", "Açıklama": "MağazaID, tarih veya operasyon metriği eksik."}])
    x = op.copy()
    x[date] = pd.to_datetime(x[date], errors="coerce")
    x = x.dropna(subset=[sid, date])
    detail = []
    for store, g in x.groupby(sid):
        for metric_name, col in metrics.items():
            monthly = g.set_index(date)[col]
            monthly = pd.to_numeric(monthly, errors="coerce").resample("MS").sum().dropna()
            if len(monthly) < 8:
                continue
            for test_i in range(6, len(monthly)):
                train = monthly.iloc[:test_i]
                actual = float(monthly.iloc[test_i])
                pred = _naive_forecast(train, 1)
                detail.append({
                    "MağazaID": str(store),
                    "Metrik": metric_name,
                    "Tahmin Ayı": monthly.index[test_i],
                    "Gerçek": actual,
                    "Tahmin": pred,
                    "Hata": pred - actual,
                    "Mutlak Hata": abs(pred - actual),
                })
    detail_df = pd.DataFrame(detail)
    if detail_df.empty:
        return detail_df, pd.DataFrame([{"Durum": "SKIPPED", "Açıklama": "Backtest için mağaza başına en az 8 aylık veri gerekir."}])
    rows = []
    for (store, metric), g in detail_df.groupby(["MağazaID", "Metrik"]):
        row = {"MağazaID": store, "Metrik": metric, **_metrics(g["Gerçek"], g["Tahmin"])}
        rows.append(row)
    for metric, g in detail_df.groupby("Metrik"):
        rows.append({"MağazaID": "TÜMÜ", "Metrik": metric, **_metrics(g["Gerçek"], g["Tahmin"])})
    return detail_df, pd.DataFrame(rows)


def headcount_backtest(sheets: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Tarihsel mağaza-unvan gerçekleşeni varsa kadro tahminini ölçer.

    Kabul edilen sayfa adları: Tarihsel_Mevcut, Aylik_Mevcut_Tarihcesi,
    Fact_Mevcut_Tarihce. Gerekli alanlar: Ay/Tarih, MağazaID, UnvanID,
    Aktif Mevcut/Gerçekleşen Mevcut ve tercihen Tahmini Gerekli Kadro.
    """
    hist = _sheet(sheets, "Tarihsel_Mevcut", "Aylik_Mevcut_Tarihcesi", "Fact_Mevcut_Tarihce")
    if hist.empty:
        return pd.DataFrame(), pd.DataFrame([{
            "Durum": "VERİ YOK",
            "Açıklama": "Mağaza-unvan bazlı gerçek kadro doğruluğu için tarihsel mevcut snapshot sayfası gerekir."
        }])
    date = _find_col(hist, "ay") or _find_col(hist, "tarih")
    sid = _find_col(hist, "magaza", "id")
    tid = _find_col(hist, "unvan", "id")
    actual = _find_col(hist, "gerceklesen", "mevcut") or _find_col(hist, "aktif", "mevcut")
    predicted = _find_col(hist, "tahmini", "gerekli", "kadro") or _find_col(hist, "tahmin")
    if not all([date, sid, tid, actual, predicted]):
        return pd.DataFrame(), pd.DataFrame([{
            "Durum": "ŞEMA EKSİK",
            "Açıklama": "Tarih, MağazaID, UnvanID, gerçekleşen mevcut ve tahmin kolonları gerekir."
        }])
    x = hist[[date, sid, tid, actual, predicted]].copy()
    x[date] = pd.to_datetime(x[date], errors="coerce")
    x[actual] = pd.to_numeric(x[actual], errors="coerce")
    x[predicted] = pd.to_numeric(x[predicted], errors="coerce")
    x = x.dropna(subset=[date, sid, tid, actual, predicted])
    rows = []
    for (store, title), g in x.groupby([sid, tid]):
        rows.append({"MağazaID": str(store), "UnvanID": str(title), **_metrics(g[actual], g[predicted])})
    rows.append({"MağazaID": "TÜMÜ", "UnvanID": "TÜMÜ", **_metrics(x[actual], x[predicted])})
    return x, pd.DataFrame(rows)


def run(sheets: dict[str, pd.DataFrame], outdir: Path | None = None) -> dict[str, pd.DataFrame]:
    op_detail, op_summary = operational_backtest(sheets)
    hc_detail, hc_summary = headcount_backtest(sheets)
    return {
        "Operasyon_Backtest_Detay": op_detail,
        "Operasyon_Backtest_Ozet": op_summary,
        "Kadro_Backtest_Detay": hc_detail,
        "Kadro_Backtest_Ozet": hc_summary,
    }
