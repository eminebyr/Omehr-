# OMEHR V19.21.29 - Sürüm Notları

## Doğrulanmış KPI
- Aktif Mevcut: **596**
- Toplam Norm: **607**
- Norm Eksiği: **48**
- Norm Fazlası: **37**
- Net İhtiyaç: **-11**

## Bu sürümde profesyonelleştirilen başlıklar
1. **KPI ve doküman senkronu:** Kılavuz, web mutabakat paneli, doğrulama raporu ve Python motoru aynı KPI sözlüğünü kullanır.
2. **Python hesap motoru:** Web, PDF ve Excel raporları LibreOffice'e bağlı değildir.
3. **Config tabanlı norm kuralları:** Aile, ayrı yardımcı ve yardımcı denge kuralları `config_norm_rules.json` dosyasına alınmıştır.
4. **Sade unvan modu:** `config_features.json` içindeki `raw_title_mode_enabled` bayrağı ile aile birleştirmeden ham unvan hesabı açılabilir. Varsayılan `false` değeridir.
5. **KPI Mutabakat Paneli:** Web Genel Özet sekmesinde kapsam dışı personel, brüt fark, net ihtiyaç ve dağılım/mutabakat farkı birlikte gösterilir.
6. **Otomatik şube diff testi:** 48 şubenin KPI ve ana aile tutarlılığı her build'de test edilir.
7. **Profesyonel kullanım kılavuzu:** Platformun amacı, input doldurma yöntemi, norm ailesi, web paneli, rapor/mail akışı ve hata çözümü tek belgede anlatılır.
8. **Paket hijyeni:** `__pycache__`, `.pytest_cache`, `lo_profile` ve yinelenen eski sürüm notları çıkarılmıştır.

## Norm ailesi
- Yönetici / Uzman Yönetici / Elit Yönetici -> Yönetici
- Manav / Uzman Manav / Elit Manav -> Manav
- Şarküteri / Uzman Şarküteri / Elit Şarküteri -> Şarküteri
- Kasap / Uzman Kasap / Elit Kasap -> Kasap
- Yardımcı unvanlar kendi ayrı normlarında değerlendirilir.

## Yardımcı denge
Yardımcı önce kendi normunu karşılar. Kendi normunun üzerindeki kapasitesi, ana ailede en az bir aktif personel bulunması halinde kalan ana aile açığını dengeleyebilir. Ana ailede sıfır personel varsa yardımcılar ana normu tek başına kapatmaz.

## Panelden Ana Veri Yönetimi
- Fact_Mevcut, Fact_Norm, Dim_Magaza ve Dim_Unvan için web tabanlı ekleme/düzenleme/silme ekranı eklendi.
- Kayıt öncesi veri doğrulama, otomatik input yedeği, atomik dosya yazımı ve audit geçmişi eklendi.
- Formül ve otomatik sütunlar panel kayıtlarında yeniden oluşturulur.
- Ana veri kaynağı mevcut Excel inputudur; mevcut motor ve rapor entegrasyonları korunur.

## Fact_Mevcut H Sütunu Personel Açıklaması
- `Fact_Mevcut` sayfasındaki `H: Açıklama` alanı panelde düzenlenebilir.
- Açıklamalar mağaza ve norm unvanı bazında PDF raporundaki `MEVCUT DURUM AÇIKLAMASI` bölümüne eklenir.
- Kullanıcı tarafından girilen açıklama satırları PDF'de sarı arka planla gösterilir.
- Kutucuklu yönetici Excel raporunda ilgili gerçek unvan hücresine Excel notu eklenir; hücrenin köşesindeki işaret üzerine gelindiğinde açıklama görünür.
- Mağaza başlık hücresinde de mağazaya ait açıklamaların birleşik özeti not olarak bulunur.
