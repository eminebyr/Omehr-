from __future__ import annotations

from services.settings import input_path

import argparse
import json
import re
from datetime import datetime

import pandas as pd

from services.outlook_adapter import send_outlook
from services.runtime_paths import code_root, runtime_root


def _input_file(): return input_path(runtime_root())
TEMPLATE_FILE = code_root() / "GUNLUK_SUBE_MAIL_METNI.txt"
def _log_file(): return runtime_root() / "logs" / "CURRENT_Gunluk_Sube_Mail_Log.json"
def _preview_file(): return runtime_root() / "logs" / "CURRENT_Gunluk_Sube_Mail_Onizleme.txt"

TOKEN_RE = re.compile(r"\{(MAGAZA|MAGAZA_ID|ALICI_ADI|TARIH|SAAT)\}", re.IGNORECASE)


def _text(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _yes(value: object) -> bool:
    return _text(value).casefold() in {"evet", "e", "yes", "y", "1", "true", "aktif"}


def _render(text: str, row: pd.Series, now: datetime) -> str:
    values = {
        "MAGAZA": _text(row.get("Mağaza")) or _text(row.get("Alıcı Adı")),
        "MAGAZA_ID": _text(row.get("MağazaID")),
        "ALICI_ADI": _text(row.get("Alıcı Adı")) or _text(row.get("Mağaza")) or "Yetkili",
        "TARIH": now.strftime("%d.%m.%Y"),
        "SAAT": now.strftime("%H:%M"),
    }
    return TOKEN_RE.sub(lambda match: values[match.group(1).upper()], text)


def _load_template() -> tuple[str, str]:
    if not TEMPLATE_FILE.is_file():
        raise FileNotFoundError(f"Mail metni bulunamadı: {TEMPLATE_FILE}")
    raw = TEMPLATE_FILE.read_text(encoding="utf-8-sig").strip()
    if not raw:
        raise ValueError("GUNLUK_SUBE_MAIL_METNI.txt boş bırakılamaz.")
    lines = raw.splitlines()
    first = lines[0].strip()
    if first.upper().startswith("KONU:"):
        subject = first.split(":", 1)[1].strip()
        body = "\n".join(lines[1:]).strip()
    else:
        subject = "Günlük Operasyon Bilgilendirmesi - {TARIH}"
        body = raw
    if not subject or not body:
        raise ValueError("TXT dosyasında konu ve mesaj metni bulunmalıdır.")
    return subject, body


def _load_recipients() -> pd.DataFrame:
    if not _input_file().is_file():
        raise FileNotFoundError(f"Input dosyası bulunamadı: {_input_file()}")
    frame = pd.read_excel(_input_file(), sheet_name="Sube_Mail_Listesi")
    required = {"Mağaza E-posta", "Aktif", "Günlük Gönderim"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError("Sube_Mail_Listesi eksik sütunlar: " + ", ".join(missing))
    active = frame[frame["Aktif"].map(_yes) & frame["Günlük Gönderim"].map(_yes)].copy()
    active["Mağaza E-posta"] = active["Mağaza E-posta"].map(_text)
    active = active[active["Mağaza E-posta"].str.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]
    active = active.drop_duplicates(subset=["Mağaza E-posta"], keep="first")
    if active.empty:
        raise ValueError("Günlük gönderime açık, geçerli e-posta adresli şube bulunamadı.")
    return active


def _write_json(records: list[dict]) -> None:
    _log_file().parent.mkdir(parents=True, exist_ok=True)
    _log_file().write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def run(*, dry_run: bool) -> dict:
    now = datetime.now()
    subject_template, body_template = _load_template()
    recipients = _load_recipients()
    records: list[dict] = []
    previews: list[str] = []
    sent = failed = 0

    for _, row in recipients.iterrows():
        address = _text(row.get("Mağaza E-posta"))
        subject = _render(subject_template, row, now)
        body = _render(body_template, row, now)
        record = {
            "time": now.isoformat(timespec="seconds"),
            "store_id": _text(row.get("MağazaID")),
            "store": _text(row.get("Mağaza")),
            "recipient_name": _text(row.get("Alıcı Adı")),
            "to": address,
            "subject": subject,
        }
        previews.append(
            f"ALICI: {address}\nMAĞAZA: {record['store']}\nKONU: {subject}\n\n{body}\n"
            + ("-" * 72)
        )
        if dry_run:
            record["status"] = "PREVIEW"
        else:
            transport = send_outlook(subject, body, [address], [])
            record["transport"] = transport
            if transport.startswith("SENT"):
                record["status"] = "SENT"
                sent += 1
            else:
                record["status"] = "FAILED"
                record["error"] = transport
                failed += 1
        records.append(record)

    _preview_file().parent.mkdir(parents=True, exist_ok=True)
    _preview_file().write_text("\n\n".join(previews), encoding="utf-8")
    _write_json(records)
    return {
        "status": "PREVIEW" if dry_run else ("SUCCESS" if failed == 0 else ("PARTIAL" if sent else "FAILED")),
        "recipient_count": len(records),
        "sent": sent,
        "failed": failed,
        "template": str(TEMPLATE_FILE),
        "preview": str(_preview_file()),
        "log": str(_log_file()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Günlük şube e-postalarını TXT metninden gönderir.")
    parser.add_argument("--dry-run", action="store_true", help="E-posta göndermeden alıcı ve metin önizlemesi üretir.")
    args = parser.parse_args()
    try:
        result = run(dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] in {"PREVIEW", "SUCCESS"} else 1
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "error_type": type(exc).__name__, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
