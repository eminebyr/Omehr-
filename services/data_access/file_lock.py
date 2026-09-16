from __future__ import annotations

"""
DOSYA KİLİTLEME MODÜLÜ (eşzamanlı kullanım koruması)
========================================================
Birden fazla kullanıcı web panelini aynı anda açtığında, her biri input Excel
dosyasını openpyxl ile açıp kaydeden işlemler tetikler (koordinat yenileme,
yedekleme, formül yeniden hesaplama). İki işlem TAM OLARAK aynı anda dosyayı
kaydetmeye çalışırsa, biri diğerinin yazdığını kaybedebilir ya da dosya yarım
yazılmış halde bozulabilir.

Bu modül, `path.lock` adında küçük bir kilit dosyası kullanır. Kilit dosyasının
OLUŞTURULMASI (os.O_CREAT | os.O_EXCL ile) hem Windows hem Linux'ta ATOMİKTİR
— yani iki işlem aynı anda denese bile sadece biri kilidi alabilir, diğeri
bekler. Bu sayede ekstra bir veritabanı/servis kurmadan, sadece dosya
sistemiyle güvenli sıralama sağlanır.

Bir süreç çökerse (ör. bilgisayar kapanırsa) kilit dosyası "askıda" kalabilir;
bu yüzden belirli bir süreden (STALE_SECONDS) eski kilitler otomatik olarak
"askıda kalmış" sayılıp temizlenir, sistemin sonsuza kadar kilitli kalması
engellenir.
"""

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from services.safe_exec import log_swallowed

STALE_SECONDS = 180
DEFAULT_TIMEOUT = 60
POLL_INTERVAL = 0.5


def _lock_path(path) -> Path:
    return Path(str(path) + ".lock")


def _is_stale(lock_file: Path) -> bool:
    try:
        age = time.time() - lock_file.stat().st_mtime
        return age > STALE_SECONDS
    except Exception as _exc:
        log_swallowed("services.file_lock._is_stale: beklenmeyen hata", _exc)
        return True


@contextmanager
def file_lock(path, timeout: float = DEFAULT_TIMEOUT):
    """
    Kullanım:
        with file_lock(input_path) as alindi:
            if alindi:
                ... dosyayı güvenle oku/yaz ...
            else:
                ... kilit alınamadı, zaman aşımına uğradı, işlemi atla ...

    `alindi` False ise (ör. başka bir kullanıcı hâlâ yazıyor ve zaman aşımına
    uğradı), ana akış BOZULMAZ — çağıran taraf bu durumda işlemi atlayıp
    dosyayı olduğu gibi okumaya devam edebilir.
    """
    lock_file = _lock_path(path)
    acquired = False
    waited = 0.0
    while True:
        try:
            fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, json.dumps({"pid": os.getpid(), "ts": time.time()}).encode("utf-8"))
            finally:
                os.close(fd)
            acquired = True
            break
        except FileExistsError:
            if _is_stale(lock_file):
                try:
                    lock_file.unlink()
                except Exception as _exc:
                    log_swallowed("services.file_lock.file_lock: beklenmeyen hata", _exc)
                    pass
                continue
            if waited >= timeout:
                break
            time.sleep(POLL_INTERVAL)
            waited += POLL_INTERVAL
        except Exception as _exc:
            log_swallowed("services.file_lock.file_lock: beklenmeyen hata", _exc)
            break
    try:
        yield acquired
    finally:
        if acquired:
            try:
                lock_file.unlink()
            except Exception as _exc:
                log_swallowed("services.file_lock.file_lock: beklenmeyen hata", _exc)
                pass


def is_locked(path) -> bool:
    """Dosyanın şu an başka bir işlem tarafından kilitli olup olmadığını
    (askıda kalmamış, geçerli bir kilit varsa) bildirir. Sadece bilgi
    amaçlıdır, kilit almaya çalışmaz."""
    lock_file = _lock_path(path)
    if not lock_file.is_file():
        return False
    return not _is_stale(lock_file)
