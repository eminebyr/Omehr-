# Mail Bildirimi — Eksik Bulundu ve Düzeltildi

## Soru: Girişlerde ve çıkışlarda mail atıyor mu?
Kontrol ettim: 5 personel akışından 4'ü mail gönderiyordu, biri
göndermiyordu.

| İşlem | Önceki durum |
|---|---|
| Tekli/toplu işe giriş | ✅ Gönderiyordu |
| Tekli/toplu işten çıkış | ✅ Gönderiyordu |
| Çıkışı Geri Al | ❌ Göndermiyordu |

## Düzeltme
"Çıkışı Geri Al" işlemine de bildirim eklendi — yeni bir olay türü
(CIKIS_GERI_ALINDI) tanımlandı. Artık bir çıkış yanlışlıkla işlenip
geri alındığında, aynı mağaza/bölge/İK kişileri "önceki çıkış
bildirimini dikkate almayın, personel yeniden aktif" bilgisini alıyor.

## Kimlere gidiyor (5 işlemin de aynısı)
Otomatik: ilgili mağaza + o mağazanın bölge sorumlusu + aktif admin/İK
yöneticileri. Ek olarak panelden seçilen kişiler.

## Doğrulama
Gerçek fonksiyonel testle doğrulandı — doğru alıcılar (mağaza + bölge
sorumlusu) bulundu, mail gönderim mantığı uçtan uca çalışıyor (bu
ortamda SMTP tanımlı olmadığı için "SKIPPED" dönüyor, gerçek kurulumda
gönderilir). 233/233 test geçiyor.
