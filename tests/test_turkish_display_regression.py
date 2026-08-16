from pathlib import Path

from web.display_text import MAIN_TITLE, display_text


def test_main_title_preserves_turkish_characters():
    assert MAIN_TITLE == "OMEHR Norm Kadro, Transfer ve İş Gücü Optimizasyon Platformu"
    assert display_text("ŞİĞÜÖÇ şığıöç") == "ŞİĞÜÖÇ şığıöç"


def test_web_title_uses_font_independent_rendering():
    """DÜZELTME (4. kez — marka değişikliği): Başlık artık matplotlib
    tarafından üretilen bir SVG glif-anahat dosyası DEĞİL, OMEHR marka
    logosunun kendisi (PNG, st.image ile) — bu da aynı felsefeyi
    (görsel dosya, font/encoding bağımlılığı yok) korur, yalnız kaynağı
    üretilen metin yerine tasarlanmış bir logo dosyası.

    BAKIM NOTU: Bu mekanizma yine değişirse, bu testi silmeyin —
    hangi yöntem kullanılırsa kullanılsın şunları doğrulayacak şekilde
    güncelleyin: (1) tarayıcı sekmesi başlığı (page_config) doğru
    metni içeriyor, (2) görünür başlık gerçekten render ediliyor,
    (3) kullanılan görsel/dosya GERÇEKTEN var.
    """
    root = Path(__file__).resolve().parents[1]
    app = (root / "web" / "app.py").read_text(encoding="utf-8")
    css = (root / "web" / "styles.py").read_text(encoding="utf-8")

    assert 'page_title="OMEHR Norm Kadro, Transfer ve İş Gücü Optimizasyon Platformu"' in app
    assert "&#350;" not in app, "Terk edilmiş HTML varlık kodlaması geri gelmemeli"
    assert "fonts.googleapis.com" not in css

    assert "st.image(str(title_asset)" in app or "omehr_logo.png" in app
    logo_yolu = root / "web" / "assets" / "omehr_logo.png"
    assert logo_yolu.is_file(), "OMEHR logo dosyası eksik — web paneli logosuz açılır"
