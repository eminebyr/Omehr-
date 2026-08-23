from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from services.settings import input_file_name

CODE_ROOT = Path(__file__).resolve().parents[1]


def tenant_code() -> str:
    raw = os.getenv("OMEHR_TENANT", "OMEHR").strip().upper()
    code = re.sub(r"[^A-Z0-9_-]", "", raw)
    if not code or code != raw:
        raise ValueError("Geçersiz OMEHR_TENANT kodu.")
    return code


_ENSURED_ROOTS: set[str] = set()
_RESOLVED_PATH_CACHE: dict[str, Path] = {}


def runtime_root() -> Path:
    explicit = os.getenv("OMEHR_RUNTIME_ROOT", "").strip()
    if explicit:
        # DÜZELTME (performans): Path.resolve() bir sistem çağrısı
        # gerektirir (dosya sistemiyle etkileşir) — HER çağrıda tekrar
        # çözmek yerine, AYNI ortam değişkeni DEĞERİ için önbellekten
        # döner. Ortam değişkeni GERÇEKTEN değişirse (farklı bir string),
        # önbellek anahtarı da değişir, yeniden çözülür — bayatlık riski
        # yoktur.
        root = _RESOLVED_PATH_CACHE.get(explicit)
        if root is None:
            root = Path(explicit).expanduser().resolve()
            _RESOLVED_PATH_CACHE[explicit] = root
    elif os.getenv("OMEHR_ISOLATED", "0") == "1":
        tcode = tenant_code()
        cache_key = f"__isolated__{tcode}"
        root = _RESOLVED_PATH_CACHE.get(cache_key)
        if root is None:
            root = (CODE_ROOT / "tenants" / tcode).resolve()
            _RESOLVED_PATH_CACHE[cache_key] = root
    else:
        root = CODE_ROOT
    root_key = str(root)
    if root_key in _ENSURED_ROOTS:
        # DÜZELTME (performans regresyonu): common_veri_okuma.py'deki
        # kritik test-izolasyon hatası düzeltilirken (ROOT artık her
        # çağrıda TAZE çözümleniyor, modül import anında DONDURULMUYOR),
        # bu fonksiyonun kendisi HER çağrıda 9 alt klasörü .mkdir() ile
        # kontrol ediyordu — önceden bu yalnız modül başına BİR KEZ
        # oluyordu, artık YÜZLERCE kez tekrarlanıyordu (ölçüldü: tam test
        # paketi zaman aşımına uğradı). Bu önbellek DOĞRULUĞU BOZMAZ —
        # ortam değişkeni HER ZAMAN taze okunur (root_key her çağrıda
        # yeniden hesaplanır); yalnız AYNI çözümlenmiş yol için GEREKSİZ
        # mkdir tekrarını atlar.
        return root
    root.mkdir(parents=True, exist_ok=True)
    for name in ("input", "output", "data", "logs", "archive", "backup", "reference", "assets"):
        (root / name).mkdir(exist_ok=True)
    if os.getenv("OMEHR_BOOTSTRAP_RUNTIME", "0") == "1" and root != CODE_ROOT:
        defaults = [
            (CODE_ROOT / "input" / input_file_name(), root / "input" / input_file_name()),
            (CODE_ROOT / "reference" / "KONTROL_NORM_KADRO_24_07_2026.xlsx", root / "reference" / "KONTROL_NORM_KADRO_24_07_2026.xlsx"),
        ]
        for source, destination in defaults:
            if source.exists() and not destination.exists():
                shutil.copy2(source, destination)
        for font in (CODE_ROOT / "assets" / "fonts").glob("*.ttf"):
            destination = root / "assets" / "fonts" / font.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                shutil.copy2(font, destination)
    _ENSURED_ROOTS.add(root_key)
    return root


def code_root() -> Path:
    return CODE_ROOT
