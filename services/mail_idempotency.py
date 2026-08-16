from __future__ import annotations

"""
MAIL IDEMPOTENCY (TEKRAR GÖNDERİM ÖNLEME) MODÜLÜ
=====================================================
Sorun: "Aynı dosyadan ikişer mail gidiyor" şüphesinin gerçek çözümü sadece
loglama değildir — HER gönderimden önce, "bu TAM İÇERİK bu alıcı(lar)a daha
önce başarıyla gönderilmiş mi?" sorusu SORULMALI ve cevap evetse gönderim
KESİN olarak engellenmelidir.

Anahtar: run_id + report_type + alıcı(lar) + ek dosya hash'i
Aynı anahtarla daha önce BAŞARILI (SENT) bir gönderim varsa, ikinci çağrı
gönderim yapmadan "SKIPPED: idempotent" döner.

Durumlar: PENDING, SENDING, SENT, FAILED_RETRYABLE, FAILED_FINAL
"Outlook Gönderildi mi = Evet/Hayır" gibi tek boyutlu bir alan yerine, bu
modül gönderimin TAM YAŞAM DÖNGÜSÜNÜ (kaç deneme, ne zaman, hangi anahtarla)
kalıcı olarak SQLite'ta tutar.
"""

import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path

from services.outlook_adapter import send_outlook
from services.runtime_paths import runtime_root

def _db_path():
    from services.runtime_paths import runtime_root
    return runtime_root() / "data" / "mail_idempotency.db"


MAX_RETRIES_DEFAULT = 3

_SCHEMA = """
CREATE TABLE IF NOT EXISTS mail_sends (
    idempotency_key TEXT PRIMARY KEY,
    mail_id TEXT,
    report_type TEXT NOT NULL,
    run_id TEXT NOT NULL,
    recipients TEXT NOT NULL,
    subject TEXT,
    attachment_hash TEXT,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_result TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


def yeni_mail_id() -> str:
    """Madde 32: MAIL-YYYYMMDD-NNNNN — insan tarafından okunabilir,
    günlük artan sıra numaralı benzersiz mail kimliği. Gerçek
    tekilleştirme/idempotency KARARI hâlâ idempotency_key (hash) ile
    verilir; bu yalnız bir kullanıcının/İK'nın "MAIL-20260811-00042
    hangi mail?" diye sorabilmesi için OKUNABİLİR bir referanstır."""
    bugun = datetime.now().strftime("%Y%m%d")
    con = _connect()
    try:
        satir = con.execute(
            "SELECT COUNT(*) AS n FROM mail_sends WHERE mail_id LIKE ?", (f"MAIL-{bugun}-%",)
        ).fetchone()
        sira = int(satir["n"]) + 1
    finally:
        con.close()
    return f"MAIL-{bugun}-{sira:05d}"


def _connect() -> sqlite3.Connection:
    _db_path().parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(_db_path(), timeout=30)
    con.row_factory = sqlite3.Row
    con.execute(_SCHEMA)
    # DÜZELTME (Madde 32): daha önce oluşturulmuş bir veritabanında
    # mail_id sütunu olmayabilir (yeni eklendi) — CREATE TABLE IF NOT
    # EXISTS var olan tabloyu değiştirmez, bu yüzden güvenli bir göç
    # gerekir.
    mevcut_sutunlar = {row[1] for row in con.execute("PRAGMA table_info(mail_sends)").fetchall()}
    if "mail_id" not in mevcut_sutunlar:
        con.execute("ALTER TABLE mail_sends ADD COLUMN mail_id TEXT")
        con.commit()
    return con


def compute_attachment_hash(paths) -> str:
    """Ek dosyaların İÇERİĞİNİN (sadece dosya adının değil) SHA-256 özeti.
    Aynı isimli ama İÇERİĞİ DEĞİŞMİŞ bir dosya (ör. rapor güncellenmiş)
    farklı bir hash üretir — bu da onu yeni/farklı bir gönderim olarak
    değerlendirmemizi sağlar (eski içeriğin tekrar gönderimini engellemez,
    çünkü içerik gerçekten farklıdır)."""
    h = hashlib.sha256()
    for p in sorted(str(x) for x in (paths or [])):
        path = Path(p)
        if path.is_file():
            h.update(path.read_bytes())
        else:
            h.update(p.encode("utf-8"))
    return h.hexdigest()[:16]


def build_key(report_type: str, run_id: str, recipients, attachment_hash: str, subject: str = "") -> str:
    recipient_part = ";".join(sorted(str(r).strip().casefold() for r in (recipients or [])))
    raw = f"{report_type}|{run_id}|{recipient_part}|{attachment_hash}|{subject.strip().casefold()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def send_idempotent(
    report_type: str,
    subject: str,
    body: str,
    recipients: list[str],
    attachments=None,
    run_id: str | None = None,
    max_retries: int = MAX_RETRIES_DEFAULT,
) -> str:
    """send_outlook()'un idempotent sarmalayıcısı. Aynı (report_type, run_id,
    alıcılar, ek-dosya-içeriği, konu) kombinasyonu daha önce BAŞARIYLA
    gönderildiyse, gönderim yapmadan atlar."""
    attachments = list(attachments or [])
    run_id = run_id or datetime.now().strftime("%Y-%m-%d")
    attachment_hash = compute_attachment_hash(attachments)
    key = build_key(report_type, run_id, recipients, attachment_hash, subject)
    now = datetime.now().isoformat(timespec="seconds")

    con = _connect()
    try:
        row = con.execute("SELECT * FROM mail_sends WHERE idempotency_key=?", (key,)).fetchone()
        if row is not None and row["status"] == "SENT":
            return f"SKIPPED: idempotent (daha önce {row['updated_at']} tarihinde bu tam içerikle gönderilmiş)"
        if row is not None and row["status"] == "SENDING":
            # Aynı anahtarla eşzamanlı ikinci bir çağrı (ör. iki worker süreci
            # aynı anda tetiklenmiş) — çakışan gönderimi önlemek için atla.
            return "SKIPPED: idempotent (bu gönderim şu an başka bir işlemde işleniyor)"
        attempts = (row["attempts"] if row is not None else 0)
        if row is not None and row["status"] == "FAILED_FINAL":
            return f"FAILED_FINAL: {max_retries} deneme sonrası kalıcı olarak başarısız işaretlenmiş — {row['last_result']}"
        if row is None:
            mail_id = yeni_mail_id()
            con.execute(
                """INSERT INTO mail_sends
                   (idempotency_key, mail_id, report_type, run_id, recipients, subject,
                    attachment_hash, status, attempts, last_result, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (key, mail_id, report_type, run_id, ";".join(recipients or []), subject, attachment_hash,
                 "SENDING", attempts + 1, None, now, now),
            )
        else:
            con.execute(
                "UPDATE mail_sends SET status='SENDING',attempts=?,updated_at=? WHERE idempotency_key=?",
                (attempts + 1, now, key),
            )
        con.commit()
    finally:
        con.close()

    result = send_outlook(subject, body, recipients, attachments)

    con = _connect()
    try:
        if result.startswith("SENT"):
            con.execute(
                "UPDATE mail_sends SET status='SENT',last_result=?,updated_at=? WHERE idempotency_key=?",
                (result, datetime.now().isoformat(timespec="seconds"), key),
            )
        else:
            new_status = "FAILED_FINAL" if attempts + 1 >= max_retries else "FAILED_RETRYABLE"
            con.execute(
                "UPDATE mail_sends SET status=?,last_result=?,updated_at=? WHERE idempotency_key=?",
                (new_status, result, datetime.now().isoformat(timespec="seconds"), key),
            )
        con.commit()
    finally:
        con.close()
    return result


def stats(report_type: str | None = None) -> list[dict]:
    """Gözlemlenebilirlik/denetim için: mail_sends tablosundaki kayıtları
    (isteğe bağlı rapor tipine göre filtrelenmiş) döndürür."""
    con = _connect()
    try:
        if report_type:
            rows = con.execute("SELECT * FROM mail_sends WHERE report_type=? ORDER BY updated_at DESC", (report_type,)).fetchall()
        else:
            rows = con.execute("SELECT * FROM mail_sends ORDER BY updated_at DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()
