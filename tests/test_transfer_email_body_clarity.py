"""E-posta gövdesi netliği — regresyon testi.

ÖNEMLİ BAĞLAM: Bu düzeltme (_transfer_bilgi_govdesi), V19.21.5'te
eklenmiş ama V19.21.6'nın bu paketi hazırlayan dalı, o düzeltmeden
ÖNCEKİ bir noktadan çatallandığı için düzeltme bu pakette HİÇ YOKTU —
yalnızca alıcı listesi (kime gittiği) doğruydu, gövde (ne dediği) hâlâ
eski/genel haldeydi. Bu, çoklu-dal geliştirmede bir düzeltmenin
SESSİZCE kaybolabileceğinin somut bir örneği. Bu test hem DAVRANIŞI
hem de KAYNAK KODUNDA fonksiyonun varlığını kontrol ederek gelecekte
aynı şekilde sessizce kaybolmasını zorlaştırır.
"""
from __future__ import annotations

from pathlib import Path


def test_transfer_bilgi_govdesi_function_exists_in_source():
    """Kaynak kod taraması: yardımcı fonksiyon dosyada gerçekten var mı."""
    kok = Path(__file__).resolve().parents[1]
    kaynak = (kok / "web" / "tab_modules" / "onaylar.py").read_text(encoding="utf-8")
    assert "_transfer_bilgi_govdesi" in kaynak
    assert kaynak.count('"body":_govde') >= 3 or kaynak.count("'body':_govde") >= 3, (
        "3 e-posta gönderim noktasının ÜÇÜ DE _transfer_bilgi_govdesi() çıktısını "
        "kullanmalı — eski genel body metni (f'Karar: {dec}\\nNot: {note}' gibi) "
        "hiçbir yerde KALMAMALI."
    )


def test_transfer_bilgi_govdesi_names_person_and_both_stores():
    from web.transfer_email import transfer_bilgi_govdesi as _transfer_bilgi_govdesi

    row = {
        "person_name": "Ahmet Yılmaz", "person_id": "P0042",
        "source_store": "Kadıköy Şubesi", "target_store": "Beşiktaş Şubesi",
    }
    govde = _transfer_bilgi_govdesi(row, "İK Onayladı", "Norm dengesizliği", rotasyon_var=True)

    assert "Ahmet Yılmaz" in govde
    assert "Kadıköy Şubesi" in govde
    assert "Beşiktaş Şubesi" in govde
    assert "devreden" in govde.casefold()
    assert "devralan" in govde.casefold()
    assert "rotasyon belgesi" in govde.casefold()


def test_transfer_bilgi_govdesi_omits_rotation_note_when_not_approved():
    from web.transfer_email import transfer_bilgi_govdesi as _transfer_bilgi_govdesi

    row = {"person_name": "Test", "source_store": "A", "target_store": "B"}
    reddedilen = _transfer_bilgi_govdesi(row, "Reddedildi", rotasyon_var=False)

    assert "rotasyon belgesi" not in reddedilen.casefold()


def test_old_generic_body_pattern_is_fully_removed():
    """REGRESYON: eski, netliksiz gövde metninin (f'Karar: {dec}\\nNot: {note}')
    hiçbir e-posta gönderim çağrısında KALMADIĞINI doğrular — bu tam
    olarak bu pakette bir kez sessizce geri gelen kalıptı."""
    kok = Path(__file__).resolve().parents[1]
    kaynak = (kok / "web" / "tab_modules" / "onaylar.py").read_text(encoding="utf-8")
    assert 'f"Karar: {dec}\\nNot: {note}"' not in kaynak
    assert 'f"Bölge kararı: {dec}\\nKararı veren: {username}\\nYeni durum: {new}"' not in kaynak
