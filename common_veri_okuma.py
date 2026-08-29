import hashlib, json, os, shutil, pandas as pd
from datetime import datetime
from pathlib import Path
from zipfile import is_zipfile
from services.runtime_paths import runtime_root
from services.settings import input_file_name


def _excel_saglam(path):
    """Dosyanın yalnız uzantısını değil, gerçek XLSX içeriğini doğrular."""
    path = Path(path)
    if not path.is_file() or path.stat().st_size == 0 or not is_zipfile(path):
        return False
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=False)
        ok = bool(wb.sheetnames)
        wb.close()
        return ok
    except Exception:
        return False


def _en_yeni_saglam_yedek(root):
    adaylar = []
    for klasor in ('backups', 'backup'):
        adaylar.extend((root / klasor).glob('*.xlsx'))
    adaylar = sorted((p for p in adaylar if p.is_file()), key=lambda p: p.stat().st_mtime, reverse=True)
    return next((p for p in adaylar if _excel_saglam(p)), None)


def _bozuk_inputtan_kurtar(root, bozuklar):
    """Bozuk inputları saklayıp en yeni açılabilir yedeği atomik geri yükler."""
    yedek = _en_yeni_saglam_yedek(root)
    if yedek is None:
        return None
    damga = datetime.now().strftime('%Y%m%d_%H%M%S')
    karantina = root / 'recovery_quarantine'
    karantina.mkdir(parents=True, exist_ok=True)
    for bozuk in bozuklar:
        if not bozuk.is_file():
            continue
        hedef = karantina / f'{bozuk.name}.{damga}.corrupt'
        sayac = 2
        while hedef.exists():
            hedef = karantina / f'{bozuk.name}.{damga}.{sayac}.corrupt'
            sayac += 1
        bozuk.replace(hedef)
        print(f'BOZUK INPUT KORUNDU: {bozuk} -> {hedef}', flush=True)
    hedef = root / 'input' / input_file_name()
    # openpyxl uzantıyı da doğruladığı için geçici dosya .xlsx ile bitmeli.
    gecici = hedef.with_name(f'.{hedef.stem}.{os.getpid()}.recovery.tmp.xlsx')
    try:
        shutil.copy2(yedek, gecici)
        if not _excel_saglam(gecici):
            raise RuntimeError(f'Kopyalanan yedek doğrulanamadı: {yedek}')
        os.replace(gecici, hedef)
    finally:
        gecici.unlink(missing_ok=True)
    print(f'INPUT OTOMATİK KURTARILDI: {yedek} -> {hedef}', flush=True)
    return hedef

def _db_modu():
    return os.getenv("OMEHR_INPUT_SOURCE", "excel").strip().lower() == "db"

def input_file():
    # DÜZELTME (kritik test-izolasyon + potansiyel üretim hatası): ROOT
    # önceden modül seviyesinde, import anında BİR KEZ hesaplanıyordu —
    # Python modülleri process boyunca yalnız bir kez import edildiği
    # için, OMEHR_RUNTIME_ROOT SONRADAN değişse bile (ör. testler arası,
    # ya da teorik olarak uzun süre çalışan bir süreçte) bu değişiklik
    # ASLA yansımıyordu. Bizzat kanıtlandı: tam test paketinde bir test
    # başka bir testin kök dizinini okuyordu. Artık her çağrıda taze
    # çözümlenir.
    root = runtime_root()
    fs=sorted(p for p in (root/'input').glob('*.xlsx') if not p.name.startswith('~$'))
    if not fs:
        if _db_modu():
            # Veritabanı modunda Excel dosyası hiç OLMAYABİLİR — bu bir
            # hata değildir. Bazı çağıranlar (preflight/backup gibi) yine
            # de bir Path bekler; var olmayan sembolik bir yol döner,
            # İÇERİĞİ hiçbir zaman okunmaz (read_all() DB'ye yönlenir).
            return root/'input'/'OMEHR_AI_NORM_TRANSFER_INPUT.xlsx'
        raise FileNotFoundError('input klasorunde Excel dosyasi yok.')
    saglam = [p for p in fs if _excel_saglam(p)]
    if saglam:
        tercih = root/'input'/input_file_name()
        secilen = tercih if tercih in saglam else max(saglam, key=lambda p: p.stat().st_mtime)
        if len(fs)>1: print('UYARI: Birden fazla Excel bulundu; sağlam dosya kullanılıyor:',secilen.name)
        return secilen
    kurtarilan = _bozuk_inputtan_kurtar(root, fs)
    if kurtarilan is not None:
        return kurtarilan
    raise RuntimeError(
        'Input Excel bozuk veya açılabilir değil ve backup/backups klasörlerinde sağlam yedek bulunamadı. '
        f'Kontrol edilen dosyalar: {[p.name for p in fs]}'
    )

def fingerprint(path=None):
    if _db_modu():
        # Kiracı içeriği her write_sheet() işleminde artırılır. Sabit değer
        # rapor kayıt defteri/lineage katmanına farklı verileri aynı sürüm gibi
        # gösteriyordu ve eski raporun yeniden kullanılmasına yol açabiliyordu.
        from services.input_data_access import tenant_content_version
        from services.tenant_context import current_tenant_id
        tenant = current_tenant_id()
        return f"db:{tenant}:{tenant_content_version(tenant)}"
    p=path or input_file(); h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def read_all(path=None):
    if _db_modu():
        from services.input_data_access import read_all_sheets
        return read_all_sheets()
    p=path or input_file()
    with pd.ExcelFile(p) as xls:
        return {sheet: pd.read_excel(xls, sheet_name=sheet, dtype=object) for sheet in xls.sheet_names}

def _df_hash(df):
    """DataFrame içeriğini tam kopya oluşturmadan deterministik olarak özetler."""
    h = hashlib.sha256()
    columns = [str(c) for c in df.columns]
    h.update(("COLUMNS\n" + "\x1f".join(columns) + "\n").encode("utf-8"))
    h.update(f"ROWS\n{len(df)}\n".encode("utf-8"))
    try:
        row_hashes = pd.util.hash_pandas_object(df, index=False, categorize=True)
        values = row_hashes.to_numpy(copy=False)
        view = memoryview(values).cast("B")
        chunk_size = 1024 * 1024
        for pos in range(0, len(view), chunk_size):
            h.update(view[pos:pos + chunk_size])
    except (TypeError, ValueError):
        for row in df.itertuples(index=False, name=None):
            cells = []
            for value in row:
                try:
                    missing = bool(pd.isna(value))
                except (TypeError, ValueError):
                    missing = False
                cells.append("<NA>" if missing else str(value))
            h.update("\x1f".join(cells).encode("utf-8", errors="replace"))
            h.update(b"\n")
    return h.hexdigest()

def semantic_manifest(sheets):
    data={'sheets':{}}
    for n,df in sheets.items():
        data['sheets'][n]={'rows':int(len(df)),'columns':[str(c) for c in df.columns],'semantic_hash':_df_hash(df)}
    joined='\n'.join(f"{n}|{v['rows']}|{','.join(v['columns'])}|{v['semantic_hash']}" for n,v in data['sheets'].items())
    data['global_semantic_hash']=hashlib.sha256(joined.encode('utf-8')).hexdigest()
    data['sheet_count']=len(sheets)
    return data

def save_manifest(path=None):
    p=path or input_file(); all_=read_all(p); data={'file':p.name,'sha256':fingerprint(p),**semantic_manifest(all_)}
    out=runtime_root()/'output'/'OMEHR_Input_Manifest.json'; out.parent.mkdir(exist_ok=True); out.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    return data
