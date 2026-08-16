# V19.21.28 Ünvan Analizi Şema Düzeltmesi

Bu paket, kullanıcının yüklediği `TUM_SUBELER_AILE_DENGE_DUZELTILDI` tam sürümü esas alınarak hazırlanmıştır.

Yalnız `web/tab_modules/unvan_analizi.py` güncellenmiştir:

- Engine Core şemasındaki `Aktif Mevcut / Norm Kadro / Norm Eksiği / Norm Fazlası` alanları web görünümündeki `Mevcut / Norm / Eksik / Fazla` alanlarına güvenli biçimde eşlenir.
- `Gerçek Unvanlar` ve `Personel Adı Soyadı` sabit olarak beklenmez.
- Bu alanlar mevcutsa korunur; yoksa aktif `Fact_Mevcut` kayıtlarından mağaza + norm ailesi bazında yeniden üretilir.
- `Departman` norm ailesi, `Unvan` gerçek personel unvanı, `İsim Soyisim` personel adı olarak kullanılır.
- Eksik sütun nedeniyle pembe KeyError ekranı oluşmaz.

Doğrudan doğrulama:

- Sentetik Uzman Şarküteri örneği başarıyla eşlendi.
- Paket içindeki gerçek input ile 464 ünvan analiz satırı üretildi.
- Gerekli 10 görünüm sütununun tamamı oluşturuldu.

Diğer modüller ve hesap kuralları değiştirilmemiştir.
