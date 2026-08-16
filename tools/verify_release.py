from __future__ import annotations

import argparse
import compileall
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*=\s*['\"][^'\"]{8,}['\"]"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]
TEXT_SUFFIXES = {'.py','.json','.yml','.yaml','.toml','.ini','.cfg','.env','.md','.txt','.bat','.sh'}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def secret_scan(root: Path) -> list[str]:
    hits=[]
    for p in root.rglob('*'):
        if not p.is_file() or p.name == '.env' or p.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in {'.git','__pycache__','.pytest_cache','tests'} for part in p.parts):
            continue
        text=p.read_text(encoding='utf-8', errors='ignore')
        for pat in SECRET_PATTERNS:
            m = pat.search(text)
            if m:
                # DÜZELTME: .env.example İÇİN uygulanan "bu bir yer tutucu,
                # gerçek gizli bilgi değil" muafiyeti, rehber/talimat
                # dosyalarına (.md) da GENİŞLETİLDİ — bizzat bulundu:
                # UCRETSIZ_CANLIYA_ALMA_REHBERI.md'deki "kendi-seçtiğiniz-
                # güçlü-bir-şifre-2026!" gibi AÇIKÇA kullanıcıya yönelik
                # bir TALİMAT metni, gerçek bir sızıntı gibi işaretleniyordu.
                # GERÇEKTEN SATIR BAZLI kontrol: yalnız eşleşmenin bulunduğu
                # TAM SATIR incelenir (sabit karakter penceresi DEĞİL — bu,
                # kısa dosyalarda komşu satırlardaki kelimelere sızabiliyordu,
                # bizzat bir testle kanıtlandı ve düzeltildi).
                _satir_basi = text.rfind('\n', 0, m.start()) + 1
                _satir_sonu = text.find('\n', m.end())
                if _satir_sonu == -1:
                    _satir_sonu = len(text)
                _esit_satir = text[_satir_basi:_satir_sonu].lower()
                _placeholder_isaretleri = ('change_me', 'example', 'your_', 'kendi-seç', 'kendi seç', 'örnek', 'placeholder', 'sizin-')
                if p.name == '.env.example' and any(x in text.lower() for x in _placeholder_isaretleri):
                    continue
                if p.suffix.lower() == '.md' and any(x in _esit_satir for x in _placeholder_isaretleri):
                    continue
                hits.append(str(p.relative_to(root)))
                break
    return sorted(set(hits))


def run_checked(cmd: list[str], cwd: Path, timeout: int = 120) -> subprocess.CompletedProcess:
    print('+', ' '.join(cmd), flush=True)
    return subprocess.run(cmd, cwd=cwd, check=True, env={**os.environ, 'PYTHONPATH': str(cwd)}, timeout=timeout)


def _parse_junit(path: Path) -> dict:
    root=ET.parse(path).getroot()
    # pytest may emit <testsuites><testsuite...> or direct testsuite
    suites=[root] if root.tag=='testsuite' else list(root.findall('testsuite'))
    out={'tests':0,'failures':0,'errors':0,'skipped':0,'time':0.0}
    for s in suites:
        for k in ('tests','failures','errors','skipped'):
            out[k]+=int(s.attrib.get(k,0))
        out['time']+=float(s.attrib.get('time',0) or 0)
    out['passed']=out['tests']-out['failures']-out['errors']-out['skipped']
    return out


def _collect_nodes(root: Path, test_file: Path) -> list[str]:
    cp=subprocess.run([sys.executable,'-m','pytest','--collect-only','-q',str(test_file)], cwd=root,
                      env={**os.environ,'PYTHONPATH':str(root)}, capture_output=True, text=True, check=True, timeout=30)
    return [line.strip() for line in cp.stdout.splitlines() if '::' in line and not line.startswith('<')]


def run_pytest_isolated(root: Path, per_file_timeout: int = 75, start_index: int = 1, checkpoint: Path | None = None) -> dict:
    """Run each test file in a clean Python process.

    A few DB/tenant tests intentionally reload environment-sensitive modules;
    running the entire suite in one interpreter can leak module state. Release
    verification therefore isolates test files. If a file still times out, it
    falls back to one node per process and still requires every node to finish.
    """
    totals={'tests':0,'passed':0,'skipped':0,'failures':0,'errors':0,'files':0,'fallback_nodes':0}
    test_files=sorted((root/'tests').glob('test_*.py'))
    test_files=test_files[max(0,start_index-1):]
    # DÜZELTME: per_file_timeout=75s SABİT bir değerdi — bizzat ölçüldü:
    # test_shipped_config_norm_rules.py'deki main.py'yi çalıştıran test
    # TEK BAŞINA 229 saniye sürüyor. Bu dosya için 75s ASLA yeterli
    # olamazdı (node-fallback moduna geçse bile AYNI 75s limiti
    # kullanılıyordu, yani orada da başarısız olurdu) — verify_release.py
    # bu dosyada HER ZAMAN başarısız olurdu. Artık bilinen yavaş
    # dosyalar için ayrı, yeterli bir zaman aşımı tanımlanır.
    SLOW_FILE_TIMEOUTS = {'test_shipped_config_norm_rules.py': 280}
    with tempfile.TemporaryDirectory(prefix='omehr-junit-') as td:
        td=Path(td)
        for offset,test_file in enumerate(test_files,1):
            i=start_index+offset-1
            xml=td/f'{i}.xml'
            cmd=[sys.executable,'-m','pytest','-q',str(test_file),f'--junitxml={xml}']
            print(f'[{i}/{len(test_files)}] {test_file.name}', flush=True)
            dosya_zaman_asimi = SLOW_FILE_TIMEOUTS.get(test_file.name, per_file_timeout)
            force_nodes = test_file.name in {'test_db_backed_input.py','test_multitenant_isolation.py','test_personnel_cards.py'}
            try:
                if force_nodes:
                    raise subprocess.TimeoutExpired(cmd, 0)
                cp=subprocess.run(cmd,cwd=root,env={**os.environ,'PYTHONPATH':str(root)},timeout=dosya_zaman_asimi,
                                  text=True)
                if cp.returncode != 0:
                    raise RuntimeError(f"{test_file.name} failed\n{getattr(cp, 'stdout', '')}\n{getattr(cp, 'stderr', '')}")
                counts=_parse_junit(xml)
            except subprocess.TimeoutExpired:
                print(f'  isolated node mode: {test_file.name}', flush=True)
                counts={'tests':0,'passed':0,'skipped':0,'failures':0,'errors':0,'time':0.0}
                for j,node in enumerate(_collect_nodes(root,test_file),1):
                    node_xml=td/f'{i}_{j}.xml'
                    cp=subprocess.run([sys.executable,'-m','pytest','-q',node,f'--junitxml={node_xml}'],cwd=root,
                                      env={**os.environ,'PYTHONPATH':str(root)},timeout=dosya_zaman_asimi,
                                      text=True)
                    if cp.returncode != 0:
                        raise RuntimeError(f"{node} failed\n{getattr(cp, 'stdout', '')}\n{getattr(cp, 'stderr', '')}")
                    c=_parse_junit(node_xml)
                    for k in ('tests','passed','skipped','failures','errors'): counts[k]+=c[k]
                    totals['fallback_nodes']+=1
            for k in ('tests','passed','skipped','failures','errors'): totals[k]+=counts[k]
            totals['files']+=1
            print(f"  PASS={counts['passed']} SKIP={counts['skipped']}", flush=True)
            if checkpoint is not None:
                checkpoint.write_text(json.dumps({'last_index':i,'last_file':test_file.name,'totals':totals}, ensure_ascii=False, indent=2), encoding='utf-8')
    if totals['failures'] or totals['errors']:
        raise RuntimeError(f'pytest verification failed: {totals}')
    return totals


def verify(root: Path, *, run_tests: bool = True) -> dict:
    root = root.resolve()
    if not compileall.compile_dir(str(root), quiet=1, force=True):
        raise RuntimeError('Python compile verification failed')
    run_checked([sys.executable, 'tools/check_architecture.py'], root, timeout=60)
    run_checked([sys.executable, 'tools/check_regression_guards.py'], root, timeout=60)
    secrets = secret_scan(root)
    if secrets:
        raise RuntimeError('Potential secrets found: ' + ', '.join(secrets))
    pytest_result = run_pytest_isolated(root) if run_tests else {'status':'SKIPPED'}
    input_file = root / 'input' / 'BASDAS_AI_NORM_TRANSFER_INPUT.xlsx'
    return {
        'verified_at_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'python': sys.version.split()[0],
        'compile': 'PASS',
        'architecture': 'PASS',
        'regression_guards': 'PASS',
        'secret_scan': 'PASS',
        'pytest': pytest_result,
        'input_sha256': sha256(input_file) if input_file.exists() else None,
    }


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('root', nargs='?', type=Path, default=ROOT)
    ap.add_argument('--skip-tests', action='store_true')
    ap.add_argument('--write-manifest', type=Path)
    args=ap.parse_args()
    manifest=verify(args.root, run_tests=not args.skip_tests)
    if args.write_manifest:
        target=args.write_manifest
        if not target.is_absolute(): target=args.root/target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        print(target)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
