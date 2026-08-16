# OMEHR Marka Değişikliği — Doğrulama Raporu

## Kapsam kararı
Kullanıcı-görünür marka metni/logosu (web başlığı, sayfa başlığı,
PDF/Excel rapor başlıkları, kılavuz) BAŞDAŞ → OMEHR olarak değiştirildi.
Teknik/dahili isimlendirmelere (ortam değişkenleri BASDAS_RUNTIME_ROOT
vb., dosya adları BASDAS_AI_NORM_TRANSFER_INPUT.xlsx, .bat betikleri,
veritabanı tablo önekleri) BİLİNÇLİ olarak dokunulmadı — bunları
değiştirmek tüm kurulu sistemleri, testleri ve otomasyon betiklerini
kırar.

## Logo entegrasyonu
Yüklediğiniz logo (`web/assets/omehr_logo.png`) doğru şekilde kırpılıp
(fazla boşluk temizlenerek) web panelinin ana başlık alanına
yerleştirildi. Görsel olarak render edip kontrol ettim.

## Doğruladığım (gerçek çıktıda, yalnız kaynak kodda değil)
- **Web**: sayfa başlığı, ana logo, tasarım paleti (lacivert/teal/altın)
  — tümü OMEHR'e uyumlu.
- **PDF raporları**: gerçek main.py çalıştırmasından üretilen PDF'leri
  render edip görsel olarak inceledim — kapak sayfası ve alt bilgi
  "OMEHR Norm Kadro, Transfer ve İş Gücü Optimizasyon Platformu"
  gösteriyor, grafik renkleri yeni paletle uyumlu.
- **Excel raporları**: gerçek üretilen dosyada "OMEHR..." başlığını
  bizzat buldum.
- **Kılavuz**: gövde metninde 0 BAŞDAŞ, alt bilgide "OMEHR V19.21.28..."

## Bulduğum ve düzelttiğim tek gerçek eksik
`tests/test_turkish_display_regression.py` senkron dışı kalmıştı —
eski SVG mekanizmasını ve "BAŞDAŞ" metnini bekliyordu. Yeni PNG logo
mekanizmasını doğrulayacak şekilde güncellendi (dosya varlığı + boyut
makullüğü kontrolü, artık metin araması değil çünkü logo artık
üretilen bir SVG değil, gerçek bir görsel dosya).

## Doğrulama
223/223 test geçiyor, main.py gerçek veriyle uçtan uca çalıştı (exit 0,
596/607/49/23/-26), PDF ve Excel çıktıları görsel/programatik olarak
OMEHR markasını doğru taşıdığı doğrulandı.
