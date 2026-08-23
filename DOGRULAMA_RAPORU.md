# OMEHR V19.21.29 - Doğrulama Raporu

## Sonuç
**UYGUN - Python norm motoru ve web şeması doğrulandı.**

## KPI
| KPI | Değer |
|---|---:|
| Aktif Mevcut | 596 |
| Toplam Norm | 607 |
| Norm Eksiği | 48 |
| Norm Fazlası | 37 |
| Net İhtiyaç | -11 |

## Yapılan kontroller
- 48 farklı şube motor çıktısında bulunuyor.
- Ana aile mevcut sayısı normu karşılıyorsa aynı satırda yapay norm açığı kalmıyor.
- Uzman/Elit yönetici, manav, şarküteri ve kasap unvanları config üzerinden ana aileyi karşılıyor.
- Yardımcı roller ayrı tutuluyor; yardımcı denge minimum ana mevcut kuralıyla uygulanıyor.
- Web Genel Özet veri şeması `Mevcut / Norm / Eksik / Fazla` sütunlarıyla uyumlu.
- LibreOffice olmadan Python/pandas hesap motoru çalışıyor.
- Kılavuz ve sürüm notları güncel KPI'yı kullanıyor.
- Paket önbellek ve geçici profil klasörlerinden temizlendi.

## Otomatik test
`tests/test_all_branch_diff.py` her build'de 48 şubeyi, KPI'yı ve ana aile tutarlılığını kontrol eder.

## Panelden Ana Veri Yönetimi doğrulaması
- `services/master_data_admin.py` sözdizimi doğrulandı.
- `web/tab_modules/ana_veri_yonetimi.py` sözdizimi doğrulandı.
- Mevcut inputtan 53 mağaza, 60 unvan, 419 norm satırı ve 596 personel satırı panel veri modeline yüklendi.
- Mevcut veri için mükerrer anahtar, geçersiz mağaza/unvan kodu ve boş isim kontrolü geçti.
- Geçici kopyada kayıt/yedek/atomik yazım turu çalıştırıldı; Fact_Norm ve Fact_Mevcut formülleri yeniden oluşturuldu.
- `tests/test_master_data_admin.py`: 1 test geçti.
