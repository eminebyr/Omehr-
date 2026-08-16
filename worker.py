from __future__ import annotations

import argparse
import subprocess
import sys
import time
import traceback
from pathlib import Path
from services.excel_read_shim import install as _install_excel_read_shim
_install_excel_read_shim()

from services.job_queue import claim, fail, finish
from services.mail_idempotency import send_idempotent
from services.observability import get_logger
from services.rotation_document import create_rotation_documents
from services.runtime_paths import code_root
from services.web_runtime import connect_web_db
from services.safe_exec import log_swallowed

LOGGER = get_logger("basdas.worker")

def _admin_copy_recipients() -> list[str]:
    """Rotasyon evrakının bir kopyasını Mail_Listesi'ndeki admin hesabına ekler."""
    try:
        import pandas as pd
        from common_veri_okuma import input_file
        df = pd.read_excel(input_file(), sheet_name="Mail_Listesi")
        user_col = next((c for c in df.columns if str(c).strip() == "Web Kullanıcı"), None)
        mail_col = next((c for c in df.columns if str(c).strip() == "E-posta"), None)
        active_col = next((c for c in df.columns if str(c).strip() == "Aktif"), None)
        if not user_col or not mail_col:
            return []
        mask = df[user_col].astype(str).str.strip().str.casefold().eq("admin")
        if active_col:
            mask &= df[active_col].astype(str).str.strip().str.casefold().isin({"evet","aktif","1","true"})
        out=[]
        for value in df.loc[mask, mail_col].dropna():
            out.extend(x.strip() for x in str(value).replace(';',',').split(',') if x.strip())
        return list(dict.fromkeys(out))
    except Exception as exc:
        log_swallowed("admin rotasyon kopya alıcısı okunamadı", exc, level="WARNING")
        return []


def execute(job: dict) -> dict:
    kind, payload = job["job_type"], job["payload"]
    if kind == "RUN_REPORTS":
        result = subprocess.run([sys.executable, str(code_root() / "main.py")], cwd=code_root())
        if result.returncode:
            raise RuntimeError(f"Rapor motoru çıkış kodu: {result.returncode}")
        return {"returncode": 0}
    if kind == "SEND_EMAIL":
        # İDEMPOTENCY: Aynı alıcı(lar)a, aynı konu/ek-dosya içeriğiyle daha
        # önce (bugün) başarıyla gönderilmişse (ör. toplu mail kuyruğunun
        # kazara iki kez oluşması — kullanıcı gönder butonuna iki kez basarsa
        # her seferinde YENİ bir job ID üretilir, bu yüzden run_id burada
        # BİLEREK job ID değil GÜNÜN TARİHİ'dir; aksi halde iki farklı job ID
        # birbirinden habersiz iki gönderim yapardı) burada KESİN engellenir.
        result = send_idempotent(
            payload.get("report_type", "SEND_EMAIL"),
            payload["subject"], payload["body"], payload["recipients"],
            payload.get("attachments", []),
        )
        if result.startswith("FAILED") and not result.startswith("FAILED_"):
            raise RuntimeError(result)
        transfer_id = payload.get("transfer_id")
        if transfer_id:
            with connect_web_db() as con:
                con.execute("UPDATE transfers SET outlook_status=? WHERE id=?", (result, int(transfer_id)))
        return {"transport": result}
    if kind == "TRANSFER_DECISION":
        row = payload["row"]
        documents = {}
        if payload.get("approved"):
            if payload.get("document_type") == "TEMPORARY":
                from services.gecici_gorevlendirme import create_temporary_assignment_documents
                _tf = payload.get("temp_fields") or {}
                documents = create_temporary_assignment_documents({
                    "person_name": row.get("person_name"), "person_id": _tf.get("person_id") or row.get("person_id"),
                    "current_title": row.get("current_title"), "source_store": row.get("source_store"),
                    "target_store": row.get("target_store"), "start_date": row.get("planned_date"),
                    "end_date": _tf.get("end_date"), "total_duration": _tf.get("total_duration"),
                    "reason": _tf.get("reason"), "reason_other": _tf.get("reason_other"),
                })
            else:
                documents = create_rotation_documents(row)
        attachments = [value for key, value in documents.items() if key in {"pdf", "docx"} and value]
        # İDEMPOTENCY: run_id olarak transfer_id kullanılır — aynı transfer
        # kararı için (ör. sayfa yenilenip butona tekrar basılırsa) rotasyon
        # evrakı ve e-posta İKİNCİ KEZ üretilip gönderilmez.
        recipients = list(dict.fromkeys([*(payload.get("recipients") or []), *_admin_copy_recipients()]))
        # Normal akışta transfer_id idempotency anahtarıdır. Kullanıcının açıkça
        # "yeniden oluştur ve gönder" komutu verdiği durumda benzersiz resend_token
        # kullanılır; böylece önceki başarılı gönderim yeni gönderimi engellemez.
        if payload.get("force_resend"):
            run_id = f"{payload.get('transfer_id', job.get('id', ''))}:resend:{payload.get('resend_token', job.get('id', ''))}"
        else:
            run_id = str(payload.get("transfer_id", job.get("id", "")))
        result = send_idempotent(
            "TRANSFER_DECISION",
            payload["subject"], payload["body"], recipients, attachments,
            run_id=run_id,
        )
        if result.startswith("FAILED") and not result.startswith("FAILED_"):
            raise RuntimeError(result)
        with connect_web_db() as con:
            con.execute(
                """UPDATE transfers SET outlook_status=?,rotation_docx=?,rotation_pdf=?,
                   rotation_status=?,rotation_recipients=?,updated_at=datetime('now') WHERE id=?""",
                (result, documents.get("docx", ""), documents.get("pdf", ""),
                 "CREATED" if documents else "NOT_APPLICABLE",
                 ", ".join(recipients),
                 int(payload["transfer_id"])),
            )
        return {"transport": result, "documents": documents}
    if kind == "RECALCULATE_FORMULAS":
        # Hızlı web yazmaları (işe giriş/çıkış vb.), openpyxl'in formül
        # HÜCRELERİNİN önceden-hesaplanmış değerlerini koruyamaması
        # nedeniyle, formüle dayalı raporlama sayfalarını (ör.
        # Magaza_KPI_Skor_Karti) geçici olarak NaN bırakabilir. Bu ARKA
        # PLAN işi, LibreOffice ile tam yeniden hesaplamayı (60-150 sn
        # sürebilir) kullanıcının hızlı işlemini bloklamadan tamamlar —
        # aynı içerik hash'i için tekrar tekrar çalışmaz (bkz.
        # excel_recalc.recalculate_workbook'un kendi hash kısa-devresi).
        from services.excel_recalc import recalculate_workbook
        ok = recalculate_workbook(Path(payload["input_path"]))
        return {"recalculated": ok}
    raise ValueError(f"Desteklenmeyen görev: {kind}")


def run(once: bool = False, drain: bool = False) -> int:
    LOGGER.info("Görev worker başlatıldı")
    islenen = 0
    while True:
        job = claim()
        if job is None:
            if once or drain:
                return 0
            time.sleep(1)
            continue
        try:
            finish(job["id"], execute(job))
            LOGGER.info("Görev tamamlandı: %s/%s", job["id"], job["job_type"])
        except Exception as exc:
            log_swallowed("worker.run: beklenmeyen hata", exc)
            fail(job["id"], traceback.format_exc())
            LOGGER.exception("Görev başarısız: %s: %s", job["id"], exc)
        islenen += 1
        if once:
            return 0
        # --drain: tek bir görev değil, kuyrukta o an bekleyen TÜM görevleri
        # işler (claim() None dönene kadar döner). Toplu mail gibi çok sayıda
        # görevin AYNI ANDA kuyruğa eklendiği durumlarda ("15 şubeye toplu
        # mail" gibi), --once sadece İLK görevi işleyip çıkıyordu — geri
        # kalan 14'ü sürekli çalışan ayrı bir worker penceresi olmadan
        # sonsuza kadar "QUEUED" kalıyordu. --drain bu sorunu çözer.


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--drain", action="store_true", help="Kuyrukta bekleyen TÜM görevleri işleyip çıkar.")
    args = parser.parse_args()
    raise SystemExit(run(once=args.once, drain=args.drain))
