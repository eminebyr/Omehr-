"""services.safe_exec testleri — 'sessiz hata' loglama katmanı.

Bu, tur 3'te (hata yönetimi) 86 sitede kullanılan log_swallowed()/swallow()
mekanizmasının gerçekten (a) hatayı yuttuğunu [akış bozulmuyor] ve (b) bir
iz bıraktığını [tamamen sessiz değil] doğrular.

NEDEN caplog KULLANILMIYOR: services/observability.py'deki logger
BİLEREK kendi handler'larını (dosya + konsol) doğrudan ekliyor ve
`propagate = False` ayarlıyor (kütüphane kodunun konsola/kendi dosyasına
çift satır basmasını önlemek için). Bu, pytest sürümüne/eklenti
yapılandırmasına göre `caplog`'un bu logger'ı yakalamasını KIRILGAN hale
getirebiliyor (bazı ortamlarda çalışır, bazılarında logger zaten başka
bir testte yapılandırılmış olduğu için caplog'un handler'ı hiç devreye
girmeyebilir). Bunun yerine, log_swallowed()/swallow()'un asıl ürettiği
KALICI yan etkiyi — gerçek log dosyasını — doğrudan okuyoruz. Bu hem daha
sağlam (pytest iç mekaniğine bağımlı değil) hem de daha anlamlıdır: asıl
garanti edilen şey "bir yerlere caplog yakalar" değil, "logs/BASDAS_CURRENT.log
dosyasına gerçekten yazılır"dır.
"""
from __future__ import annotations

from pathlib import Path

from services.safe_exec import log_swallowed, swallow


def _log_dosya_yolu() -> Path:
    """services.safe_exec._LOGGER'ın GERÇEKTEN yazdığı dosyanın yolunu,
    logger'ın canlı handler'ından okur (LOG_DIR sabitini yeniden
    hesaplamaya çalışmak yerine) — böylece logger'ın hangi testte ilk
    kez yapılandırıldığına bakılmaksızın her zaman doğru dosyayı buluruz.
    """
    from services.safe_exec import _LOGGER

    for handler in _LOGGER.handlers:
        base = getattr(handler, "baseFilename", None)
        if base:
            return Path(base)
    raise AssertionError("_LOGGER üzerinde dosyaya yazan bir handler bulunamadı")


def _dosyanin_yeni_icerigi(dosya: Path, onceki_boyut: int) -> str:
    """Bir işlem SIRASINDA dosyaya eklenen (önceden var olan satırları
    içermeyen) yeni içeriği döndürür."""
    with open(dosya, "r", encoding="utf-8", errors="ignore") as f:
        f.seek(onceki_boyut)
        return f.read()


def test_swallow_suppresses_the_exception():
    """with swallow(...) içinde patlayan bir hata, akışı BOZMAMALI."""
    with swallow("test bağlamı"):
        raise ValueError("beklenen test hatası")
    # Buraya kadar geldiysek hata gerçekten yutulmuş demektir.


def test_swallow_logs_the_context_and_error():
    dosya = _log_dosya_yolu()
    onceki_boyut = dosya.stat().st_size if dosya.exists() else 0

    with swallow("ornek_baglam"):
        raise ValueError("test mesaji")

    yeni_icerik = _dosyanin_yeni_icerigi(dosya, onceki_boyut)
    assert "ornek_baglam" in yeni_icerik
    assert "ValueError" in yeni_icerik


def test_swallow_reraise_true_propagates_after_logging():
    import pytest

    dosya = _log_dosya_yolu()
    onceki_boyut = dosya.stat().st_size if dosya.exists() else 0

    with pytest.raises(ValueError):
        with swallow("kritik_baglam", reraise=True):
            raise ValueError("kritik hata")

    yeni_icerik = _dosyanin_yeni_icerigi(dosya, onceki_boyut)
    assert "kritik_baglam" in yeni_icerik


def test_log_swallowed_writes_context_and_exception_type():
    dosya = _log_dosya_yolu()
    onceki_boyut = dosya.stat().st_size if dosya.exists() else 0

    try:
        raise KeyError("eksik_sutun")
    except Exception as exc:
        log_swallowed("ornek_fonksiyon: beklenmeyen hata", exc)

    yeni_icerik = _dosyanin_yeni_icerigi(dosya, onceki_boyut)
    assert "ornek_fonksiyon" in yeni_icerik
    assert "KeyError" in yeni_icerik


def test_log_swallowed_respects_custom_level():
    """level='ERROR' verildiğinde satırın gerçekten ERROR olarak
    yazıldığını (varsayılan WARNING'e sabit kalmadığını) doğrular."""
    dosya = _log_dosya_yolu()
    onceki_boyut = dosya.stat().st_size if dosya.exists() else 0

    try:
        raise RuntimeError("kritik durum")
    except Exception as exc:
        log_swallowed("ornek_kritik_baglam", exc, level="ERROR")

    yeni_icerik = _dosyanin_yeni_icerigi(dosya, onceki_boyut)
    assert "ERROR" in yeni_icerik
    assert "ornek_kritik_baglam" in yeni_icerik
