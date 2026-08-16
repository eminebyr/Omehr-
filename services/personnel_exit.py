"""PERSONEL KARTLARI — kaynak-bağımsız (Excel/veritabanı) CRUD servisi.

Web panelindeki "Personel Kartları" sayfasının TÜM veri okuma/yazma
mantığı burada toplanır — UI katmanı (web/tab_modules/personel_kartlari.py)
yalnızca bu fonksiyonları çağırır, hangi kaynağın (Excel/veritabanı)
aktif olduğunu bilmesi GEREKMEZ.

DÜZELTME: Bu sayfa önceden YALNIZ veritabanı modunda (BASDAS_INPUT_
SOURCE=db) çalışıyordu; Excel modunda (VARSAYILAN durum) tamamen devre
dışıydı. Artık ikisi de destekleniyor:
  - Veritabanı modu: services/input_data_access.py (read_sheet/write_sheet)
  - Excel modu: services/master_data_admin.py'nin MEVCUT, test edilmiş
    yedekleme+doğrulama+atomik-yazma mekanizması AYNEN kullanılır
    (tekerlek yeniden icat edilmez) — yalnız Fact_Mevcut'un EDITABLE_
    COLUMNS alt kümesi yazılabilir, Mağaza/Unvan görüntü adları o
    kaynakta zaten VLOOKUP formülüyle otomatik gelir.

Kimlik anahtarı: İsim Soyisim + MağazaID (src/data_loading.py'nin
kurduğu "Ad Soyad benzersiz anahtardır" ilkesiyle tutarlı).
"""
from __future__ import annotations

import os
from datetime import date, datetime
import json
from pathlib import Path

import pandas as pd


def _db_modu() -> bool:
    return os.environ.get("BASDAS_INPUT_SOURCE", "excel").strip().lower() == "db"


# ------------------------------------------------------------------
# OKUMA (görüntüleme için Mağaza/Unvan adları dahil tam görünüm)
# ------------------------------------------------------------------
from functools import lru_cache


@lru_cache(maxsize=8)
def _load_personnel_view_excel_cached(path_text: str, mtime_ns: int, size: int):
    """DÜZELTME (performans): önceden bu okuma HİÇ önbelleklenmiyordu —
    her sayfa etkileşiminde (personel görünümü + 4 izin kontrolü gibi)
    tekrar tekrar diskten okunuyordu, ölçülen maliyet ~0.93 sn/etkileşim.
    Artık dosyanın mtime+boyutuna göre önbelleklenir; dosya GERÇEKTEN
    değişmediği sürece (başka bir yazma olmadıkça) tekrar okunmaz, ama
    herhangi bir yazmadan HEMEN sonra otomatik olarak taze okunur."""
    staff = pd.read_excel(path_text, sheet_name="Fact_Mevcut", dtype=object)
    magaza = pd.read_excel(path_text, sheet_name="Dim_Magaza", dtype=object)
    unvan = pd.read_excel(path_text, sheet_name="Dim_Unvan", dtype=object)
    cikis_nedeni = pd.read_excel(path_text, sheet_name="Dim_CikisNedeni", dtype=object)
    return staff, magaza, unvan, cikis_nedeni


def load_personnel_view(input_path: Path | None = None):
    """(staff, magaza, unvan, cikis_nedeni) — dördü de DataFrame.
    staff'ta Mağaza/Unvan GÖRÜNTÜ ADLARI (ID değil) doludur."""
    if _db_modu():
        from services.input_data_access import read_sheet
        staff = read_sheet("Fact_Mevcut")
        magaza = read_sheet("Dim_Magaza")
        unvan = read_sheet("Dim_Unvan")
        cikis_nedeni = read_sheet("Dim_CikisNedeni")
    else:
        p = Path(input_path)
        st_ = p.stat()
        staff, magaza, unvan, cikis_nedeni = _load_personnel_view_excel_cached(
            str(p.resolve()), int(st_.st_mtime_ns), int(st_.st_size)
        )
        staff, magaza, unvan, cikis_nedeni = (
            staff.copy(deep=True), magaza.copy(deep=True), unvan.copy(deep=True), cikis_nedeni.copy(deep=True)
        )

    for c in ("İsim Soyisim", "MağazaID", "Mağaza", "UnvanID", "Unvan", "Departman",
              "İşe Giriş", "İşten Çıkış", "Çıkış Kodu", "CikisNedeniID", "Çıkış Nedeni", "Açıklama"):
        if c not in staff.columns:
            staff[c] = None

    # Mağaza/Unvan sütunları GERÇEK dosyada Excel formülüdür (VLOOKUP) —
    # ham okumada (özellikle veritabanı modunda) boş gelebilir. Aynı
    # src/data_loading.py::load() mantığıyla Python tarafında tamamlanır.
    if not magaza.empty and {"MağazaID", "Mağaza"}.issubset(magaza.columns):
        mag_ad_map = dict(zip(magaza["MağazaID"], magaza["Mağaza"]))
        staff["Mağaza"] = staff["MağazaID"].map(mag_ad_map).fillna(staff["Mağaza"])
        if "Bölge Sorumlusu" in magaza.columns:
            bolge_map = dict(zip(magaza["MağazaID"], magaza["Bölge Sorumlusu"]))
            staff["Bölge Sorumlusu"] = staff["MağazaID"].map(bolge_map)
    if not unvan.empty and {"UnvanID", "Unvan"}.issubset(unvan.columns):
        unvan_ad_map = dict(zip(unvan["UnvanID"], unvan["Unvan"]))
        staff["Unvan"] = staff["UnvanID"].map(unvan_ad_map).fillna(staff["Unvan"])

    return staff, magaza, unvan, cikis_nedeni


def is_active(row) -> bool:
    from services.personnel_status import row_is_active
    return row_is_active(row)


# ------------------------------------------------------------------
# YAZMA — ortak alt katman: Excel modunda değişikliği güvenli biçimde
# geri yazar (master_data_admin'in mevcut mekanizmasıyla), veritabanı
# modunda doğrudan write_sheet çağırır.
# ------------------------------------------------------------------
def _invalidate_current_reports(root: Path) -> None:
    """Personel değiştiğinde eski raporun yanlış isim/mevcut göstermesini önler.

    Arşiv/yedeklere dokunulmaz; yalnız yeniden üretilebilir güncel çıktı dosyaları
    temizlenir. Böylece kullanıcı eski PDF'yi yanlışlıkla açamaz.
    """
    output = root / 'output'
    for name in (
        'BASDAS_Yonetici_Raporu.pdf',
        'BASDAS_Yonetici_Raporu.xlsx',
        'BASDAS_Kutucuklu_Yonetici_Raporu.xlsx',
        'BASDAS_Executive_Data.xlsx',
    ):
        try:
            (output / name).unlink(missing_ok=True)
        except Exception:
            pass
    # Tüm yeniden üretilebilir yönetici/bölge çıktıları eski personel adını
    # taşımasın. Arşiv ve rotasyon belgelerine dokunulmaz.
    for pattern in ('BASDAS_*Yonetici*.*', 'BASDAS_Executive_Data.xlsx', 'CURRENT_*Yonetici*.*', 'TUMU_*Yonetici*.*'):
        for fp in output.glob(pattern):
            if fp.is_file() and fp.suffix.lower() in {'.pdf','.xlsx'}:
                try:
                    fp.unlink()
                except Exception:
                    pass
    region_dir = output / 'Bolge_Raporlari'
    if region_dir.is_dir():
        for fp in region_dir.glob('*'):
            if fp.is_file() and fp.suffix.lower() in {'.pdf','.xlsx'}:
                try:
                    fp.unlink()
                except Exception:
                    pass


def _audit_event(**kwargs) -> None:
    """Değiştirilemez (immutable) merkezi denetim izni — SQLite trigger'ları
    UPDATE/DELETE'i veritabanı düzeyinde engeller. İş yazması, denetim
    kaydı geçici olarak yazılamasa bile BAŞARILI kalmalıdır."""
    try:
        from services.audit_events import record
        record(**kwargs)
    except Exception as exc:
        from services.safe_exec import log_swallowed
        log_swallowed("personnel business audit could not be written", exc)


def _save_full_staff_frame(*, input_path: Path, root: Path, df: pd.DataFrame, username: str) -> None:
    if _db_modu():
        from services.input_data_access import write_sheet
        write_sheet("Fact_Mevcut", df, kullanici=username)
        _invalidate_current_reports(root)
        return

    from services.master_data_admin import EDITABLE_COLUMNS, read_tables, save_tables
    tables = read_tables(input_path)
    alt_kume = df[[c for c in EDITABLE_COLUMNS["Fact_Mevcut"] if c in df.columns]].copy()
    for c in EDITABLE_COLUMNS["Fact_Mevcut"]:
        if c not in alt_kume.columns:
            alt_kume[c] = None
    tables["Fact_Mevcut"] = alt_kume[EDITABLE_COLUMNS["Fact_Mevcut"]]
    save_tables(root, input_path, tables, username, acquire_lock=False)
    _invalidate_current_reports(root)
    # DÜZELTME (canlı üretim hatası): openpyxl ile yazmak, dosyadaki
    # formüle dayalı sayfaların (ör. Magaza_KPI_Skor_Karti — CEO Özeti
    # tarafından okunuyor) önceden hesaplanmış değerlerini KAYBEDER —
    # bizzat kanıtlandı: personel eklendikten sonra bu sayfa tamamen
    # NaN'a düşüyordu. Tam LibreOffice yeniden hesaplaması 60-150 sn
    # sürdüğü için (hızlı web işlemini BLOKE ETMEMESİ gerekiyor) bunu
    # arka plan işi olarak kuyruğa alıyoruz — kullanıcı hızlı kalır,
    # formüller birkaç dakika içinde arka planda düzelir.
    try:
        from services.job_queue import enqueue
        from services.tenant_context import current_tenant_id
        enqueue("RECALCULATE_FORMULAS", {"input_path": str(input_path)}, tenant=current_tenant_id() or "BASDAS")
    except Exception as _exc:
        from services.safe_exec import log_swallowed
        log_swallowed("personnel_exit._save_full_staff_frame: formül yeniden hesaplama kuyruğa alınamadı", _exc)


def add_personnel(*, input_path: Path, root: Path, staff: pd.DataFrame, yeni_kayit: dict, username: str) -> None:
    from services.multi_pc_excel import excel_transaction_lock
    with excel_transaction_lock(input_path, user=username):
        fresh, magaza_df, unvan_df, _ = load_personnel_view(input_path)
        # DÜZELTME (Madde 11 — servis katmanı doğrulaması): önceden bu
        # kontroller yalnız UI'daki selectbox'larla DOLAYLI olarak
        # sağlanıyordu (kullanıcı arayüzden geçersiz bir mağaza/unvan
        # SEÇEMEZDİ) — ama servis fonksiyonunun KENDİSİ hiçbir doğrulama
        # yapmıyordu. Başka bir çağıran (script, API, gelecekteki farklı
        # bir arayüz) bu korumayı atlayabilirdi.
        isim = str(yeni_kayit.get("İsim Soyisim") or "").strip()
        magaza_id = yeni_kayit.get("MağazaID")
        unvan_id = yeni_kayit.get("UnvanID")
        if not isim:
            raise ValueError("İsim Soyisim zorunludur.")
        if not yeni_kayit.get("İşe Giriş"):
            raise ValueError("İşe Giriş tarihi zorunludur.")
        if magaza_id is None or str(magaza_id).strip() == "" or not (magaza_df["MağazaID"].astype(str) == str(magaza_id)).any():
            raise ValueError(f"Geçersiz Mağaza: '{magaza_id}' Dim_Magaza'da bulunamadı.")
        if unvan_id is None or str(unvan_id).strip() == "" or not (unvan_df["UnvanID"].astype(str) == str(unvan_id)).any():
            raise ValueError(f"Geçersiz Unvan: '{unvan_id}' Dim_Unvan'da bulunamadı.")
        _ayni_isim = fresh[fresh["İsim Soyisim"].astype(str).str.strip().str.casefold() == isim.casefold()]
        _ayni_isim_aktif = _ayni_isim[_ayni_isim.apply(lambda r: is_active(r.to_dict()), axis=1)]
        if not _ayni_isim_aktif.empty:
            _mevcut_magaza = str(_ayni_isim_aktif.iloc[0].get("Mağaza", ""))
            raise ValueError(f"{isim} adında zaten AKTİF bir personel kaydı var ({_mevcut_magaza}). Mükerrer giriş engellendi.")

        guncel = pd.concat([fresh, pd.DataFrame([yeni_kayit])], ignore_index=True)
        _save_full_staff_frame(input_path=input_path, root=root, df=guncel, username=username)
    _audit_event(actor=username, action="PERSONNEL_ADD", entity_type="personnel",
                 entity_key=str(yeni_kayit.get("İsim Soyisim", "")), before=None, after=yeni_kayit)


def update_personnel(*, input_path: Path, root: Path, staff: pd.DataFrame, index, guncellemeler: dict, username: str) -> None:
    from services.multi_pc_excel import excel_transaction_lock
    with excel_transaction_lock(input_path, user=username):
        fresh, _, _, _ = load_personnel_view(input_path)
        if index not in fresh.index:
            raise ValueError("Personel kaydı başka bir kullanıcı tarafından değişmiş; ekranı yenileyin.")
        onceki = fresh.loc[index].to_dict()
        for k, v in guncellemeler.items():
            fresh.loc[index, k] = v
        _save_full_staff_frame(input_path=input_path, root=root, df=fresh, username=username)
    _audit_event(actor=username, action="PERSONNEL_UPDATE", entity_type="personnel",
                 entity_key=str(onceki.get("İsim Soyisim", "")), before=onceki, after=guncellemeler)


def cikis_nedenleri(sheets: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
    """Geriye dönük uyum: sheets verilirse oradan, verilmezse doğrudan kaynaktan okur."""
    if sheets is not None:
        df = sheets.get("Dim_CikisNedeni")
        if df is not None and not df.empty:
            return df.copy()
    _, _, _, cikis_nedeni = load_personnel_view(None)
    return cikis_nedeni


def _process_exit_unlocked(
    *,
    input_path: Path,
    root: Path,
    isim_soyisim: str,
    magaza_id: str,
    staff_index=None,
    cikis_tarihi: date,
    cikis_kodu: str,
    cikis_nedeni_id,
    cikis_nedeni_metni: str = "",
    kullanici: str,
) -> dict:
    """Tek bir personelin işten çıkışını GÜVENLİ biçimde kaydeder.
    Aynı kişi zaten çıkmışsa İşlemi REDDEDER (kazara ikinci kez işlenip
    denetim izinin bozulmasını önler)."""
    staff, _, _, _ = load_personnel_view(input_path)
    # UI tek bir kayıt satırını seçtiğinde indeks üzerinden işlem yapmak kritik:
    # aynı isim + aynı mağaza kombinasyonunda birden fazla kişi bulunabilir.
    if staff_index is not None:
        try:
            idx = int(staff_index)
        except Exception as exc:
            raise ValueError("Geçersiz personel kayıt satırı.") from exc
        if idx not in staff.index:
            raise ValueError(f"Personel kayıt satırı bulunamadı: {idx}")
        row = staff.loc[idx]
        if str(row.get("İsim Soyisim", "")).strip() != isim_soyisim.strip() or \
           str(row.get("MağazaID", "")).strip() != str(magaza_id).strip():
            raise ValueError("Seçilen personel kaydı değişti; ekranı yenileyip tekrar deneyin.")
        eslesen = pd.Series(False, index=staff.index)
        eslesen.loc[idx] = True
    else:
        eslesen = (staff["İsim Soyisim"].astype(str).str.strip() == isim_soyisim.strip()) & \
                  (staff["MağazaID"].astype(str).str.strip() == str(magaza_id).strip())
        if int(eslesen.sum()) > 1:
            raise ValueError(
                f"{isim_soyisim} için aynı mağazada birden fazla kayıt bulundu. "
                "Güvenli işlem için personeli panelden yeniden seçin."
            )

    if not eslesen.any():
        raise ValueError(f"Personel bulunamadı: {isim_soyisim} ({magaza_id})")
    zaten_cikmis = staff.loc[eslesen, "İşten Çıkış"].apply(lambda v: not is_active({"İşten Çıkış": v})).any()
    if zaten_cikmis:
        raise ValueError(f"{isim_soyisim} için işten çıkış zaten kayıtlı — tekrar işlenemez.")

    staff.loc[eslesen, "İşten Çıkış"] = cikis_tarihi.isoformat()
    staff.loc[eslesen, "Çıkış Kodu"] = cikis_kodu
    staff.loc[eslesen, "CikisNedeniID"] = cikis_nedeni_id
    if cikis_nedeni_metni:
        staff.loc[eslesen, "Çıkış Nedeni"] = cikis_nedeni_metni

    _save_full_staff_frame(input_path=input_path, root=root, df=staff, username=kullanici)
    return {"durum": "OK", "guncellenen_satir": int(eslesen.sum())}



def process_exit(*, input_path: Path, root: Path, isim_soyisim: str, magaza_id: str, staff_index=None, cikis_tarihi: date, cikis_kodu: str, cikis_nedeni_id, cikis_nedeni_metni: str = "", kullanici: str) -> dict:
    from services.multi_pc_excel import excel_transaction_lock
    with excel_transaction_lock(input_path, user=kullanici):
        _oncesi, _, _, _ = load_personnel_view(input_path)
        sonuc = _process_exit_unlocked(input_path=input_path, root=root, isim_soyisim=isim_soyisim, magaza_id=magaza_id, staff_index=staff_index, cikis_tarihi=cikis_tarihi, cikis_kodu=cikis_kodu, cikis_nedeni_id=cikis_nedeni_id, cikis_nedeni_metni=cikis_nedeni_metni, kullanici=kullanici)
        _sonrasi, _, _, _ = load_personnel_view(input_path)
    _audit_event(actor=kullanici, action="PERSONNEL_EXIT", entity_type="personnel", entity_key=isim_soyisim,
                 before={"aktif": True}, after={"İşten Çıkış": cikis_tarihi.isoformat(), "Çıkış Kodu": cikis_kodu, "Çıkış Nedeni": cikis_nedeni_metni})
    try:
        from services.change_manifest import build_change_manifest, append_manifest_log, BILINEN_FORMUL_SUTUNLARI
        _manifest = build_change_manifest(sheet="Fact_Mevcut", key_col="İsim Soyisim", before=_oncesi, after=_sonrasi, ignore_columns=BILINEN_FORMUL_SUTUNLARI)
        append_manifest_log(root, _manifest)
    except Exception as _exc:
        from services.safe_exec import log_swallowed
        log_swallowed("process_exit: change manifest yazılamadı", _exc)
    return sonuc

def aktif_personel_karti_verisi(sheets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Geriye dönük uyum için korunur: verilen sheets dict'inden
    (src/data_loading.py::load() şeklinde) kart verisini türetir."""
    fm = sheets.get("Fact_Mevcut") if sheets else None
    if fm is None or fm.empty:
        return pd.DataFrame()
    df = fm.copy()
    for col in ("İsim Soyisim", "Mağaza", "Unvan", "Departman", "MağazaID", "UnvanID", "İşe Giriş", "İşten Çıkış"):
        if col not in df.columns:
            df[col] = None
    df = df[df["İsim Soyisim"].notna() & df["İsim Soyisim"].astype(str).str.strip().ne("")]
    return df.reset_index(drop=True)


def add_personnel_bulk(*, input_path: Path, root: Path, staff: pd.DataFrame, yeni_kayitlar: list[dict], username: str) -> dict:
    """Birden fazla işe girişi Excel'e TEK yazma işlemiyle kaydeder.

    Performans için her personelde dosyayı yeniden açmak yerine tüm kayıtları
    mevcut Fact_Mevcut DataFrame'ine ekler ve bir kez güvenli/atomik kaydeder.
    """
    kayitlar = [dict(x) for x in (yeni_kayitlar or []) if str((x or {}).get("İsim Soyisim") or "").strip()]
    if not kayitlar:
        raise ValueError("Kaydedilecek personel bulunamadı.")
    from services.multi_pc_excel import excel_transaction_lock
    with excel_transaction_lock(input_path, user=username):
        fresh, _, _, _ = load_personnel_view(input_path) if Path(input_path).exists() else (staff.copy(), None, None, None)
        guncel = pd.concat([fresh.copy(), pd.DataFrame(kayitlar)], ignore_index=True)
        _save_full_staff_frame(input_path=input_path, root=root, df=guncel, username=username)
    _audit_event(actor=username, action="PERSONNEL_BULK_ADD", entity_type="personnel_batch",
                 entity_key=f"{len(kayitlar)} kişi", before=None, after=kayitlar)
    return {"durum": "OK", "eklenen": len(kayitlar)}


def _process_exits_bulk_unlocked(
    *,
    input_path: Path,
    root: Path,
    cikislar: list[dict],
    kullanici: str,
) -> dict:
    """Birden fazla işten çıkışı işler; HER SATIR BAĞIMSIZ bir işlemdir.

    DÜZELTME (iş kuralı değişikliği — kullanıcı ile netleştirildi, OMEHR
    hızlandırma şartnamesi Madde 15): önceden TEK bir satırdaki hata
    (kod/neden uyuşmazlığı, zaten çıkmış personel, geçersiz satır) TÜM
    toplu işlemi reddediyordu (tüm-ya-da-hiçbiri). Artık her satır kendi
    başına doğrulanır; geçerli satırlar TEK bir yazma işlemiyle (hâlâ
    verimli) kaydedilir, geçersiz satırlar diğerlerini ETKİLEMEDEN
    ayrı ayrı raporlanır — tam şartnamedeki örnek gibi: "15 kayıt
    başarılı, 2 kayıt çıkış kodu eksik, 1 kayıt zaten çıkmış, 2 kayıt
    veri uyumsuz".

    ``cikislar`` öğeleri ``index``, ``cikis_tarihi``, ``cikis_kodu``,
    ``cikis_nedeni_id`` ve isteğe bağlı ``cikis_nedeni_metni`` içerir.
    """
    staff, _, _, cikis_nedeni = load_personnel_view(input_path)
    if not cikislar:
        raise ValueError("İşten çıkışı kaydedilecek personel seçilmedi.")

    grup_by_id = {}
    if cikis_nedeni is not None and not cikis_nedeni.empty and \
       {"CikisNedeniID", "CikisGrubu"}.issubset(cikis_nedeni.columns):
        grup_by_id = dict(zip(cikis_nedeni["CikisNedeniID"], cikis_nedeni["CikisGrubu"].astype(str)))

    basarili: list[dict] = []
    hatalar: list[dict] = []

    for item in cikislar:
        idx = item.get("index")
        isim = ""
        try:
            if idx not in staff.index:
                raise ValueError("Personel satırı bulunamadı (ekran güncel olmayabilir).")
            row = staff.loc[idx]
            isim = str(row.get("İsim Soyisim", "") or "")
            if not is_active(row.to_dict()):
                raise ValueError("İşten çıkış zaten kayıtlı.")

            verilen_kod = str(item.get("cikis_kodu") or "").strip()
            neden_id = item.get("cikis_nedeni_id")
            beklenen_grup = str(grup_by_id.get(neden_id, "")).strip()
            if beklenen_grup and verilen_kod != beklenen_grup:
                raise ValueError(
                    f"Çıkış Kodu/Nedeni uyumsuz: '{verilen_kod}' koduna karşı seçilen neden "
                    f"'{beklenen_grup}' grubundadır."
                )
            if not verilen_kod:
                raise ValueError("Çıkış Kodu eksik.")

            dt = item.get("cikis_tarihi")
            if hasattr(dt, "isoformat"):
                dt = dt.isoformat()
            staff.loc[idx, "İşten Çıkış"] = str(dt or "")
            staff.loc[idx, "Çıkış Kodu"] = verilen_kod
            staff.loc[idx, "CikisNedeniID"] = neden_id
            reason = str(item.get("cikis_nedeni_metni") or "")
            if reason:
                if "Çıkış Nedeni" not in staff.columns:
                    staff["Çıkış Nedeni"] = None
                staff.loc[idx, "Çıkış Nedeni"] = reason
            if "aciklama" in item:
                staff.loc[idx, "Açıklama"] = str(item.get("aciklama") or "").strip()
            basarili.append({"index": idx, "isim": isim})
        except ValueError as exc:
            hatalar.append({"index": idx, "isim": isim, "hata": str(exc)})

    if basarili:
        _save_full_staff_frame(input_path=input_path, root=root, df=staff, username=kullanici)

    return {
        "durum": "OK" if not hatalar else "KISMEN_BASARILI",
        "guncellenen_satir": len(basarili),
        "basarisiz_satir": len(hatalar),
        "basarili": basarili,
        "hatalar": hatalar,
    }


def process_exits_bulk(*, input_path: Path, root: Path, cikislar: list[dict], kullanici: str) -> dict:
    from services.multi_pc_excel import excel_transaction_lock
    with excel_transaction_lock(input_path, user=kullanici):
        sonuc = _process_exits_bulk_unlocked(input_path=input_path, root=root, cikislar=cikislar, kullanici=kullanici)
    _audit_event(actor=kullanici, action="PERSONNEL_BULK_EXIT", entity_type="personnel_batch",
                 entity_key=f"{len(cikislar)} kişi", before=None, after=cikislar)
    return sonuc


def _append_exit_audit(root: Path, payload: dict) -> None:
    """Çıkış/geri alma işlemlerinin denetim izini dosyada saklar."""
    try:
        path = Path(root) / "logs" / "personnel_exit_audit.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {"timestamp": datetime.now().isoformat(timespec="seconds"), **payload}
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def undo_exit(*, input_path: Path, root: Path, staff_index, isim_soyisim: str, magaza_id: str, kullanici: str) -> dict:
    """Yanlış işlenmiş bir çıkışı geri alır ve personeli yeniden aktif eder (FAST V17).

    Açıklama korunur; yalnız resmi çıkış alanları temizlenir. Ortak Excel kilidi
    altında taze veri okunur; böylece 3-PC kullanımında eski ekran verisiyle
    başka satırın üzerine yazılmaz.
    """
    from services.multi_pc_excel import excel_transaction_lock
    with excel_transaction_lock(input_path, user=kullanici):
        staff, _, _, _ = load_personnel_view(input_path)
        try:
            idx = int(staff_index)
        except Exception as exc:
            raise ValueError("Geçersiz personel kayıt satırı.") from exc
        if idx not in staff.index:
            raise ValueError("Personel kaydı değişmiş; ekranı yenileyin.")
        row = staff.loc[idx]
        if str(row.get("İsim Soyisim", "")).strip() != str(isim_soyisim).strip() or \
           str(row.get("MağazaID", "")).strip() != str(magaza_id).strip():
            raise ValueError("Seçilen personel kaydı değişmiş; ekranı yenileyin.")
        if is_active(row.to_dict()):
            raise ValueError(f"{isim_soyisim} zaten aktif; geri alınacak çıkış bulunamadı.")
        old = {k: row.get(k) for k in ("İşten Çıkış", "Çıkış Kodu", "CikisNedeniID", "Çıkış Nedeni")}
        for col in ("İşten Çıkış", "Çıkış Kodu", "CikisNedeniID", "Çıkış Nedeni"):
            if col not in staff.columns:
                staff[col] = None
            staff.loc[idx, col] = None
        _save_full_staff_frame(input_path=input_path, root=root, df=staff, username=kullanici)
        _append_exit_audit(root, {"action": "UNDO_EXIT", "user": kullanici, "name": isim_soyisim, "store_id": magaza_id, "row": idx, "previous": old})
    _audit_event(actor=kullanici, action="PERSONNEL_EXIT_UNDO", entity_type="personnel", entity_key=isim_soyisim,
                 before=old, after={"İşten Çıkış": None})
    return {"durum": "OK", "guncellenen_satir": 1}
