from __future__ import annotations

"""
TRANSFER İPTAL/YÖNLENDİRME FONKSİYONLARI (P2 — modülerleştirme, beşinci
adım)
=====================================================================
ÖNCEDEN web/app.py'de globals().get("sheets",{}) ile modül seviyesi
duruma dolaylı bağımlıydı — bu ayrı bir dosyaya taşınmayı GÜVENSİZ
kılıyordu (yeni modülün kendi boş global alanına bakardı, sessizce
yanlış/eksik alıcı listesi üretirdi). Önce sheets_param olarak AÇIK bir
parametreye çevrildi, TEST EDİLDİ, ancak SONRA buraya taşındı.
"""

from services.outlook_adapter import send_outlook
from services.transfer_lifecycle import cancel_transfer as lifecycle_cancel_transfer
from services.transfer_lifecycle import redirect_transfer as lifecycle_redirect_transfer
from services.web_runtime import connect_web_db as db, log_web_action as log

from web.accounts import transfer_recipients


def cancel_transfer_request(transfer_id, username, reason, account_frame, sheets_param=None):
    """Onaylanmış/bekleyen transferi geri alınabilir şekilde iptal eder ve mail gönderir."""
    def notifier(event,tid,row,note):
        recipients=transfer_recipients(account_frame,row,sheets_param or {})
        return send_outlook(
            f"ONAYLANAN TRANSFER İPTAL EDİLDİ #{tid}",
            (
                f"Personel: {row.get('person_name','')}\n"
                f"İptal edilen transfer: {row.get('source_store','')} -> {row.get('target_store','')}\n"
                f"Gerçek unvan: {row.get('current_title','')}\n"
                f"İptal eden: {username}\n"
                f"İptal gerekçesi: {note}\n"
                f"Fact_Mevcut durumu: {row.get('fact_status','')}"
            ),
            recipients,
        )
    return lifecycle_cancel_transfer(
        db,int(transfer_id),username,reason,notifier,
        lambda user,action,detail: log(user,action,detail),
    )

def redirect_transfer_request(transfer_id, username, new_store, new_title, new_region, reason, account_frame, sheets_param=None):
    """Eski talebi iptal edip aynı personel için yeni hedefe bağlı talep oluşturur."""
    def notifier(event,tid,row,note):
        recipients=transfer_recipients(account_frame,row,sheets_param or {})
        if event=="CANCEL":
            return send_outlook(
                f"ONAYLANAN TRANSFER İPTAL EDİLDİ #{tid}",
                (
                    f"Personel: {row.get('person_name','')}\n"
                    f"İptal edilen transfer: {row.get('source_store','')} -> {row.get('target_store','')}\n"
                    f"Gerçek unvan: {row.get('current_title','')}\n"
                    f"İptal eden: {username}\nİptal gerekçesi: {note}"
                ),recipients,
            )
        return send_outlook(
            f"YENİ HEDEFE TRANSFER TALEBİ #{tid}",
            (
                f"Önceki talep: #{transfer_id} iptal edildi.\n"
                f"Personel: {row.get('person_name','')}\n"
                f"Yeni transfer: {row.get('source_store','')} -> {row.get('target_store','')}\n"
                f"Gerçek unvan: {row.get('current_title','')}\n"
                f"Hedef departman/unvan: {row.get('target_title','')}\n"
                f"Gerekçe: {note}"
            ),recipients,
        )
    return lifecycle_redirect_transfer(
        db,int(transfer_id),username,new_store,new_title,new_region,reason,notifier,
        lambda user,action,detail: log(user,action,detail),
    )

