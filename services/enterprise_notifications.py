from __future__ import annotations
import json, mimetypes, smtplib
from email.message import EmailMessage
from pathlib import Path
import requests
ROOT = Path(__file__).resolve().parents[1]

def cfg(): return json.loads((ROOT/'config_integrations.json').read_text(encoding='utf-8'))['notifications']

def send_teams(message: str):
    c=cfg()
    if not c.get('teams_enabled') or not c.get('teams_webhook_url'): return False,'Teams kapalı veya webhook tanımlı değil.'
    r=requests.post(c['teams_webhook_url'],json={'text':message},timeout=30); r.raise_for_status(); return True,'Teams bildirimi gönderildi.'

def send_outlook(subject: str, body: str):
    c=cfg()
    if not c.get('outlook_enabled'): return False,'Outlook e-posta gönderimi kapalı.'
    msg=EmailMessage(); msg['Subject']=subject; msg['From']=c['from'] or c['smtp_username']; msg['To']=c['to']; msg.set_content(body)
    attachments=[]
    if c.get('send_pdf'): attachments.append(ROOT/'output'/'BASDAS_Yonetici_Raporu.pdf')
    if c.get('send_excel'): attachments.append(ROOT/'output'/'BASDAS_Executive_Data.xlsx')
    for p in attachments:
        if p.exists():
            typ,_=mimetypes.guess_type(str(p)); main,sub=(typ or 'application/octet-stream').split('/',1)
            msg.add_attachment(p.read_bytes(),maintype=main,subtype=sub,filename=p.name)
    with smtplib.SMTP(c['smtp_host'],int(c.get('smtp_port',587)),timeout=45) as s:
        s.starttls(); s.login(c['smtp_username'],c['smtp_password']); s.send_message(msg)
    return True,'Outlook e-posta raporu gönderildi.'
