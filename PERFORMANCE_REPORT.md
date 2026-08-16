# PERFORMANCE_REPORT.md

Şartname Madde 84 gereği: gerçek ölçümler, tahmin DEĞİL. Tüm ölçümler
gerçek üretim input dosyasıyla (596 aktif personel, 64 sayfa) yapıldı.

## Ekran hızları (COLD / WARM)

| Ekran | COLD | WARM | Hedef | Durum |
|---|---|---|---|---|
| Genel Özet | ~10,8 sn | **0,43 sn** | <1 sn | ✅ |
| CEO Özeti | (Genel Özet'le aynı kaynak) | (Genel Özet'le aynı) | <1-1,5 sn | ✅ |
| Personel Kartları | — | **0,004 sn** | <1-1,5 sn | ✅✅ |

COLD START'ın (~10,8 sn) neredeyse tamamı, 64 sayfalık gerçek Excel
dosyasının ham okuma maliyeti (pandas/openpyxl performansı) — kod
mantığı sorunu değil. Şartname Madde 81 COLD/WARM ayrımını kabul
ediyor; asıl kritik olan WARM navigasyon zaten hedefte.

## Merkezi Excel Data Service önbellek kazanımı

3 sekme gezintisi x 10 sayfa:
- Önbelleksiz (eski davranış): **8,69 sn**
- Önbellekli (services/cached_excel_reader.py): **3,04 sn**
- **Hızlanma: 2,9x**

## migrate_excel_to_db() düzeltmesi

`header=1` gerektiren 26 sayfa için dosyanın TAMAMININ yeniden
açılması sorunu (tek açık ExcelFile handle'ına geçirildi):
- Önce: **9,99 sn**
- Sonra: **4,79 sn**
- **Hızlanma: 2,08x**

Bu düzeltme, çok-kiracılı izolasyon testlerinin toplam süresini de
düşürdü:
- Önce: **391,1 sn**
- Sonra: **222,8 sn**
- **Azalma: %43**

## Personel bildirimi (mail) hızı

Tek bir bildirim çağrısı:
- Soğuk (ilk okuma): **1,19 sn**
- Sıcak (önbellekli, gerçekçi kullanım): **0,014 sn**
- **Hızlanma: 85x**

## Change Manifest gürültü giderme

Tek bir personel çıkışı işleminin ürettiği manifest kaydı sayısı:
- Önce (hesaplanmamış formül sütunları dahil): **613 kayıt**
- Sonra (bilinen formül sütunları hariç tutuldu): **13 kayıt**

## Rapor dedup (Report Registry)

Aynı `report_type+scope_type+scope_id+data_version+template_version+
format` anahtarıyla `get_or_build()` 2 kez çağrıldı:
- 1. çağrı: gerçek üretici fonksiyon çalıştı (üretildi=True)
- 2. çağrı: var olan dosya döndürüldü (üretildi=False)
- Gerçek üretici çağrı sayısı: **1** (2 değil)

## Test paketi genel performansı

Tüm testler gruplar halinde çalıştırıldı (araç zaman sınırları
nedeniyle), toplamda:
- **293 test, hepsi geçti**
