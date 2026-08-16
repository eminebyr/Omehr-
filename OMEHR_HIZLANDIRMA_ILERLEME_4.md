# OMEHR Hızlandırma Şartnamesi — İlerleme Raporu #4 (Madde 11-15)

## Madde 11: İşe Giriş doğrulaması
**Gerçek eksik bulundu:** `add_personnel()` servis fonksiyonu hiçbir
doğrulama yapmıyordu — yalnız UI'daki selectbox'larla DOLAYLI koruma
vardı. Servis katmanına 4 doğrulama eklendi: mağaza geçerliliği, unvan
geçerliliği, zorunlu alanlar, mükerrer aktif personel. 5 senaryoyla
(4 red + 1 kabul) gerçek veride doğrulandı.

## Madde 13/76: Gelecek tarihli çıkış kuralı
**İki kural çelişkiye düştü** — mevcut kod "çıkış kaydedilince ANINDA
pasif" (bilinçli önceki karar), şartname "çıkış tarihine kadar aktif"
istiyordu. **Sizinle netleştirildi: şartnamedeki kural doğru.**
İncelemede bu değişikliğin ZATEN (muhtemelen bu oturumun daha önceki
bir bölümünde) doğru şekilde uygulandığı görüldü — şartnamenin TAM
örnek senaryosuyla (10.08→aktif, 16.08→pasif) yeniden doğrulandı.
Gerçek üretim verisinde hiç gelecek tarihli çıkış olmadığı için
596/607/49/23/-26 rakamları etkilenmedi.

## Madde 15: Toplu çıkış hata izolasyonu
**İkinci bir çelişki bulundu** — mevcut kod bilinçli olarak "tek hata
TÜM toplu işlemi reddeder" tasarımındaydı. **Sizinle netleştirildi:
şartnamedeki kural (her satır bağımsız) doğru.** Servis katmanı VE
web arayüzü (`personel_kartlari.py`) tamamen yeniden tasarlandı:
- Servis: her satır ayrı doğrulanır, geçerliler TEK yazmayla
  kaydedilir (verimlilik korunur), geçersizler ayrı raporlanır
- UI: ön-doğrulama artık İLK hatada durmuyor, geçersiz satırı atlayıp
  devam ediyor; mail SADECE gerçekten başarılı olanlara gidiyor
- Gerçek karışık senaryoyla (2 geçerli + 1 uyumsuz + 1 geçersiz index)
  doğrulandı: geçerliler kaydedildi, geçersizler etkilenmeden atlandı

## KRİTİK EK BULGU: common_veri_okuma.py'de test-izolasyon hatası
Madde 13 testini tam pakette çalıştırırken bir test başarısız oldu
(tek başına geçiyordu). Kök neden: `common_veri_okuma.py`'de
`ROOT = runtime_root()` MODÜL SEVİYESİNDE, import anında BİR KEZ
hesaplanıyordu — Python modülleri process boyunca yalnız bir kez
import edildiği için, `BASDAS_RUNTIME_ROOT` SONRADAN değişse bile bu
YANSIMIYORDU. Bu, hem test izolasyonunu BOZUYORDU hem de TEORİK
olarak üretimde (runtime kökü değişebilecek herhangi bir senaryoda)
bir risk oluşturabilirdi. Her çağrıda taze çözümlenecek şekilde
düzeltildi.

## Doğrulama
**281/281 test geçiyor** (düzeltilen/eklenen testler dahil), mimari +
regresyon bariyerleri temiz, main.py uçtan uca çalıştı
(596/607/49/23/-26).

## Sırada
Madde 16-21 (Atama modülü, ATAMA_NO, Rotasyon/Transfer durum
makinesi) ile devam edilecek.
