from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Callable


Notifier = Callable[[str, int, dict, str], str]
Logger = Callable[[str, str, str], None]


def cancel_transfer(
    connection_factory,
    transfer_id: int,
    username: str,
    reason: str,
    notifier: Notifier,
    logger: Logger,
) -> tuple[dict, str]:
    if not str(reason).strip():
        raise ValueError("İptal gerekçesi zorunludur.")
    con=connection_factory(); con.row_factory=sqlite3.Row
    record=con.execute("SELECT * FROM transfers WHERE id=?",(int(transfer_id),)).fetchone()
    if record is None:
        con.close(); raise ValueError("Transfer talebi bulunamadı.")
    row=dict(record)
    if row.get("status")=="İptal Edildi":
        con.close(); raise ValueError("Transfer talebi zaten iptal edilmiş.")
    now=datetime.now().isoformat(timespec="seconds")
    fact_status=(
        "İptal - Fact_Mevcut Geri Alma/Güncelleme Bekleniyor"
        if row.get("status")=="İK Onayladı" or row.get("fact_status")=="Tamamlandı"
        else "İptal Edildi"
    )
    con.execute(
        """UPDATE transfers SET status='İptal Edildi',cancel_reason=?,cancelled_by=?,
           cancelled_at=?,fact_status=?,rotation_status='CANCELLED',updated_at=? WHERE id=?""",
        (reason,username,now,fact_status,now,int(transfer_id)),
    )
    con.commit(); con.close()
    sent=notifier("CANCEL",int(transfer_id),{**row,"fact_status":fact_status},reason)
    con=connection_factory(); con.execute(
        "UPDATE transfers SET cancellation_outlook_status=?,updated_at=? WHERE id=?",
        (sent,now,int(transfer_id)),
    ); con.commit(); con.close()
    logger(username,"TRANSFER_CANCEL",f"{transfer_id}: {reason}")
    return row,sent


def redirect_transfer(
    connection_factory,
    transfer_id: int,
    username: str,
    new_store: str,
    new_title: str,
    new_region: str,
    reason: str,
    notifier: Notifier,
    logger: Logger,
) -> tuple[int, str]:
    old,_=cancel_transfer(
        connection_factory,transfer_id,username,
        f"Başka hedefe yönlendirildi. {reason}",notifier,logger,
    )
    now=datetime.now().isoformat(timespec="seconds")
    con=connection_factory()
    cur=con.execute(
        """INSERT INTO transfers(
           created_at,created_by,region,source_store,target_store,person_id,person_name,
           current_title,target_title,target_region,planned_date,reason,status,fact_status,
           outlook_status,updated_at,supersedes_id
           ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            now,username,old.get("region"),old.get("source_store"),new_store,
            old.get("person_id"),old.get("person_name"),old.get("current_title"),new_title,
            new_region,old.get("planned_date"),reason,"Bölge Müdürleri Onayı Bekliyor",
            "Bekliyor","PENDING",now,int(transfer_id),
        ),
    )
    new_id=int(cur.lastrowid)
    con.execute(
        "UPDATE transfers SET superseded_by_id=?,updated_at=? WHERE id=?",
        (new_id,now,int(transfer_id)),
    )
    con.commit(); con.close()
    new_row={**old,"id":new_id,"target_store":new_store,"target_title":new_title,"target_region":new_region}
    sent=notifier("REDIRECT",new_id,new_row,reason)
    con=connection_factory(); con.execute(
        "UPDATE transfers SET outlook_status=?,updated_at=? WHERE id=?",(sent,now,new_id)
    ); con.commit(); con.close()
    logger(username,"TRANSFER_REDIRECT",f"{transfer_id} -> {new_id}: {new_store}")
    return new_id,sent
