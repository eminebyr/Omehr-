# Streamlit → Vercel/React Dönüşüm Envanteri

Bu doküman, OMEHR'in Streamlit (Railway) panelindeki her sekmenin gerçek
görsel/işlevsel içeriğini çıkarıp, Vercel (`vercel-ui/`) tarafındaki mevcut
karşılığıyla (varsa) eşleştirir. Amaç: "veri Vercel'e gitti" ile "Streamlit'in
işlevsel eşdeğeri Vercel'de var" arasındaki farkı kapatacak somut bir yol
haritası çıkarmak.

İki ayrı kategori var — bunlar FARKLI mühendislik işleri gerektirir:

- **A) Salt-okunur görsel/analiz sekmeleri** — grafik, filtre, KPI kutusu
  içerir; React tarafında özel bileşen (chart component) gerektirir.
- **B) Aksiyon/iş akışı sekmeleri** — kayıt, onay, form doldurma yapar;
  React tarafında form + mutation (yazma) mantığı gerektirir, grafik değil.

---

## A) Salt-okunur görsel/analiz sekmeleri

| Streamlit modülü | Satır | Grafikler | Filtre | Tablo | Vercel'deki mevcut veri kaynağı (module_key) | Durum |
|---|---|---|---|---|---|---|
| `genel_ozet.py` | 236 | bar, imshow (ısı haritası), scatter, treemap | 2 | 3 | `kpi_snapshot` + `store_summary`/`title_summary` | Vercel'de yalnız KPI kutuları var; ısı haritası/treemap YOK |
| `ceo_ozet.py` | 162 | — (sadece tablo) | 0 | 6 | `kpi_snapshot` + özet tablolar | Kısmen — tablo var, CEO'ya özel biçim yok |
| `bolge_magaza.py` | 80 | — | 1 | 1 | `store_title` | Kısmen — ham tablo var, bölge filtresi YOK |
| `unvan_analizi.py` | 172 | — | 0 | 2 | `store_title` (türetilmiş) | Kısmen |
| `personel_kartlari.py` | 811 | — | **15** | 0 (kart görünümü) | `personnel` | Ham tablo var, kart görünümü + 15 filtre YOK |
| `performans.py` | 164 | bar, pie | 0 | 1 | `performance` | Ham tablo var, grafik YOK |
| `isgucu_tahmini.py` | 152 | bar (turnover riski dahil) | 1 | 6 | `forecast`, `forecast_summary` | Ham tablo var, grafik + doğruluk bölümü YOK |
| `transfer_optimizasyon.py` | 50 | scatter | 1 | 1 | `transfer` | Ham tablo var, harita/scatter YOK |
| `ai_operasyon.py` | 391 | bar | 2 | 6 | `ai_norm`, `model_comparison` | Ham tablo var, grafik YOK |
| `operasyon_gorselleri.py` | 189 | bar, imshow (ısı haritası), line | 1 | 1 | `operations`, `daily_operations`, `hourly_density`, `register_usage`, `online_orders`, `goods_receipt`, `waste_returns` | Ham tablo var, TÜM grafikler YOK |
| `verimlilik_gorselleri.py` | 222 | bar, line | 1 | 0 | `productivity`, `overtime`, `absence`, `store_performance` | Ham tablo var, grafik YOK |
| `satis_kok_neden.py` | 68 | bar, scatter | 0 | 1 | `sales_targets` (+ `sales_accountability`) | **Bu tek istisna** — Vercel'de zaten özel bir görünümü var (bugün ekran görüntüsünde gördük) |
| `gercek_personel_ihtiyaci.py` | 45 | bar | 0 | 1 | `real_staffing_need` | Ham tablo var, grafik YOK |
| `raporlar.py` | 220 | — | 2 | 1 | `reports` | Kısmen — dosya listesi var, indirme/gönderme akışı belirsiz |

**Toplam: 14 görsel sekme. Sadece 1'i (Satış Kök Neden) gerçek bir özel
görünüme sahip. Diğer 13'ü Vercel'de yalnız ham tablo olarak duruyor.**

---

## B) Aksiyon/iş akışı sekmeleri (form + yazma gerektirir, grafik değil)

| Streamlit modülü | Filtre | Vercel'de karşılığı | Not |
|---|---|---|---|
| `onaylar.py` | 10 | "Bölge ve İK onay merkezi" (stub) | Onay/red butonu, akış mantığı YOK — yalnız açıklama metni var |
| `transfer_merkezi.py` | 4 | "Transfer talebi, takip ve karar akışı" (stub) | Aynı durum |
| `toplu_mail.py` | 0 | "Yetkili toplu iletişim merkezi" (stub) | Aynı durum |
| `bildirimler.py` | 0 | "Kullanıcı ve operasyon bildirimleri" (stub) | Aynı durum |
| `ai_geri_bildirim.py` | 2 | "AI önerilerine insan geri bildirimi" (stub) | Aynı durum |
| `veri_toplama.py` | 0 | "Atanmış veri toplama formları" (stub) | Aynı durum |
| `ana_veri_yonetimi.py` | 0 | "Kontrollü referans ve iş kuralı yönetimi" (stub) | Aynı durum |
| `tum_sayfalar_veri_yonetimi.py` | 2 | "Motor veri sayfalarının denetimli görünümü" (stub) | Aynı durum |
| `ayarlar.py` | 1 | "Kullanıcı, rol ve görünüm ayarları" (stub) | Aynı durum |

**Bu 9 sekmenin TAMAMI şu an Vercel'de yalnız "açıklama kartı" — hiçbiri
gerçek kayıt/onay işlemi yapmıyor.** Bunlar (A)'dan farklı bir iş: Supabase'e
YAZMA (insert/update), yetki kontrolü, ve genelde onay iş akışı state
makinesi gerektiriyor.

---

## Sayısal sınırlar (ayrı ayrı ele alınmalı)

1. **Railway → Supabase üretim sınırı:** `services/cloud_module_snapshots.py`
   içinde `_records(frame, limit=500)` (çoğu modül) veya `limit=1500`
   (`daily_operations`, `forecast`) — kaynak Excel/DataFrame'den kaç satır
   Supabase'e YAZILACAĞINI belirler.
2. **Vercel görüntüleme sınırı:** `vercel-ui/app/page.tsx` içinde
   `filtered.slice(0, 500)` — Supabase'den OKUNAN veriden ekrana kaçının
   BASILACAĞINI belirler.

Bu ikisi bağımsız katmanlar; ikisi de "körlemesine artırma" yerine
sayfalama (pagination) ile çözülmeli — aksi halde tarayıcıda 1500 satırlık
tek bir tablo render etmek performans sorunu yaratır.

---

## Önerilen sıralama (öncelik)

Verinin zaten Supabase'de tam olarak durduğu, sadece GÖRSELLEŞTİRME
eksik olan modüllerden başlamak en hızlı görünür ilerlemeyi sağlar:

1. **Genel Özet** — ısı haritası + treemap (şirket geneli ilk bakılan sayfa)
2. **İş Gücü Tahmini** — bar chart + turnover doğruluk tablosu (bugün
   Streamlit'e eklediğimiz özellik, iş değeri yüksek)
3. **Operasyon Görselleri** — ısı haritası + trend çizgileri
4. **Personel Kartları** — kart görünümü + 15 filtre (en çok kullanılan
   sekmelerden, ama en büyük iş - 811 satır Streamlit kodu var)
5. Kalan görsel sekmeler (Performans, Verimlilik, AI Operasyon, Transfer)
6. **Aksiyon sekmeleri (B grubu)** — ayrı bir iş paketi, form/yazma
   mimarisi gerektirdiği için görsel dönüşümden SONRA ele alınmalı

Her madde için: React bileşeni (muhtemelen `recharts` — zaten Claude'un
artifact ortamında kullanılabilir, Vercel'de de npm bağımlılığı olarak
eklenebilir), veri çekme hook'u (`useEffect` + Supabase client sorgusu),
ve Streamlit'teki filtre mantığının React state'ine taşınması gerekiyor.
