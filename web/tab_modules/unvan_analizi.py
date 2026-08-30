"""Ünvan Analizi sekmesi.

Bu sekme, engine_core ve dashboard_model çıktılarındaki farklı sütun şemalarını
tek bir güvenli görünümde birleştirir. Personel adı ve gerçek unvan bilgileri
Fact_Mevcut'tan dinamik olarak üretilir; sabit sütun adına bağımlı değildir.
"""
from __future__ import annotations

import re
import unicodedata

import pandas as pd
import streamlit as st

from web.context import PageContext


def _text(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _key(value: object) -> str:
    """Türkçe karakter ve yazım farklarına dayanıklı eşleştirme anahtarı."""
    text = _text(value).upper().replace("İ", "I").replace("İ", "I")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^A-Z0-9]+", " ", text).strip()


def _first_existing(frame: pd.DataFrame, names: tuple[str, ...]) -> str | None:
    return next((name for name in names if name in frame.columns), None)


def _prepare_title_view(detail: pd.DataFrame, staff: pd.DataFrame) -> pd.DataFrame:
    """Ünvan analizi için şemadan bağımsız, güvenli tablo üretir.

    ``detail`` engine_core'dan geldiğinde personel adı/gerçek unvan sütunları
    bulunmaz. Bu bilgiler aktif Fact_Mevcut kayıtlarından mağaza + norm ailesi
    bazında yeniden oluşturulur ve tabloya eklenir.
    """
    view = detail.copy() if isinstance(detail, pd.DataFrame) else pd.DataFrame()
    people = staff.copy() if isinstance(staff, pd.DataFrame) else pd.DataFrame()

    # DÜZELTME: uyarı bayrağını burada, herhangi bir merge/reset_index
    # işleminden ÖNCE gerçek bir "view" sütunu haline getiriyoruz —
    # aksi halde fonksiyonun sonundaki merge sonrası index kayması
    # yüzünden yanlış satırlara yanlış uyarı atanabilirdi.
    _uyari_kaynagi = _first_existing(view, ("Ana Unvan Personelsiz Uyarısı", "_Ana Unvan Personelsiz"))
    view["_yetkinlik_uyarisi_ham"] = view[_uyari_kaynagi].fillna(False) if _uyari_kaynagi else False

    # Sayısal kolonların iki olası ad grubunu da kabul et.
    aliases = {
        "Mevcut": ("Mevcut", "Aktif Mevcut"),
        "Norm": ("Norm", "Norm Kadro"),
        "Eksik": ("Eksik", "Norm Eksiği"),
        "Fazla": ("Fazla", "Norm Fazlası"),
    }
    for target, candidates in aliases.items():
        source = _first_existing(view, candidates)
        view[target] = pd.to_numeric(view[source], errors="coerce").fillna(0).astype(int) if source else 0

    # Zorunlu kimlik/görünüm kolonlarını güvenli biçimde oluştur.
    for col in ("Bölge Sorumlusu", "Mağaza", "Unvan"):
        if col not in view.columns:
            view[col] = ""
        view[col] = view[col].fillna("").map(_text)

    # Detail kendi personel sütunlarıyla geldiyse onları koru; gelmediyse
    # Fact_Mevcut'tan üretilecek değerlerle doldur.
    existing_names = _first_existing(view, ("Personel Adı Soyadı", "İsim Soyisim", "Ad Soyad"))
    existing_titles = _first_existing(view, ("Gerçek Unvanlar", "Gerçek Ünvanlar", "Gerçek Unvan", "Unvanlar"))
    if existing_names and existing_names != "Personel Adı Soyadı":
        view["Personel Adı Soyadı"] = view[existing_names]
    elif "Personel Adı Soyadı" not in view.columns:
        view["Personel Adı Soyadı"] = ""
    if existing_titles and existing_titles != "Gerçek Unvanlar":
        view["Gerçek Unvanlar"] = view[existing_titles]
    elif "Gerçek Unvanlar" not in view.columns:
        view["Gerçek Unvanlar"] = ""

    if not people.empty:
        store_col = _first_existing(people, ("Mağaza", "Magaza"))
        family_col = _first_existing(people, ("Departman", "Norm Ailesi", "Unvan"))
        title_col = _first_existing(people, ("Unvan", "Gerçek Unvan", "Gerçek Ünvan"))
        name_col = _first_existing(people, ("İsim Soyisim", "Personel Adı Soyadı", "Ad Soyad"))
        status_col = _first_existing(people, ("Durum",))
        exit_col = _first_existing(people, ("İşten Çıkış", "Isten Cikis"))

        if store_col and family_col and title_col and name_col:
            p = people.copy()
            if status_col:
                status = p[status_col].fillna("").astype(str).str.strip().str.upper()
                p = p[(status.eq("") | status.eq("AKTIF") | status.eq("AKTİF"))]
            elif exit_col:
                p = p[p[exit_col].isna() | p[exit_col].astype(str).str.strip().eq("")]

            p["_store_key"] = p[store_col].map(_key)
            p["_role_key"] = p[family_col].map(_key)
            p["_name"] = p[name_col].map(_text)
            p["_title"] = p[title_col].map(_text)
            p = p[(p["_store_key"] != "") & (p["_role_key"] != "") & (p["_name"] != "")]

            if not p.empty:
                grouped = p.groupby(["_store_key", "_role_key"], dropna=False).agg(
                    **{
                        "_names": ("_name", lambda s: ", ".join(dict.fromkeys(v for v in s if v))),
                        "_titles": ("_title", lambda s: ", ".join(dict.fromkeys(v for v in s if v))),
                    }
                ).reset_index()
                view["_store_key"] = view["Mağaza"].map(_key)
                view["_role_key"] = view["Unvan"].map(_key)
                view = view.merge(grouped, on=["_store_key", "_role_key"], how="left")
                current_names = view["Personel Adı Soyadı"].fillna("").map(_text)
                current_titles = view["Gerçek Unvanlar"].fillna("").map(_text)
                view["Personel Adı Soyadı"] = current_names.where(current_names.ne(""), view["_names"].fillna(""))
                view["Gerçek Unvanlar"] = current_titles.where(current_titles.ne(""), view["_titles"].fillna(""))
                view = view.drop(columns=["_store_key", "_role_key", "_names", "_titles"], errors="ignore")

    view["Personel Adı Soyadı"] = view["Personel Adı Soyadı"].fillna("").map(_text)
    view["Gerçek Unvanlar"] = view["Gerçek Unvanlar"].fillna("").map(_text)
    if "Norm Tanımı Durumu" not in view.columns:
        view["Norm Tanımı Durumu"] = ""
    view["Norm Tanımı Durumu"] = view["Norm Tanımı Durumu"].fillna("").map(_text)
    view["Net Fark"] = view["Fazla"] - view["Eksik"]
    # DÜZELTME: "Ana Unvan Personelsiz Uyarısı" bayrağı (state_engine.py'de
    # hesaplanıyor — ana unvanda gerçek kişi olmadığı halde aile dengesiyle
    # Eksik/Fazla 0'a çekilen satırlar) önceden hesaplanıyordu ama HİÇBİR
    # ekranda gösterilmiyordu; bu bilgi kullanıcıya hiç ulaşmıyordu.
    view["Yetkinlik Uyarısı"] = view["_yetkinlik_uyarisi_ham"].map(
        lambda v: "⚠ Ana unvanda doğrudan görevli personel yok" if bool(v) else ""
    )
    view = view.drop(columns=["_yetkinlik_uyarisi_ham"], errors="ignore")
    return view


def render(ctx: PageContext) -> None:
    """Ünvan Analizi sekmesinin içeriğini çizer."""
    title_view = _prepare_title_view(ctx.detail, ctx.fm)
    tanimsiz = title_view[title_view["Norm Tanımı Durumu"].ne("")].copy()
    if not tanimsiz.empty:
        toplam = int(tanimsiz["Mevcut"].sum())
        st.warning(
            f"⚠ Normda tanımlı olmayan {len(tanimsiz)} aktif mağaza/unvan satırı var "
            f"({toplam} personel). Bu kişiler norm 0 kabul edilerek fazlaya dahil edilmiştir; "
            "resmî norma otomatik ekleme yapılmamıştır."
        )
        st.dataframe(
            tanimsiz[[
                "Bölge Sorumlusu", "Mağaza", "Unvan", "Mevcut", "Norm", "Fazla",
                "Norm Tanımı Durumu",
            ]].sort_values(["Bölge Sorumlusu", "Mağaza", "Unvan"]),
            use_container_width=True,
            hide_index=True,
        )
    cols = [
        "Bölge Sorumlusu", "Mağaza", "Unvan", "Gerçek Unvanlar",
        "Personel Adı Soyadı", "Mevcut", "Norm", "Eksik", "Fazla", "Net Fark",
        "Norm Tanımı Durumu", "Yetkinlik Uyarısı",
    ]
    st.dataframe(
        title_view[cols].sort_values(["Bölge Sorumlusu", "Mağaza", "Unvan"]),
        use_container_width=True,
        hide_index=True,
    )
    _uyarili = int((title_view["Yetkinlik Uyarısı"] != "").sum())
    if _uyarili:
        st.caption(
            f"⚠ {_uyarili} satırda ana unvanda doğrudan görevli personel yok — aile içi denge "
            "kadroyu koruyor (Eksik/Fazla 0 görünür) ama bu rolde yetkinlik/eğitim ihtiyacı olabilir."
        )
