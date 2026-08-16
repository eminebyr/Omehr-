# Mimari Ayrıştırma + Performans Turu

## 1) "Sekmeler hızlı açılsın"
**Kök neden bulundu:** 10 sekme modülü (ceo_ozet, performans,
isgucu_tahmini, operasyon_gorselleri, verimlilik_gorselleri,
ai_operasyon, ai_geri_bildirim, veri_toplama, personnel_notifications,
management_center), zaten önbelleğe alınmış veriler varken kendi
başlarına Excel'i TEKRAR TEKRAR okuyordu. Ölçüldü: ek sayfa okuması
başına ~0,5 saniye.

**Düzeltme:** Yeni, merkezi bir önbellek katmanı
(`services/cached_excel_reader.py`) — dosyanın mtime+boyutuna göre
anahtarlanır, `header` parametresi DAHİL tam doğru okuma semantiğini
korur (bazı sayfalar `header=1` kullanıyordu, bu detay atlanırsa yanlış
sütun eşlemesi olurdu — bunu tespit edip düzelttim). ~40 okuma noktasını
buna yönlendirdim. Yazma amaçlı workbook nesnelerini (veri bozulması
riski nedeniyle) BİLEREK önbelleklemedim.

**Ölçülen gerçek iyileşme:** 3 sekme gezintisi x 10 sayfa: 8,69 sn →
3,04 sn (2,9x). `management_center.py` (Genel Özet dahil en çok
ziyaret edilen sayfalardan çağrılıyor) ayrıca düzeltildi.

## 2) "Mailler hızlı gitsin"
**Kök neden bulundu:** `send_outlook()` Windows Outlook'u COM
otomasyonuyla kontrol ediyor — bu doğası gereği birkaç saniye sürebilir.
Önceden bu, "Kaydet ve Bildir" butonunun İÇİNDE, senkron çalışıyordu —
buton bu süre boyunca donmuş görünüyordu.

**Düzeltme:** Zaten sürekli arka planda çalışan (`BASDAS_CURRENT_
BASLAT.bat`'ta otomatik başlayan) `worker.py` kuyruk mekanizmasını
keşfedip personel bildirimlerini buna yönlendirdim. Ayrıca
`personnel_notifications.py`'nin KENDİ İÇİNDEKİ okumaların da
önbelleksiz olduğunu bulup düzelttim (aynı sınıf hata).

**Ölçülen gerçek iyileşme:** Tek bir bildirim çağrısı: 5,6 sn → 1,19 sn
(soğuk) → 0,014 sn (sıcak, gerçekçi kullanım senaryosu — 85x). Kuyruğa
alınan mailin worker tarafından GERÇEKTEN işlendiği uçtan uca doğrulandı
(idempotency koruması dahil çalışıyor).

## Doğrulama
240/240 test geçiyor, mimari sınır kontrolü temiz, main.py gerçek
veriyle uçtan uca çalıştı (exit 0, 596/607/49/23/-26).
