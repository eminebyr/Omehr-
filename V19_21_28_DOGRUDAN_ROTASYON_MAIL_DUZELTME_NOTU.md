# V19.21.28 — Doğrudan İK Onayında Rotasyon Evrakı

Bu güncelleme yalnız transfer/rotasyon gönderim akışını düzeltir.

- Transfer Merkezi'nde **İK doğrudan yetkisiyle onaylı** oluşturulan talep artık normal İK onayıyla aynı `TRANSFER_DECISION` akışını çalıştırır.
- Rotasyon PDF ve DOCX belgeleri anında oluşturulur.
- Belgeler devreden ve devralan şube alıcılarına Outlook e-postasıyla gönderilir.
- Onaylar sekmesine, daha önce onaylanmış kayıtlar için **Rotasyon evrakını yeniden oluştur ve gönder** düğmesi eklenmiştir.
- Açıkça yeniden gönderim seçildiğinde önceki idempotency kaydı yeni gönderimi engellemez.
- Norm, rapor, personel açıklaması, web sekmeleri, yetki ve input yapısında başka değişiklik yapılmamıştır.
