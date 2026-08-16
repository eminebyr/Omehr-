# İkinci Kritik, Canlı Üretim Hatası — Kutucuklu Yönetici Raporu Sayfaları

## Bulduğum hata
Bir önceki turdaki `family_balance.py` düzeltmesini yaparken sapmıştım
ve asıl araştırdığım şeyi (excel_report.py'deki sabit `groups` listesi)
hiç düzeltmemiştim. Bu turda tamamladım.

`src/excel_report.py::build_boxed_manager_excel()` — Kutucuklu Yönetici
Raporu'nu üreten fonksiyon — 4 SABİT, orijinal firmanın gerçek bölge
sorumlusu ismine göre sayfa oluşturuyordu ("Ali Çelik", "Derya
Yardımcı", "Cüneyt & Ayşe Avcu", "Ertan Teki"). **BAŞKA HER kiracı
için bu 4 sayfanın TAMAMI sessizce BOŞ üretilirdi** — rapor "başarıyla"
oluşur ama hiçbir mağaza verisi göstermezdi.

## Düzeltme
Sayfalar artık TENANT'IN KENDİ verisinde gerçekten var olan "Bölge
Sorumlusu" değerlerinden dinamik türetiliyor — sabit bir isim listesine
ihtiyaç duymadan, `canon()` normalizasyonuyla (zaten Türkçe karakter/
büyük-küçük harf farklarını tekilleştiriyor).

## Doğrulama
- **Orijinal veri**: aynı 4 sayfa, aynı dolu satır sayıları — sıfır
  regresyon
- **Farklı (gerçek olmayan) kiracı isimleriyle**: 3 yeni sayfa, 501
  satır dolu veri üretildi — eskiden bu TAMAMEN BOŞ 4 sabit sayfa verirdi
- Kalıcı regresyon testi eklendi

## Yan bulgu: 2 eski test de eski (hatalı) davranışı varsayıyordu
Biri, "Cüneyt Çıkrıkçı" ve "Ayşe Avcu" gibi İKİ FARKLI ismin bile tek
sayfada zorla birleştirilmesini bekliyordu — bu, orijinal firmaya özel
bir "ortak yönetici" kuralıydı ve gerçek üretim verisinde zaten TEK
birleşik metin olarak saklanıyor. İkisini de doğru, kiracıdan-bağımsız
davranışa göre güncelledim.

## Doğrulama
**256/256 test geçiyor** (2 yeni test eklendi), mimari + regresyon
bariyerleri temiz, main.py uçtan uca çalıştı (596/607/49/23/-26, 9
Excel dosyası üretildi).
