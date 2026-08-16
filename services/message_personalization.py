from __future__ import annotations

import json
from services.runtime_paths import code_root
from typing import Any
from services.safe_exec import log_swallowed

ROOT = code_root()


def text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def ai_enabled() -> bool:
    path = ROOT / "config_features.json"
    try:
        return bool(json.loads(path.read_text(encoding="utf-8")).get("ai_enabled", True))
    except Exception as _exc:
        log_swallowed("services.message_personalization.ai_enabled: beklenmeyen hata", _exc)
        return True


def recipient_name(row: Any) -> str:
    """Mail_Listesi satırını kurumsal hitap adına dönüştürür.

    DÜZELTME (çok kiracılı SaaS): önceden burada belirli bir gerçek
    kişinin adı/e-postası ("Ömer Arasın", "M. Feyzi Başdaş") koda GÖMÜLÜ
    özel durum olarak işleniyordu — bu, ÇOK KİRACILI bir SaaS'ta her
    firmanın kendi "ik1" kullanıcısını veya CEO'sunu yanlışlıkla bu
    belirli kişi olarak adlandırırdı. Artık yalnız verinin KENDİSİNDEKİ
    (Sorumlu/Bölge alanı) genel, kiracıdan bağımsız bilgi kullanılır.
    """
    responsible = text(row.get("Sorumlu", ""))
    region = text(row.get("Bölge", ""))
    if responsible.casefold() == "ceo" or region.casefold() == "ceo":
        return "CEO"
    return responsible or region or "Yetkili"


def salutation(row: Any) -> str:
    return f"Sayın {recipient_name(row)}"


def is_company_owner(row: Any) -> bool:
    return recipient_name(row).casefold() == "ceo"


def is_executive_audience(row: Any) -> bool:
    """Şirket sahibi, GMY ve İK Direktörü için genişletilmiş yönetici raporu."""
    username = text(row.get("Web Kullanıcı", "")).casefold()
    return is_company_owner(row) or username in {"admin", "ik1"}


def product_label() -> str:
    return (
        "OMEHR İş Gücü Yönetimi ve Karar Destek Platformu"
        if ai_enabled()
        else "OMEHR İş Gücü Yönetimi ve Karar Destek Platformu"
    )


def report_scope_text(row: Any) -> str:
    region = text(row.get("Bölge", ""))
    return "şirket geneli" if is_executive_audience(row) or region.upper() in {"TÜMÜ", "TUMU", "ALL"} else f"{region} bölgesi"
