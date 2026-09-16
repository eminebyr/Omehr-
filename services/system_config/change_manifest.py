from __future__ import annotations

"""MADDE 7 — Değişiklik Manifesti (Change Manifest).

Bir yazma işleminden ÖNCEKİ ve SONRAKİ DataFrame'leri karşılaştırarak,
hangi sayfa/anahtar/alanın değiştiğini yapılandırılmış biçimde üretir.
Bu bilgi ile sistem hangi KPI/mağaza/unvan/raporun etkilendiğini
anlayabilir (bkz. şartname örneği).

Kapsam notu: bu modül GENEL, yeniden kullanılabilir bir birincil yapı
taşıdır (primitive). Şu an personel giriş/çıkış akışına (en sık
kullanılan senaryo) bağlanmıştır; diğer yazma yollarına (norm
değişikliği, atama, rotasyon) sonraki aşamalarda aynı fonksiyon
çağrılarak genişletilebilir — YENİ bir mekanizma yazmaya gerek yoktur.
"""

from datetime import datetime
from typing import Any

import pandas as pd

# DÜZELTME: Fact_Mevcut'ta hâlâ Excel FORMÜLÜ olarak yazılan (pandas ile
# okunduğunda her zaman boş/None dönen) sütunlar — bkz. build_change_manifest
# docstring'i. Tüm çağıranların TEK, tutarlı bir kaynaktan almasını
# sağlamak için burada merkezi bir sabit olarak tanımlanır.
BILINEN_FORMUL_SUTUNLARI = ("Norm fazlası Norm eksiği", "Kıdem (Gün)", "Kıdem (Yıl)")


def build_change_manifest(
    *, sheet: str, key_col: str, before: pd.DataFrame, after: pd.DataFrame,
    magaza_col: str = "Mağaza", unvan_col: str = "Unvan",
    ignore_columns: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    """İki DataFrame'i (aynı `key_col` ile hizalanmış) karşılaştırıp,
    değişen her hücre için bir manifest kaydı döner.

    ignore_columns: karşılaştırmadan HARİÇ TUTULACAK sütunlar. DÜZELTME:
    Fact_Mevcut'ta hâlâ Excel FORMÜLÜ olarak yazılan (statik değere
    çevrilmemiş) "Norm fazlası Norm eksiği", "Kıdem (Gün)", "Kıdem (Yıl)"
    sütunları, pandas ile okunduğunda (LibreOffice hesaplaması olmadan)
    HER ZAMAN boş/None döner — bu da HERHANGİ bir yazma işleminde bu
    sütunların "değişti" görünmesine yol açar (gerçek veri hiç
    değişmese bile). Bizzat kanıtlandı: tek bir kişinin çıkışı 613
    sahte manifest kaydı üretiyordu; bu sütunlar uygulamanın başka
    hiçbir yerinde okunmadığı (yalnız görsel amaçlı) için hariç
    tutulmaları güvenlidir.

    Örnek çıktı (şartnamedeki örnekle birebir aynı şekil):
    {"sheet": "Fact_Mevcut", "key": "ŞEYMA ASLAN", "field": "İşten Çıkış",
     "old_value": "", "new_value": "16.08.2026",
     "magaza": "AKEVLER", "unvan": "KASİYER"}
    """
    if before is None or after is None or key_col not in after.columns:
        return []
    if key_col not in before.columns:
        before = pd.DataFrame(columns=after.columns)

    # DÜZELTME: anahtar sütununda (ör. "İsim Soyisim") baştaki/sondaki
    # boşluk farkı ("ENES GÜN " vs "ENES GÜN" — aynı veri temizleme
    # sürecinin isimler üzerindeki etkisi), aynı kişinin YANLIŞLIKLA
    # "silindi + yeniden eklendi" olarak görünmesine yol açıyordu.
    # Anahtar karşılaştırması normalleştirilmiş (strip edilmiş) metinle
    # yapılır; ORİJİNAL (normalleştirilmemiş) değer satırın kendi
    # içeriğinde zaten saklı kaldığı için bilgi kaybı olmaz.
    before = before.copy(); after = after.copy()
    before[key_col] = before[key_col].astype(str).str.strip()
    after[key_col] = after[key_col].astype(str).str.strip()

    onceki = before.set_index(key_col) if not before.empty else pd.DataFrame(columns=before.columns)
    sonraki = after.set_index(key_col)

    kayitlar: list[dict[str, Any]] = []
    ortak_sutunlar = [c for c in sonraki.columns if c in onceki.columns and c not in ignore_columns] if not onceki.empty else []
    tum_anahtarlar = set(sonraki.index) | (set(onceki.index) if not onceki.empty else set())

    for anahtar in tum_anahtarlar:
        yeni_satir = sonraki.loc[anahtar] if anahtar in sonraki.index else None
        eski_satir = onceki.loc[anahtar] if (not onceki.empty and anahtar in onceki.index) else None
        magaza = str(yeni_satir.get(magaza_col, "")) if yeni_satir is not None else ""
        unvan = str(yeni_satir.get(unvan_col, "")) if yeni_satir is not None else ""

        if eski_satir is None:
            kayitlar.append({
                "sheet": sheet, "key": str(anahtar), "field": "*", "old_value": None,
                "new_value": "EKLENDİ", "magaza": magaza, "unvan": unvan,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            })
            continue
        if yeni_satir is None:
            kayitlar.append({
                "sheet": sheet, "key": str(anahtar), "field": "*", "old_value": "MEVCUTTU",
                "new_value": None, "magaza": str(eski_satir.get(magaza_col, "")),
                "unvan": str(eski_satir.get(unvan_col, "")),
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            })
            continue
        for alan in ortak_sutunlar:
            eski_deger = eski_satir.get(alan)
            yeni_deger = yeni_satir.get(alan)
            if pd.isna(eski_deger) and pd.isna(yeni_deger):
                continue
            if str(eski_deger) != str(yeni_deger):
                kayitlar.append({
                    "sheet": sheet, "key": str(anahtar), "field": alan,
                    "old_value": None if pd.isna(eski_deger) else eski_deger,
                    "new_value": None if pd.isna(yeni_deger) else yeni_deger,
                    "magaza": magaza, "unvan": unvan,
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                })
    return kayitlar


def append_manifest_log(root, kayitlar: list[dict[str, Any]]) -> None:
    """Manifest kayıtlarını logs/change_manifest.jsonl dosyasına ekler."""
    if not kayitlar:
        return
    import json
    from pathlib import Path
    p = Path(root) / "logs" / "change_manifest.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        for kayit in kayitlar:
            fh.write(json.dumps(kayit, ensure_ascii=False, default=str) + "\n")
