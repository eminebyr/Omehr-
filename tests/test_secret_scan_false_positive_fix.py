from __future__ import annotations

"""secret_scan() — yanlış-pozitif ve gerçek sızıntı ayrımı regresyon testi.

Önceden .env.example DIŞINDAKİ hiçbir dosya için "bu bir yer tutucu"
muafiyeti yoktu — UCRETSIZ_CANLIYA_ALMA_REHBERI.md'deki AÇIKÇA
kullanıcıya yönelik bir talimat metni ("kendi-seçtiğiniz-güçlü-bir-
şifre-2026!") gerçek bir sızıntı gibi işaretleniyordu.
"""

import sys
sys.path.insert(0, "tools")


def test_instructional_placeholder_in_md_is_not_flagged(tmp_path):
    from verify_release import secret_scan

    (tmp_path / "REHBER.md").write_text(
        'BASDAS_ADMIN_PASSWORD = "kendi-seçtiğiniz-güçlü-bir-şifre-2026!"',
        encoding="utf-8",
    )
    sonuc = secret_scan(tmp_path)
    assert sonuc == [], f"REGRESYON: talimat metni yanlış-pozitif veriyor: {sonuc}"


def test_real_secret_in_md_is_still_caught(tmp_path):
    from verify_release import secret_scan

    (tmp_path / "sizinti.md") .write_text(
        'BASDAS_ADMIN_PASSWORD = "GercekSifre123456"',
        encoding="utf-8",
    )
    sonuc = secret_scan(tmp_path)
    assert "sizinti.md" in sonuc, (
        "REGRESYON: gerçek bir sızıntı artık yakalanmıyor — muafiyet çok geniş."
    )


def test_real_secret_alongside_unrelated_example_word_is_still_caught(tmp_path):
    """Aynı dosyada BAŞKA bir yerde 'örnek' kelimesi geçse bile, GERÇEK
    bir sızıntı satırının yakalanması gerektiğini doğrular (satır-bazlı
    kontrol, dosya-genelinde değil)."""
    from verify_release import secret_scan

    (tmp_path / "karisik.md").write_text(
        "Bu bir örnek doküman.\n\n"
        'BASDAS_ADMIN_PASSWORD = "GercekSizintiSifre999"\n',
        encoding="utf-8",
    )
    sonuc = secret_scan(tmp_path)
    assert "karisik.md" in sonuc, (
        "REGRESYON: dosyada BAŞKA yerde 'örnek' kelimesi geçtiği için "
        "gerçek bir sızıntı satırı gözden kaçıyor (muafiyet dosya-genelinde "
        "uygulanıyor olabilir, satır-bazlı olması gerekirdi)."
    )
