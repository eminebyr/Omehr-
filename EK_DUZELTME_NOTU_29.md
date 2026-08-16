# Ek düzeltme notu (bu teslim)

## 1. Paket yapısı hatası — iç içe tam kopya
Yüklenen zip, tüm projenin (269 dosya, 7.4MB) YANLIŞLIKLA bir
`basdas_toolbar_fix/` alt klasörüne kopyalanıp öyle paketlenmiş halini
içeriyordu — dış kök eski (04:32), iç klasör güncel (21:40, gerçek
toolbar düzeltmesini içeriyordu). İç (doğru/güncel) kopya taban alındı,
dış bayat kopya atıldı.

## 2. Belgeler arası KPI senkron hatası (sizin bulduğunuz)
`00_OKU_CURRENT.txt` bu pakette (doğru iç kopyada) zaten 49/23/-26
gösteriyordu — ama DOGRULAMA_RAPORU.md, SURUM_NOTLARI.md ve
KULLANICI_KILAVUZU.docx/pdf hâlâ eski 47/-24 taşıyordu. Hepsi 49/23/-26
olarak düzeltildi ve PDF yeniden üretildi.

## Doğrulanan (değişmeden korunmuş)
- REFERENTIAL_CONTROL ezmesi kasıtlı davranışı olarak korunmuş (doğru).
- Yardımcı unvan dengeleme düzeltmesi korunmuş.
- Yeni "Ana Veri Yönetimi" paneli ve testi (`test_master_data_admin.py`)
  gerçekten çalışıyor.
- Yeni Plotly araç çubuğu (zoom/dışa aktarma) düzeltmesi pakette.
- E-posta gövdesi, venv yolu, image-only PDF, assets/fonts, .bat
  temizliği, gizlilik — hepsi sağlam.

## Doğrulama
178/178 test geçiyor (3 dürüst xfail), main.py gerçek 64 sayfalık
üretim verisiyle uçtan uca çalıştı (exit 0) ve tam olarak
Norm Eksiği=49, Norm Fazlası=23, Net İhtiyaç=-26 üretti.
