from __future__ import annotations

import json
from datetime import datetime

import pandas as pd
from services.runtime_paths import runtime_root
from services.settings import input_path

def _input():
    return input_path(runtime_root())


DATE_HINTS = ("tarih", "date", "dönem", "donem", "month")


def _looks_like_date_column(column: object) -> bool:
    name = str(column).strip().casefold()
    return name in {"ay", "yıl-ay", "yil-ay"} or any(hint in name for hint in DATE_HINTS)


def assess_model_readiness() -> dict:
    sheets = pd.read_excel(_input(), sheet_name=None)
    periods: set[str] = set()
    dated_columns: list[str] = []
    for sheet, frame in sheets.items():
        for column in frame.columns:
            if not _looks_like_date_column(column):
                continue
            raw = frame[column]
            numeric = pd.to_numeric(raw, errors="coerce")
            if numeric.notna().mean() > 0.8 and numeric.dropna().median() > 20_000:
                values = pd.to_datetime(numeric, unit="D", origin="1899-12-30", errors="coerce").dropna()
            else:
                values = pd.to_datetime(raw, errors="coerce", dayfirst=True).dropna()
            if values.empty:
                continue
            dated_columns.append(f"{sheet}.{column}")
            periods.update(values.dt.to_period("M").astype(str).unique().tolist())
    period_count = len(periods)
    level = "PRODUCTION_CANDIDATE" if period_count >= 12 else ("LIMITED" if period_count >= 3 else "DECISION_SUPPORT_ONLY")
    result = {
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "status": level,
        "distinct_months": period_count,
        "periods": sorted(periods),
        "dated_columns": dated_columns,
        "causal_claim_allowed": False,
        "automatic_hr_decision_allowed": False,
        "note": (
            "Model karar desteğidir. En az 12 dönem, saha doğrulaması ve izleme başarımı "
            "olmadan otomatik norm/transfer kararı verilmez."
        ),
    }
    target = runtime_root() / "logs" / "CURRENT_Model_Governance.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
