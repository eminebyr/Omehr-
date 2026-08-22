from __future__ import annotations
from pathlib import Path
import hashlib
import json


# ============================================================================
# MADDE 6 — Excel Change Watcher, ikinci seviye kontrol: sayfa fingerprint/hash
# ============================================================================
# Birinci seviye (dosya mtime/boyut) zaten yukarıdaki
# invalidate_local_reports_if_shared_input_changed() ile yapılıyordu, ama
# HANGİ SAYFANIN değiştiğini ayırt etmiyordu — dosya değiştiğinde her şey
# "değişmiş" sayılıyordu. Bu bölüm, şartnamenin istediği ikinci seviyeyi
# ekler: her sayfanın kendi içerik hash'i ayrı ayrı izlenir, yalnız
# GERÇEKTEN değişen sayfalar "değişti" olarak raporlanır.

_TAKIP_EDILEN_SAYFALAR = (
    "Fact_Mevcut", "Fact_Norm", "Dim_Magaza", "Dim_Unvan", "Mail_Listesi",
    "Transfer_Talepleri",
)


def _sayfa_hash(input_path: Path, sheet_name: str) -> str | None:
    try:
        from services.cached_excel_reader import read_sheet_cached
        df = read_sheet_cached(input_path, sheet_name)
    except Exception:
        return None
    # DataFrame içeriğinin deterministik hash'i — sütun sırası ve hücre
    # değerleri değişirse hash değişir, satır INDEX'i (önbellek kopyasının
    # kendi iç index'i) hash'e dahil edilmez.
    try:
        h = hashlib.sha256()
        h.update(",".join(map(str, df.columns)).encode("utf-8"))
        h.update(pd_hash_bytes(df))
        return h.hexdigest()
    except Exception:
        return None


def pd_hash_bytes(df) -> bytes:
    import pandas as pd
    return pd.util.hash_pandas_object(df, index=False).values.tobytes()


def _fingerprint_dosyasi(root: Path) -> Path:
    p = Path(root) / "logs" / ".sheet_fingerprints.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def detect_changed_sheets(root: Path, input_path: Path, sheets: tuple[str, ...] = _TAKIP_EDILEN_SAYFALAR) -> list[str]:
    """Son çağrıdan bu yana İÇERİĞİ gerçekten değişen sayfaların listesini
    döner (yalnız dosya mtime değişikliğine değil, her sayfanın kendi
    hash'ine bakarak). İlk çağrıda (kayıtlı fingerprint yoksa) TÜM izlenen
    sayfalar "değişti" sayılır (güvenli varsayım)."""
    fp_dosyasi = _fingerprint_dosyasi(root)
    onceki: dict[str, str] = {}
    try:
        onceki = json.loads(fp_dosyasi.read_text(encoding="utf-8"))
    except Exception:
        pass

    degisenler: list[str] = []
    guncel: dict[str, str] = dict(onceki)
    for sheet_name in sheets:
        yeni_hash = _sayfa_hash(input_path, sheet_name)
        if yeni_hash is None:
            continue
        eski_hash = onceki.get(sheet_name)
        if eski_hash != yeni_hash:
            degisenler.append(sheet_name)
        guncel[sheet_name] = yeni_hash

    try:
        fp_dosyasi.write_text(json.dumps(guncel, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return degisenler


def invalidate_local_reports_if_shared_input_changed(root: Path, input_path: Path) -> bool:
    """Başka PC ortak Excel'i değiştirdiyse bu PC'deki eski 'güncel' raporları siler.

    Arşivlere dokunmaz. Böylece PC-1 çıkış işlediğinde PC-2/PC-3 sonraki
    panel etkileşiminde eski PDF/XLSX'i güncel sanarak açamaz.
    """
    root = Path(root); input_path = Path(input_path)
    marker = root / 'logs' / '.last_seen_shared_input_mtime'
    marker.parent.mkdir(parents=True, exist_ok=True)
    try:
        current = str(input_path.stat().st_mtime_ns)
    except OSError:
        return False
    previous = ''
    try: previous = marker.read_text(encoding='utf-8').strip()
    except OSError: pass
    changed = bool(previous and previous != current)
    if changed:
        from services.master_data_admin import _invalidate_generated_reports
        _invalidate_generated_reports(root)
        # personnel_exit kapsamındaki daha geniş pattern temizliği de uygula.
        try:
            from services.personnel_exit import _invalidate_current_reports
            _invalidate_current_reports(root)
        except Exception:
            pass
    try: marker.write_text(current, encoding='utf-8')
    except OSError: pass
    return changed
