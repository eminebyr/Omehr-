# Bulduğunuz 2 Eksik — Düzeltildi

## 1. CI workflow gerçekten 0 byte'tı
Doğruladım — `.github/workflows/tests.yml` gerçekten boştu (yer tutucu
kalmış, içeriği hiç kopyalanmamış). V20 kaynak paketindeki gerçek
içeriği (GitHub Actions ile derleme+mimari+gizli-bilgi+test doğrulaması
+ doğrulanmış ZIP üretimi) kopyaladım. Şimdi 731 byte, gerçek bir
workflow.

## 2. Sürüm etiketi
V20 kaynak paketinin KENDİSİNDE de "19.21.28" yazıyordu (V20 bir
sürüm numarası değil, teslim/sertleştirme turunun adıydı) — yani bu
benim eksikliğim değildi. Ama haklısınız, bu kadar önemli bir
sertleştirme turu sürüm numarasına yansımalı. `APP_VERSION`'ı
**19.21.29**'a yükselttim ve şu noktaların HEPSİNİ senkronladım:
- `services/version.py` (tek kaynak)
- `00_OKU_CURRENT.txt`, `SURUM_NOTLARI.md`, `DOGRULAMA_RAPORU.md`,
  `KISA_KURULUM.txt`
- `KULLANICI_KILAVUZU.docx` (gövde + alt bilgi) — PDF'i yeniden
  ürettim
- **Gerçek main.py çalıştırmasının günlüğünde doğruladım**: "19.21.29
  başarıyla tamamlandı" yazıyor.

(Kalan "19.21.28" referansları yalnız GEÇMİŞ düzeltmeleri belgeleyen
tarihsel not dosyalarında — bunlar bilinçli olarak değiştirilmedi,
tıpkı bir commit geçmişini yeniden yazmamak gibi.)

## Doğrulama
240/240 test geçiyor, mimari kontrol temiz, main.py gerçek veriyle
uçtan uca çalıştı (596/607/49/23/-26), CI dosyası artık gerçek içerik
taşıyor.
