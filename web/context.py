"""Web paneli sekmeleri için paylaşılan bağlam (context) nesnesi.

web/app.py, giriş/rol kontrolünü ve KPI hesaplamasını bir kez yapıp bu
PageContext nesnesini doldurur; her sekme (web/tab_modules/*.py) kendi
render(ctx) fonksiyonunda yalnızca ihtiyacı olan alanları okur. Böylece
sekmeler birbirinden bağımsız dosyalarda durabilir ama hepsi aynı
"tek doğru kaynak" veriyi (sheets, fm/detail/stores/kpis, kullanıcı/rol
bilgisi, servis fonksiyonları) kullanır.

Not: Bu obje her Streamlit "run" turunda (her etkileşimde) app.py
tarafından yeniden oluşturulur; sekmeler arasında saklı/kalıcı bir durum
tutmaz. Kalıcı durum için st.session_state kullanılmaya devam eder.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import pandas as pd


@dataclass
class PageContext:
    # --- yollar / sabitler ---
    root: Path
    input_path: Path
    output_path: Path
    db_path: Path
    approvers: set
    bd_renk: dict

    # --- veri ---
    sheets: dict
    acc: pd.DataFrame
    fm: pd.DataFrame
    detail: pd.DataFrame
    stores: pd.DataFrame
    kpis: dict

    # --- oturum açan kullanıcı ---
    user: dict
    username: str
    role: str
    scope: str
    email: str
    is_global: bool
    can_view_personal_address: bool
    approval_level: int
    can_approve: bool

    # --- servis / yardımcı fonksiyonlar (app.py'de bağlanır) ---
    db: Callable[..., Any]
    log: Callable[..., Any]
    enqueue: Callable[..., Any]
    job_status: Callable[..., Any]
    tenant_code: Callable[..., Any]
    norm_text: Callable[..., Any]
    tr_number: Callable[..., Any]
    tr_money_compact: Callable[..., Any]
    set_password: Callable[..., Any]
    password_error: Callable[..., Any]
    refresh_home_proximity: Callable[..., Any]
    maps_route: Callable[..., Any]
    verify_password: Callable[..., Any]
    transfer_recipients: Callable[..., Any]
    cancel_transfer_request: Callable[..., Any]
    redirect_transfer_request: Callable[..., Any]
    bulk_branch_mail_panel: Callable[..., Any]
    enqueue_and_process: Callable[..., Any]
    read_input: Callable[..., Any]
