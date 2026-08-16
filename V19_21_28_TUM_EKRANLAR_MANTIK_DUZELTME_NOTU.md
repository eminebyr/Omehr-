# V19.21.28 — Yönetim Ekranları Mantık Düzeltmeleri

Bu teslimde yalnız kullanıcı tarafından ekranda tespit edilen mantık ve adlandırma sorunları düzeltilmiştir.

- AI toplamı; **AI önerilen norm / brüt açık / brüt fazla / net fark** olarak ayrıldı. “AI kapasite açığı” adı kaldırıldı.
- Reel büyüme, basit çıkarma yerine bileşik formülle hesaplanır: `(1+nominal)/(1+enflasyon)-1`.
- Personel ekranı gerçek kişi performansı gibi sunulmaz; **Mağaza Bazlı Proxy Performans Risk Göstergesi** olarak adlandırılır. Transfer, ücret, terfi, disiplin ve feshe otomatik etkisi yoktur.
- İş gücü tahmini düşük güvenliyse “Ham Tahmin Adayı” olarak gösterilir.
- Turnover gözlemi olmayan “Varsayılan” oran yayımlanan kadroya doğrudan eklenmez; senaryo sütununda tutulur.
- Fazla mesai ve kayıp kapasite tamponları çifte sayılmaz; yayımlanan hesapta büyük olan kullanılır.
- Mağaza veya unvan eşleşmesi olmayan satırlar yönetici toplamlarından çıkarılır ve `Veri_Kalitesi_Eslesmeyen` sayfasına yazılır.
- Tahmin raporuna `Operasyon Tampon FTE`, `Turnover Riski FTE (Senaryo)` ve `Yuvarlama Etkisi Kişi` alanları eklendi.
- Operasyon backtestinin kadro doğruluğu olmadığı web ekranında açıkça belirtilir.

Norm/transfer çekirdeği, REFERENTIAL_CONTROL, aile dengesi, rotasyon/onay, Outlook ve rapor akışları değiştirilmemiştir.
