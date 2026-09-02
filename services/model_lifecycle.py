from __future__ import annotations

"""Veri büyüdükçe ML kullanımını güvenli biçimde olgunlaştıran kurallar.

Bu modül model eğitmez. Günlük kaynakların kapsadığı gerçek tarih aralığını,
zamansal backtest kanıtını ve yeniden eğitim zamanını tek bir denetlenebilir
karara dönüştürür. Böylece örnek veriyle çalışan panel ile üretim için yeterli
tarihçeye sahip model aynı kod yolunu, fakat farklı yayın kapılarını kullanır.
"""

from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any, Iterable
import unicodedata

import numpy as np
import pandas as pd


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().upper())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _find_column(frame: pd.DataFrame, *tokens: str) -> str | None:
    wanted = tuple(_norm(token) for token in tokens)
    for column in frame.columns:
        normalized = _norm(column)
        if all(token in normalized for token in wanted):
            return str(column)
    return None


def _sheet(sheets: dict[str, pd.DataFrame], *names: str) -> pd.DataFrame:
    normalized = {_norm(name): name for name in sheets}
    for name in names:
        hit = normalized.get(_norm(name))
        if hit is not None and isinstance(sheets[hit], pd.DataFrame):
            return sheets[hit].copy()
    return pd.DataFrame()


@dataclass(frozen=True)
class ModelMaturity:
    stage: str
    distinct_days: int
    calendar_span_days: int
    real_data_share: float
    temporal_backtest_periods: int
    temporal_backtest_passed: bool
    group_validation_required: bool
    temporal_validation_required: bool
    release_allowed: bool
    allowed_horizons: tuple[int, ...]
    retrain_cadence_days: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["allowed_horizons"] = list(self.allowed_horizons)
        return payload

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"Gösterge": "Model yaşam evresi", "Değer": self.stage},
                {"Gösterge": "Benzersiz gerçek veri günü", "Değer": self.distinct_days},
                {"Gösterge": "Takvim kapsamı (gün)", "Değer": self.calendar_span_days},
                {"Gösterge": "Gerçek/türetilmiş veri payı %", "Değer": round(100 * self.real_data_share, 1)},
                {"Gösterge": "Zamansal backtest dönemi", "Değer": self.temporal_backtest_periods},
                {"Gösterge": "Zamansal backtest geçti mi", "Değer": "Evet" if self.temporal_backtest_passed else "Hayır"},
                {"Gösterge": "Üretim yayını", "Değer": "Açık" if self.release_allowed else "Kapalı"},
                {"Gösterge": "Aktif tahmin ufukları", "Değer": ", ".join(map(str, self.allowed_horizons)) or "Yok"},
                {"Gösterge": "Yeniden eğitim sıklığı (gün)", "Değer": self.retrain_cadence_days},
                {"Gösterge": "Karar gerekçesi", "Değer": self.reason},
            ]
        )


def _activity_profile(sheets: dict[str, pd.DataFrame]) -> tuple[int, int, float]:
    activity = _sheet(sheets, "Gunluk_Aktivite_Hacmi", "Günlük Aktivite Hacmi")
    if activity.empty:
        return 0, 0, 0.0
    date_column = _find_column(activity, "tarih")
    if not date_column:
        return 0, 0, 0.0
    all_dates = pd.to_datetime(activity[date_column], errors="coerce").dt.normalize()
    status_column = _find_column(activity, "veri", "durumu")
    if status_column:
        status = activity[status_column].map(_norm)
        real_mask = status.str.contains("GERCEK", case=False, na=False)
        real_share = float(real_mask.mean())
        dates = all_dates[real_mask & all_dates.notna()]
    else:
        real_share = 0.0
        dates = all_dates.iloc[0:0]
    distinct_days = int(dates.nunique())
    span = int((dates.max() - dates.min()).days + 1) if not dates.empty else 0
    return distinct_days, span, real_share


def _backtest_profile(backtest_summary: pd.DataFrame | None) -> tuple[int, bool]:
    if backtest_summary is None or backtest_summary.empty:
        return 0, False
    status_column = _find_column(backtest_summary, "durum")
    if status_column and backtest_summary[status_column].map(_norm).str.contains(
        "SKIPPED|VERI YOK|SEMA EKSIK", case=False, na=False
    ).any():
        return 0, False
    period_column = _find_column(backtest_summary, "gozlem") or _find_column(backtest_summary, "donem")
    periods = 0
    if period_column:
        values = pd.to_numeric(backtest_summary[period_column], errors="coerce").dropna()
        periods = int(values.max()) if not values.empty else 0
    mae_column = _find_column(backtest_summary, "mae")
    baseline_column = _find_column(backtest_summary, "naif", "mae")
    if mae_column and baseline_column:
        mae = pd.to_numeric(backtest_summary[mae_column], errors="coerce")
        baseline = pd.to_numeric(backtest_summary[baseline_column], errors="coerce")
        passed = bool(((mae < baseline) & mae.notna() & baseline.notna()).any())
    else:
        passed = periods >= 3
    return periods, passed


def assess_model_maturity(
    sheets: dict[str, pd.DataFrame],
    *,
    backtest_summary: pd.DataFrame | None = None,
) -> ModelMaturity:
    distinct_days, span, real_share = _activity_profile(sheets)
    periods, temporal_passed = _backtest_profile(backtest_summary)

    if distinct_days < 30:
        stage, horizons = "BAŞLANGIÇ VERİSİ", ()
        reason = "30 gerçek veri günü oluşana kadar ML yalnız deneysel; yönetim normu ve formül tabanlı iş yükü korunur."
    elif distinct_days < 90:
        stage, horizons = "ÖĞRENME AŞAMASI", (7,)
        reason = "Ön model ve geriye dönük kontroller çalışır; kesin kadro önerisi yayımlanmaz."
    elif distinct_days < 180:
        stage, horizons = "ÖN DOĞRULAMA", (7, 30)
        reason = "7/30 günlük tahminler izlenebilir; üretim yayını için zamansal backtest ve gerçek veri payı gerekir."
    elif distinct_days < 365:
        stage, horizons = "ÜRETİM ADAYI", (7, 30, 90)
        reason = "Yeterli tarihçe var; başarılı zamansal backtest ve veri kalitesi kapısı sonrası karar desteği yayımlanabilir."
    else:
        stage, horizons = "ÜRETİM İÇİN UYGUN", (7, 30, 90)
        reason = "Yıllık mevsimsellik kapsanıyor; model drift ve aylık kapsamlı doğrulama izlenmelidir."

    release_allowed = bool(
        distinct_days >= 180
        and span >= 180
        and real_share >= 0.70
        and periods >= 3
        and temporal_passed
    )
    if distinct_days >= 180 and not release_allowed:
        blockers = []
        if real_share < 0.70:
            blockers.append("gerçek veri payı %70'in altında")
        if periods < 3:
            blockers.append("en az 3 zamansal test dönemi yok")
        elif not temporal_passed:
            blockers.append("zamansal model naif karşılaştırmayı geçmedi")
        if span < 180:
            blockers.append("takvim kapsamı 180 günden kısa")
        reason = f"{reason} Yayın kapalı: {', '.join(blockers)}."

    return ModelMaturity(
        stage=stage,
        distinct_days=distinct_days,
        calendar_span_days=span,
        real_data_share=real_share,
        temporal_backtest_periods=periods,
        temporal_backtest_passed=temporal_passed,
        group_validation_required=True,
        temporal_validation_required=True,
        release_allowed=release_allowed,
        allowed_horizons=horizons,
        retrain_cadence_days=7,
        reason=reason,
    )


def rolling_origin_splits(
    dates: Iterable[Any],
    *,
    min_train_days: int = 90,
    test_days: int = 30,
    gap_days: int = 1,
    max_splits: int = 5,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Tarih sırasını koruyan, eğitim/test çakışmasını engelleyen indeksler."""
    parsed = pd.to_datetime(pd.Series(list(dates)), errors="coerce").dt.normalize()
    valid = parsed.notna()
    unique_dates = np.array(sorted(parsed[valid].unique()))
    required = min_train_days + gap_days + test_days
    if len(unique_dates) < required:
        return []
    cutoffs = list(range(min_train_days, len(unique_dates) - gap_days - test_days + 1, test_days))[-max_splits:]
    splits: list[tuple[np.ndarray, np.ndarray]] = []
    for cutoff in cutoffs:
        train_end = unique_dates[cutoff - 1]
        test_start = unique_dates[cutoff + gap_days]
        test_end = unique_dates[min(cutoff + gap_days + test_days - 1, len(unique_dates) - 1)]
        train_index = np.flatnonzero(valid & parsed.le(train_end))
        test_index = np.flatnonzero(valid & parsed.ge(test_start) & parsed.le(test_end))
        if len(train_index) and len(test_index):
            splits.append((train_index, test_index))
    return splits


def independent_classification_target(sheets: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, str]:
    """Yalnız sonradan gerçekleşmiş/onanmış bağımsız kadro sonucunu kabul eder."""
    target = _sheet(sheets, "Gerceklesen_Kadro_Ihtiyaci", "Gerçekleşen Kadro İhtiyacı")
    required = (
        _find_column(target, "tarih"),
        _find_column(target, "magaza", "id"),
        _find_column(target, "unvan", "id"),
        _find_column(target, "gerceklesen", "ihtiyac"),
    ) if not target.empty else (None, None, None, None)
    if not all(required):
        return pd.DataFrame(), (
            "Bağımsız gerçekleşen ihtiyaç etiketi yok; AI-Mevcut Fark aynı formülden türetildiği için "
            "sınıflandırma hedefi olarak kullanılmadı."
        )
    return target, "Bağımsız gerçekleşen ihtiyaç etiketi bulundu."


def retraining_due(
    last_trained_at: datetime | date | pd.Timestamp | None,
    latest_data_at: datetime | date | pd.Timestamp | None,
    *,
    cadence_days: int = 7,
    drift_detected: bool = False,
) -> bool:
    if latest_data_at is None:
        return False
    if drift_detected or last_trained_at is None:
        return True
    last = pd.Timestamp(last_trained_at)
    latest = pd.Timestamp(latest_data_at)
    return bool(latest > last and (latest - last).days >= cadence_days)


def temporal_workload_backtest(
    sheets: dict[str, pd.DataFrame],
    *,
    min_train_days: int = 90,
    test_days: int = 30,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Geçmiş günlük iş yükünden geleceğe doğru sızıntısız ML backtesti.

    Hedef aynı günün bileşenlerinden değil, her mağaza-unvanın gerçekleşmiş
    günlük FTE'sidir. Özellikler yalnız önceki gün/haftalardan gelir. Test
    blokları tarihte eğitim bloğundan sonra bulunur; bir günlük boşluk bırakılır.
    Naif referans son gerçekleşen FTE'dir.
    """
    activity = _sheet(sheets, "Gunluk_Aktivite_Hacmi", "Günlük Aktivite Hacmi")
    capacity = _sheet(sheets, "Kapasite_Parametreleri", "Kapasite Parametreleri")
    if activity.empty or capacity.empty:
        return pd.DataFrame(), pd.DataFrame([{"Durum": "SKIPPED", "Açıklama": "Aktivite veya kapasite verisi yok."}])
    date_col = _find_column(activity, "tarih")
    store_col = _find_column(activity, "magaza", "id")
    title_col = _find_column(activity, "unvan", "id")
    workload_col = _find_column(activity, "is", "yuku", "dk")
    cap_title = _find_column(capacity, "unvan", "id")
    cap_value = _find_column(capacity, "net", "uretken", "dakika")
    if not all([date_col, store_col, title_col, workload_col, cap_title, cap_value]):
        return pd.DataFrame(), pd.DataFrame([{"Durum": "ŞEMA EKSİK", "Açıklama": "Tarih, mağaza, unvan, iş yükü veya kapasite alanı eksik."}])

    daily = activity[[date_col, store_col, title_col, workload_col]].copy()
    daily[date_col] = pd.to_datetime(daily[date_col], errors="coerce").dt.normalize()
    daily[workload_col] = pd.to_numeric(daily[workload_col], errors="coerce")
    daily = daily.dropna(subset=[date_col, store_col, title_col, workload_col])
    daily = daily.groupby([date_col, store_col, title_col], as_index=False)[workload_col].sum()
    caps = capacity[[cap_title, cap_value]].copy()
    caps[cap_value] = pd.to_numeric(caps[cap_value], errors="coerce")
    caps = caps.dropna(subset=[cap_title, cap_value]).drop_duplicates(cap_title, keep="last")
    daily = daily.merge(caps.rename(columns={cap_title: title_col}), on=title_col, how="left")
    daily["Gerçek FTE"] = daily[workload_col] / daily[cap_value].replace(0, np.nan)
    daily = daily.replace([np.inf, -np.inf], np.nan).dropna(subset=["Gerçek FTE"])

    daily = daily.sort_values([store_col, title_col, date_col]).reset_index(drop=True)
    grouped = daily.groupby([store_col, title_col], sort=False)["Gerçek FTE"]
    daily["Lag 1"] = grouped.shift(1)
    daily["Lag 7"] = grouped.shift(7)
    daily["Hareketli 7"] = grouped.transform(lambda values: values.shift(1).rolling(7, min_periods=3).mean())
    daily["Hareketli 28"] = grouped.transform(lambda values: values.shift(1).rolling(28, min_periods=7).mean())
    day_of_week = daily[date_col].dt.dayofweek
    daily["Hafta Günü Sin"] = np.sin(2 * np.pi * day_of_week / 7)
    daily["Hafta Günü Cos"] = np.cos(2 * np.pi * day_of_week / 7)
    features = ["Lag 1", "Lag 7", "Hareketli 7", "Hareketli 28", "Hafta Günü Sin", "Hafta Günü Cos"]
    usable = daily.dropna(subset=["Lag 1", "Hareketli 7", "Gerçek FTE"]).copy()
    splits = rolling_origin_splits(
        usable[date_col], min_train_days=min_train_days, test_days=test_days, gap_days=1, max_splits=5
    )
    if len(splits) < 3:
        return pd.DataFrame(), pd.DataFrame([{
            "Durum": "SKIPPED",
            "Açıklama": "Zamansal backtest için en az 3 ileri test bloğu ve yeterli günlük tarihçe gerekir.",
            "Gözlem (Dönem)": len(splits),
        }])

    try:
        from sklearn.compose import ColumnTransformer
        from sklearn.impute import SimpleImputer
        from sklearn.linear_model import Ridge
        from sklearn.metrics import mean_absolute_error, mean_squared_error
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OneHotEncoder, StandardScaler
    except Exception as exc:  # pragma: no cover - kurulum ortamına bağlı
        return pd.DataFrame(), pd.DataFrame([{"Durum": "SKIPPED", "Açıklama": f"scikit-learn kullanılamadı: {exc}"}])

    categorical = [store_col, title_col]
    pipeline = Pipeline([
        ("prepare", ColumnTransformer([
            ("num", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), features),
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical),
        ])),
        ("model", Ridge(alpha=2.0)),
    ])
    detail_rows: list[dict[str, Any]] = []
    x = usable[features + categorical]
    y = usable["Gerçek FTE"].astype(float)
    for fold, (train_index, test_index) in enumerate(splits, start=1):
        fitted = pipeline.fit(x.iloc[train_index], y.iloc[train_index])
        prediction = np.maximum(fitted.predict(x.iloc[test_index]), 0)
        naive = usable.iloc[test_index]["Lag 1"].to_numpy(float)
        for position, predicted, baseline in zip(test_index, prediction, naive):
            row = usable.iloc[position]
            detail_rows.append({
                "Kat": fold,
                "Tarih": row[date_col],
                "MağazaID": row[store_col],
                "UnvanID": row[title_col],
                "Gerçek FTE": float(row["Gerçek FTE"]),
                "Model Tahmini FTE": float(predicted),
                "Naif Tahmin FTE": float(baseline),
            })
    detail = pd.DataFrame(detail_rows)
    actual = detail["Gerçek FTE"]
    predicted = detail["Model Tahmini FTE"]
    naive = detail["Naif Tahmin FTE"]
    mae = float(mean_absolute_error(actual, predicted))
    naive_mae = float(mean_absolute_error(actual, naive))
    summary = pd.DataFrame([{
        "Model": "Ridge gecikmeli günlük FTE",
        "Gözlem (Dönem)": len(splits),
        "Test Satırı": len(detail),
        "MAE": mae,
        "Naif MAE": naive_mae,
        "RMSE": float(np.sqrt(mean_squared_error(actual, predicted))),
        "Naif Modele Göre MAE İyileşmesi %": (naive_mae - mae) / naive_mae * 100 if naive_mae else np.nan,
        "Durum": "GEÇTİ" if mae < naive_mae else "GEÇMEDİ",
    }])
    return detail, summary
