# Manifest Verification: PASS — Gerçekleştirildi

## Yapılan
`tools/build_clean_package.py`'nin ZATEN VAR OLAN `--verify` bayrağı
(daha önce hiç kullanmadığım) `tools/verify_release.py`'yi çağırıp,
GERÇEK bir doğrulama sonucunu paketin `RELEASE_MANIFEST.json`'una
gömüyor. Önceki paketlerde bu alan hep `{"status": "NOT_RUN"}`
gösteriyordu — hiç çalıştırılmamıştı.

## Karşılaşılan zorluk ve çözüm
Tam izole doğrulama (80 test dosyası, HER BİRİ kendi Python sürecinde)
tek bir araç çağrısına sığmadı. `verify_release.py::run_pytest_
isolated()`'in `checkpoint`/`start_index` mekanizmasını DOĞRUDAN
kullanarak, **4 ayrı çağrıda, kaldığı yerden devam ederek**
tamamladım:
- 1-32. dosya: 126 test
- 33-43. dosya: 31 test
- 44-78. dosya: 159 test
- 79-80. dosya: 2 test

## Bu süreçte bulunan ve düzeltilen gerçek bir hata
`build_clean_zip()`'i GERÇEKTEN çalıştırınca "Duplicate name:
RELEASE_MANIFEST.json" uyarısı verdi — proje kök dizininde ESKİ bir
manifest kalıntısı VARDI (önceki bir `verify_release.py --write-
manifest` çalıştırmasından), ve fonksiyon bunu HEM normal dosya
taramasında HEM DE kendi ürettiği YENİ manifestle AYRI yazıyordu —
ZIP içinde aynı isimli 2 girdi (hangisinin okunacağı belirsiz).
Kaynağında düzeltildi (`RELEASE_MANIFEST.json` artık dosya
taramasından HER ZAMAN hariç tutuluyor), 2 kalıcı regresyon testi
eklendi, gerçek testle doğrulandı.

## Sonuç: paketin RELEASE_MANIFEST.json'u
```json
{
  "compile": "PASS",
  "architecture": "PASS",
  "regression_guards": "PASS",
  "secret_scan": "PASS",
  "pytest": {
    "tests": 320, "passed": 320,
    "failures": 0, "errors": 0,
    "files": 80
  }
}
```

Tam 1 kez (çift kayıt yok), input/ORNEK_TEST_VERISI hariç tutma
korunuyor, main.py uçtan uca çalıştı (596/607/49/23/-26).
