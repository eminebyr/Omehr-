from __future__ import annotations

"""
MERKEZİ UNVAN ALIAS/EŞLEŞTİRME MODÜLÜ (P2 — reviewer önerisi)
====================================================================
SORUN: "Uzman/Elit varyant -> baz unvan" ve "unvan -> yardımcı unvanı"
eşleştirmeleri, bu kod tabanında BİRDEN FAZLA yerde (services/
formula_bagimsiz_hesapla.py ve src/engine_core.py) BAĞIMSIZ OLARAK,
FARKLI mekanizmalarla (biri UnvanID sözlüğü, diğeri metin öneki temizleme)
tekrar tekrar yazılmıştı. Bu hem tutarsız eşleşme riski yaratıyordu hem de
kod değiştirmeden yeni bir mağaza/unvan varyantı eklemeyi imkansız
kılıyordu.

Bu modül TEK DOĞRU KAYNAKTIR (single source of truth) — tüm diğer
modüller buradan import etmelidir, kendi kopyalarını TUTMAMALIDIR.

Yeni bir Uzman/Elit varyantı veya Yardımcı çifti eklemek için SADECE bu
dosya değiştirilir; başka hiçbir yerde kod değişikliği gerekmez.
"""

# UnvanID BAZINDA: Uzman/Elit varyant ID'lerinin, ait oldukları BAZ unvan
# ID'sine eşleştirilmesi. Norm sayımında bu varyantlar baz unvanla
# BİRLEŞTİRİLİR (COUNTIFS çoklu zincirle sayılır).
VARYANT: dict[str, list[str]] = {
    "U036": ["U049", "U052"],  # YÖNETİCİ -> Uzman/Elit Yönetici
    "U017": ["U051", "U055"],  # KASİYER -> Uzman/Elit Kasiyer
    "U013": ["U053", "U054"],  # KASAP -> Uzman/Elit Kasap
    "U042": ["U050"],           # ŞARKÜTERİ -> Uzman Şarküteri
}

# UnvanID BAZINDA: Baz unvanın, kendi "Yardımcı" unvanına eşleştirilmesi
# (ör. YÖNETİCİ <-> YÖNETİCİ YARDIMCISI). Norm Eksiği/Fazlası hesaplanırken
# bu ikili birlikte değerlendirilir.
AILE: dict[str, str] = {
    "U036": "U038",  # YÖNETİCİ <-> YÖNETİCİ YARDIMCISI
    "U017": "U019",  # KASİYER <-> KASİYER YARDIMCISI
    "U013": "U014",  # KASAP <-> KASAP YARDIMCISI
    "U042": "U043",  # ŞARKÜTERİ <-> ŞARKÜTERİ YARDIMCISI
}

YARDIMCI_SET: set[str] = set(AILE.values())

# METİN BAZINDA (UnvanID mevcut olmayan/güvenilmez bağlamlar için — ör.
# title-level birleştirmelerde UnvanID taşınmayabiliyor, sadece Unvan METNİ
# güvenilir kalıyor): Uzman/Elit unvan METNİ önekleri.
UZMAN_ELIT_ONEKLERI: tuple[str, ...] = ("UZMAN ", "ELİT ")


def baz_unvan_id(unvan_id: str) -> str:
    """Bir UnvanID'nin, Uzman/Elit varyantıysa BAZ (asıl) UnvanID'sini
    döndürür; değilse kendisini olduğu gibi döndürür."""
    for baz, varyantlar in VARYANT.items():
        if unvan_id in varyantlar:
            return baz
    return unvan_id


def baz_unvan_metni(unvan_metni: str) -> str:
    """Bir unvan METNİNİN (ID değil), Uzman/Elit öneki varsa temizlenmiş
    (baz) halini döndürür; değilse kendisini olduğu gibi döndürür.
    UnvanID güvenilir olmayan bağlamlarda (ör. title-level birleştirme)
    kullanılır."""
    s = str(unvan_metni or "").strip().upper()
    for on_ek in UZMAN_ELIT_ONEKLERI:
        if s.startswith(on_ek):
            return s[len(on_ek):].strip()
    return s
