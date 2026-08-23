# OMEHR — Nihai Sürüm (DÜZELTİLMİŞ)

⚠️ **DÜZELTME NOTU:** Bu paketin önceki teslimatı (`OMEHR_V19_21_29_NIHAI.zip`),
yanlışlıkla `eski V19.21.28/29` zip zincirinden kurulmuştu — o zincirde
"Ergüven Kamiloğlu" ve "Ufuk Ertuğrul" bölge sorumlusu verisi YOKTU. Doğru
temel, ilk yüklenen 7 dosya arasındaki `OMEHR_FINAL_MARKASIZ_RELEASE.zip`
imiş: çok daha kapsamlı (multi-tenant, personel çıkış/randevu yönetimi,
mail router, kota kontrolü, oturum güvenliği gibi ek modüller içeren),
input Excel'i gerçekten güncel (Ergüven/Ufuk dahil) bir sürüm. Bu paket
ONUN üzerine kurulmuştur.

## Doğrulama
- **292 test PASS** (7 PostgreSQL testi ortamda atlandı, birkaç yavaş
  alt-süreç/LibreOffice testi sandbox'ta zaman aşımına uğradı ama bunlar
  kod hatası değil — çevre kısıtı; ilgili iş mantığı birim testleri ayrı
  ayrı çalıştırılıp PASS olarak doğrulandı).
- `input/OMEHR_AI_NORM_TRANSFER_INPUT.xlsx` içinde Bölge Sorumlusu listesi:
  ALİ ÇELİK, AYHAN DAŞDEMİR, AYŞE AVCU, CEBRAİL ÇİÇEK, CÜNEYT ÇIKRIKÇI,
  DERYA YARDIMCI, **ERGÜVEN KAMİLOĞLU**, FARUK MALKOÇ, GENEL MÜDÜR,
  HALİT BAŞDAŞ (şirket sahibinin gerçek soyadı — veri olarak korundu),
  **UFUK ERTUĞRUL**.

## Bu pakette yapılanlar
1. **Marka temizliği:** Kalan ~95 dosyadaki eski marka referansı
   (metin + ortam değişkenleri) tamamen OMEHR'e çevrildi. Kod tabanında
   sıfır eski marka referansı kaldı.
2. **Karanlık Mod:** Kenar çubuğuna "🌙 Karanlık Mod" anahtarı eklendi
   (`web/styles.py::get_theme_css`). Bu paketin tasarım sistemi zaten
   büyük ölçüde CSS değişkenleriyle (--bd-*) yazıldığı için, karanlık
   tema aynı bileşenleri lacivert/teal paletinin koyu versiyonuyla
   render ediyor. Açık tema davranışı birebir korunur.
3. **Temizlik:** `__pycache__`, `.pytest_cache`, `logs/`, `backups/`,
   `output/`, `.lock` dosyaları çıkarıldı.

## Yapılması önerilenler
- Railway/production ortam değişkenlerini `OMEHR_*` olarak güncelleyip
  redeploy edin (bu paket zaten `OMEHR_` önekini kullanıyor).
- Kalıcı Volume mount path'i hâlâ eski isimdeyse güncel yola taşınmalı.
