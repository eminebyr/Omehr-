# Personel Yönetimi — Panel Kaynaklı Yeni Mimari

## Ne değişti?
- `Fact_Mevcut` günlük personel hareketlerinde artık Excel'den yönetilmez.
- Paket içindeki mevcut `Fact_Mevcut` personelleri `data/personnel_registry.db` siciline aktarılmıştır.
- Web paneline **Personel Yönetimi** sekmesi eklendi.
- Yeni işe giriş, personel açıklaması, mağaza/unvan/departman düzeltmesi ve işten çıkış bu ekrandan yapılır.
- İşten çıkışta kayıt silinmez; sicil geçmişinde kalır, ancak `Aktif Mevcut` hesabından otomatik çıkar.
- Web, KPI, norm, transfer ve rapor motorları `Fact_Mevcut` verisini panel sicilinden alır.
- Excel input dosyası diğer ana tablolar/operasyon verileri için kullanılmaya devam eder. `Fact_Mevcut` ise yalnız başlangıç aktarımı ve uyumluluk/yedek kopyasıdır.

## İlk veri
Bu paket hazırlanırken mevcut Excel'deki 596 personel satırı sicile gömülmüştür. Eski Excel tekrar açıldığında bu sicili ezmez.

## Günlük kullanım
1. Yeni personel geldiğinde: `Personel Yönetimi > Yeni İşe Giriş`.
2. Açıklama veya mağaza/unvan değişikliği: `Personel Yönetimi > Personel Düzenle`.
3. Çıkış olduğunda: `Personel Yönetimi > İşten Çıkış`.
4. Çıkış kaydedildiği anda personel `Pasif` olur; panel yeniden yüklendiğinde aktif mevcut otomatik düşer.
5. Hatalı çıkış işlemi `Sicil / Geçmiş` ekranından geri alınabilir.

## Tek doğru kaynak
Varsayılan `OMEHR_PERSONNEL_SOURCE=panel` davranışıdır. Eski davranışa zorunlu dönüş gerekirse ortam değişkeni `OMEHR_PERSONNEL_SOURCE=excel` yapılabilir.
