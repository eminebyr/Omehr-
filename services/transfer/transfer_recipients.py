from __future__ import annotations

"""ALICI LİSTESİ ÇÖZÜMLEME — servis katmanı kopyası.

DÜZELTME (dayanıklılık): rotasyon/geçici görevlendirme belge üretimi
(services/rotation_document.py, services/gecici_gorevlendirme.py) ve mail
gönderimi önceden SADECE web paneli -> onay ekranı -> worker.py zinciri
üzerinden birbirine bağlıydı. Bu zincirin dışında (örn. bir script'ten,
ileride eklenecek bir otomasyondan) bu servisler doğrudan çağrılırsa mail
otomatik GİTMEZDİ — alıcı listesi mantığı (`transfer_recipients` ve
yardımcıları) yalnızca web/accounts.py içindeydi, servis katmanından
erişilemiyordu.

Bu modül, o mantığın SERVİS KATMANINDA bağımsız bir kopyasıdır (web/
katmanına bağımlılık olmasın diye import değil, kopya — iki dosya kasıtlı
olarak aynı davranışı taşır). web/accounts.py'deki orijinal fonksiyonlar ve
mevcut üretim akışı (worker.py TRANSFER_DECISION) HİÇBİR ŞEKİLDE
değiştirilmedi; bu modül sadece EK, opsiyonel bir "kendi kendine yeten"
erişim noktası sağlar (bkz. create_rotation_documents_and_notify,
create_temporary_assignment_documents_and_notify).
"""

import pandas as pd


def _norm_text(v):
    return str(v or "").strip().upper().replace("İ", "I").replace("Ş", "S").replace("Ğ", "G").replace("Ü", "U").replace("Ö", "O").replace("Ç", "C")


def _admin_copy_email_list(account_frame):
    if account_frame is None or account_frame.empty:
        return []
    role_col = next((c for c in ("Rol", "Role", "Yetki") if c in account_frame.columns), None)
    email_col = next((c for c in ("E-posta", "Email") if c in account_frame.columns), None)
    if not role_col or not email_col:
        return []
    roles = account_frame[role_col].astype(str).map(_norm_text)
    rows = account_frame[roles.str.contains("ADMIN|IK[ _]?DIREKTOR|HR[ _]?DIRECTOR", regex=True, na=False)]
    emails = []
    for value in rows[email_col].dropna().astype(str):
        emails.extend(x.strip() for x in value.replace(",", ";").split(";") if "@" in x)
    return list(dict.fromkeys(emails))


def _region_email_list(account_frame, region):
    if account_frame is None or account_frame.empty:
        return []
    target = _norm_text(region)
    rows = account_frame[account_frame["Yetki Kapsamı"].astype(str).map(_norm_text).eq(target)]
    emails = []
    for value in rows.get("E-posta", pd.Series(dtype=str)).dropna().astype(str):
        value = value.strip()
        if "@" in value and "dummy.omehr.local" not in value.casefold():
            emails.append(value)
    return list(dict.fromkeys(emails))


def _branch_email_list(sheet_frames, *stores):
    frame = (sheet_frames or {}).get("Sube_Mail_Listesi", pd.DataFrame()).copy()
    if frame.empty:
        return []
    store_col = next((c for c in ("Mağaza", "Magaza") if c in frame.columns), None)
    email_col = next((c for c in ("Mağaza E-posta", "E-posta", "Email") if c in frame.columns), None)
    if not store_col or not email_col:
        return []
    wanted = {_norm_text(value) for value in stores if str(value or "").strip()}
    rows = frame[frame[store_col].astype(str).map(_norm_text).isin(wanted)]
    emails = []
    for value in rows[email_col].dropna().astype(str):
        emails.extend(x.strip() for x in value.replace(",", ";").split(";") if "@" in x)
    return list(dict.fromkeys(emails))


def transfer_recipients(account_frame, row, sheet_frames=None):
    """web/accounts.py::transfer_recipients ile BİREBİR aynı davranış —
    servis katmanından (web bağımlılığı olmadan) erişilebilir kopya."""
    return list(dict.fromkeys(
        _admin_copy_email_list(account_frame)
        + _region_email_list(account_frame, row.get("region"))
        + _region_email_list(account_frame, row.get("target_region"))
        + _branch_email_list(sheet_frames, row.get("source_store"), row.get("target_store"))
    ))
