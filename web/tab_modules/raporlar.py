"""Raporlar sekmesi (Rapor Merkezi).

DÜZELTME (29 Ağustos 2026): Bu dosya önceden yanlışlıkla `onaylar.py` ile
neredeyse birebir aynı içeriği barındırıyordu (transfer onay iş akışı) —
gerçek rapor listeleme/indirme kodu, muhtemelen web/app.py içindeki eski
"with tabs[N]:" bloğunun otomatik dosyalara ayrıştırılması sırasında kaybolmuş
veya yanlışlıkla onaylar.py içeriğiyle üzerine yazılmıştır. Sonuç: "Raporlar"
sekmesi kullanıcıya üretilen PDF/Excel raporlarını hiç göstermiyor, bunun
yerine "Onaylar" sekmesiyle birebir aynı ekranı (Bölge ve İK Onayları
tablosu) gösteriyordu.

Bu dosya, ctx.output_path (= runtime_root()/"output") altında üretilen tüm
rapor dosyalarını (.pdf, .xlsx, .xlsm) bulur, kullanıcının yetkisine göre
filtreler (bölge kullanıcıları yalnızca kendi bölgeleriyle ilgili dosyaları
görür), ana şirket geneli raporları ile bölge/şube bazlı raporları ayrı
bölümlerde listeler ve her biri için indirme butonu sağlar.
"""

from __future__ import annotations

import streamlit as st

from datetime import datetime
from pathlib import Path

from web.context import PageContext


REPORT_EXTENSIONS = {".pdf", ".xlsx", ".xlsm"}


def _dosya_boyutu_okunur(byte_sayisi: int) -> str:
    """Byte cinsinden boyutu MB/KB olarak okunur biçime çevirir."""
    if byte_sayisi >= 1024 * 1024:
        return f"{byte_sayisi / (1024 * 1024):.1f} MB"
    if byte_sayisi >= 1024:
        return f"{byte_sayisi / 1024:.0f} KB"
    return f"{byte_sayisi} B"


def _rapor_dosyalarini_bul(output_dir: Path) -> list[Path]:
    """output_dir altındaki (alt klasörler dahil) tüm rapor dosyalarını bulur."""
    if not output_dir.is_dir():
        return []
    return [
        p for p in output_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in REPORT_EXTENSIONS
    ]


def _kullaniciya_gorunur_mu(dosya: Path, is_global: bool, scope: str, norm_text) -> bool:
    """Bölge kullanıcıları yalnızca kendi bölge/isim eşleşen dosyalarını görür.

    Genel (is_global) kullanıcılar (İK, yönetim, admin) tüm dosyaları görür.
    """
    if is_global:
        return True
    return norm_text(scope) in norm_text(dosya.stem)


def _dosyalari_listele(dosyalar: list[Path], output_dir: Path, baslik: str) -> None:
    """Bir grup rapor dosyasını, en yeniden en eskiye sıralı şekilde,
    indirme butonlarıyla birlikte gösterir."""
    if not dosyalar:
        return

    st.markdown(f"**{baslik} ({len(dosyalar)})**")
    dosyalar_sirali = sorted(dosyalar, key=lambda p: p.stat().st_mtime, reverse=True)

    for dosya in dosyalar_sirali:
        istatistik = dosya.stat()
        degisim_zamani = datetime.fromtimestamp(istatistik.st_mtime).strftime("%d.%m.%Y %H:%M")
        boyut = _dosya_boyutu_okunur(istatistik.st_size)
        try:
            goreli_yol = dosya.relative_to(output_dir)
        except ValueError:
            goreli_yol = dosya.name

        kolon_ad, kolon_bilgi, kolon_indir = st.columns([3, 2, 1])
        with kolon_ad:
            st.write(f"📄 {dosya.name}")
            if str(goreli_yol) != dosya.name:
                st.caption(str(goreli_yol.parent) if hasattr(goreli_yol, "parent") else "")
        with kolon_bilgi:
            st.caption(f"{degisim_zamani} · {boyut}")
        with kolon_indir:
            try:
                veri = dosya.read_bytes()
                st.download_button(
                    "İndir",
                    data=veri,
                    file_name=dosya.name,
                    key=f"indir_{dosya}",
                    use_container_width=True,
                )
            except Exception:
                st.caption("⚠️ Okunamadı")


def render(ctx: PageContext) -> None:
    """Raporlar (Rapor Merkezi) sekmesinin içeriğini çizer."""
    is_global = ctx.is_global
    scope = ctx.scope
    norm_text = ctx.norm_text
    OUTPUT = ctx.output_path

    st.subheader("Rapor Merkezi")
    st.caption(
        "Üretilen tüm PDF/Excel raporlarını buradan görüntüleyip indirebilirsiniz. "
        "Yeni raporlar için soldaki menüden 'Tüm tabloları şimdi yenile' butonunu kullanın."
    )

    tum_dosyalar = _rapor_dosyalarini_bul(OUTPUT)

    if not tum_dosyalar:
        st.info(
            "Henüz üretilmiş bir rapor bulunamadı. Soldaki menüden "
            "'Tüm tabloları şimdi yenile' butonuna basarak raporları üretebilirsiniz."
        )
        return

    gorunur_dosyalar = [
        d for d in tum_dosyalar
        if _kullaniciya_gorunur_mu(d, is_global, scope, norm_text)
    ]

    if not gorunur_dosyalar:
        st.info("Yetki kapsamınıza ait bir rapor bulunamadı.")
        return

    # Ana (şirket geneli / yönetici) raporlar: OUTPUT'un doğrudan altındaki dosyalar.
    ana_raporlar = [d for d in gorunur_dosyalar if d.parent == OUTPUT]

    # Bölge/şube bazlı raporlar: OUTPUT altındaki alt klasörlerde duran dosyalar
    # (örn. Bolge_Raporlari/). Alt klasör adına göre gruplanır.
    alt_klasor_gruplari: dict[str, list[Path]] = {}
    for dosya in gorunur_dosyalar:
        if dosya.parent == OUTPUT:
            continue
        try:
            ilk_alt_klasor = dosya.relative_to(OUTPUT).parts[0]
        except (ValueError, IndexError):
            ilk_alt_klasor = "Diğer"
        alt_klasor_gruplari.setdefault(ilk_alt_klasor, []).append(dosya)

    toplam = len(gorunur_dosyalar)
    st.success(f"Toplam {toplam} rapor dosyası bulundu.")

    if ana_raporlar:
        _dosyalari_listele(ana_raporlar, OUTPUT, "Yönetici ve Ana Raporlar")
        st.divider()

    for klasor_adi, dosyalar in sorted(alt_klasor_gruplari.items()):
        with st.expander(f"{klasor_adi.replace('_', ' ')} ({len(dosyalar)})", expanded=False):
            _dosyalari_listele(dosyalar, OUTPUT, klasor_adi.replace("_", " "))
