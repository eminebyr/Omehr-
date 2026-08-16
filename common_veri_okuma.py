import hashlib, json, os, pandas as pd
from services.runtime_paths import runtime_root

def _db_modu():
    return os.getenv("BASDAS_INPUT_SOURCE", "excel").strip().lower() == "db"

def input_file():
    # DÜZELTME (kritik test-izolasyon + potansiyel üretim hatası): ROOT
    # önceden modül seviyesinde, import anında BİR KEZ hesaplanıyordu —
    # Python modülleri process boyunca yalnız bir kez import edildiği
    # için, BASDAS_RUNTIME_ROOT SONRADAN değişse bile (ör. testler arası,
    # ya da teorik olarak uzun süre çalışan bir süreçte) bu değişiklik
    # ASLA yansımıyordu. Bizzat kanıtlandı: tam test paketinde bir test
    # başka bir testin kök dizinini okuyordu. Artık her çağrıda taze
    # çözümlenir.
    root = runtime_root()
    fs=sorted((root/'input').glob('*.xlsx'))
    if not fs:
        if _db_modu():
            # Veritabanı modunda Excel dosyası hiç OLMAYABİLİR — bu bir
            # hata değildir. Bazı çağıranlar (preflight/backup gibi) yine
            # de bir Path bekler; var olmayan sembolik bir yol döner,
            # İÇERİĞİ hiçbir zaman okunmaz (read_all() DB'ye yönlenir).
            return root/'input'/'BASDAS_AI_NORM_TRANSFER_INPUT.xlsx'
        raise FileNotFoundError('input klasorunde Excel dosyasi yok.')
    if len(fs)>1: print('UYARI: Birden fazla Excel bulundu; ilk dosya kullaniliyor:',fs[0].name)
    return fs[0]

def fingerprint(path=None):
    if _db_modu():
        return "veritabani-kaynakli"
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
    out=runtime_root()/'output'/'BASDAS_Input_Manifest.json'; out.parent.mkdir(exist_ok=True); out.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    return data
