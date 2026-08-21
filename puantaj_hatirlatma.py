from __future__ import annotations

"""
GÜNLÜK PUANTAJ HATIRLATMA MODÜLÜ
====================================
Her sabah saat 09:00'de, Sube_Mail_Listesi'nde "Aktif=Evet" ve
"Günlük Gönderim=Evet" olan HER mağazaya, o günün puantaj bildirimini
İK'ya iletmelerini isteyen otomatik bir e-posta gönderir. Metin,
kullanıcı (İK) tarafından onaylanmış sabit bir şablondur.

Her mağazaya AYRI bir e-posta gider (alıcılar birbirini görmez) — bu,
Şubelere Toplu Mail özelliğinin arkasındaki mantıkla aynıdır.

DÜZELTME (çok kiracılı SaaS): Bu modül önceden (1) yalnız Excel modunu
destekliyordu, (2) e-posta gövdesinde SABİT bir firmanın adresini
ve imzasında SABİT bir firma adını
("Başdaş Market") koda gömüyordu. ÇOK KİRACILI bir SaaS'ta bu, HER
kiracının mağazalarının, kendileriyle hiçbir ilgisi olmayan başka bir
firmanın İK adresine puantaj göndermesi TALİMATINI içeren bir e-posta
almasına yol açardı — hem yanlış hem veri gizliliği açısından riskli.
Artık: (a) hem Excel hem veritabanı modu destekleniyor, (b) hedef
adres kiracının KENDİ Mail_Listesi'nden (ADMIN/İK Direktörü rolündeki
aktif hesaplar) dinamik olarak belirleniyor, (c) imza jenerik/marka
bağımsız.
"""

from datetime import datetime

import os
import pandas as pd

from services.mail_idempotency import send_idempotent
from services.runtime_paths import runtime_root
from services.settings import input_path

def _input():
    return input_path(runtime_root())

KONU_SABLONU = "Günlük Puantaj Bildirimi Hatırlatması — {tarih}"

GOVDE_SABLONU = """Çok değerli çalışma arkadaşımız merhaba,

Bu otomatik hatırlatma, günlük personel puantaj bildiriminizin zamanında ve eksiksiz iletilmesi amacıyla gönderilmektedir.

Mağazanızda görevli personelin puantaj kayıtlarının (giriş-çıkış, izin, rapor, devamsızlık bilgileri dahil) var ise ekleriyle birlikte İnsan Kaynakları Direktörlüğü'ne{hedef_ek} en geç bugün saat 14:00'ye kadar iletilmesini rica ederiz.

Zamanında ve doğru puantaj bildirimi; norm kadro hesaplamalarının, ücret ve fazla mesai işlemlerinin sağlıklı yürütülmesi açısından büyük önem taşımaktadır.

Herhangi bir sorunuz veya bildirim sürecinde karşılaştığınız bir aksaklık olması durumunda İnsan Kaynakları Direktörlüğü ile iletişime geçebilirsiniz.

İlginiz ve iş birliğiniz için teşekkür ederiz.

Saygılarımızla,
İnsan Kaynakları Direktörlüğü

Bu e-posta, OMEHR İş Gücü Yönetimi ve Karar Destek Platformu tarafından her sabah saat 09:00'de otomatik olarak gönderilmektedir."""


def _db_modu() -> bool:
    return os.environ.get("OMEHR_INPUT_SOURCE", "excel").strip().lower() == "db"


def _read_sheet(sheet_adi: str) -> pd.DataFrame:
    if _db_modu():
        from services.input_data_access import read_sheet
        return read_sheet(sheet_adi)
    try:
        from services.cached_excel_reader import read_sheet_cached
        return read_sheet_cached(_input(), sheet_adi)
    except Exception:
        return pd.DataFrame()


def _ik_hedef_adres_metni() -> str:
    """Kiracının KENDİ Mail_Listesi'ndeki aktif ADMIN/İK Direktörü
    hesabının e-postasını gövdeye ekler (varsa) — sabit adres YOKTUR."""
    try:
        from web.accounts import admin_copy_email_list
        accounts = _read_sheet("Mail_Listesi")
        if "Aktif" in accounts.columns:
            accounts = accounts[accounts["Aktif"].astype(str).str.strip().str.casefold().isin(
                {"evet", "e", "yes", "1", "true"}
            )]
        emails = admin_copy_email_list(accounts)
        if emails:
            return f" ({emails[0]})"
    except Exception:
        pass
    return ""


def _alici_listesi() -> pd.DataFrame:
    branch = _read_sheet("Sube_Mail_Listesi")
    if branch.empty:
        return pd.DataFrame()
    email_col = next((c for c in ("Mağaza E-posta", "E-posta", "Email") if c in branch.columns), None)
    if email_col is None:
        return pd.DataFrame()
    if "Aktif" in branch.columns:
        branch = branch[branch["Aktif"].astype(str).str.strip().str.casefold() == "evet"]
    if "Günlük Gönderim" in branch.columns:
        branch = branch[branch["Günlük Gönderim"].astype(str).str.strip().str.casefold() == "evet"]
    branch = branch[branch[email_col].astype(str).str.contains("@", na=False)]
    branch = branch[~branch[email_col].astype(str).str.contains("dummy.basdas.local", case=False, na=False)]
    branch = branch.rename(columns={email_col: "_email"})
    return branch


def gunluk_puantaj_hatirlatma_gonder() -> dict:
    """Tüm uygun mağazalara puantaj hatırlatma e-postası gönderir.
    Her mağaza için ayrı sonuç (SENT/FAILED/SKIPPED) döndürür."""
    tarih = datetime.now().strftime("%d.%m.%Y")
    konu = KONU_SABLONU.format(tarih=tarih)
    govde = GOVDE_SABLONU.format(hedef_ek=_ik_hedef_adres_metni())

    alicilar = _alici_listesi()
    sonuclar = []
    for _, r in alicilar.iterrows():
        magaza = r.get("Mağaza", "")
        email = r.get("_email", "")
        durum = send_idempotent("PUANTAJ_HATIRLATMA", konu, govde, [email])
        sonuclar.append({"Mağaza": magaza, "E-posta": email, "Durum": durum})

    ozet = {
        "tarih": tarih,
        "toplam_magaza": len(sonuclar),
        "basarili": sum(1 for s in sonuclar if str(s["Durum"]).startswith("SENT")),
        "basarisiz": sum(1 for s in sonuclar if str(s["Durum"]).startswith("FAILED")),
        "detay": sonuclar,
    }
    return ozet
