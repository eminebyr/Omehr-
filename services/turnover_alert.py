from __future__ import annotations

"""Yüksek turnover riski taşıyan mağaza-unvan kombinasyonları için otomatik
İK/bölge uyarısı.

BOŞLUK: services/workforce_forecast.py her rapor turunda (main.py üzerinden)
OMEHR_Magaza_Unvan_Isgucu_Tahmini.xlsx dosyasını üretiyor ve bu dosya
turnover riski için "Turnover Riski FTE", "Tahmin Güveni %" ve "Turnover
Veri Durumu" gibi zengin sütunlar içeriyor — ama bu YALNIZ pasif bir rapor
dosyası olarak kalıyordu, kimseye otomatik gitmiyordu. (Gerçekleşmiş işe
giriş/çıkışlar için services/personnel_notifications.py zaten mail atıyor;
ama "önden risk uyarısı" için karşılık YOKTU.) Bu modül o boşluğu kapatır:
taze üretilen tahmin dosyasını tarar, eşik üstü satırları toplar, İK/admin +
ilgili bölge sorumlularına (personnel_notifications.py ile AYNI alıcı/kuyruk
deseni kullanılarak) özet bir uyarı maili kuyruklar.

Yalnızca gerçek gözleme dayanan satırlar dikkate alınır ("Turnover Veri
Durumu" in {Yüksek, Orta, Düşük}) — "Varsayılan" (gözlem yok) satırlar
asılsız alarm üretmesin diye hariç tutulur; bu, workforce_forecast.py'nin
resmî kadroya etkiyi de aynı koşulla sınırlayan mantığıyla tutarlıdır.

Eşikler ortam değişkenleriyle özelleştirilebilir:
  OMEHR_TURNOVER_ALERT_HORIZON        -> taranacak ufuk (gün), varsayılan 90
  OMEHR_TURNOVER_ALERT_MIN_FTE        -> "Turnover Riski FTE" alt sınırı, varsayılan 0.5
  OMEHR_TURNOVER_ALERT_MIN_CONFIDENCE -> "Tahmin Güveni %" alt sınırı, varsayılan 35
"""

import os
from pathlib import Path
from typing import Any

import pandas as pd

from services.job_queue import enqueue as _enqueue_job
from services.workforce_forecast import OUTPUT_FILE_NAME
from web.accounts import admin_copy_email_list, region_email_list
from web.formatting import norm_text

SHEET_NAME = "Mağaza_Unvan_Tahmini"
REPORT_TYPE = "TURNOVER_RISK_ALERT"


def _forecast_path(outdir: Path) -> Path:
    return Path(outdir) / OUTPUT_FILE_NAME


def _thresholds() -> dict[str, float]:
    def _num(name: str, default: float) -> float:
        try:
            return float(os.getenv(name, default))
        except (TypeError, ValueError):
            return default

    return {
        "horizon": _num("OMEHR_TURNOVER_ALERT_HORIZON", 90),
        "min_fte": _num("OMEHR_TURNOVER_ALERT_MIN_FTE", 0.5),
        "min_confidence": _num("OMEHR_TURNOVER_ALERT_MIN_CONFIDENCE", 35),
    }


def high_risk_rows(outdir: Path, thresholds: dict[str, float] | None = None) -> pd.DataFrame:
    """Eşik üstü, gözleme dayalı turnover riski taşıyan satırları döner.

    Dosya yoksa veya beklenen sayfa/sütunlar eksikse sessizce boş DataFrame
    döner — bu adım asla ana rapor motorunu (main.py) durdurmamalı.
    """
    path = _forecast_path(outdir)
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_excel(path, sheet_name=SHEET_NAME, dtype=object)
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return df

    th = thresholds or _thresholds()
    horizon = pd.to_numeric(df.get("Tahmin Ufku Gün"), errors="coerce")
    risk_fte = pd.to_numeric(df.get("Turnover Riski FTE"), errors="coerce")
    confidence = pd.to_numeric(df.get("Tahmin Güveni %"), errors="coerce")
    veri_durumu = df.get("Turnover Veri Durumu", pd.Series(dtype=object))

    mask = (
        (horizon == th["horizon"])
        & veri_durumu.isin(["Yüksek", "Orta", "Düşük"])
        & (risk_fte >= th["min_fte"])
        & (confidence >= th["min_confidence"])
    )
    out = df.loc[mask.fillna(False)].copy()
    if out.empty:
        return out
    out["Turnover Riski FTE"] = pd.to_numeric(out["Turnover Riski FTE"], errors="coerce")
    return out.sort_values("Turnover Riski FTE", ascending=False)


def _format_body(rows: pd.DataFrame, th: dict[str, float]) -> str:
    lines = [
        "Merhaba,",
        "",
        f"OMEHR İş Gücü Tahmini motoru, {int(th['horizon'])} günlük ufukta gerçek gözleme "
        "dayalı (Yüksek/Orta/Düşük veri durumu) yüksek turnover riski taşıyan aşağıdaki "
        f"mağaza-unvan kombinasyonlarını tespit etti (eşik: Turnover Riski FTE ≥ "
        f"{th['min_fte']:g}, Tahmin Güveni % ≥ {th['min_confidence']:g}).",
        "",
    ]
    for _, r in rows.iterrows():
        oran = pd.to_numeric(r.get("Beklenen Turnover Oranı (90G)"), errors="coerce") or 0.0
        fte = pd.to_numeric(r.get("Turnover Riski FTE"), errors="coerce") or 0.0
        guven = pd.to_numeric(r.get("Tahmin Güveni %"), errors="coerce") or 0.0
        lines.append(
            f"- {r.get('Mağaza', '-')} / {r.get('Unvan', '-')}: "
            f"Turnover Riski FTE={fte:.2f}, Beklenen Oran (90G)={oran:.0%}, "
            f"Veri Durumu={r.get('Turnover Veri Durumu', '-')}, Tahmin Güveni={guven:.0f}%"
        )
    lines += [
        "",
        "Bu, resmî yönetim normunu DEĞİŞTİRMEYEN bir karar destek uyarısıdır; işe alım/"
        "transfer planlaması için erken sinyal amaçlıdır. Detaylar için İş Gücü Tahmini "
        "raporundaki 'Mağaza_Unvan_Tahmini' sayfasına bakınız.",
        "",
        "İyi çalışmalar.",
    ]
    return "\n".join(lines)


def _recipients(sheets: dict[str, pd.DataFrame], rows: pd.DataFrame) -> list[str]:
    accounts = sheets.get("Mail_Listesi", pd.DataFrame()).copy()
    if "Aktif" in accounts.columns:
        accounts = accounts[
            accounts["Aktif"].astype(str).map(norm_text).isin({"EVET", "E", "YES", "1", "TRUE", "AKTIF"})
        ]

    recipients = list(admin_copy_email_list(accounts))

    dim = sheets.get("Dim_Magaza", pd.DataFrame())
    if not dim.empty and "MağazaID" in dim.columns and "Bölge Sorumlusu" in dim.columns and "MağazaID" in rows.columns:
        wanted_ids = set(rows["MağazaID"].astype(str).str.strip())
        matched = dim[dim["MağazaID"].astype(str).str.strip().isin(wanted_ids)]
        regions = {str(v).strip() for v in matched["Bölge Sorumlusu"].dropna() if str(v).strip()}
        for region in regions:
            recipients += region_email_list(accounts, region)

    seen: set[str] = set()
    normalized: list[str] = []
    for address in recipients:
        address = str(address).strip()
        if "@" not in address:
            continue
        key = address.casefold()
        if key not in seen:
            seen.add(key)
            normalized.append(address)
    return normalized


def run(sheets: dict[str, pd.DataFrame], outdir: Path) -> dict[str, Any]:
    """Taze üretilen İş Gücü Tahmini dosyasını tarar; eşik üstü satır varsa
    İK/admin + ilgili bölge sorumlularına özet uyarı maili kuyruklar.

    main.py içinde workforce_forecast.run()'DAN HEMEN SONRA (aynı dosyaya
    bağımlı olduğu için) çağrılmalıdır. Hatalar ana rapor motorunu asla
    durdurmamalı — çağıran taraf (main.py) try/except ile sarmalar.
    """
    th = _thresholds()
    rows = high_risk_rows(outdir, th)
    if rows.empty:
        return {"status": "NO_RISK", **th}

    recipients = _recipients(sheets, rows)
    if not recipients:
        return {"status": "SKIPPED_NO_RECIPIENTS", "rows": len(rows), **th}

    tenant_id = ""
    try:
        from services.tenant_context import current_tenant_id
        tenant_id = current_tenant_id()
    except Exception:
        pass

    subject = f"Turnover Riski Uyarısı | {len(rows)} mağaza-unvan kombinasyonu | {int(th['horizon'])} gün ufuk"
    body = _format_body(rows, th)
    # DÜZELTME: job_type worker.py'nin dispatch ettiği "SEND_EMAIL" olmalı
    # (services/personnel_notifications.py ile AYNI desen) — REPORT_TYPE
    # yalnız payload içindeki "report_type" alanına, idempotency anahtarının
    # bir parçası olarak gider. job_type=REPORT_TYPE yazılsaydı worker.py
    # bunu tanımayıp "Desteklenmeyen görev" hatasıyla FAILED düşürürdü.
    _enqueue_job("SEND_EMAIL", {
        "report_type": REPORT_TYPE,
        "subject": subject, "body": body, "recipients": recipients, "attachments": [],
    }, tenant=tenant_id or "OMEHR")
    return {"status": "QUEUED", "rows": len(rows), "recipients": len(recipients), **th}
