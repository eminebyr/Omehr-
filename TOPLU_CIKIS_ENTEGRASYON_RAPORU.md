# Toplu İşe Giriş/Çıkış Entegrasyonu — Rapor

## Entegre edilen (istediğiniz) özellik
- **Toplu İşe Giriş**: Birden fazla personel tek tabloda hazırlanıp tek
  yazma işlemiyle kaydediliyor.
- **Toplu İşten Çıkış**: Birden fazla personel seçilip, HER BİRİ KENDİ
  çıkış kodu/nedenini taşıyabiliyor (hepsi aynı olmak zorunda değil).
  Kod ve neden aynı grupta değilse kayıt reddediliyor.
- Her iki işlem de otomatik e-posta bildirimi tetikliyor (ilgili mağaza,
  bölge sorumlusu, admin/İK).

## Entegrasyon sırasında bulduğum ve düzelttiğim ciddi hatalar
Yüklediğiniz paket, SaaS/çok-kiracı dönüşümünden ÖNCEki bir daldı.
İncelerken, kodun ÇEŞİTLİ yerlerinde **belirli bir gerçek kişinin adı/
e-postasının paylaşılan koda gömülü** olduğunu buldum — çok kiracılı
bir SaaS'ta bu, bir firmanın verisinin/bildirimlerinin başka bir
firmaya sızması anlamına gelirdi. 6 ayrı yerde düzelttim:

| Dosya | Sorun | Düzeltme |
|---|---|---|
| `personnel_notifications.py` | Her bildirime sabit kişisel e-posta ekleniyordu | Kaldırıldı |
| `message_personalization.py` | "ik1" kullanıcısı ve CEO, belirli bir kişinin adıyla eşleştiriliyordu | Genel rol tabanlı mantığa çevrildi |
| `web/accounts.py` | `NOTIFY_TO` sabit listesi HER transfer bildirimine 4 adres CC'liyordu | Kaldırıldı |
| `web/app.py` | `APPROVERS` sabit e-posta listesi onay yetkisi veriyordu | Kaldırıldı (rol tabanlı kontrol zaten yeterliydi) |
| `puantaj_hatirlatma.py` | Otomatik e-postada sabit adres + "Omehr Market" imzası | Kiracının kendi verisinden dinamik çözümleme + OMEHR markası |
| `management_center.py` | CEO rolündeki HER kullanıcı belirli bir kişinin adıyla gösteriliyordu | Düzeltildi |

## Doğrulama
- **233/233 test geçiyor**
- **Gerçek uçtan uca fonksiyonel test**: 3 kişi toplu eklendi (596→599),
  3 FARKLI çıkış kodu/nedeniyle toplu çıkarıldı (599→596) — her kişinin
  gerçekten kendi kodunu taşıdığı doğrulandı (İstifa / İşveren feshi /
  Karşılıklı-Deneme)
- **Bildirim sızıntısı testi**: sabit kişisel e-postanın artık hiçbir
  otomatik alıcı listesinde yer almadığı doğrulandı
- `main.py` gerçek veriyle uçtan uca çalıştı (exit 0, 596/607/49/23/-26)
