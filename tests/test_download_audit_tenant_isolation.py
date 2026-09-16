"""İNDİRME DENETİM KAYDI (KVKK) — ÇOK KİRACILI İZOLASYON regresyon testi.

Denetim bulgusu: tek süreç birden fazla kiracıya hizmet ettiğinde
(web girişinde firma seçimi), services/download_audit.py, runtime_root()
üzerinden TÜM kiracılar arasında paylaşılan tek bir download_audit.db
dosyasını kiracı ayrımı YAPMADAN kullanıyordu — bir firmanın KVKK
indirme denetim kaydı (kim, ne zaman, hangi kişisel-veri içeren dosyayı
indirdi) her firmanın İK/Admin kullanıcısına görünüyordu.
"""
from __future__ import annotations


def test_iki_kiracinin_indirme_kaydi_karismaz(isolated_root, monkeypatch):
    from services.download_audit import kaydet, son_kayitlar

    monkeypatch.setenv("OMEHR_TENANT", "KIRACI_A")
    kaydet("ahmet", "A_Firmasi_Rapor.pdf", rol="IK")

    monkeypatch.setenv("OMEHR_TENANT", "KIRACI_B")
    kaydet("mehmet", "B_Firmasi_Rapor.pdf", rol="IK")

    kayitlar_a = son_kayitlar(200, tenant_id="KIRACI_A")
    kayitlar_b = son_kayitlar(200, tenant_id="KIRACI_B")

    assert len(kayitlar_a) == 1 and kayitlar_a[0]["dosya_adi"] == "A_Firmasi_Rapor.pdf"
    assert len(kayitlar_b) == 1 and kayitlar_b[0]["dosya_adi"] == "B_Firmasi_Rapor.pdf"
    assert not any(k["dosya_adi"] == "B_Firmasi_Rapor.pdf" for k in kayitlar_a), \
        "KRİTİK SIZINTI (KVKK): KIRACI_A, KIRACI_B'nin indirme kaydını görüyor!"


def test_eski_kiracisiz_kayitlar_varsayilan_kiraciya_ait_sayilir(isolated_root, monkeypatch):
    """Göç öncesi (tenant_id sütunu eklenmeden önce) yazılmış satırlar
    varsayılan 'OMEHR' kiracısına düşer ve başka bir kiracıya SIZMAZ."""
    import sqlite3
    from datetime import datetime
    from services.runtime_paths import runtime_root

    monkeypatch.setenv("OMEHR_TENANT", "OMEHR")
    db_path = runtime_root() / "data" / "download_audit.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.execute(
        """CREATE TABLE indirme_kayitlari (
            id INTEGER PRIMARY KEY AUTOINCREMENT, kullanici TEXT NOT NULL,
            rol TEXT, dosya_adi TEXT NOT NULL, zaman TEXT NOT NULL)"""
    )
    con.execute(
        "INSERT INTO indirme_kayitlari (kullanici, rol, dosya_adi, zaman) VALUES (?,?,?,?)",
        ("eski_kullanici", "IK", "eski_rapor.pdf", datetime.now().isoformat()),
    )
    con.commit()
    con.close()

    from services.download_audit import son_kayitlar

    assert len(son_kayitlar(200, tenant_id="OMEHR")) == 1
    assert son_kayitlar(200, tenant_id="KIRACI_A") == []
