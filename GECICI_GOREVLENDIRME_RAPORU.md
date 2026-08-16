# Geçici Görevlendirme / Şube Destek Formu — Entegrasyon Raporu

## Ne yaptım
Yüklediğiniz belgeyi gerçek bir üçüncü belge türü olarak sisteme
entegre ettim — mevcut **Rotasyon Belgesi** (kalıcı) ve **Atama
Bildirimi** (terfi) belgelerinden AYRI, ama aynı onay akışına bağlı.

## Nasıl çalışıyor
Onaylar ekranında bir transfer talebi "İK Onayladı" olarak
işaretlendiğinde, artık bir seçim çıkıyor:
- **Kalıcı Rotasyon Belgesi** (varsayılan, mevcut davranış — hiçbir
  şey değişmedi)
- **Geçici Görevlendirme / Şube Destek Formu** — seçilirse Bitiş
  Tarihi, Toplam Süre, Görevlendirme Nedeni gibi ek alanlar sorulur

Belge üretimi ve mail gönderimi (worker.py üzerinden, ilgili her iki
mağazaya + bölge sorumlularına — zaten mevcut `transfer_recipients()`
mekanizması bunu otomatik kapsıyor) aynı, tek tıkla, tek akışta olur.

## Bulduğum ve düzelttiğim gerçek hata
İlk üretimde Türkçe karakterler (İ, ı, ş, ğ vb.) PDF'te **siyah kutu**
olarak çıkıyordu — ReportLab'ın varsayılan fontunu kullanmışım.
Rotasyon Belgesi modülündeki TEK, Türkçe-doğrulanmış font kayıt
noktasını (`src/pdf_fonts.font`) kullanacak şekilde düzelttim,
görsel olarak yeniden ürettim ve doğruladım.

## Doğrulama
- Gerçek DOCX+PDF ürettim, ikisini de görsel olarak inceledim — tüm
  alanlar doğru doluyor, çıkış nedeni onay kutusu (☑) doğru işaretleniyor
- **Uçtan uca gerçek akış testi**: worker.py'nin TRANSFER_DECISION
  işleyicisi hem GEÇİCİ hem KALICI türü doğru üretiyor, mail eki
  olarak ekleniyor
- Geriye dönük uyumluluk doğrulandı: `document_type` belirtilmediğinde
  (mevcut 2 onay akışı) eski (kalıcı rotasyon) davranış AYNEN korunuyor
- Bir test dosyasını (eski kodun birebir metnini arıyordu) gerçek
  davranışı doğrulayacak şekilde güncelledim
- **240/240 test geçiyor**, mimari sınır kontrolü temiz, main.py
  uçtan uca çalıştı (596/607/49/23/-26)
