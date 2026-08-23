from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

EXCLUDED_DIRS = {
    '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache', '.git',
    'logs', 'backup', 'backups', 'archive', 'tmp', 'temp',
    # DÜZELTME: 'data' önceden bu listede YOKTU — bu, bir test/geliştirme
    # çalıştırmasından kalma business_audit.db (53 gerçek kayıt) dosyasının
    # önceki bir V20 paketine SIZMASININ tam nedeniydi (bizzat bulundu ve
    # doğrulandı). data/ çalışma zamanı verisidir, kaynak kod değildir.
    'data',
    # DÜZELTME (KRİTİK — bizzat bulundu): 'input' ve 'ORNEK_TEST_VERISI'
    # önceden bu listede YOKTU. Bu klasörlerdeki örnek Excel dosyası
    # (Mail_Listesi sayfası) GERÇEK GÖRÜNEN düz metin şifreler ("Admin1",
    # "Ertan1", "Halit1" vb.), gerçek bir şirket domaini (@omehrmarket.com)
    # ve gerçek görünen kişi isimleri (bunlardan biri şirketin adıyla aynı
    # soyadı taşıyor) içeriyordu — kaynağı KESİN olarak doğrulanamadı.
    # Belirsizlik durumunda EN GÜVENLİ varsayılan: bu veriyi paketten
    # HARİÇ TUTMAK — hem gerçek veriyse korur, hem kasıtlı test verisiyse
    # zarar vermez (test verisi ayrı bir geliştirme ortamına aittir,
    # HER üretim teslimatına gömülü olmamalıdır).
    'input', 'ORNEK_TEST_VERISI',
    # DÜZELTME (bizzat bulundu — 37 dosya, 564KB, ÖNCEKİ TÜM paketlere
    # sızmıştı): 'lo_profile', docx→pdf dönüşümü test edilirken
    # LibreOffice'in OLUŞTURDUĞU, TAMAMEN geliştirme ortamına özgü bir
    # profil dizinidir (.lock dosyası, iç veritabanları, Linux'a özgü
    # yollar). Ürünün kendisiyle hiçbir ilgisi yoktur.
    'lo_profile',
}
EXCLUDED_SUFFIXES = {'.pyc', '.pyo', '.tmp', '.lock'}
EXCLUDED_NAMES = {
    '.DS_Store', 'Thumbs.db',
    # DÜZELTME (KRİTİK — bizzat bulundu): bu iki dosya gerçek telefon
    # numaraları, gerçek fiziksel adresler ve gerçek görünen bölge
    # sorumlusu isimlerini (sayfa adlarında) içeriyordu. main.py bu
    # dosyaları OPSİYONEL olarak okur (yoksa sessizce atlar, çökmez) —
    # paketten çıkarılması hiçbir işlevi bozmaz.
    'GUNCEL_NORM_KADRO_KONTROL.xlsx', 'KONTROL_NORM_KADRO_24_07_2026.xlsx',
}


def should_include(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    if any(part in EXCLUDED_DIRS for part in rel.parts):
        return False
    if path.name in EXCLUDED_NAMES or path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    if rel.parts and rel.parts[0] == 'output':
        return False
    if path.name.startswith('V20_JUNIT_') or path.name.startswith('V20_TEST_BATCH_') or path.name.startswith('V20_TEST_CHECKPOINT_'):
        return False
    return True


def _sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as fh:
        for block in iter(lambda: fh.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def build_clean_zip(source: Path, destination: Path, *, verification: dict | None = None) -> Path:
    source = source.resolve(); destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    files=[p for p in sorted(source.rglob('*')) if p.is_file() and should_include(p, source) and p.name != 'RELEASE_MANIFEST.json']
    release_manifest={
        'built_at_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'file_count': len(files),
        'verification': verification or {'status':'NOT_RUN'},
        'files': {str(p.relative_to(source)): _sha256(p) for p in files},
    }
    with ZipFile(destination, 'w', compression=ZIP_DEFLATED, compresslevel=6) as zf:
        for path in files:
            zf.write(path, path.relative_to(source))
        zf.writestr('RELEASE_MANIFEST.json', json.dumps(release_manifest, ensure_ascii=False, indent=2))
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description='OMEHR temiz/opsiyonel doğrulanmış dağıtım ZIP paketi oluşturur.')
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--verify', action='store_true', help='Derleme + mimari + secret scan + tüm pytest koşusunu zorunlu kılar.')
    args = parser.parse_args()
    verification=None
    if args.verify:
        import importlib.util
        verifier_path=Path(__file__).with_name('verify_release.py')
        spec=importlib.util.spec_from_file_location('verify_release', verifier_path)
        mod=importlib.util.module_from_spec(spec); assert spec.loader is not None; spec.loader.exec_module(mod)
        verification=mod.verify(args.source, run_tests=True)
    print(build_clean_zip(args.source, args.destination, verification=verification))

if __name__ == '__main__':
    main()
