from __future__ import annotations

"""
MERKEZİ CSS/STİL MODÜLÜ — OMEHR Tasarım Sistemi v3 (marka değişikliği)
=====================================================================
Bu dosya, ürünün BAŞDAŞ'tan OMEHR'e marka değişikliği kapsamında,
tasarım jetonlarını yeni logo paletiyle (lacivert/teal/altın) uyumlu
hale getirir. Önceki "Çam & Amber" paleti tamamen değiştirildi.

KORUNMASI ZORUNLU olan, geçmişte gerçek kullanıcı testleriyle doğrulanmış
davranışlar (bkz. ilgili yorum satırları):
  - Material Symbols ikon fontu istisnası (aksi halde ikonlar "arrow_forward"
    gibi bozuk metin olarak görünür)
  - Kural SIRASI: genel koyu-metin kuralından SONRA gelen buton/kenar-çubuğu
    istisnaları (aksi halde beyaz metin siyaha döner, okunmaz olur)
  - Kenar çubuğunun üstte yatay şerit olması (kullanıcı isteğiyle kurulmuş
    yerleşim, buradan geri alınmadı)
  - Tek/kararlı kaydırma alanı (100vh + stMain overflow-y:auto)
  - Harici Google Fonts CDN'i ASLA eklenmez (bkz. tests/test_turkish_display_regression.py)

Ölü/kullanılmayan kod TEMİZLENDİ: .basdas-page-tab* sınıfları hiçbir
Python dosyasında referans edilmiyordu (navigasyon st.radio'ya taşınmış),
kaldırıldı.
"""

CSS_STYLES = """
    <style>
    /* ================================================================
       1) JETON SİSTEMİ (design tokens)
       Palet: "OMEHR Lacivert & Teal" — DÜZELTME (marka değişikliği):
       önceki "Çam & Amber" (koyu yeşil+amber) paleti, yeni OMEHR
       logosunun renkleriyle (lacivert #102F64, teal #118B94, altın
       #D5A95C — logodan bizzat örneklendi) UYUMSUZ kalmıştı; sadece
       başlık görseli değişmiş, arayüzün geri kalanı eski renklerde
       kalmıştı. Artık tüm jeton sistemi logo paletiyle eşleşiyor.
       Altın, logodaki gibi SEYREK/vurgu amaçlı kullanılır (aşırıya
       kaçmamak için ana renk değil).
       ================================================================ */
    :root {
        --bd-primary: #102F64;
        --bd-primary-deep: #081B3D;
        --bd-primary-light: #1B4A7A;
        --bd-primary-tint: #E8EDF5;
        --bd-accent: #118B94;
        --bd-accent-deep: #0D6D74;
        --bd-accent-tint: #E3F3F4;
        --bd-selected-yellow: #FFEEA6;
        --bd-gold: #D5A95C;
        --bd-gold-tint: #FAF2E3;
        --bd-bg: #F5F7F9;
        --bd-surface: #FFFFFF;
        --bd-surface-sunken: #FAFBFC;
        --bd-ink: #1A2233;
        --bd-ink-soft: #57616F;
        --bd-ink-faint: #8B94A1;
        --bd-border: #E2E6EC;
        --bd-border-strong: #C9D0D9;
        --bd-danger: #9B2D2D;
        --bd-danger-tint: #F7E8E6;
        --bd-success: #2F7A4F;
        --bd-success-tint: #E9F3EC;
        --bd-radius-sm: 6px;
        --bd-radius-md: 10px;
        --bd-radius-lg: 16px;
        --bd-shadow-sm: 0 1px 2px rgba(8,27,61,0.07), 0 1px 1px rgba(8,27,61,0.05);
        --bd-shadow-md: 0 6px 16px rgba(8,27,61,0.10), 0 2px 5px rgba(8,27,61,0.05);
        --bd-shadow-lg: 0 16px 40px rgba(8,27,61,0.16), 0 4px 10px rgba(8,27,61,0.06);
        --bd-font-sans: 'Segoe UI', Arial, Tahoma, 'DejaVu Sans', sans-serif;
        --bd-font-mono: Consolas, 'Cascadia Mono', 'Courier New', 'DejaVu Sans Mono', monospace;
    }

    html, body, .stApp {
        font-family: var(--bd-font-sans);
        text-rendering: optimizeLegibility;
        -webkit-font-smoothing: antialiased;
    }
    .stApp { background-color: var(--bd-bg); }

    div[data-testid="stTextArea"] textarea,
    div[data-testid="stTextArea"] textarea:disabled {
        color: var(--bd-ink) !important;
        -webkit-text-fill-color: var(--bd-ink) !important;
        opacity: 1 !important;
        background-color: #ffffff !important;
        font-weight: 500 !important;
    }
    div[data-testid="stTextArea"] label, div[data-testid="stTextArea"] label p,
    div[data-testid="stSelectbox"] label, div[data-testid="stSelectbox"] label p {
        color: var(--bd-ink) !important;
        opacity: 1 !important;
    }
    div[data-testid="stAlert"] p { color: var(--bd-ink) !important; opacity: 1 !important; }
    div[data-testid="stDataFrame"] { color: var(--bd-ink) !important; }

    [data-testid="stIconMaterial"],
    span[class*="material-symbol"],
    span[class*="material-icon"] {
        font-family: "Material Symbols Rounded", "Material Icons" !important;
        font-weight: normal !important;
        font-style: normal !important;
        letter-spacing: normal !important;
        text-transform: none !important;
        white-space: nowrap !important;
        word-wrap: normal !important;
        direction: ltr !important;
        -webkit-font-feature-settings: "liga" !important;
        -webkit-font-smoothing: antialiased !important;
    }

    h1, h2, h3, h4 {
        font-family: var(--bd-font-sans) !important;
        color: var(--bd-primary) !important;
        letter-spacing: -0.01em;
    }
    h2 { font-weight: 700 !important; font-size: 1.5rem !important; margin-bottom: 0.9rem !important; }
    h3 { font-weight: 700 !important; font-size: 1.2rem !important; }
    h4 { font-weight: 600 !important; font-size: 1.02rem !important; color: var(--bd-ink-soft) !important; }

    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * {
        color: var(--bd-ink-soft) !important;
    }
    small, .stMarkdown small { color: var(--bd-ink-soft) !important; }
    div[data-testid="stDataFrame"] * { color: var(--bd-ink) !important; }

    div[data-testid="stMetric"] {
        background-color: var(--bd-surface);
        border: 1px solid var(--bd-border);
        border-top: 3px solid var(--bd-accent);
        border-radius: var(--bd-radius-md);
        padding: 0.85rem 1rem 0.7rem 1rem;
        box-shadow: var(--bd-shadow-sm);
        transition: box-shadow 0.18s ease, transform 0.18s ease;
    }
    div[data-testid="stMetric"]:hover {
        box-shadow: var(--bd-shadow-md);
        transform: translateY(-1px);
    }
    div[data-testid="stMetric"] label {
        color: var(--bd-ink-soft) !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        font-size: 0.7rem !important;
        letter-spacing: 0.06em;
    }
    div[data-testid="stMetricValue"] {
        font-family: var(--bd-font-mono) !important;
        font-variant-numeric: tabular-nums;
        color: var(--bd-primary) !important;
        font-weight: 600 !important;
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: unset !important;
        font-size: 1.55rem !important;
        letter-spacing: -0.01em;
    }
    div[data-testid="stMetricDelta"] { font-family: var(--bd-font-mono) !important; }

    div[data-testid="stRadio"] > div[role="radiogroup"] {
        gap: 0.3rem !important;
        flex-wrap: nowrap !important;
        overflow-x: auto !important;
        overflow-y: hidden !important;
        border-bottom: 1px solid var(--bd-border);
        padding-bottom: 0.4rem;
        scrollbar-width: thin;
    }
    div[data-testid="stRadio"] label {
        border-radius: 999px !important;
        padding: 0.32rem 0.85rem !important;
        font-size: 0.82rem !important;
        font-weight: 600 !important;
        color: var(--bd-ink-soft) !important;
        background: transparent !important;
        border: 1px solid transparent !important;
        transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
        white-space: nowrap !important;
    }
    div[data-testid="stRadio"] label:hover {
        background: var(--bd-primary-tint) !important;
        color: var(--bd-primary) !important;
    }
    div[data-testid="stRadio"] label[data-checked="true"] {
        /* DÜZELTME: önceden koyu lacivert zemin + beyaz yazıydı, ama
           sayfanın alt kısmındaki genel "koyu metin" kuralı (bkz. bu
           dosyanın METİN KONTRASTI bölümü) bu beyaz rengi eziyor, koyu
           zemin üzerinde koyu yazı bırakıp OKUNMAZ hale getiriyordu.
           Kullanıcı isteğiyle: gerçekten GÖRÜNÜR açık sarı zemin + koyu
           yazı (--bd-accent-tint pale teal'dir, bu amaç için çok soluk
           kalıyordu — bu yüzden ayrı, belirgin bir sarı jeton eklendi). */
        background: var(--bd-selected-yellow) !important;
        color: var(--bd-primary-deep) !important;
        border-color: var(--bd-accent) !important;
        font-weight: 700 !important;
    }
    /* AYRI kural olarak tutulur: bazı CSS ayrıştırıcıları, virgülle
       ayrılmış bir seçici listesinde TEK bir geçersiz/desteklenmeyen
       seçici (:has()) varsa TÜM listeyi (yukarıdaki geçerli [data-checked]
       seçicisi dahil) sessizce reddedebilir. Ayrı tutmak bu riski ortadan
       kaldırır. */
    div[data-testid="stRadio"] label:has(input:checked) {
        background: var(--bd-selected-yellow) !important;
        color: var(--bd-primary-deep) !important;
        border-color: var(--bd-accent) !important;
        font-weight: 700 !important;
    }

    div.stButton > button, div.stDownloadButton > button {
        background-color: var(--bd-primary) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: var(--bd-radius-sm) !important;
        font-weight: 600 !important;
        padding: 0.45rem 1rem !important;
        box-shadow: var(--bd-shadow-sm);
        transition: background-color 0.15s ease, box-shadow 0.15s ease, transform 0.1s ease;
    }
    div.stButton > button:hover, div.stDownloadButton > button:hover {
        background-color: var(--bd-primary-light) !important;
        box-shadow: var(--bd-shadow-md);
    }
    div.stButton > button:active, div.stDownloadButton > button:active { transform: translateY(1px); }
    div.stButton > button:focus-visible, div.stDownloadButton > button:focus-visible {
        outline: 3px solid var(--bd-accent-tint) !important;
        outline-offset: 1px;
        box-shadow: 0 0 0 2px var(--bd-accent) !important;
    }
    div.stButton > button[kind="secondary"] {
        background-color: var(--bd-surface) !important;
        color: var(--bd-primary) !important;
        border: 1.5px solid var(--bd-border-strong) !important;
        box-shadow: none;
    }
    div.stButton > button[kind="secondary"]:hover {
        border-color: var(--bd-primary) !important;
        background-color: var(--bd-primary-tint) !important;
    }

    div[data-testid="stExpander"] {
        border: 1px solid var(--bd-border) !important;
        border-radius: var(--bd-radius-md) !important;
        background-color: var(--bd-surface);
        box-shadow: var(--bd-shadow-sm);
    }
    div[data-testid="stAlert"] {
        border-radius: var(--bd-radius-sm) !important;
        border-left-width: 4px !important;
        box-shadow: var(--bd-shadow-sm);
    }

    div[data-testid="stAppViewContainer"] { flex-direction: column !important; }
    section[data-testid="stSidebar"] {
        /* DÜZELTME (FAST V14): Streamlit sidebar'ı bazı sürümlerde bir üst
           kapsayıcıdan devraldığı transform/pozisyon nedeniyle "width:100%"
           ile bile tam viewport genişliğine ulaşamıyor, sağda beyaz bir
           şerit kalıyordu. 100vw + left/right/transform sıfırlaması bunu
           kapsayıcıdan bağımsız, kesin biçimde çözer. */
        position: relative !important;
        left: 0 !important;
        right: 0 !important;
        transform: none !important;
        align-self: stretch !important;
        flex: 0 0 auto !important;
        box-sizing: border-box !important;
        width: 100vw !important;
        min-width: 100vw !important;
        max-width: 100vw !important;
        height: auto !important;
        order: -1 !important;
        background: linear-gradient(180deg, var(--bd-primary) 0%, var(--bd-primary-deep) 100%) !important;
        border-right: none !important;
        border-bottom: 2px solid var(--bd-accent);
        box-shadow: 0 2px 8px rgba(13,41,37,0.18);
    }
    section[data-testid="stSidebar"] * { color: #F2F5F3 !important; }
    section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] p { color: #C9D6D1 !important; }
    section[data-testid="stSidebar"] button {
        background-color: rgba(255,255,255,0.08) !important;
        border: 1px solid rgba(255,255,255,0.22) !important;
        border-radius: 999px !important;
        transition: background-color 0.15s ease;
    }
    section[data-testid="stSidebar"] button:hover { background-color: rgba(255,255,255,0.16) !important; }
    section[data-testid="stSidebar"] input {
        background-color: var(--bd-primary-light) !important;
        color: #FFFFFF !important;
        border: 1px solid rgba(255,255,255,0.22) !important;
        border-radius: var(--bd-radius-sm) !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stExpander"] {
        background-color: rgba(255,255,255,0.06) !important;
        border: 1px solid rgba(255,255,255,0.18) !important;
        border-radius: 999px !important;
        min-width: 170px;
    }
    section[data-testid="stSidebar"] div[data-testid="stExpander"] summary,
    section[data-testid="stSidebar"] div[data-testid="stExpander"] summary * { color: #FFFFFF !important; }
    section[data-testid="stSidebar"] div[data-testid="stExpander"] summary {
        padding: 0.25rem 0.75rem !important;
        min-height: unset !important;
    }
    section[data-testid="stSidebar"] > div {
        width: 100vw !important;
        min-width: 100vw !important;
        max-width: 100vw !important;
        box-sizing: border-box !important;
        padding: 0.4rem 1rem !important;
        display: flex !important;
        justify-content: center !important;
        min-height: 92px !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        align-items: center !important;
        gap: 0.6rem !important;
        width: auto !important;
        max-width: fit-content !important;
        margin: 0 auto !important;
        min-height: 0 !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] > div {
        width: auto !important;
        flex: 0 0 auto !important;
    }
    section[data-testid="stSidebar"] button { padding: 0.28rem 0.85rem !important; font-size: 0.85rem !important; }
    /* DÜZELTME (FAST V14): Streamlit sürümüne göre kapanma/açılma oku
       farklı test-id kullanabiliyor — hepsi kapsanır. */
    div[data-testid="stSidebarCollapsedControl"],
    button[data-testid="stSidebarCollapsedControl"],
    div[data-testid="stSidebarCollapseButton"],
    button[data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="stSidebarCollapseButton"] { display: none !important; }
    /* DÜZELTME: OMEHR logosu şeride sığması için yükseklik artırıldı. */
    section[data-testid="stSidebar"] { max-height: 112px !important; min-height: 92px !important; overflow: visible !important; }
    @media (max-width: 900px) {
        section[data-testid="stSidebar"] { max-height: 150px !important; }
    }

    div[data-testid="stMain"],
    div[data-testid="stAppViewContainer"] > div:not(section[data-testid="stSidebar"]),
    section.main {
        width: 100% !important;
        max-width: 100% !important;
        margin-left: 0 !important;
        left: 0 !important;
    }
    div[data-testid="stMainBlockContainer"], div[data-testid="block-container"] {
        max-width: 100% !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        padding-top: 1cm !important;
        padding-bottom: 6rem !important;
    }
    @media (max-width: 900px) {
        div[data-testid="stMainBlockContainer"], div[data-testid="block-container"] {
            padding-left: 0.85rem !important; padding-right: 0.85rem !important;
        }
    }

    div[data-testid="stAppViewContainer"] p,
    div[data-testid="stAppViewContainer"] span,
    div[data-testid="stAppViewContainer"] label,
    div[data-testid="stAppViewContainer"] li,
    div[data-testid="stAppViewContainer"] div[data-testid="stMarkdownContainer"] {
        color: var(--bd-ink) !important;
    }
    div.stButton > button p, div.stButton > button span,
    div.stDownloadButton > button p, div.stDownloadButton > button span,
    div.stButton > button, div.stDownloadButton > button { color: #FFFFFF !important; }
    div.stButton > button[kind="secondary"] p, div.stButton > button[kind="secondary"] span,
    div.stButton > button[kind="secondary"] { color: var(--bd-primary) !important; }
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] { color: #F2F5F3 !important; }
    section[data-testid="stSidebar"] div[data-testid="stExpander"] summary,
    section[data-testid="stSidebar"] div[data-testid="stExpander"] summary * { color: #FFFFFF !important; }
    div[data-testid="stMetricValue"] { color: var(--bd-primary) !important; }
    div[data-testid="stRadio"] label[data-checked="true"] { color: var(--bd-primary-deep) !important; }
    div[data-testid="stRadio"] label:has(input:checked) { color: var(--bd-primary-deep) !important; }

    html, body, .stApp, div[data-testid="stAppViewContainer"] {
        height: 100vh !important;
        min-height: 100vh !important;
        overflow: hidden !important;
    }
    div[data-testid="stMain"] {
        height: calc(100vh - 100px) !important;
        min-height: 0 !important;
        overflow-y: auto !important;
        overflow-x: hidden !important;
        scroll-behavior: smooth;
    }

    div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {
        min-height: 420px !important;
        max-width: 100% !important;
        overflow: auto !important;
        border: 1px solid var(--bd-border) !important;
        border-radius: var(--bd-radius-md) !important;
        box-shadow: var(--bd-shadow-sm);
    }
    div[data-testid="stDataFrame"] thead tr th {
        background-color: var(--bd-primary) !important;
        color: #FFFFFF !important;
        font-weight: 600 !important;
        font-size: 0.82rem !important;
    }
    div[data-testid="stDataFrame"] tbody tr:nth-child(even) { background-color: var(--bd-surface-sunken) !important; }

    div[data-testid="stForm"] {
        background: var(--bd-surface) !important;
        border: 1px solid var(--bd-border) !important;
        border-radius: var(--bd-radius-lg) !important;
        padding: 1.1rem !important;
        margin-bottom: 1rem !important;
        box-shadow: var(--bd-shadow-sm);
    }
    div[data-testid="stFormSubmitButton"] button { min-height: 44px !important; font-size: 1rem !important; }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
    div[data-testid="stTextArea"] textarea,
    div[data-testid="stTextInput"] input,
    div[data-testid="stDateInput"] input {
        background-color: #FFFFFF !important;
        color: var(--bd-ink) !important;
        opacity: 1 !important;
        border-radius: var(--bd-radius-sm) !important;
        border: 1px solid var(--bd-border-strong) !important;
    }
    div[data-testid="stSelectbox"] div[data-baseweb="select"]:focus-within > div,
    div[data-testid="stTextArea"] textarea:focus,
    div[data-testid="stTextInput"] input:focus,
    div[data-testid="stDateInput"] input:focus {
        border-color: var(--bd-accent) !important;
        box-shadow: 0 0 0 2px var(--bd-accent-tint) !important;
    }

    .omehr-title-top-gap { height: 2.3rem !important; }
    .omehr-title-gap { height: 0.35rem !important; }
    </style>
    """
