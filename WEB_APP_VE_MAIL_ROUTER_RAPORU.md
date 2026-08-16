# web/app.py Düzeltmesi + mail_router.py Bağlantı Doğrulaması

## web/app.py
Modül seviyesinde `ROOT = runtime_root()` ve türetilmiş `INPUT`/`OUTPUT`/`DB`
sabitleri, 4 basit fonksiyona (`_root()`, `_input()`, `_output()`, `_db()`)
çevrildi. 20+ kullanım yeri tek tek doğru şekilde güncellendi.

Süreç içinde kendi inisiyatifimle eklediğim spekülatif bir `@lru_cache`
optimizasyonunu (Streamlit'in her session için tam olarak ayrı bir
namespace kullandığından %100 emin olamadığım için) **geri aldım** —
kullanıcının istediği kapsamda (yalnız taze çözümleme) kaldım, ek risk
almadım.

**Doğrulama**: `streamlit.testing.v1.AppTest` ile dosya GERÇEKTEN
çalıştırıldı (Streamlit'in kendi `exec(code, module.__dict__)`
mekanizmasıyla) — hiçbir exception oluşmadı, hem başta hem son
kontrolde.

## mail_router.py
`report_mail_engine.py::send_reports_via_outlook()`'a zaten bağlıydı
(abonelik filtresi olarak). Bunu körü körüne kabul etmeyip **uçtan
uca gerçek bir senaryoyla** kanıtladım: 2 aktif alıcıdan biri
(Norm_Genel=Hayır) abonelikten çıkmış, gerçek gönderim çağrısı sonrası
bu kişi işlem/log kaydına HİÇ girmedi. Kalıcı bir regresyon testi
eklendi.

## Yol boyunca çözülen bir "flaky test" araştırması
Test paketini gruplar halinde çalıştırırken bir noktada 2 test
(`test_norm_family_department_rules.py`) belirli bir dosya sırasında
başarısız oldu. Kapsamlı bisection (tek başına, ikili kombinasyonlar,
yarı gruplar — 10+ farklı kombinasyon denendi) yapıldı; HİÇBİRİ tekrar
üretilemedi. Aynı tam dizi 3 kez daha çalıştırıldı, hepsi %100 geçti.
Sonuç: bu, kalıcı bir kod hatası DEĞİL, geçici/ortam kaynaklı (muhtemelen
sistem yükü/zamanlama) bir durumdu.

## Doğrulama
- **Tam test paketi (71 dosya, gruplar halinde) tamamen yeniden
  çalıştırıldı — hepsi geçti**
- Mimari + regresyon bariyerleri temiz
- main.py uçtan uca çalıştı (596/607/49/23/-26)
- web/app.py AppTest ile 2 kez doğrulandı (başta ve teslim öncesi)
