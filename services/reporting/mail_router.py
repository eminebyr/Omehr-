from __future__ import annotations

"""MAIL ROUTER — merkezi alıcı çözümleme (Madde 30-31).

Bu modül YENİ bir alıcı-hesaplama mantığı YAZMAZ — mevcut, halihazırda
test edilmiş fonksiyonları (web/accounts.py, services/personnel_
notifications.py) TEK bir arayüz altında SARMALAR:

    resolve_recipients(event_type="COMPANY_NORM_REPORT", scope="ALL")
    resolve_recipients(event_type="REGION_NORM_REPORT", scope="ERTAN")
    resolve_recipients(event_type="ROTATION", source_store="M001", target_store="M032")

Madde 31 (abonelik modeli): Mail_Listesi'nde Norm_Genel/AI_Genel/
Norm_Bolge/Rotasyon/Atama/Ise_Giris/Isten_Cikis/Transfer gibi boolean
abonelik sütunları VARSA, sonuç bu sütunlara göre İNCE AYARLANIR
(abone olmayan bir yönetim/İK hesabı o türden mail almaz). Sütunlar
YOKSA (mevcut, çoğu kurulumda olduğu gibi) mevcut role-bazlı davranışa
sorunsuzca DÜŞÜLÜR — bu yüzden Excel şeması DEĞİŞTİRİLMEDEN de çalışır.
"""

from pathlib import Path

import pandas as pd

EVENT_SUBSCRIPTION_COLUMN = {
    "COMPANY_NORM_REPORT": "Norm_Genel",
    "COMPANY_AI_REPORT": "AI_Genel",
    "REGION_NORM_REPORT": "Norm_Bolge",
    "ROTATION": "Rotasyon",
    "APPOINTMENT": "Atama",
    "ISE_GIRIS": "Ise_Giris",
    "ISTEN_CIKIS": "Isten_Cikis",
    "TRANSFER": "Transfer",
}


def _apply_subscription_filter(recipients: list[str], account_frame: pd.DataFrame, event_type: str) -> list[str]:
    """Abonelik sütunu VARSA ve bir alıcının o sütunda AÇIKÇA False/
    Hayır/0 değeri VARSA, o alıcıyı listeden çıkarır. Sütun yoksa VEYA
    alıcı için değer boşsa (varsayılan: abone), dokunulmaz — bu, mevcut
    kurulumlarla geriye dönük tam uyumluluk sağlar."""
    kolon = EVENT_SUBSCRIPTION_COLUMN.get(event_type)
    if not kolon or account_frame is None or account_frame.empty or kolon not in account_frame.columns:
        return recipients
    email_col = next((c for c in ("E-posta", "Email") if c in account_frame.columns), None)
    if not email_col:
        return recipients
    hayir_degerleri = {"hayır", "hayir", "false", "0", "no"}
    abone_olmayanlar = set()
    for _, row in account_frame.iterrows():
        deger = str(row.get(kolon, "")).strip().casefold()
        if deger in hayir_degerleri:
            e = str(row.get(email_col, "")).strip().casefold()
            if e:
                abone_olmayanlar.add(e)
    if not abone_olmayanlar:
        return recipients
    return [r for r in recipients if str(r).strip().casefold() not in abone_olmayanlar]


def resolve_recipients(*, event_type: str, scope: str = "", sheets: dict | None = None,
                        input_path: Path | None = None, **kwargs) -> list[str]:
    """Şartnamedeki TEK, merkezi alıcı çözümleyici arayüzü.

    event_type: COMPANY_NORM_REPORT | COMPANY_AI_REPORT | REGION_NORM_REPORT |
                ROTATION | APPOINTMENT | ISE_GIRIS | ISTEN_CIKIS | TRANSFER
    scope: REGION_NORM_REPORT için bölge adı; COMPANY_* için "ALL"
    kwargs: ROTATION/TRANSFER için source_store/target_store, ISE_GIRIS/
            ISTEN_CIKIS için magaza/magaza_id.
    """
    from web.accounts import accounts, region_email_list, admin_copy_email_list, transfer_recipients

    sheets = sheets or {}
    acc = accounts(sheets)

    if event_type in ("COMPANY_NORM_REPORT", "COMPANY_AI_REPORT"):
        alicilar = admin_copy_email_list(acc)
    elif event_type == "REGION_NORM_REPORT":
        # DÜZELTME (Madde 29): bölge müdürüne şirket geneli rapor
        # OTOMATİK gitmemeli — yalnız KENDİ bölgesi. İK'nın da bölge
        # raporlarını görmesi gerekiyorsa admin_copy_email_list zaten
        # ayrıca eklenebilir; burada BİLİNÇLİ olarak yalnız bölge
        # e-postaları döner (şartname Madde 25: "sadece ilgili Bölge
        # Müdürü + gerekli İK").
        alicilar = list(dict.fromkeys(region_email_list(acc, scope) + admin_copy_email_list(acc)))
    elif event_type in ("ROTATION", "TRANSFER"):
        row = {
            "region": kwargs.get("source_region", ""), "target_region": kwargs.get("target_region", ""),
            "source_store": kwargs.get("source_store", ""), "target_store": kwargs.get("target_store", ""),
        }
        alicilar = transfer_recipients(acc, row, sheets)
    elif event_type in ("ISE_GIRIS", "ISTEN_CIKIS", "APPOINTMENT"):
        from services.personnel_notifications import personnel_event_recipients
        sonuc = personnel_event_recipients(
            input_path, kwargs.get("magaza", ""), kwargs.get("magaza_id", ""), extra=kwargs.get("extra"),
        )
        alicilar = sonuc.get("recipients", [])
    else:
        raise ValueError(f"Bilinmeyen event_type: {event_type}")

    alicilar = list(dict.fromkeys(a for a in alicilar if a))
    return _apply_subscription_filter(alicilar, acc, event_type)
