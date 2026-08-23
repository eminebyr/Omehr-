from __future__ import annotations

"""
HESAP/YETKİ VE ALICI LİSTESİ FONKSİYONLARI (P2 — modülerleştirme,
dördüncü adım)
=====================================================================
Mail_Listesi hesap okuma, şifre doğrulama, bölge/şube e-posta listeleri
ve transfer bildirimi alıcı birleştirme — Streamlit'e bağımlı değildir.

NOT: cancel_transfer_request/redirect_transfer_request BİLEREK burada
DEĞİL — onlar globals().get("sheets",...) ile web/app.py'nin modül
seviyesi durumuna bağımlı; ayrı dosyaya taşınsalar bu sessizce bozulurdu.
"""

import pandas as pd

from services.security import authenticate as secure_authenticate
from web.formatting import norm_text

# DÜZELTME (çok kiracılı SaaS): önceden burada 4 SABİT, gerçek bir
# firmaya (@omehrmarket.com) ait e-posta adresi HER transfer
# bildirimine otomatik CC olarak ekleniyordu — ÇOK KİRACILI bir SaaS'ta
# bu, her firmanın transfer bildirimlerinin bambaşka bir firmaya ait
# adreslere gitmesi anlamına gelirdi (veri gizliliği ihlali). Kaldırıldı;
# alıcılar artık TAMAMEN kiracının kendi verisinden (Mail_Listesi/
# Sube_Mail_Listesi) türetilir.
NOTIFY_TO: list[str] = []


def accounts(sheets):
    ml = sheets.get("Mail_Listesi", pd.DataFrame()).copy()
    if ml.empty: return pd.DataFrame()
    if "Aktif" in ml.columns: ml = ml[ml["Aktif"].astype(str).str.casefold().isin(["evet", "e", "yes", "1", "true"])]
    return ml


def verify_password(user_row, password, tenant_id=None):
    username = str(user_row.get("Web Kullanıcı", "")).strip()
    return secure_authenticate(username, password, tenant_id=tenant_id)


def region_email_list(account_frame, region):
    if account_frame.empty: return []
    target = norm_text(region)
    rows = account_frame[account_frame["Yetki Kapsamı"].astype(str).map(norm_text).eq(target)]
    emails = []
    for value in rows.get("E-posta", pd.Series(dtype=str)).dropna().astype(str):
        value = value.strip()
        if "@" in value and "dummy.omehr.local" not in value.casefold(): emails.append(value)
    return list(dict.fromkeys(emails))

def branch_email_list(sheet_frames, *stores):
    frame=(sheet_frames or {}).get("Sube_Mail_Listesi",pd.DataFrame()).copy()
    if frame.empty: return []
    store_col=next((c for c in ("Mağaza","Magaza") if c in frame.columns),None)
    email_col=next((c for c in ("Mağaza E-posta","E-posta","Email") if c in frame.columns),None)
    if not store_col or not email_col: return []
    wanted={norm_text(value) for value in stores if str(value or "").strip()}
    rows=frame[frame[store_col].astype(str).map(norm_text).isin(wanted)]
    emails=[]
    for value in rows[email_col].dropna().astype(str):
        emails.extend(x.strip() for x in value.replace(",", ";").split(";") if "@" in x)
    return list(dict.fromkeys(emails))

def admin_copy_email_list(account_frame):
    """Rotasyon evrakının arşiv kopyasını aktif ADMIN/İK Direktörü hesaplarına gönderir.

    DÜZELTME: norm_text() metni BÜYÜK harfe çeviriyor (küçük harfe DEĞİL),
    ama buradaki regex önceden küçük harfli ve boşluklu yazılmıştı
    ("hr director") — gerçek Rol değerleri ise büyük harfli ve alt
    çizgili ("HR_DIRECTOR"). Bu ikisi ASLA eşleşmiyordu; yani şirket
    geneli rapor dağıtımı (Madde 27-28) sessizce hiç çalışmıyordu.
    Bizzat kanıtlandı: gerçek veriyle admin_copy_email_list() boş liste
    döndürüyordu. Regex artık gerçek (büyük harfli, alt çizgili) rol
    biçimini kapsıyor."""
    if account_frame is None or account_frame.empty: return []
    role_col=next((c for c in ("Rol","Role","Yetki") if c in account_frame.columns),None)
    email_col=next((c for c in ("E-posta","Email") if c in account_frame.columns),None)
    if not role_col or not email_col: return []
    roles=account_frame[role_col].astype(str).map(norm_text)
    rows=account_frame[roles.str.contains("ADMIN|IK[ _]?DIREKTOR|HR[ _]?DIRECTOR",regex=True,na=False)]
    emails=[]
    for value in rows[email_col].dropna().astype(str):
        emails.extend(x.strip() for x in value.replace(",",";").split(";") if "@" in x)
    return list(dict.fromkeys(emails))

def transfer_recipients(account_frame, row, sheet_frames=None):
    return list(dict.fromkeys(
        NOTIFY_TO
        + admin_copy_email_list(account_frame)
        + region_email_list(account_frame, row.get("region"))
        + region_email_list(account_frame, row.get("target_region"))
        + branch_email_list(sheet_frames,row.get("source_store"),row.get("target_store"))
    ))

