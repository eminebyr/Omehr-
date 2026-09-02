from __future__ import annotations

import numpy as np
import pandas as pd

from services.model_lifecycle import (
    assess_model_maturity,
    independent_classification_target,
    retraining_due,
    rolling_origin_splits,
    temporal_workload_backtest,
)


def _sheets(days: int, real_share: float = 1.0) -> dict[str, pd.DataFrame]:
    dates = pd.date_range("2026-01-01", periods=days, freq="D")
    rows_per_day = 10
    real_rows = int(rows_per_day * real_share)
    repeated_dates = dates.repeat(rows_per_day)
    statuses = (["Gerçek/Mevcut Kaynak"] * real_rows + ["Saha Etüdü Bekleniyor"] * (rows_per_day - real_rows)) * days
    return {
        "Gunluk_Aktivite_Hacmi": pd.DataFrame(
            {
                "Tarih": repeated_dates,
                "MağazaID": "M001",
                "UnvanID": "U001",
                "Veri Durumu": statuses,
            }
        )
    }


def test_two_day_demo_stays_experimental() -> None:
    maturity = assess_model_maturity(_sheets(2))
    assert maturity.stage == "BAŞLANGIÇ VERİSİ"
    assert maturity.release_allowed is False
    assert maturity.allowed_horizons == ()


def test_mature_history_still_requires_temporal_backtest() -> None:
    maturity = assess_model_maturity(_sheets(200))
    assert maturity.stage == "ÜRETİM ADAYI"
    assert maturity.release_allowed is False
    assert "zamansal" in maturity.reason.lower()


def test_mature_real_history_and_backtest_open_release_gate() -> None:
    backtest = pd.DataFrame({"Gözlem (Dönem)": [5], "MAE": [0.30], "Naif MAE": [0.55]})
    maturity = assess_model_maturity(_sheets(200, 0.80), backtest_summary=backtest)
    assert maturity.release_allowed is True
    assert maturity.allowed_horizons == (7, 30, 90)


def test_rolling_origin_never_mixes_future_into_training() -> None:
    dates = pd.date_range("2026-01-01", periods=220, freq="D")
    splits = rolling_origin_splits(dates, min_train_days=90, test_days=30, gap_days=1)
    assert len(splits) >= 3
    for train, test in splits:
        assert train.max() < test.min()
        assert dates[train].max() < dates[test].min()


def test_circular_ai_gap_is_not_accepted_as_classification_target() -> None:
    target, reason = independent_classification_target({"AI_Norm_Sonuclari": pd.DataFrame({"AI-Mevcut Fark": [1]})})
    assert target.empty
    assert "kullanılmadı" in reason


def test_weekly_retraining_or_drift() -> None:
    assert retraining_due("2026-01-01", "2026-01-08") is True
    assert retraining_due("2026-01-01", "2026-01-04") is False
    assert retraining_due("2026-01-03", "2026-01-04", drift_detected=True) is True


def test_temporal_backtest_waits_for_real_history() -> None:
    detail, summary = temporal_workload_backtest(_sheets(20))
    assert detail.empty
    assert summary.iloc[0]["Durum"] in {"SKIPPED", "ŞEMA EKSİK"}
