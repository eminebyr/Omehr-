# Outlook Staging Temizlik Mekanizması

## Ne yapıldı
`output/Outlook_Hazir/` klasöründeki (her gönderim için üretilen,
SHA-256 doğrulanmış, tek kullanımlık kopyalar) dosyalar için hiçbir
temizleme mekanizması yoktu — bu oturumun test çalıştırmalarından
**1025 birikmiş dosya** bulundu ve silindi.

## Düzeltme
`report_mail_engine.py`'ye yaş bazlı (48 saatten eski) otomatik
temizleme fonksiyonu eklendi, her gönderim çalıştırmasının SONUNDA
otomatik çağrılıyor. `backup.py`'deki mevcut temizlik desenine
(safe_exec loglama, silinemeyen dosyada işlemi durdurmama) uyumlu.

## Doğrulama
- Gerçek fonksiyon çağrısıyla test edildi: 49 saatlik dosya silindi,
  1 saatlik dosya korundu
- 2 kalıcı regresyon testi eklendi
- **Tam test paketi (71 dosya, gruplar halinde) yeniden çalıştırıldı,
  hepsi geçti**
- Mimari + regresyon bariyerleri temiz
- main.py uçtan uca çalıştı (596/607/49/23/-26)
