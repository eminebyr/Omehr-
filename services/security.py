from __future__ import annotations

import hashlib
import hmac
import os
import re
import sqlite3
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from services.runtime_paths import runtime_root

def _db_path():
    from services.runtime_paths import runtime_root
    return runtime_root() / "data" / "security.db"
ITERATIONS = 600_000
MAX_FAILURES = 5
LOCK_MINUTES = 15


def _connect() -> sqlite3.Connection:
    _db_path().parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(_db_path(), timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS credentials(
            tenant_id TEXT NOT NULL DEFAULT 'BASDAS',
            username TEXT NOT NULL,
            salt BLOB NOT NULL,
            password_hash BLOB NOT NULL,
            iterations INTEGER NOT NULL,
            must_change INTEGER NOT NULL DEFAULT 1,
            failed_attempts INTEGER NOT NULL DEFAULT 0,
            locked_until TEXT,
            changed_at TEXT NOT NULL,
            PRIMARY KEY (tenant_id, username)
        );
        CREATE TABLE IF NOT EXISTS security_audit(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            tenant_id TEXT,
            username TEXT,
            event TEXT NOT NULL,
            detail TEXT
        );
        """
    )
    # DÜZELTME (çok kiracılı SaaS): eski (V19.21.28 öncesi) credentials
    # tablosu yalnız "username TEXT PRIMARY KEY" idi — iki farklı firma
    # aynı kullanıcı adını (ör. "ik1") kullanırsa şifre kaydı ÇAKIŞIRDI.
    # Var olan bir kurulumda hâlâ eski şema varsa (tenant_id sütunu yok),
    # veri kaybetmeden yeni şemaya taşı: tüm eski kayıtlar varsayılan
    # 'BASDAS' kiracısına ait kabul edilir (geriye dönük uyumluluk).
    mevcut_sutunlar = {row["name"] for row in con.execute("PRAGMA table_info(credentials)")}
    if "tenant_id" not in mevcut_sutunlar:
        con.executescript(
            """
            ALTER TABLE credentials RENAME TO credentials_v1_gecis;
            CREATE TABLE credentials(
                tenant_id TEXT NOT NULL DEFAULT 'BASDAS',
                username TEXT NOT NULL,
                salt BLOB NOT NULL,
                password_hash BLOB NOT NULL,
                iterations INTEGER NOT NULL,
                must_change INTEGER NOT NULL DEFAULT 1,
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                locked_until TEXT,
                changed_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, username)
            );
            INSERT INTO credentials(tenant_id,username,salt,password_hash,iterations,
                must_change,failed_attempts,locked_until,changed_at)
            SELECT 'BASDAS',username,salt,password_hash,iterations,
                must_change,failed_attempts,locked_until,changed_at
            FROM credentials_v1_gecis;
            DROP TABLE credentials_v1_gecis;
            """
        )
    denetim_sutunlar = {row["name"] for row in con.execute("PRAGMA table_info(security_audit)")}
    if "tenant_id" not in denetim_sutunlar:
        con.execute("ALTER TABLE security_audit ADD COLUMN tenant_id TEXT")
    con.commit()
    return con


def _varsayilan_kiraci() -> str:
    try:
        from services.tenant_context import current_tenant_id
        return current_tenant_id()
    except Exception:
        return "BASDAS"


def _audit(con: sqlite3.Connection, username: str, event: str, detail: str = "", tenant_id: str | None = None) -> None:
    con.execute(
        "INSERT INTO security_audit(created_at,tenant_id,username,event,detail) VALUES(?,?,?,?,?)",
        (datetime.now().isoformat(timespec="seconds"), tenant_id or _varsayilan_kiraci(), username, event, detail),
    )


def password_error(password: str) -> str:
    """Kurumsal güç parola politikası (V19.9 — dış inceleme sonrası
    güçlendirme: min 8 → min 10, İK/personel verisi taşıyan bir sistem
    için daha uygun). En az 10 karakter; en az bir büyük harf, bir küçük
    harf ve bir rakam."""
    if len(password) < 10:
        return "Şifre en az 10 karakter olmalıdır."
    checks = [
        (r"[A-ZÇĞİÖŞÜ]", "en az bir büyük harf"),
        (r"[a-zçğıöşü]", "en az bir küçük harf"),
        (r"\d", "en az bir rakam"),
    ]
    missing = [message for pattern, message in checks if not re.search(pattern, password)]
    return "Şifre " + ", ".join(missing) + " içermelidir." if missing else ""


def _derive(password: str, salt: bytes, iterations: int = ITERATIONS) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)


def set_password(username: str, password: str, must_change: bool = False, tenant_id: str | None = None) -> None:
    error = password_error(password)
    if error:
        raise ValueError(error)
    tenant_id = (tenant_id or _varsayilan_kiraci()).strip().upper()
    username = username.strip().casefold()
    # DÜZELTME (SaaS kota uygulaması): kullanici_kotasi tabloda tanımlıydı
    # ama hiçbir yerde kontrol edilmiyordu. Yalnız YENİ bir kullanıcı
    # (henüz credential kaydı olmayan) eklenirken kontrol edilir — mevcut
    # bir kullanıcının şifresini sıfırlamak kotayı artırmaz, o yüzden
    # engellenmemelidir.
    if not credential_exists(username, tenant_id=tenant_id):
        try:
            from services.tenant_registry import check_quota
            with _connect() as con:
                mevcut = con.execute(
                    "SELECT COUNT(*) AS n FROM credentials WHERE tenant_id=?", (tenant_id,)
                ).fetchone()["n"]
            uygun, mesaj = check_quota(tenant_id, "kullanici", int(mevcut) + 1)
            if not uygun:
                raise ValueError(mesaj)
        except ImportError:
            pass
    salt = os.urandom(16)
    digest = _derive(password, salt)
    with _connect() as con:
        con.execute(
            """INSERT INTO credentials(tenant_id,username,salt,password_hash,iterations,must_change,
               failed_attempts,locked_until,changed_at) VALUES(?,?,?,?,?,?,0,NULL,?)
               ON CONFLICT(tenant_id,username) DO UPDATE SET salt=excluded.salt,
               password_hash=excluded.password_hash,iterations=excluded.iterations,
               must_change=excluded.must_change,failed_attempts=0,locked_until=NULL,
               changed_at=excluded.changed_at""",
            (tenant_id, username, salt, digest, ITERATIONS, int(must_change), datetime.now().isoformat(timespec="seconds")),
        )
        _audit(con, username, "PASSWORD_SET", f"must_change={int(must_change)}", tenant_id=tenant_id)


def credential_exists(username: str, tenant_id: str | None = None) -> bool:
    tenant_id = (tenant_id or _varsayilan_kiraci()).strip().upper()
    with _connect() as con:
        return con.execute(
            "SELECT 1 FROM credentials WHERE tenant_id=? AND username=?",
            (tenant_id, username.strip().casefold()),
        ).fetchone() is not None


def authenticate(username: str, password: str, tenant_id: str | None = None) -> tuple[bool, str, bool]:
    tenant_id = (tenant_id or _varsayilan_kiraci()).strip().upper()
    username = username.strip().casefold()
    now = datetime.now()
    # DÜZELTME (çok kiracılı SaaS): askıya alınmış/iptal edilmiş bir
    # firma, şifre doğru olsa bile içeri alınamaz. tenant_registry
    # bulunamazsa (tek kiracılı/eski kurulum) bu kontrol atlanır —
    # geriye dönük uyumluluk bilerek korunur.
    try:
        from services.tenant_registry import get_tenant as _get_tenant
        kayit = _get_tenant(tenant_id)
        if kayit is not None and kayit.get("durum") != "aktif":
            with _connect() as con:
                _audit(con, username, "LOGIN_DENIED", f"Kiracı durumu: {kayit.get('durum')}", tenant_id=tenant_id)
            return False, "Bu firma hesabı şu an askıya alınmış veya kapatılmış.", False
    except ImportError:
        pass
    with _connect() as con:
        row = con.execute(
            "SELECT * FROM credentials WHERE tenant_id=? AND username=?", (tenant_id, username)
        ).fetchone()
        if row is None:
            _audit(con, username, "LOGIN_DENIED", "Güvenli şifre kaydı yok", tenant_id=tenant_id)
            return False, "Bu hesap için güvenli şifre oluşturulmamış.", False
        locked_until = datetime.fromisoformat(row["locked_until"]) if row["locked_until"] else None
        if locked_until and locked_until > now:
            _audit(con, username, "LOGIN_LOCKED", locked_until.isoformat(timespec="minutes"), tenant_id=tenant_id)
            return False, f"Hesap {locked_until:%H:%M} saatine kadar kilitli.", False
        candidate = _derive(password, bytes(row["salt"]), int(row["iterations"]))
        if not hmac.compare_digest(candidate, bytes(row["password_hash"])):
            failures = int(row["failed_attempts"]) + 1
            lock = now + timedelta(minutes=LOCK_MINUTES) if failures >= MAX_FAILURES else None
            con.execute(
                "UPDATE credentials SET failed_attempts=?,locked_until=? WHERE tenant_id=? AND username=?",
                (0 if lock else failures, lock.isoformat(timespec="seconds") if lock else None, tenant_id, username),
            )
            _audit(con, username, "LOGIN_FAILED", f"attempt={failures}", tenant_id=tenant_id)
            return False, "Kullanıcı adı veya şifre hatalı.", False
        con.execute(
            "UPDATE credentials SET failed_attempts=0,locked_until=NULL WHERE tenant_id=? AND username=?",
            (tenant_id, username),
        )
        _audit(con, username, "LOGIN_SUCCESS", tenant_id=tenant_id)
        return True, "", bool(row["must_change"])


def migrate_legacy_input(input_path: Path) -> int:
    """Inputtaki geçici ilk giriş şifrelerini bir kez güvenli kasaya taşır."""
    marker = runtime_root() / "data" / ".legacy_passwords_migrated"
    # GÜVENLİK AĞI: Normalde bu fonksiyon marker dosyası varsa hiç çalışmaz
    # (bir kez taşınır, bir daha dokunulmaz). Ancak eski/kısmi bir kurulumdan
    # (ör. farklı bir klasöre taşınmış "data/" içeriği) kalan bir marker,
    # "admin" hesabı HİÇ taşınmamış olsa bile migrasyonun bir daha asla
    # denenmemesine yol açabilir — sistem kalıcı olarak açılamaz hale gelir.
    # Bu yüzden "admin" özellikle eksikse, marker'ı yok sayıp yine de
    # denenir (sadece admin için; diğer kullanıcılar marker'a saygı gösterir).
    if marker.exists() and credential_exists("admin"):
        return 0
    if not input_path.exists():
        return 0
    import pandas as pd
    try:
        frame = pd.read_excel(input_path, sheet_name="Mail_Listesi")
    except Exception as _exc:
        # DÜZELTME: önceden yalnız ValueError yakalanıyordu — bozuk dosya
        # (zipfile.BadZipFile), Excel'de açık/kilitli dosya (PermissionError)
        # gibi diğer okuma hataları BURADAN sızıp INITIAL_PASSWORD_IMPORT.py
        # üzerinden TÜM kurulum/başlatma sürecini durduruyordu. Şifre
        # taşıma sistemin ÇALIŞMASI için ZORUNLU değildir (admin zaten
        # .env'deki varsayılan şifreyle girebilir) — bu yüzden herhangi
        # bir okuma hatasında sessizce atlanır, kurulum devam eder.
        from services.safe_exec import log_swallowed
        log_swallowed("migrate_legacy_input: Mail_Listesi okunamadı, şifre taşıma atlandı", _exc, level="WARNING")
        return 0
    if not {"Web Kullanıcı", "Web Şifre"}.issubset(frame.columns):
        return 0
    migrated = 0
    for _, record in frame.iterrows():
        username = str(record.get("Web Kullanıcı") or "").strip()
        password = str(record.get("Web Şifre") or "").strip()
        if password.casefold() == "nan":
            password = ""
        if username and password:
            if not credential_exists(username):
                # Eski kısa geçici parolalar yalnız taşıma için kabul edilir; ilk girişte değiştirilir.
                salt = os.urandom(16)
                digest = _derive(password, salt)
                tenant_id = _varsayilan_kiraci().strip().upper()
                with _connect() as con:
                    con.execute(
                        """INSERT INTO credentials
                           (tenant_id,username,salt,password_hash,iterations,must_change,failed_attempts,locked_until,changed_at)
                           VALUES(?,?,?,?,?,1,0,NULL,?)""",
                        (tenant_id, username.casefold(), salt, digest, ITERATIONS, datetime.now().isoformat(timespec="seconds")),
                    )
                    _audit(con, username, "LEGACY_MIGRATED", tenant_id=tenant_id)
                migrated += 1
    # Web Şifre sütunu kullanıcının istediği başlangıç şifre listesidir.
    # Bu değerler yalnız ilk içe aktarmada kullanılır; webde değiştirilen yeni
    # şifreler hiçbir zaman Excel'e geri yazılmaz.
    marker.write_text(datetime.now().isoformat(timespec="seconds"), encoding="utf-8")
    return migrated


def _clear_xlsx_column(path: Path, sheet_name: str, header_name: str) -> None:
    """Yalnız hedef hücre XML'lerini temizler; diğer sayfaları ve formül cache'lerini yeniden yazmaz."""
    ns = {
        "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        "p": "http://schemas.openxmlformats.org/package/2006/relationships",
    }
    with zipfile.ZipFile(path, "r") as source:
        workbook = ET.fromstring(source.read("xl/workbook.xml"))
        relation_id = None
        for sheet in workbook.findall("m:sheets/m:sheet", ns):
            if sheet.get("name") == sheet_name:
                relation_id = sheet.get(f"{{{ns['r']}}}id")
                break
        if not relation_id:
            raise ValueError(f"Excel sayfası bulunamadı: {sheet_name}")
        rels = ET.fromstring(source.read("xl/_rels/workbook.xml.rels"))
        target = next(
            (rel.get("Target") for rel in rels.findall("p:Relationship", ns) if rel.get("Id") == relation_id),
            None,
        )
        if not target:
            raise ValueError("Excel sayfa ilişkisi bulunamadı.")
        normalized_target = target.lstrip("/")
        sheet_path = normalized_target if normalized_target.startswith("xl/") else "xl/" + normalized_target
        shared = []
        if "xl/sharedStrings.xml" in source.namelist():
            shared_root = ET.fromstring(source.read("xl/sharedStrings.xml"))
            for item in shared_root.findall("m:si", ns):
                shared.append("".join(node.text or "" for node in item.iter(f"{{{ns['m']}}}t")))
        sheet_root = ET.fromstring(source.read(sheet_path))
        header_column = None
        for cell in sheet_root.findall(".//m:row[@r='1']/m:c", ns):
            if _xlsx_cell_text(cell, shared, ns["m"]).strip() == header_name:
                header_column = "".join(ch for ch in cell.get("r", "") if ch.isalpha())
                break
        if not header_column:
            raise ValueError(f"Excel sütunu bulunamadı: {header_name}")
        for cell in sheet_root.findall(".//m:c", ns):
            ref = cell.get("r", "")
            column = "".join(ch for ch in ref if ch.isalpha())
            row = int("".join(ch for ch in ref if ch.isdigit()) or "0")
            if column == header_column and row > 1:
                for child in list(cell):
                    cell.remove(child)
                cell.attrib.pop("t", None)
        replacement = ET.tostring(sheet_root, encoding="utf-8", xml_declaration=True)
        fd, temp_name = tempfile.mkstemp(suffix=".xlsx", dir=path.parent)
        os.close(fd)
        try:
            with zipfile.ZipFile(temp_name, "w") as target_zip:
                for info in source.infolist():
                    target_zip.writestr(info, replacement if info.filename == sheet_path else source.read(info.filename))
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)


def _xlsx_cell_text(cell: ET.Element, shared: list[str], main_ns: str) -> str:
    kind = cell.get("t")
    value = cell.find(f"{{{main_ns}}}v")
    if kind == "s" and value is not None:
        index = int(value.text or "0")
        return shared[index] if 0 <= index < len(shared) else ""
    if kind == "inlineStr":
        return "".join(node.text or "" for node in cell.iter(f"{{{main_ns}}}t"))
    return value.text if value is not None and value.text else ""
