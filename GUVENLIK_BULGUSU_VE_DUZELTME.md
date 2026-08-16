# KRİTİK GÜVENLİK BULGUSU — Örnek Veri Dosyasının Pakete Sızması

## Bulunan sorun
`input/` ve `ORNEK_TEST_VERISI/` klasörlerindeki örnek Excel dosyası
(Mail_Listesi sayfası), bu oturumdaki HER teslim edilen pakette
**şunları düz metin olarak içeriyordu**:
- 12 kullanıcının gerçek görünen giriş şifreleri (Admin1, Ertan1,
  Halit1, Faruk1 vb.)
- Gerçek bir şirket domaini (@basdasmarket.com)
- Gerçek görünen kişi isimleri (biri şirketin adıyla aynı soyadı
  taşıyor)

Bu, önceki bir soruda ("şifreler içeri atılıyor mu?") yalnız KAYNAK
KODU kontrol edip "hayır" dediğimde GÖZDEN KAÇMıştı — paketlenen
ÖRNEK VERİ DOSYASININ İÇERİĞİNİ kontrol etmemiştim.

## Belirsizlik ve karar
Bu verinin gerçek şirket verisi mi yoksa bilerek sağlanan test verisi
mi olduğu netleştirilemedi. **Belirsizlik durumunda en güvenli
varsayım seçildi: veriyi paketten hariç tutmak** — bu, hangi cevap
doğru olursa olsun zarar vermez (gerçekse korur, kasıtlı test
verisiyse zaten her üretim teslimatına gömülü olmaması gerekir).

## Düzeltme
`tools/build_clean_package.py`'nin `EXCLUDED_DIRS` listesine `input`
ve `ORNEK_TEST_VERISI` eklendi. Kalıcı bir regresyon testi eklendi
(`tests/test_packaging_excludes_sample_data.py`) — bu iki klasörün
bir daha sessizce pakete sızmasını engeller.

## Doğrulama
- Yeniden paketlenip GERÇEKTEN sıfır dosya sızdığı doğrulandı
- **Tam test paketi (71 dosya, gruplar halinde) yeniden çalıştırıldı
  — hepsi geçti**
- Süreç içinde, paylaşılan `input/` dosyasının BAŞKA bir testin
  (test_shipped_config_norm_rules.py, kendi main.py subprocess'ini
  proje kök dizininde çalıştırıyor) yan etkisiyle GEÇİCİ olarak
  bozulduğu fark edildi ve düzeltildi — bu, paketleme değişikliğimle
  ilgisizdi (önceden var olan bir test-izolasyon sorunu, ayrıca not
  edildi)
- Mimari + regresyon bariyerleri temiz
- main.py uçtan uca çalıştı (596/607/49/23/-26)

## Önemli not
Bu, `input/` ve `ORNEK_TEST_VERISI/` klasörlerinin yalnız PAKETTEN
çıkarıldığı anlamına gelir — geliştirme/çalışma zamanı ortamında
(main.py'nin gerçekten çalışması için gereken `input/` klasörü) hiçbir
şey değişmedi. Kullanıcı, GERÇEK şirket verisini kendi `input/`
klasörüne KENDİSİ yerleştirecektir (zaten mevcut kurulum akışı böyle).
