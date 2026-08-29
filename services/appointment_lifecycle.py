from __future__ import annotations

"""Atama (appointment) yaşam döngüsü — Madde 16-17.

Her atamada benzersiz ATAMA_NO üretir. Atama tarihi bugün/geçmişse
Fact_Mevcut HEMEN güncellenir (APPLIED). Gelecekteyse yalnız PLANNED
olarak kaydedilir; Fact_Mevcut'a DOKUNULMAZ. apply_due_appointments()
her main.py çalıştırmasında (ve web açılışında) tarihi gelmiş PLANNED
atamaları uygular.
"""

from datetime import date, datetime
from pathlib import Path
import sqlite3

import pandas as pd

from services.web_runtime import connect_web_db


def yeni_atama_no() -> str:
    """Örnek: ATM-20260810-00042 (gün içi artan sıra numarasıyla)."""
    bugun = datetime.now().strftime("%Y%m%d")
    con = connect_web_db()
    con.row_factory = sqlite3.Row
    try:
        satir = con.execute(
            "SELECT COUNT(*) AS n FROM appointments WHERE atama_no LIKE ?", (f"ATM-{bugun}-%",)
        ).fetchone()
        sira = int(satir["n"]) + 1
    finally:
        con.close()
    return f"ATM-{bugun}-{sira:05d}"


def create_appointment(*, input_path: Path, root: Path, person_name: str, staff_index, staff_df,
                        magaza_df, unvan_df, source_store: str, source_title: str,
                        target_store: str, target_title: str, planned_date, created_by: str) -> dict:
    """Atamayı kaydeder. Tarih bugün/geçmişse ANINDA Fact_Mevcut'a
    uygulanır (APPLIED); gelecekteyse yalnız PLANNED olarak durur."""
    if hasattr(planned_date, "isoformat"):
        planned_date_str = planned_date.isoformat()
        planned_date_obj = planned_date if isinstance(planned_date, date) else planned_date.date()
    else:
        planned_date_obj = pd.to_datetime(planned_date).date()
        planned_date_str = planned_date_obj.isoformat()

    atama_no = yeni_atama_no()
    durum = "APPLIED" if planned_date_obj <= date.today() else "PLANNED"

    if durum == "APPLIED":
        # DÜZELTME: önceden bu dal yalnız izleme kaydı ekliyordu,
        # Fact_Mevcut'u GERÇEKTEN güncellemiyordu — "APPLIED" durumu
        # hesaplanıyordu ama fiilen uygulanmıyordu. Artık gerçekten
        # uygulanıyor (aynı taze-oku + kilit korumasını update_personnel
        # zaten sağlıyor).
        from services.personnel_exit import update_personnel
        magaza_id_satir = magaza_df.loc[magaza_df["Mağaza"].astype(str) == str(target_store), "MağazaID"]
        unvan_id_satir = unvan_df.loc[unvan_df["Unvan"].astype(str) == str(target_title), "UnvanID"]
        update_personnel(
            input_path=input_path, root=root, staff=staff_df, index=staff_index,
            guncellemeler={
                "Mağaza": target_store,
                "MağazaID": magaza_id_satir.iloc[0] if not magaza_id_satir.empty else None,
                "Unvan": target_title,
                "UnvanID": unvan_id_satir.iloc[0] if not unvan_id_satir.empty else None,
                # Norm motorunun resmi hesap anahtarı Departman'dır. Yalnız
                # görünen unvanı değiştirmek personeli eski norm ailesinde
                # bırakıyordu. Uzman/elit unvanlar state_engine'deki aile
                # eşlemesiyle yine ana ailelerine normalleştirilir.
                "Departman": target_title,
            },
            username=created_by,
        )

    con = connect_web_db()
    try:
        con.execute(
            """INSERT INTO appointments
               (atama_no, created_at, created_by, person_name, staff_index,
                source_store, source_title, target_store, target_title, planned_date, status, applied_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (atama_no, datetime.now().isoformat(timespec="seconds"), created_by, person_name, staff_index,
             source_store, source_title, target_store, target_title, planned_date_str, durum,
             datetime.now().isoformat(timespec="seconds") if durum == "APPLIED" else None),
        )
        con.commit()
    finally:
        con.close()
    return {"atama_no": atama_no, "status": durum, "planned_date": planned_date_str}


def apply_due_appointments(*, input_path: Path, root: Path) -> list[dict]:
    """Tarihi GELMİŞ (bugün veya geçmiş) PLANNED atamaları bulup
    Fact_Mevcut'a uygular, durumu APPLIED'e çevirir.

    main.py'nin her çalıştırmasında VE web panelinin açılışında (bir
    gün önce girilmiş, tarihi bu arada gelmiş bir PLANNED atama varsa
    otomatik yürürlüğe girsin diye) çağrılmalıdır."""
    from services.personnel_exit import load_personnel_view, update_personnel

    con = connect_web_db()
    con.row_factory = sqlite3.Row
    try:
        bugun = date.today().isoformat()
        bekleyenler = con.execute(
            "SELECT * FROM appointments WHERE status='PLANNED' AND planned_date<=?", (bugun,)
        ).fetchall()
    finally:
        con.close()

    if not bekleyenler:
        return []

    uygulanan = []
    staff, magaza, unvan, _ = load_personnel_view(input_path)
    for row in bekleyenler:
        idx = row["staff_index"]
        try:
            if idx not in staff.index:
                continue
            magaza_id_satir = magaza.loc[magaza["Mağaza"].astype(str) == str(row["target_store"]), "MağazaID"]
            unvan_id_satir = unvan.loc[unvan["Unvan"].astype(str) == str(row["target_title"]), "UnvanID"]
            update_personnel(
                input_path=input_path, root=root, staff=staff, index=idx,
                guncellemeler={
                    "Mağaza": row["target_store"],
                    "MağazaID": magaza_id_satir.iloc[0] if not magaza_id_satir.empty else None,
                    "Unvan": row["target_title"],
                    "UnvanID": unvan_id_satir.iloc[0] if not unvan_id_satir.empty else None,
                    "Departman": row["target_title"],
                },
                username="sistem_planli_atama",
            )
            con2 = connect_web_db()
            try:
                con2.execute(
                    "UPDATE appointments SET status='APPLIED', applied_at=? WHERE id=?",
                    (datetime.now().isoformat(timespec="seconds"), row["id"]),
                )
                con2.commit()
            finally:
                con2.close()
            uygulanan.append({"atama_no": row["atama_no"], "person_name": row["person_name"]})
            staff, magaza, unvan, _ = load_personnel_view(input_path)  # taze oku (bir sonraki atama için)
        except Exception as exc:
            from services.safe_exec import log_swallowed
            log_swallowed(f"apply_due_appointments: {row['atama_no']} uygulanamadı", exc)
    return uygulanan
