# Ek kontrol notu

## Bulunan ve temizlenen tek şey
`src/state_engine.py.orig` — beklenmeyen bir yedek/geçici dosya
(muhtemelen bir düzenleme aracından kalma). Paketten çıkarıldı;
aktif `src/state_engine.py` dosyasına dokunulmadı.

## Doğrulanan (hepsi sağlam)
- Sürüm numaraları tutarlı (APP_VERSION, 00_OKU, SURUM_NOTLARI,
  DOGRULAMA_RAPORU, kılavuz — hepsi 49/23/-26 KPI'sını doğru gösteriyor).
- E-posta gövdesi, venv yolu, image-only PDF, assets/fonts, .bat
  temizliği — hepsi sağlam.
- Ana Veri Yönetimi paneli ve Plotly araç çubuğu düzeltmesi mevcut.
- İç içe klasör sorunu yok, pycache committed değil.

## Doğrulama
178/178 test geçiyor (3 dürüst xfail), main.py gerçek 64 sayfalık
üretim verisiyle uçtan uca çalıştı (exit 0) ve tam olarak
Norm Eksiği=49, Norm Fazlası=23, Net İhtiyaç=-26 üretti.
