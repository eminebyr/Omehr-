# ANA VERİ YÖNETİMİ — PANELDEN VERİ GİRİŞ KILAVUZU

## Amaç
Bu ekran, ana Excel input dosyasını açmadan dört temel veri tablosunu web panelinden yönetmek için hazırlanmıştır:

- **Personel / Fact_Mevcut**
- **Norm Kadro / Fact_Norm**
- **Mağaza Sözlüğü / Dim_Magaza**
- **Unvan Sözlüğü / Dim_Unvan**

Ana veri kaynağı yine `input/OMEHR_AI_NORM_TRANSFER_INPUT.xlsx` dosyasıdır. Panelde kaydedilen değişiklikler bu dosyaya yazılır; mevcut norm, transfer, PDF/Excel ve Outlook motorları aynı dosyayı okumaya devam eder.

## Yetki
Ekran yalnız ADMIN ve İK Direktörü rollerine açıktır.

## Kullanım sırası
1. Web panelinde **Ana Veri Yönetimi** sekmesine girin.
2. İlgili alt sekmeyi açın.
3. Hücreyi düzenleyin, yeni satır ekleyin veya satırı silin.
4. **Kontrol ve Kaydet** sekmesine geçin.
5. Veri doğrulamasında hata yoksa **Değişiklikleri Kaydet** düğmesine basın.
6. Üst bölümden **Tüm tabloları şimdi yenile** işlemini çalıştırın.
7. KPI, rapor ve transfer sonuçlarını kontrol edin.

## Güvenlik ve geri alma
Her kayıt öncesinde input dosyasının tarih-saatli yedeği `backups` klasörüne alınır. Değişiklik geçmişi `logs/ana_veri_degisiklik_gecmisi.csv` dosyasına yazılır.

## Önemli kurallar
- **İsim Soyisim benzersiz anahtardır.** Aynı ad-soyad iki kez kaydedilemez.
- `Departman`, norm ailesini; `UnvanID`, gerçek unvanı temsil eder.
- Aynı `MağazaID + UnvanID` norm satırı iki kez girilemez.
- Dim_Magaza veya Dim_Unvan içinde olmayan kodlar Fact tablolarına kaydedilemez.
- Formül/otomatik sütunlar panelde gösterilmez; kayıt sırasında yeniden oluşturulur.
