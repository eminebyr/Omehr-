from __future__ import annotations

import os
import re
import smtplib
import sys
from email.message import EmailMessage
from mimetypes import guess_type
from pathlib import Path
from services.safe_exec import log_swallowed


def _send_smtp(subject: str, body: str, recipients: list[str], files: list[Path]) -> str:
    host = os.getenv("BASDAS_SMTP_HOST", "").strip()
    sender = os.getenv("BASDAS_SMTP_FROM", "").strip()
    if not host or not sender:
        return "SKIPPED: SMTP yapılandırılmadı"
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, sender, ", ".join(recipients)
    msg.set_content(body)
    for path in files:
        mime, _ = guess_type(path.name)
        maintype, subtype = (mime or "application/octet-stream").split("/", 1)
        msg.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name)
    port = int(os.getenv("BASDAS_SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=30) as server:
        if os.getenv("BASDAS_SMTP_TLS", "1") == "1":
            server.starttls()
        username = os.getenv("BASDAS_SMTP_USER", "").strip()
        password = os.getenv("BASDAS_SMTP_PASSWORD", "")
        if username:
            server.login(username, password)
        server.send_message(msg)
    return "SENT: SMTP"


def send_outlook(subject: str, body: str, recipients: list[str], attachments=None) -> str:
    """Windows'ta Outlook, diğer platformlarda yapılandırılmış SMTP kullanır."""
    files = [Path(x) for x in (attachments or []) if Path(x).is_file()]
    normalized = []
    for recipient in recipients or []:
        normalized.extend(x.strip() for x in re.split(r"[;,]", str(recipient)) if x.strip())
    normalized = list(dict.fromkeys(normalized))
    if os.getenv("BASDAS_MAIL_DRY_RUN", "0") == "1":
        return f"SENT: DRY_RUN ({len(normalized)} alıcı, {len(files)} ek)"
    if sys.platform != "win32":
        try:
            return _send_smtp(subject, body, normalized, files)
        except Exception as exc:
            log_swallowed("services.outlook_adapter.send_outlook: beklenmeyen hata", exc)
            return f"FAILED: SMTP: {exc}"
    try:
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)
        mail.To = ";".join(normalized)
        mail.Subject = subject
        mail.Body = body
        for attachment in files:
            if attachment.stat().st_size <= 0:
                raise ValueError(f"Boş ek dosyası: {attachment.name}")
            mail.Attachments.Add(str(attachment.resolve()))
        if not mail.Recipients.ResolveAll():
            raise ValueError("Outlook alıcıları doğrulanamadı")
        mail.Send()
        return "SENT"
    except Exception as exc:
        log_swallowed("services.outlook_adapter.send_outlook: beklenmeyen hata", exc)
        return f"FAILED: {exc}"
