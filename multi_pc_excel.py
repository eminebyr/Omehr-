from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import json, os, socket, time, uuid

LOCK_SUFFIX = '.basdas.lock'


def lock_path(input_path: Path) -> Path:
    p = Path(input_path)
    return p.with_name(p.name + LOCK_SUFFIX)


def _owner_payload(user: str = '') -> dict:
    return {
        'token': str(uuid.uuid4()),
        'user': user or os.getenv('USERNAME') or os.getenv('USER') or '',
        'computer': socket.gethostname(),
        'pid': os.getpid(),
        'created_at': datetime.now().isoformat(timespec='seconds'),
    }

@contextmanager
def excel_transaction_lock(input_path: Path | None, *, user: str = '', timeout: float = 90.0, stale_after: float = 300.0):
    """SMB/Windows ortak klasörde çalışan basit dosya kilidi.

    `O_CREAT|O_EXCL` aynı paylaşım üzerinde tek sahip oluşturur. Çökmüş bir
    istemciden kalan kilit, stale_after süresi geçince temizlenebilir.

    DÜZELTME: Veritabanı modunda (OMEHR_INPUT_SOURCE=db) paylaşılacak bir
    Excel dosyası YOKTUR — ``input_path`` bilerek ``None`` gelir, eşzamanlı
    yazma güvenliğini PostgreSQL/SQLite'ın kendi transaction mekanizması
    sağlar. Bu durumda dosya kilidi TAMAMEN ATLANIR (no-op); aksi halde
    ``Path(None)`` çağrısı çökerdi.
    """
    if input_path is None:
        yield _owner_payload(user)
        return
    lp = lock_path(input_path)
    lp.parent.mkdir(parents=True, exist_ok=True)
    owner = _owner_payload(user)
    deadline = time.monotonic() + max(1.0, timeout)
    acquired = False
    while not acquired:
        try:
            fd = os.open(str(lp), os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            try:
                os.write(fd, json.dumps(owner, ensure_ascii=False, indent=2).encode('utf-8'))
            finally:
                os.close(fd)
            acquired = True
        except FileExistsError:
            try:
                age = time.time() - lp.stat().st_mtime
                if age > stale_after:
                    lp.unlink(missing_ok=True)
                    continue
            except OSError:
                pass
            if time.monotonic() >= deadline:
                who = ''
                try:
                    info = json.loads(lp.read_text(encoding='utf-8'))
                    who = f" ({info.get('user') or '?'} / {info.get('computer') or '?'})"
                except Exception:
                    pass
                raise TimeoutError(
                    'Merkezi Excel şu anda başka bir kullanıcı tarafından güncelleniyor' + who + '. '
                    'İşlem güvenlik için uygulanmadı. Birkaç saniye sonra tekrar deneyin.'
                )
            time.sleep(0.25)
    try:
        yield owner
    finally:
        try:
            current = json.loads(lp.read_text(encoding='utf-8')) if lp.exists() else {}
            if current.get('token') == owner['token']:
                lp.unlink(missing_ok=True)
        except Exception:
            try: lp.unlink(missing_ok=True)
            except OSError: pass
