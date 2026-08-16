# Aile Dengesi (Kural A) — Durum Raporu ve Tamamlanan Eksik

## Sizin bulgunuz: doğru, ama kod ZATEN düzeltilmişti
İncelediğimde `src/state_engine.py::_reconcile_main_family_rules()` ve
`services/family_balance.py::balance_store_title_rows()`'un HER İKİSİNİN
DE zaten tam istediğiniz "Kural A" mantığını uyguladığını buldum:
- Ana unvanda 0 (veya asgari eşiğin altında) gerçek kişi olsa bile,
  aile toplam kapasitesi aile toplam normunu karşılıyorsa Eksik=0,
  Fazla=0 (yapay 1 eksik + 1 fazla ÜRETİLMİYOR)
- Bu bilgi ayrı, niteliksel bir bayrakta (`Ana Unvan Personelsiz
  Uyarısı` / `_Ana Unvan Personelsiz`) KPI sayısını bozmadan korunuyor

Bunu tam sizin örneğinizle (Yönetici norm=1 mevcut=0, Yönetici
Yardımcısı norm=1 mevcut=2) doğrudan test edip kanıtladım: Eksik=0,
Fazla=0, bayrak=True.

## Asıl eksik bulduğum ve tamamladığım şey
Bayrak hesaplanıyordu ama **hiçbir ekranda gösterilmiyordu** — sizin
"gösterilsin" isteğiniz karşılanmamıştı. Bunu tamamladım:

**Unvan Analizi** ekranına yeni bir **"Yetkinlik Uyarısı"** sütunu
ekledim — ana unvanda gerçek kişi yokken "⚠ Ana unvanda doğrudan
görevli personel yok" gösteriyor, KPI sayılarını (Eksik/Fazla)
ETKİLEMEDEN. Sayfanın altına, kaç satırda bu uyarı olduğunu özetleyen
bir not da eklendi.

## Bulduğum ve düzelttiğim bir index hizalama riski
Uyarı sütununu eklerken, `_prepare_title_view()` fonksiyonunun
İÇİNDE bir `.merge()` işlemi olduğunu fark ettim — eğer uyarı
sütununu fonksiyonun SONUNDA, orijinal `detail` parametresinden tekrar
okusaydım, merge sonrası index kayması yüzünden YANLIŞ satıra YANLIŞ
uyarı atanabilirdi. Sütunu fonksiyonun EN BAŞINDA, herhangi bir
merge'den ÖNCE gerçek bir `view` sütunu haline getirdim — bunu özel
bir testle (2 farklı mağaza, biri uyarılı biri değil) doğruladım.

## Doküman güncellendi
`TUM_SUBELER_AILE_DENGE_DUZELTME_NOTU.md`'ye, uyarının artık panelde
göründüğünü belirten bir bölüm ekledim.

## Doğrulama
- Gerçek sizin örneğinizle test ettim: Eksik=0, Fazla=0, uyarı
  gösteriliyor
- Index hizalama riski özel testle kapatıldı
- **258/258 test geçiyor** (2 yeni test), mimari + regresyon
  bariyerleri temiz, main.py uçtan uca çalıştı (596/607/49/23/-26)
