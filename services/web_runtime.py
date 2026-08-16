from __future__ import annotations

import sqlite3
from datetime import datetime
from services.runtime_paths import runtime_root


def db_path():
    """DÜZELTME (aynı kritik hata sınıfı — bkz. common_veri_okuma.py):
    önceden DB modül seviyesinde, import anında BİR KEZ hesaplanıyordu.
    Artık her çağrıda taze çözümlenir."""
    return runtime_root() / "data" / "v16_management.db"


def connect_web_db() -> sqlite3.Connection:
    DB = db_path()
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, check_same_thread=False, timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")
    con.execute("""CREATE TABLE IF NOT EXISTS transfers(
        id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, created_by TEXT, region TEXT,
        source_store TEXT, target_store TEXT, person_id TEXT, person_name TEXT, current_title TEXT,
        target_title TEXT, target_region TEXT, planned_date TEXT, reason TEXT, status TEXT,
        decision_by TEXT, decision_note TEXT, decision_at TEXT, fact_status TEXT, completed_at TEXT,
        outlook_status TEXT, updated_at TEXT)""")
    # MADDE 16-17: her atamada benzersiz ATAMA_NO + PLANNED/APPLIED durumu.
    # Atama tarihi bugün/geçmişse APPLIED (Fact_Mevcut hemen güncellenir);
    # gelecekteyse PLANNED kalır (Fact_Mevcut DOKUNULMAZ, tarih geldiğinde
    # services.appointment_lifecycle.apply_due_appointments() ile uygulanır).
    con.execute("""CREATE TABLE IF NOT EXISTS appointments(
        id INTEGER PRIMARY KEY AUTOINCREMENT, atama_no TEXT UNIQUE, created_at TEXT, created_by TEXT,
        person_name TEXT, staff_index INTEGER,
        source_store TEXT, source_title TEXT, target_store TEXT, target_title TEXT,
        planned_date TEXT, status TEXT, applied_at TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS action_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, username TEXT, action TEXT, detail TEXT)""")
    # DEĞİŞTİRİLEMEZ DENETİM KAYDI: action_log yalnız INSERT edilebilir.
    # Bir hata (kod hatası, elle müdahale, hatta kötü niyetli erişim) bu
    # tabloya UPDATE veya DELETE denerse, SQLite motorunun kendisi
    # reddeder — uygulama kodunun "dikkatli davranmasına" güvenmek yerine
    # veritabanı seviyesinde garanti edilir.
    con.execute("""CREATE TRIGGER IF NOT EXISTS action_log_no_update
        BEFORE UPDATE ON action_log
        BEGIN SELECT RAISE(ABORT, 'action_log değiştirilemez: UPDATE reddedildi'); END""")
    con.execute("""CREATE TRIGGER IF NOT EXISTS action_log_no_delete
        BEFORE DELETE ON action_log
        BEGIN SELECT RAISE(ABORT, 'action_log değiştirilemez: DELETE reddedildi'); END""")
    existing = {row[1] for row in con.execute("PRAGMA table_info(transfers)").fetchall()}
    migrations = {
        "rotation_docx": "TEXT", "rotation_pdf": "TEXT", "rotation_status": "TEXT",
        "rotation_sent_at": "TEXT", "rotation_recipients": "TEXT",
        "source_region_decision": "TEXT", "source_region_decision_by": "TEXT",
        "source_region_decision_at": "TEXT", "target_region_decision": "TEXT",
        "target_region_decision_by": "TEXT", "target_region_decision_at": "TEXT",
        "cancel_reason": "TEXT", "cancelled_by": "TEXT", "cancelled_at": "TEXT",
        "cancellation_outlook_status": "TEXT", "supersedes_id": "INTEGER",
        "superseded_by_id": "INTEGER",
        "source_home_km": "REAL", "source_home_route": "TEXT",
        "target_home_km": "REAL", "target_home_route": "TEXT",
        # OPTIMISTIC LOCKING (P1 — reviewer önerisi): iki farklı kullanıcı
        # AYNI transfer talebini AYNI ANDA açıp onaylarsa/reddederse veri
        # çakışması oluşabilirdi (ikinci kaydeden, birincinin kararını fark
        # etmeden üzerine yazardı). "version" sütunu, her güncellemede +1
        # artırılır ve UPDATE ... WHERE version=? koşuluyla korunur —
        # etkilenen satır sayısı 0 ise "bu talep başka biri tarafından
        # işlenmiş" denir.
        "version": "INTEGER DEFAULT 0",
        "approval_source": "TEXT",
        "previous_status": "TEXT",
        # MADDE 19: her transfer talebinde benzersiz, insan-okunabilir
        # TRANSFER_NO (TRF-YYYYMMDD-NNNNN) — appointments tablosundaki
        # ATAMA_NO ile aynı desen (services.transfer_lifecycle_no).
        "transfer_no": "TEXT",
    }
    for column, ctype in migrations.items():
        if column not in existing:
            con.execute(f"ALTER TABLE transfers ADD COLUMN {column} {ctype}")
    con.commit()
    return con


def yeni_transfer_no() -> str:
    """Örnek: TRF-20260810-00123 — Madde 19."""
    from datetime import datetime
    import sqlite3 as _sqlite3
    bugun = datetime.now().strftime("%Y%m%d")
    con = connect_web_db()
    con.row_factory = _sqlite3.Row
    try:
        satir = con.execute(
            "SELECT COUNT(*) AS n FROM transfers WHERE transfer_no LIKE ?", (f"TRF-{bugun}-%",)
        ).fetchone()
        sira = int(satir["n"]) + 1
    finally:
        con.close()
    return f"TRF-{bugun}-{sira:05d}"


def optimistic_update_transfer(transfer_id: int, beklenen_status: str, beklenen_version: int, guncellemeler: dict) -> bool:
    """OPTIMISTIC LOCKING (P1): Bir transfer kaydını, SADECE o an
    beklediğimiz status/version ile eşleşiyorsa günceller. İki kullanıcı
    aynı talebi aynı anda işlemeye çalışırsa, ikinci çağrı 0 satır
    etkileyecek ve False döner — böylece "bu talep başka biri tarafından
    işlenmiş" denebilir, sessizce üzerine yazılmaz.

    guncellemeler: {'status': 'İK Onayladı', 'decision_by': 'ik1', ...}
    Dönüş: True (başarılı) / False (çakışma — beklenen version/status artık geçerli değil)
    """
    guncellemeler = dict(guncellemeler)
    guncellemeler["version"] = beklenen_version + 1
    guncellemeler["previous_status"] = beklenen_status
    kolonlar = ", ".join(f"{k}=?" for k in guncellemeler)
    degerler = list(guncellemeler.values()) + [int(transfer_id), beklenen_status, int(beklenen_version)]
    con = connect_web_db()
    try:
        cur = con.execute(
            f"UPDATE transfers SET {kolonlar} WHERE id=? AND status=? AND version=?",
            degerler,
        )
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


def log_web_action(username: str, action: str, detail: str = "") -> None:
    con = connect_web_db()
    con.execute(
        "INSERT INTO action_log(created_at,username,action,detail) VALUES(?,?,?,?)",
        (datetime.now().isoformat(timespec="seconds"), username, action, detail),
    )
    con.commit()
    con.close()
