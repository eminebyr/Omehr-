from __future__ import annotations

"""İşe giriş / işten çıkış bildirim alıcıları ve mail gönderimi.

Otomatik alıcılar:
- ilgili mağaza e-postası (Sube_Mail_Listesi)
- aktif ADMIN / İK Direktörü hesapları (Mail_Listesi)
- ilgili mağazanın Bölge Sorumlusu (Dim_Magaza -> Mail_Listesi Yetki Kapsamı)

Bunlara ek olarak kullanıcı, Mail_Listesi'ndeki aktif kişilerden ek alıcı seçebilir.

DÜZELTME (çok kiracılı SaaS entegrasyonu):
1) Önceki sürüm YALNIZ Excel modunu destekliyordu (pd.read_excel
   doğrudan çağrılıyordu) — veritabanı modunda (BASDAS_INPUT_SOURCE=db)
   bu modül ya hatalı çalışırdı ya da yanlış/eski veriyi okurdu. Artık
   services/personnel_exit.py ile AYNI çift-modlu desen kullanılıyor.
2) Önceki sürümde SABİT, gerçek bir kişinin e-posta adresi
   HER bildirime otomatik ekleniyordu.
   Bu, tek firmalık kurulumda zararsız görünse de ÇOK KİRACILI bir
   SaaS'ta CİDDİ bir hata olurdu: Firma B'nin personel giriş/çıkış
   bildirimleri, Firma A'yla hiçbir ilgisi olmayan bu sabit adrese de
   giderdi — veri gizliliği ihlali. Bu davranış TAMAMEN KALDIRILDI.
   Bir firma ek/sabit bir alıcı istiyorsa Mail_Listesi'ne kendi
   kiracısı için ekleyebilir (zaten desteklenen "ek alıcı" mekanizması).
"""

import os
import re
from pathlib import Path

import pandas as pd

from services.job_queue import enqueue as _enqueue_job
from web.accounts import admin_copy_email_list, branch_email_list, region_email_list
from web.formatting import norm_text


def _db_modu() -> bool:
    return os.environ.get("BASDAS_INPUT_SOURCE", "excel").strip().lower() == "db"


def _read_sheet(input_path: Path | None, sheet_adi: str) -> pd.DataFrame:
    if _db_modu():
        from services.input_data_access import read_sheet
        return read_sheet(sheet_adi)
    try:
        from services.cached_excel_reader import read_sheet_cached
        return read_sheet_cached(input_path, sheet_adi)
    except Exception:
        return pd.DataFrame()


def _split_addresses(value) -> list[str]:
    out: list[str] = []
    for x in re.split(r"[;,]", str(value or "")):
        x = x.strip()
        if "@" in x:
            out.append(x)
    return out


def _active_mail_frame(input_path: Path | None) -> pd.DataFrame:
    df = _read_sheet(input_path, "Mail_Listesi")
    if df.empty:
        return df
    if "Aktif" in df.columns:
        df = df[df["Aktif"].astype(str).map(norm_text).isin({"EVET", "E", "YES", "1", "TRUE", "AKTIF"})]
    return df.copy()


def selectable_extra_contacts(input_path: Path | None) -> list[tuple[str, str]]:
    """[(etiket, eposta)] -- ek alıcı multiselect için."""
    df = _active_mail_frame(input_path)
    if df.empty:
        return []
    items: list[tuple[str, str]] = []
    seen: set[str] = set()
    for _, row in df.iterrows():
        who = str(row.get("Sorumlu") or row.get("Web Kullanıcı") or "Ek alıcı").strip()
        for email in _split_addresses(row.get("E-posta")):
            key = email.casefold()
            if key in seen:
                continue
            seen.add(key)
            items.append((f"{who} — {email}", email))
    return items


def _read_relevant_frames(input_path: Path | None) -> dict[str, pd.DataFrame]:
    return {
        "Dim_Magaza": _read_sheet(input_path, "Dim_Magaza"),
        "Mail_Listesi": _read_sheet(input_path, "Mail_Listesi"),
        "Sube_Mail_Listesi": _read_sheet(input_path, "Sube_Mail_Listesi"),
    }


def personnel_event_recipients(input_path: Path | None, magaza: str, magaza_id: str = "", extra=None) -> dict:
    """Otomatik + ek alıcıları döndürür; ayrıca bölge adını verir."""
    sheets = _read_relevant_frames(input_path)
    dim = sheets.get("Dim_Magaza", pd.DataFrame()).copy()
    accounts = sheets.get("Mail_Listesi", pd.DataFrame()).copy()
    if "Aktif" in accounts.columns:
        accounts = accounts[accounts["Aktif"].astype(str).map(norm_text).isin({"EVET", "E", "YES", "1", "TRUE", "AKTIF"})]

    region = ""
    if not dim.empty:
        rows = pd.DataFrame()
        if magaza_id and "MağazaID" in dim.columns:
            rows = dim[dim["MağazaID"].astype(str).str.strip().eq(str(magaza_id).strip())]
        if rows.empty and magaza and "Mağaza" in dim.columns:
            target = norm_text(magaza)
            rows = dim[dim["Mağaza"].astype(str).map(norm_text).eq(target)]
        if not rows.empty and "Bölge Sorumlusu" in rows.columns:
            region = str(rows.iloc[0].get("Bölge Sorumlusu") or "").strip()

    automatic: list[str] = []
    automatic += branch_email_list(sheets, magaza)
    automatic += admin_copy_email_list(accounts)
    automatic += region_email_list(accounts, region)

    all_recipients = automatic + list(extra or [])
    normalized: list[str] = []
    seen: set[str] = set()
    for e in all_recipients:
        for address in _split_addresses(e):
            k = address.casefold()
            if k not in seen:
                seen.add(k)
                normalized.append(address)

    auto_normalized: list[str] = []
    seen_auto: set[str] = set()
    for e in automatic:
        for address in _split_addresses(e):
            k = address.casefold()
            if k not in seen_auto:
                seen_auto.add(k)
                auto_normalized.append(address)

    return {"recipients": normalized, "automatic": auto_normalized, "region": region}


def send_personnel_event_mail(*, input_path: Path | None, event: str, person: dict, extra_recipients=None, attachments=None) -> dict:
    magaza = str(person.get("Mağaza") or "").strip()
    magaza_id = str(person.get("MağazaID") or "").strip()
    rec = personnel_event_recipients(input_path, magaza, magaza_id, extra_recipients)
    recipients = rec["recipients"]
    if not recipients:
        return {"status": "SKIPPED", **rec}

    name = str(person.get("İsim Soyisim") or "").strip()
    title = str(person.get("Unvan") or "").strip()
    dept = str(person.get("Departman") or "").strip()
    desc = str(person.get("Açıklama") or "").strip()

    if event == "ISE_GIRIS":
        dt = str(person.get("İşe Giriş") or "").strip()
        subject = f"İşe Giriş Bildirimi | {name} | {magaza}"
        body = (
            "Merhaba,\n\n"
            "Aşağıdaki personelin işe giriş kaydı OMEHR personel panelinden oluşturulmuştur.\n\n"
            f"Personel: {name}\nMağaza: {magaza}\nBölge: {rec['region']}\n"
            f"Unvan: {title}\nDepartman / Norm Ailesi: {dept}\nİşe Giriş: {dt}\n"
            f"Açıklama: {desc or '-'}\n\n"
            "Aktif mevcut ve norm eksik/fazla hesapları bu kayıtla birlikte güncellenmiştir.\n"
            "İyi çalışmalar."
        )
    elif event == "CIKIS_GERI_ALINDI":
        subject = f"İşten Çıkış Geri Alındı | {name} | {magaza}"
        body = (
            "Merhaba,\n\n"
            "Daha önce bildirilen aşağıdaki işten çıkış kaydı GERİ ALINMIŞ ve personel "
            "YENİDEN AKTİF hale getirilmiştir — önceki işten çıkış bildirimini dikkate almayınız.\n\n"
            f"Personel: {name}\nMağaza: {magaza}\nBölge: {rec['region']}\n"
            f"Unvan: {title}\nDepartman / Norm Ailesi: {dept}\n\n"
            "Aktif mevcut ve norm eksik/fazla hesapları bu düzeltmeyle birlikte güncellenmiştir.\n"
            "İyi çalışmalar."
        )
    elif event == "ATAMA":
        onceki_pozisyon = str(person.get("Önceki Unvan") or "").strip()
        onceki_magaza = str(person.get("Önceki Mağaza") or "").strip()
        tarih = str(person.get("Atama Tarihi") or "").strip()
        subject = f"Atama / Görev Değişikliği Bildirimi | {name} | {magaza}"
        body = (
            "Merhaba,\n\n"
            f"Aşağıdaki personelin görev değişikliği OMEHR personel panelinden işlenmiştir. "
            "Resmi bildirim belgesi ektedir.\n\n"
            f"Personel: {name}\nÖnceki Görev: {onceki_pozisyon} — {onceki_magaza}\n"
            f"Yeni Görev: {title} — {magaza}\nAtama Tarihi: {tarih}\n"
            f"Açıklama: {desc or '-'}\n\n"
            "İyi çalışmalar."
        )
    else:
        dt = str(person.get("İşten Çıkış") or "").strip()
        reason = str(person.get("Çıkış Nedeni") or person.get("Çıkış Kodu") or "").strip()
        subject = f"İşten Çıkış Bildirimi | {name} | {magaza}"
        body = (
            "Merhaba,\n\n"
            "Aşağıdaki personelin işten çıkış kaydı OMEHR personel panelinden oluşturulmuştur.\n\n"
            f"Personel: {name}\nMağaza: {magaza}\nBölge: {rec['region']}\n"
            f"Unvan: {title}\nDepartman / Norm Ailesi: {dept}\nİşten Çıkış: {dt}\n"
            f"Çıkış Nedeni: {reason or '-'}\nAçıklama: {desc or '-'}\n\n"
            "Personel aktif mevcuttan çıkarılmış; norm eksik/fazla hesabı yeniden değerlendirilmiştir. "
            "Güncel raporlar eski personel adını göstermemesi için geçersiz kılınmıştır.\n"
            "İyi çalışmalar."
        )

    # DÜZELTME (performans — "mailler hızlı gitsin"): önceden bu çağrı
    # send_outlook()'u DOĞRUDAN, Streamlit isteği İÇİNDE çalıştırıyordu —
    # Outlook COM otomasyonu birkaç saniye sürebildiği için "Kaydet ve
    # Bildir" düğmesi o süre boyunca donmuş görünüyordu. Artık e-posta,
    # zaten sürekli çalışan arka plan worker'ına (worker.py) kuyruklanır;
    # düğme ANINDA yanıt verir, gönderim ~1 saniye içinde arka planda
    # gerçekleşir.
    tenant_id = ""
    try:
        from services.tenant_context import current_tenant_id
        tenant_id = current_tenant_id()
    except Exception:
        pass
    _enqueue_job("SEND_EMAIL", {
        "report_type": f"PERSONEL_{event}",
        "subject": subject, "body": body, "recipients": recipients,
        "attachments": attachments or [],
    }, tenant=tenant_id or "BASDAS")
    status = "QUEUED"
    return {"status": status, "subject": subject, **rec}
