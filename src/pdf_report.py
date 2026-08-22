from __future__ import annotations

"""
PDF RAPOR ÜRETİM KATMANI (P2 — engine_core.py modülerleştirme, beşinci adım)
=====================================================================
Yönetici/mağaza/bölge PDF çıktısını (reportlab) üreten fonksiyonlar.
Türkçe-karakter-güvenli font kaydı artık BAĞIMSIZ bir modülde:
src/pdf_fonts.py (bkz. FONT_TURKCE_DOGRULAMA.md) — font eksik/bozuksa veya
gerekli Türkçe glifler (ÇĞİÖŞÜçğıöşü₺) pakette yoksa PDF üretimi RuntimeError
ile durur, Helvetica'ya sessizce düşmez.

state()/kpis()/ai_features_enabled()/executive_analysis_enabled() artık
src/state_engine.py, src/kpi_engine.py, src/feature_flags.py'de tanımlı
BAĞIMSIZ modüllerden gelir — engine_core.py'ye dönüp dolanan bir bağımlılık
YOKTUR, bu modül engine_core.py'den önce dahi güvenle import edilebilir.
Tek gerçek bağımlılık: excel_report._executive_analysis_frames (aşağıda
doğrudan import edilir, kendi de bağımsızdır).
"""

import html
import json
import shutil
import unicodedata
from datetime import datetime

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)
from reportlab.graphics.shapes import Drawing, Line, Rect, String

from services.runtime_paths import runtime_root
from services.settings import input_path
from services.personnel_notes import format_person_note, note_kind
from services.family_balance import balance_store_title_rows
from src.text_utils import canon, col, numeric, product_name, req, txt, unvan_sirali, _title_key
from src.excel_report import _executive_analysis_frames



def _person_norm_key(real_title, department):
    """Gerçek unvanı doğru norm ailesine bağlar.

    Fact_Mevcut.Departman normalde norm ailesidir; ancak saha girişinde
    UZMAN/ELİT personelin departmanı yanlışlıkla yardımcı aileye yazılmış
    olabilir. Bu durumda gerçek unvan her zaman önceliklidir.
    """
    real=_title_key(real_title)
    dep=_title_key(department)
    specialist_map={
        _title_key('UZMAN YÖNETİCİ'):_title_key('YÖNETİCİ'),
        _title_key('ELİT YÖNETİCİ'):_title_key('YÖNETİCİ'),
        _title_key('UZMAN ŞARKÜTERİ'):_title_key('ŞARKÜTERİ'),
        _title_key('ELİT ŞARKÜTERİ'):_title_key('ŞARKÜTERİ'),
        _title_key('UZMAN KASAP'):_title_key('KASAP'),
        _title_key('ELİT KASAP'):_title_key('KASAP'),
        _title_key('UZMAN MANAV'):_title_key('MANAV'),
        _title_key('ELİT MANAV'):_title_key('MANAV'),
    }
    exact_family_map = {
        _title_key('YÖNETİCİ'): _title_key('YÖNETİCİ'),
        _title_key('UZMAN YÖNETİCİ'): _title_key('YÖNETİCİ'),
        _title_key('ELİT YÖNETİCİ'): _title_key('YÖNETİCİ'),
        _title_key('YÖNETİCİ YARDIMCISI'): _title_key('YÖNETİCİ YARDIMCISI'),
        _title_key('MANAV'): _title_key('MANAV'),
        _title_key('UZMAN MANAV'): _title_key('MANAV'),
        _title_key('ELİT MANAV'): _title_key('MANAV'),
        _title_key('MANAV YARDIMCISI'): _title_key('MANAV YARDIMCISI'),
        _title_key('ŞARKÜTERİ'): _title_key('ŞARKÜTERİ'),
        _title_key('UZMAN ŞARKÜTERİ'): _title_key('ŞARKÜTERİ'),
        _title_key('ELİT ŞARKÜTERİ'): _title_key('ŞARKÜTERİ'),
        _title_key('ŞARKÜTERİ YARDIMCISI'): _title_key('ŞARKÜTERİ YARDIMCISI'),
        _title_key('KASAP'): _title_key('KASAP'),
        _title_key('UZMAN KASAP'): _title_key('KASAP'),
        _title_key('ELİT KASAP'): _title_key('KASAP'),
        _title_key('KASAP YARDIMCISI'): _title_key('KASAP YARDIMCISI'),
    }
    # Gerçek unvan bu tanımlı ailelerden biriyse Departman hatalı olsa bile
    # gerçek unvan önceliklidir. Diğer görevlerde Departman norm ailesidir.
    return exact_family_map.get(real, specialist_map.get(real, dep or real))

# font()/_PDF_FONTS_READY artık src/pdf_fonts.py'de TEK noktada tanımlı
# (bağımsız, döngüsel-import riski olmayan modül). Buradan aynı isimle geri
# içe aktarılır — mevcut hiçbir çağrı noktası (font(), font(bold=True))
# değişmedi. BU SATIR, aşağıdaki engine_core importundan ÖNCE olmalı: eğer
# pdf_report.py programın İLK içe aktardığı modül olursa (engine_core değil),
# engine_core.py'nin kendi sonunda "from src.pdf_report import font" satırı
# çalışırken font()'un burada ZATEN tanımlanmış olması gerekir — aksi halde
# döngüsel içe aktarma 'font tanımlı değil' hatasıyla çöker.
from src.pdf_fonts import font
from services.pdf_compat import make_outlook_safe_pdf

# Döngüsel içe aktarma NOTU: aşağıdaki dört isim engine_core.py'de tanımlıdır
# (gerçek hesaplama çekirdeği - state/kpis - ve özellik bayrakları, bunlar
# yalnız engine_core.py'de olabilir). engine_core.py bu modülü onlar
# tanımlandıktan SONRA içe aktardığı için güvenle çalışır. _title_key artık
# döngüsel DEĞİL — src/text_utils.py'den doğrudan alınıyor (yukarıda).
# NOT (artık döngüsel DEĞİL — P2 modülerleştirme sonrası): state()/kpis()/
# ai_features_enabled()/executive_analysis_enabled() artık kendi bağımsız
# modüllerinde tanımlı (state_engine, kpi_engine, feature_flags). Bu importlar
# engine_core.py'ye dönüp dolanmaz, pdf_report.py HER SIRADA (engine_core'dan
# önce dahi) güvenle import edilebilir.
from src.state_engine import state
from src.kpi_engine import kpis
from src.feature_flags import ai_features_enabled, executive_analysis_enabled



def _pdf_text(value):
    """Dinamik metni ReportLab Paragraph XML'i için güvenli hâle getirir."""
    return html.escape(_pdf_plain_text(value), quote=True)




def _pdf_plain_text(value):
    """PDF çizim metnini NFC Unicode olarak temizler, fakat HTML'e dönüştürmez."""
    value=unicodedata.normalize('NFC',txt(value))
    return ''.join(ch for ch in value if ch in '\n\t' or unicodedata.category(ch)[0] != 'C')


def _pdf_cell(value, style):
    return Paragraph(_pdf_text(value), style)


def _pdf_int_text(value):
    try:
        return f"{int(round(float(value))):,}".replace(',', '.')
    except Exception:
        return txt(value)


def pdf_report(kpi,st,scens):
    out=runtime_root()/'output'/'OMEHR_Yonetici_Raporu.pdf';f=font();styles=getSampleStyleSheet();title=ParagraphStyle('t',parent=styles['Title'],fontName=f,fontSize=18,textColor=colors.HexColor('#102F64'));body=ParagraphStyle('b',parent=styles['BodyText'],fontName=f,fontSize=7,leading=9,leftIndent=0,rightIndent=0,firstLineIndent=0)
    doc=SimpleDocTemplate(str(out),pagesize=landscape(A4),leftMargin=9*mm,rightMargin=9*mm,topMargin=9*mm,bottomMargin=9*mm);story=[Paragraph('OMEHR NORM KADRO VE TRANSFER YÖNETİM SİSTEMİ',title),Spacer(1,4*mm)]
    dat=[list(kpi.keys()),list(kpi.values())];t=Table(dat,colWidths=[48*mm]*5);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#102F64')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,-1),f),('ALIGN',(0,0),(-1,-1),'CENTER'),('GRID',(0,0),(-1,-1),.5,colors.grey)]));story+=[t,Spacer(1,5*mm)]
    for reg,g in st.groupby('Bölge Sorumlusu',dropna=False):
        story.append(Paragraph(_pdf_text('Bölge Sorumlusu: '+txt(reg)),ParagraphStyle('h',parent=body,fontName=f,fontSize=11,textColor=colors.HexColor('#102F64'))));rows=[['Mağaza','Mevcut','Norm','Eksik','Fazla','Net']]+[[txt(r['Mağaza']),int(r['Aktif Mevcut']),int(r['Norm Kadro']),int(r['Norm Eksiği']),int(r['Norm Fazlası']),int(r['Net Fark'])] for _,r in g.sort_values('Mağaza').iterrows()];tb=Table(rows,colWidths=[70*mm,23*mm,23*mm,23*mm,23*mm,23*mm],repeatRows=1);tb.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#4472C4')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,-1),f),('FONTNAME',(0,0),(-1,0),font(True)),('FONTSIZE',(0,0),(-1,-1),7),('GRID',(0,0),(-1,-1),.3,colors.grey)]));story += [tb,Spacer(1,3*mm)]
    d=scens.get('Dengeli',pd.DataFrame())
    if not d.empty:
        story += [PageBreak(),Paragraph('Kural Tabanlı Transfer Önerileri - Dengeli',title),Spacer(1,3*mm)]
        cs=['İsim Soyisim','Kaynak Mağaza','Mevcut Unvan','Hedef Mağaza','İhtiyaç Unvanı','Şubeler Arası Mesafe (km)','Ev-Hedef Şube (km)','Yol Kazancı (km)','Transfer Uygunluk Puanı'];pdf_header=ParagraphStyle('pdf_header',parent=body,fontName=font(True),textColor=colors.white,alignment=1,leftIndent=0,rightIndent=0,firstLineIndent=0)
        rows=[[Paragraph(_pdf_text(c),pdf_header) for c in cs]]+[[Paragraph(_pdf_text(r[c]),body) for c in cs] for _,r in d.iterrows()];tb=Table(rows,colWidths=[34*mm,28*mm,28*mm,28*mm,28*mm,26*mm,26*mm,24*mm,24*mm],repeatRows=1);tb.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#102F64')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,-1),f),('GRID',(0,0),(-1,-1),.3,colors.grey),('VALIGN',(0,0),(-1,-1),'TOP')]));story.append(tb)
    doc.build(story)
    make_outlook_safe_pdf(out)
    return out


# ============================================================================
# OUTPUT LAYER
# Preserves the existing engines and replaces only output orchestration.
# ============================================================================



def _pdf_styles():
    f=font(); fb=font(True); styles=getSampleStyleSheet()
    return f, ParagraphStyle('EntTitle',parent=styles['Title'],fontName=fb,fontSize=15,leading=18,textColor=colors.HexColor('#102F64'),alignment=1), ParagraphStyle('EntBody',parent=styles['BodyText'],fontName=f,fontSize=6.6,leading=8,leftIndent=0,rightIndent=0,firstLineIndent=0)



def _footer(canvas, doc):
    # DİKKAT: PDF_SOURCE_HASH/PDF_GENERATED_AT engine_core.run_all() içinde
    # `global` ile HER çalıştırmada güncellenir. Burada `import src.engine_core
    # as _core` ile modülün kendisi tutulup çağrı anında _core.X okunuyor;
    # `from src.engine_core import PDF_SOURCE_HASH` kullanılsaydı, import
    # anındaki (boş) değer donardı ve raporda hep 'bilinmiyor' görünürdü.
    import src.engine_core as _core
    canvas.saveState(); f=font(); canvas.setFont(f,6.2); canvas.setFillColor(colors.HexColor('#666666'))
    source=(_core.PDF_SOURCE_HASH[:12] if _core.PDF_SOURCE_HASH else 'bilinmiyor')
    generated=(_core.PDF_GENERATED_AT or datetime.now().strftime('%d.%m.%Y %H:%M:%S'))
    canvas.drawString(10*mm,6*mm,f'Kaynak: {source} | Üretim: {generated}')
    canvas.drawCentredString(landscape(A4)[0]/2,6*mm,product_name()+' - Confidential')
    canvas.drawRightString(landscape(A4)[0]-10*mm,6*mm,f'Sayfa {doc.page}')
    canvas.restoreState()




def enhanced_pdf_reports(kpi, norm, staff, sheets, scens, ai, validation_summary):
    # PERFORMANS NOTU (P2 — cProfile ile ölçüldü, 2026-07-31): run_all()'ın
    # toplam ~144 saniyesinin ~35 saniyesi (%24), bu fonksiyonun çağırdığı
    # zincirdeki BİRDEN FAZLA yardımcı fonksiyonun (_v16_add_workbook_layers,
    # _add_executive_analysis_sheets, _add_visible_ai_dashboard vb.) HER
    # BİRİNİN AYNI Excel dosyasını KENDİ BAŞINA açıp (openpyxl.load_workbook)
    # kaydetmesinden (wb.save) kaynaklanıyor — tek bir workbook nesnesi
    # PAYLAŞILIP TEK SEFERDE kaydedilebilirdi.
    # BİLEREK DÜZELTİLMEDİ: Bu birleştirme, çalışan rapor üretim zincirini
    # yeniden yazmayı gerektirir (sıra bağımlılığı, sayfa silme/ekleme
    # sırası riski) — kullanıcıyla değerlendirilip, riskin ödemeyeceğine
    # KARAR VERİLDİ. Gelecekte tekrar ele alınırsa: her katman fonksiyonunu
    # `wb` parametresi alacak, kendi load_workbook/save'ini YAPMAYACAK
    # şekilde yeniden yazıp, TEK bir load→[tüm katmanlar]→save akışına
    # geçirin. Yeniden ölçmek için: cProfile.Profile() ile run_all()'ı
    # sarıp pstats.Stats(...).sort_stats('cumulative').print_stats(20).
    outdir=runtime_root()/'output'; outdir.mkdir(exist_ok=True)
    main_tmp=outdir/'OMEHR_Yonetici_Raporu.pdf.tmp'
    main=outdir/'OMEHR_Yonetici_Raporu.pdf'
    _build_store_pdf(main_tmp,kpi,norm,staff,ai,validation_summary,sheets=sheets)
    main_tmp.replace(main)
    region_dir=outdir/'Bolge_Raporlari'; region_dir.mkdir(exist_ok=True)
    temp_dir=outdir/'Bolge_Raporlari_Yeni'; shutil.rmtree(temp_dir,ignore_errors=True); temp_dir.mkdir(exist_ok=True)
    nb=req(norm,'Bölge Sorumlusu','Bolge Sorumlusu','Bölge')
    sb=req(staff,'Bölge Sorumlusu','Bolge Sorumlusu','Bölge')
    # Bölge listesi yalnızca Fact_Norm'dan alınırsa, norm kaydı bulunmayan ancak
    # Fact_Mevcut'ta personeli olan bölgelerin PDF'i üretilmez. İki kaynağın
    # birleşimi kullanılarak Excel ve PDF bölge raporları aynı kapsamda tutulur.
    regions=sorted({txt(v) for v in norm[nb].dropna() if txt(v).strip()} | {txt(v) for v in staff[sb].dropna() if txt(v).strip()})
    for region in regions:
        safe=''.join(c if c.isalnum() else '_' for c in region).strip('_')
        _build_store_pdf(temp_dir/f'OMEHR_Bolge_{safe}.pdf',kpi,norm,staff,ai,validation_summary,[region],include_summary=True,sheets=sheets)
    for old_pdf in region_dir.glob('*.pdf'): old_pdf.unlink()
    for fresh in temp_dir.glob('*.pdf'): fresh.replace(region_dir/fresh.name)
    shutil.rmtree(temp_dir,ignore_errors=True)
    return main





def _chart_label(value, limit=22):
    value=txt(value)
    return value if len(value)<=limit else value[:limit-1]+'…'




def _tr_chart_value(value, unit=None):
    rendered=f"{int(round(float(value))):,}".replace(',','.')
    return f"{rendered} TL" if unit=='TL' else rendered




def _pdf_empty_chart(title, message='Gösterilecek pozitif değer bulunmuyor.'):
    drawing=Drawing(126*mm,61*mm)
    drawing.add(Rect(0,0,126*mm,61*mm,fillColor=colors.HexColor('#F7F9FC'),strokeColor=colors.HexColor('#D6DEE8'),strokeWidth=.7))
    drawing.add(String(63*mm,55*mm,_pdf_plain_text(title),fontName=font(True),fontSize=9,textAnchor='middle',fillColor=colors.HexColor('#102F64')))
    drawing.add(String(63*mm,29*mm,_pdf_plain_text(message),fontName=font(),fontSize=7.5,textAnchor='middle',fillColor=colors.HexColor('#6B7280')))
    return drawing




def _pdf_bar_chart(title, labels, values, bar_color='#4472C4', signed=False, unit=None):
    pairs=[(txt(label),int(round(float(value)))) for label,value in zip(labels,values)]
    pairs=pairs[:10]
    if not pairs or not any(value!=0 for _,value in pairs):
        return _pdf_empty_chart(title)
    drawing=Drawing(126*mm,61*mm)
    drawing.add(Rect(0,0,126*mm,61*mm,fillColor=colors.white,strokeColor=colors.HexColor('#D6DEE8'),strokeWidth=.7))
    drawing.add(String(63*mm,56*mm,_pdf_plain_text(title),fontName=font(True),fontSize=8.8,textAnchor='middle',fillColor=colors.HexColor('#102F64')))
    top=51*mm; bottom=5*mm; label_width=39*mm; value_width=13*mm
    chart_left=label_width+2*mm; chart_right=126*mm-value_width
    chart_width=chart_right-chart_left
    row_height=(top-bottom)/max(len(pairs),1)
    maximum=max(abs(value) for _,value in pairs) or 1
    zero_x=chart_left+(chart_width/2 if signed else 0)
    if signed:
        drawing.add(Line(zero_x,bottom,zero_x,top,strokeColor=colors.HexColor('#9CA3AF'),strokeWidth=.5))
    for index,(label,value) in enumerate(pairs):
        center=top-(index+.5)*row_height
        drawing.add(String(label_width,center-2,_pdf_plain_text(_chart_label(label)),fontName=font(),fontSize=6.1,textAnchor='end',fillColor=colors.HexColor('#374151')))
        usable=chart_width/2 if signed else chart_width
        length=usable*(abs(value)/maximum)
        x=zero_x-length if signed and value<0 else zero_x
        color=colors.HexColor('#70AD47') if signed and value<0 else colors.HexColor(bar_color)
        drawing.add(Rect(x,center-row_height*.25,max(length,.7),row_height*.5,fillColor=color,strokeColor=None))
        value_x=(x-1.5 if signed and value<0 else x+length+1.5)
        anchor='end' if signed and value<0 else 'start'
        drawing.add(String(value_x,center-2,_pdf_plain_text(_tr_chart_value(value,unit)),fontName=font(True),fontSize=8.2,textAnchor=anchor,fillColor=colors.HexColor('#111827')))
    return drawing




def _pdf_grouped_chart(title, labels, first, second, first_name='Mevcut', second_name='Yönetim Normu', first_unit=None, second_unit=None):
    rows=[(txt(label),int(round(float(a))),int(round(float(b)))) for label,a,b in zip(labels,first,second)][:10]
    if not rows:
        return _pdf_empty_chart(title)
    drawing=Drawing(126*mm,61*mm)
    drawing.add(Rect(0,0,126*mm,61*mm,fillColor=colors.white,strokeColor=colors.HexColor('#D6DEE8'),strokeWidth=.7))
    drawing.add(String(63*mm,56*mm,_pdf_plain_text(title),fontName=font(True),fontSize=8.8,textAnchor='middle',fillColor=colors.HexColor('#102F64')))
    drawing.add(Rect(76*mm,52*mm,3*mm,2*mm,fillColor=colors.HexColor('#102F64'),strokeColor=None))
    drawing.add(String(80*mm,52*mm,_pdf_plain_text(first_name),fontName=font(),fontSize=5.8,fillColor=colors.HexColor('#374151')))
    drawing.add(Rect(100*mm,52*mm,3*mm,2*mm,fillColor=colors.HexColor('#118B94'),strokeColor=None))
    drawing.add(String(104*mm,52*mm,_pdf_plain_text(second_name),fontName=font(),fontSize=5.8,fillColor=colors.HexColor('#374151')))
    top=49*mm;bottom=5*mm;label_width=39*mm;chart_left=label_width+2*mm;chart_right=115*mm
    # En uzun sütunda bile sayı sütunun hemen dışında ve kart sınırları içinde kalsın.
    monetary=first_unit=='TL' or second_unit=='TL'
    bar_right=chart_right-(27*mm if monetary else 11*mm)
    row_height=(top-bottom)/max(len(rows),1); maximum=max([1]+[max(a,b) for _,a,b in rows])
    for index,(label,a,b) in enumerate(rows):
        center=top-(index+.5)*row_height
        drawing.add(String(label_width,center-2,_pdf_plain_text(_chart_label(label)),fontName=font(),fontSize=6,textAnchor='end',fillColor=colors.HexColor('#374151')))
        first_y=center+row_height*.08
        second_y=center-row_height*.36
        for y,value,color in [(first_y,a,'#102F64'),(second_y,b,'#118B94')]:
            length=(bar_right-chart_left)*(value/maximum)
            drawing.add(Rect(chart_left,y,max(length,.7),row_height*.24,fillColor=colors.HexColor(color),strokeColor=None))
        drawing.add(String(chart_left+(bar_right-chart_left)*(a/maximum)+1.5,first_y+row_height*.03,_pdf_plain_text(_tr_chart_value(a,first_unit)),fontName=font(True),fontSize=6.8,fillColor=colors.HexColor('#102F64')))
        drawing.add(String(chart_left+(bar_right-chart_left)*(b/maximum)+1.5,second_y+row_height*.03,_pdf_plain_text(_tr_chart_value(b,second_unit)),fontName=font(True),fontSize=6.8,fillColor=colors.HexColor('#9A3412')))
    return drawing




def _pdf_visual_story(norm, staff, ai, stores_filter=None):
    st,tt=state(norm,staff,{})
    if stores_filter is not None:
        wanted={canon(value) for value in stores_filter}
        st=st[st['Bölge Sorumlusu'].map(canon).isin(wanted)].copy()
        tt=tt[tt['Bölge Sorumlusu'].map(canon).isin(wanted)].copy()
    if st.empty:
        return []
    scope='ŞİRKET GENELİ' if stores_filter is None else _pdf_text(' / '.join(map(txt,stores_filter)).upper())
    charts=[]
    top_deficit=st.sort_values('Norm Eksiği',ascending=False)
    top_deficit=top_deficit[top_deficit['Norm Eksiği']>0].head(10)
    charts.append(_pdf_bar_chart('En Yüksek Norm Açıkları',top_deficit['Mağaza'],top_deficit['Norm Eksiği'],'#4472C4'))
    top_surplus=st.sort_values('Norm Fazlası',ascending=False)
    top_surplus=top_surplus[top_surplus['Norm Fazlası']>0].head(10)
    charts.append(_pdf_bar_chart('En Yüksek Norm Fazlalıkları',top_surplus['Mağaza'],top_surplus['Norm Fazlası'],'#70AD47'))
    comparison=st.sort_values('Norm Kadro',ascending=False).head(10)
    charts.append(_pdf_grouped_chart('Mağaza Bazında Mevcut ve Yönetim Normu',comparison['Mağaza'],comparison['Aktif Mevcut'],comparison['Norm Kadro']))
    title_summary=tt.groupby('Unvan',as_index=False)[['Norm Eksiği','Norm Fazlası']].sum()
    title_summary['Toplam Fark']=title_summary['Norm Eksiği']+title_summary['Norm Fazlası']
    title_summary=title_summary.sort_values('Toplam Fark',ascending=False).head(10)
    charts.append(_pdf_grouped_chart('Unvan Bazlı Eksik ve Fazla',title_summary['Unvan'],title_summary['Norm Eksiği'],title_summary['Norm Fazlası'],'Eksik','Fazla'))
    if ai_features_enabled() and ai is not None and not ai.empty and {'Mağaza','AI-Mevcut Fark'}.issubset(ai.columns):
        ai_scope=ai.copy()
        if stores_filter is not None and 'Bölge Sorumlusu' in ai_scope.columns:
            wanted={canon(value) for value in stores_filter}
            ai_scope=ai_scope[ai_scope['Bölge Sorumlusu'].map(canon).isin(wanted)]
        ai_chart=ai_scope.groupby('Mağaza',as_index=False)['AI-Mevcut Fark'].sum()
        ai_chart['Mutlak Fark']=numeric(ai_chart['AI-Mevcut Fark']).abs()
        ai_chart=ai_chart[ai_chart['Mutlak Fark']>0].sort_values('Mutlak Fark',ascending=False).head(10)
        charts.append(_pdf_bar_chart('AI Normuna Göre Net Kadro Farkı',ai_chart['Mağaza'],ai_chart['AI-Mevcut Fark'],'#4472C4',signed=True))
    if stores_filter is None and executive_analysis_enabled():
        _,financial,operational=_executive_analysis_frames(input_path(runtime_root()))
        store_financial=financial[financial.get('Birim Tipi',pd.Series('',index=financial.index)).eq('Mağaza')].copy()
        other_financial=financial[financial.get('Birim Tipi',pd.Series('',index=financial.index)).isin(['Depo','Merkez'])].copy()
        if not store_financial.empty and {'Mağaza','Aylık Ciro','Toplam İş Gücü Maliyeti'}.issubset(store_financial.columns):
            ftop=store_financial.sort_values('Aylık Ciro',ascending=False).head(10)
            charts.append(_pdf_grouped_chart('Mağazalar - Ciro ve İş Gücü Maliyeti',ftop['Mağaza'],ftop['Aylık Ciro'],ftop['Toplam İş Gücü Maliyeti'],'Aylık Ciro','İş Gücü Maliyeti','TL','TL'))
        if not operational.empty and {'Mağaza','İş Yükü Endeksi'}.issubset(operational.columns):
            otop=operational.sort_values('İş Yükü Endeksi',ascending=False).head(10)
            charts.append(_pdf_bar_chart('En Yüksek İş Yükü Endeksi',otop['Mağaza'],otop['İş Yükü Endeksi'],'#118B94'))
        if not store_financial.empty and {'Mağaza','İş Gücü Maliyeti / Ciro %'}.issubset(store_financial.columns):
            valid=store_financial.dropna(subset=['İş Gücü Maliyeti / Ciro %'])
            rtop=valid.sort_values('İş Gücü Maliyeti / Ciro %',ascending=False).head(10)
            charts.append(_pdf_bar_chart('Mağazalar - İş Gücü Maliyeti / Ciro (%)',rtop['Mağaza'],rtop['İş Gücü Maliyeti / Ciro %'],'#BF9000'))
        if not other_financial.empty and {'Mağaza','Aylık Ciro','Toplam İş Gücü Maliyeti'}.issubset(other_financial.columns):
            ftop=other_financial.sort_values('Toplam İş Gücü Maliyeti',ascending=False).head(10)
            charts.append(_pdf_grouped_chart('Merkez ve Depolar - Ayrı Maliyet Grubu',ftop['Mağaza'],ftop['Aylık Ciro'],ftop['Toplam İş Gücü Maliyeti'],'Aylık Ciro','İş Gücü Maliyeti','TL','TL'))
    head=ParagraphStyle('visual_head',parent=_pdf_styles()[2],fontName=font(True),fontSize=11,textColor=colors.HexColor('#102F64'),alignment=1,spaceAfter=5*mm)
    note_style=ParagraphStyle('visual_note',parent=_pdf_styles()[2],fontName=font(),fontSize=6.7,leading=8.2,leftIndent=5*mm,rightIndent=5*mm,textColor=colors.black,spaceAfter=2*mm)
    notes={
        0:'Akıllı yorum: Üst grafikler, mağaza bazında en kritik norm açıklarını ve transfer havuzu oluşturabilecek norm fazlalarını birlikte gösterir.',
        2:'Akıllı yorum: Alt grafiklerde mevcut-yönetim normu farkı ile açığın hangi unvanlarda yoğunlaştığı karşılaştırılır; öncelik aynı mağaza içinde unvan uyumudur.',
        4:'Akıllı yorum: AI kadro farkı iş yükü kapasitesine göre karar desteğidir. Ciro ve iş gücü maliyeti birlikte okunmalı; yüksek ciro tek başına yüksek verimlilik anlamına gelmez.',
        6:'Akıllı yorum: İş yükü endeksi operasyon baskısını, maliyet/ciro oranı ise finansal sürdürülebilirliği gösterir. Mağaza değerleri yalnız mağaza grubuyla karşılaştırılmıştır.',
        8:'Akıllı yorum: Merkez ve depo maliyetleri mağaza satış modeliyle doğrudan kıyaslanmaz; kendi operasyon grupları içinde izlenir. Cirosuz satırlarda oran üretilmez.',
    }
    story=[Paragraph(_pdf_text(f'{scope} - YÖNETİM GÖRSEL ANALİZ MERKEZİ'),head)]
    for index in range(0,len(charts),2):
        pair=charts[index:index+2]
        if len(pair)==1: pair.append(_pdf_empty_chart(''))
        story.append(Table([pair],colWidths=[130*mm,130*mm],hAlign='CENTER',style=[('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),1.5*mm),('RIGHTPADDING',(0,0),(-1,-1),1.5*mm)]))
        if index in notes:
            story.append(Table(
                [[Paragraph(_pdf_text(notes[index]),note_style)]],
                colWidths=[260*mm],
                hAlign='CENTER',
                style=[
                    ('LEFTPADDING',(0,0),(-1,-1),2*mm),
                    ('RIGHTPADDING',(0,0),(-1,-1),2*mm),
                    ('TOPPADDING',(0,0),(-1,-1),0),
                    ('BOTTOMPADDING',(0,0),(-1,-1),0),
                ],
            ))
        story.append(Spacer(1,1.5*mm))
        if index==2 and len(charts)>4:
            story.append(PageBreak())
            story.append(Paragraph(_pdf_text(f'{scope} - İLERİ ANALİZ GRAFİKLERİ'),head))
    return story




def _build_store_pdf(path, kpi, norm, staff, ai, validation_summary=None, stores_filter=None, include_summary=True, sheets=None):
    f,title_style,body=_pdf_styles()
    _calc_sheets=sheets if isinstance(sheets,dict) else {}
    _state_all,tt=state(norm,staff,_calc_sheets)
    report_kpi=dict(kpi)
    if stores_filter is not None:
        scoped_state,_=state(norm,staff,_calc_sheets)
        wanted={canon(value) for value in stores_filter}
        scoped_state=scoped_state[scoped_state['Bölge Sorumlusu'].map(canon).isin(wanted)]
        report_kpi=kpis(scoped_state)
    def pdf_int(value):
        parsed=pd.to_numeric(pd.Series([value]),errors='coerce').fillna(0).iloc[0]
        return int(round(float(parsed)))
    doc=SimpleDocTemplate(str(path),pagesize=landscape(A4),leftMargin=8*mm,rightMargin=8*mm,topMargin=8*mm,bottomMargin=12*mm,
                          title=product_name())
    # Grafikler yönetici ve bölge raporlarının ilk sayfasında yer alır.
    story=_pdf_visual_story(norm,staff,ai,stores_filter)
    if story:
        story.append(PageBreak())
    if include_summary:
        story += [Paragraph(_pdf_text(product_name()),title_style),
                  Paragraph('Toplam Aktif Mevcut, Yönetim Normu ve Norm Kapsamı',ParagraphStyle('v13sub',parent=body,fontName=f,fontSize=9,alignment=1,textColor=colors.HexColor('#4472C4'))),Spacer(1,4*mm)]
        hdr_style=ParagraphStyle('pdf_sum_hdr', parent=body, fontName=font(True), fontSize=10, textColor=colors.white, alignment=1)
        val_style=ParagraphStyle('pdf_sum_val', parent=body, fontName=f, fontSize=10, textColor=colors.black, alignment=1)
        dat=[[
            _pdf_cell('AKTİF MEVCUT', hdr_style),
            _pdf_cell('YÖNETİM NORMU', hdr_style),
            _pdf_cell('NORM EKSİĞİ', hdr_style),
            _pdf_cell('NORM FAZLASI', hdr_style),
            _pdf_cell('NET İHTİYAÇ', hdr_style),
        ],[
            _pdf_cell(_pdf_int_text(report_kpi['Aktif Mevcut']), val_style),
            _pdf_cell(_pdf_int_text(report_kpi['Toplam Norm']), val_style),
            _pdf_cell(_pdf_int_text(report_kpi['Norm Eksiği']), val_style),
            _pdf_cell(_pdf_int_text(report_kpi['Norm Fazlası']), val_style),
            _pdf_cell(_pdf_int_text(report_kpi['Net İhtiyaç']), val_style),
        ]]
        tb=Table(dat,colWidths=[51*mm]*5)
        tb.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#102F64')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('BACKGROUND',(0,1),(-1,1),colors.HexColor('#EDF3F8')),('FONTNAME',(0,0),(-1,-1),f),('FONTNAME',(0,0),(-1,0),font(True)),('FONTSIZE',(0,0),(-1,-1),10),('ALIGN',(0,0),(-1,-1),'CENTER'),('GRID',(0,0),(-1,-1),.45,colors.HexColor('#A6A6A6')),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
        note=Paragraph('Aktif mevcut tüm aktif çalışanları kapsar. Yönetim normu input/Fact_Norm kaynağından dinamik okunur. Norm eksiği ve fazlası Python motoruyla, güncel Fact_Norm/Fact_Mevcut ile inputtaki resmî mağaza-unvan kontrol dağılımı birlikte kullanılarak hesaplanır; LibreOffice\'e bağlı değildir.',ParagraphStyle('dyn',parent=body,fontName=f,fontSize=7.5,alignment=1,textColor=colors.HexColor('#333333')))
        story += [tb,Spacer(1,2*mm),note]
        if stores_filter is None and ai_features_enabled() and ai is not None and not ai.empty:
            ai_total=int(pd.to_numeric(ai.get('AI Önerilen Norm',0),errors='coerce').fillna(0).sum())
            ai_gap=pd.to_numeric(ai.get('AI-Mevcut Fark',0),errors='coerce').fillna(0)
            ai_shortage=int(ai_gap.clip(lower=0).sum())
            ai_surplus=int((-ai_gap.clip(upper=0)).sum())
            confidence_values=pd.to_numeric(ai.get('Güven Skoru',pd.Series(dtype=float)),errors='coerce').dropna()
            ai_conf=float(confidence_values.mean()) if not confidence_values.empty else None
            model_r2=None
            analytics_path=runtime_root()/'output'/'V19_Istatistik_ML_Operasyon_Analizi.xlsx'
            if analytics_path.is_file():
                try:
                    model_scores=pd.read_excel(analytics_path,sheet_name='Model_Karsilastirma')
                    if not model_scores.empty and 'CV R²' in model_scores:
                        model_r2=float(pd.to_numeric(model_scores['CV R²'],errors='coerce').max())
                except Exception as _exc:
                    from services.safe_exec import log_swallowed
                    log_swallowed("model_r2 okunamadı (Model_Karsilastirma sayfası)", _exc, level="INFO")
                    model_r2=None
            ai_hdr=ParagraphStyle('ai_hdr', parent=body, fontName=font(True), fontSize=8, textColor=colors.white, alignment=1)
            ai_val=ParagraphStyle('ai_val', parent=body, fontName=f, fontSize=8, textColor=colors.black, alignment=1)
            ai_rows=[[
                _pdf_cell('AI ÖNERİLEN TOPLAM NORM', ai_hdr), _pdf_cell('AI KAPASİTE AÇIĞI', ai_hdr), _pdf_cell('AI TRANSFER ADAYI', ai_hdr), _pdf_cell('ORT. VERİ GÜVENİ', ai_hdr), _pdf_cell('MODEL CV R²', ai_hdr)
            ],[
                _pdf_cell(_pdf_int_text(ai_total), ai_val), _pdf_cell(_pdf_int_text(ai_shortage), ai_val), _pdf_cell(_pdf_int_text(ai_surplus), ai_val), _pdf_cell(('Hesaplanmadı' if ai_conf is None else f'%{ai_conf:.1f}'), ai_val), _pdf_cell(('Hesaplanmadı' if model_r2 is None else f'%{100*model_r2:.1f}'), ai_val)
            ]]
            ai_table=Table(ai_rows,colWidths=[50.8*mm]*5)
            ai_table.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#4472C4')),
                ('TEXTCOLOR',(0,0),(-1,0),colors.white),
                ('BACKGROUND',(0,1),(-1,1),colors.HexColor('#EAF2F8')),
                ('FONTNAME',(0,0),(-1,-1),f),('FONTNAME',(0,0),(-1,0),font(True)),
                ('FONTSIZE',(0,0),(-1,-1),8),('ALIGN',(0,0),(-1,-1),'CENTER'),
                ('GRID',(0,0),(-1,-1),.6,colors.HexColor('#595959')),
                ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
            ]))
            top_ai=ai.assign(_Gap=ai_gap).sort_values(['_Gap','Güven Skoru'],ascending=False)
            top_ai=top_ai[top_ai['_Gap']>0].head(5)
            row_hdr=ParagraphStyle('row_hdr', parent=body, fontName=font(True), fontSize=6.2, textColor=colors.white, alignment=1)
            row_val=ParagraphStyle('row_val', parent=body, fontName=f, fontSize=6.2, textColor=colors.black, alignment=0)
            action_rows=[[_pdf_cell('MAĞAZA', row_hdr),_pdf_cell('UNVAN', row_hdr),_pdf_cell('MEVCUT', row_hdr),_pdf_cell('AI NORM', row_hdr),_pdf_cell('AÇIK', row_hdr),_pdf_cell('AKSİYON', row_hdr)]]
            for _,row in top_ai.iterrows():
                action_rows.append([
                    _pdf_cell(txt(row.get('Mağaza')), row_val), _pdf_cell(txt(row.get('Unvan')), row_val), _pdf_cell(_pdf_int_text(row.get('Aktif Mevcut',0)), row_val),
                    _pdf_cell(_pdf_int_text(row.get('AI Önerilen Norm',0)), row_val), _pdf_cell(_pdf_int_text(row.get('_Gap',0)), row_val), _pdf_cell(txt(row.get('Önerilen Aksiyon')), row_val)
                ])
            action_table=Table(action_rows,colWidths=[39*mm,39*mm,18*mm,20*mm,15*mm,123*mm],repeatRows=1)
            action_table.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#102F64')),
                ('TEXTCOLOR',(0,0),(-1,0),colors.white),
                ('FONTNAME',(0,0),(-1,0),font(True)),('FONTNAME',(0,1),(-1,-1),f),
                ('FONTSIZE',(0,0),(-1,-1),6.2),('GRID',(0,0),(-1,-1),.5,colors.HexColor('#595959')),
                ('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,1),(-1,-1),colors.HexColor('#F4F7FB')),
            ]))
            story += [
                Spacer(1,4*mm),
                Paragraph('AI NORM VE ÖNCELİKLİ AKSİYON ÖZETİ',ParagraphStyle('ai_summary',parent=body,fontName=font(True),fontSize=10,textColor=colors.HexColor('#102F64'),alignment=1)),
                Spacer(1,2.5*mm),ai_table,Spacer(1,2*mm),action_table,
                Paragraph('AI normu; iş yükü dakikası, net üretken kapasite, pik katsayısı, minimum kadro ve operasyon modeliyle üretilen karar desteğidir. Resmi yönetim normunu otomatik değiştirmez.',ParagraphStyle('ai_note',parent=body,fontName=f,fontSize=6.5,textColor=colors.HexColor('#666666'),alignment=1)),
            ]
        if stores_filter is None and executive_analysis_enabled():
            summary,_,_=_executive_analysis_frames(input_path(runtime_root()))
            if not summary.empty:
                story += [Spacer(1,5*mm),Paragraph('YÖNETİCİ FİNANSAL VE OPERASYONEL ANALİZ ÖZETİ',
                    ParagraphStyle('exec_analysis',parent=body,fontName=font(True),fontSize=10,textColor=colors.HexColor('#102F64'),alignment=1)),Spacer(1,2.5*mm)]
                analysis_rows=[['GÖSTERGE','DEĞER','BİRİM','AÇIKLAMA']]
                for _,row in summary.iterrows():
                    value=row.get('Değer',0)
                    value_text=f"{float(value):,.2f}".replace(',','X').replace('.',',').replace('X','.') if row.get('Birim')=='%' else f"{int(round(float(value))):,}".replace(',','.')
                    analysis_rows.append([txt(row.get('Gösterge')),value_text,txt(row.get('Birim')),txt(row.get('Açıklama'))])
                at=Table(analysis_rows,colWidths=[58*mm,38*mm,22*mm,120*mm],repeatRows=1,hAlign='CENTER')
                at.setStyle(TableStyle([
                    ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#102F64')),
                    ('TEXTCOLOR',(0,0),(-1,0),colors.white),
                    ('FONTNAME',(0,0),(-1,0),font(True)),
                    ('FONTNAME',(0,1),(-1,-1),f),
                    ('FONTSIZE',(0,0),(-1,-1),7),
                    ('ALIGN',(1,1),(2,-1),'CENTER'),
                    ('GRID',(0,0),(-1,-1),.55,colors.HexColor('#595959')),
                    ('BACKGROUND',(0,1),(-1,-1),colors.HexColor('#F4F7FB')),
                    ('TOPPADDING',(0,0),(-1,-1),5),
                    ('BOTTOMPADDING',(0,0),(-1,-1),5),
                ]))
                story.append(at)
        story.append(PageBreak())
    # Kompakt mağaza raporları: kaynaklar kesin olarak ayrılır.
    # Mevcut = yalnızca Fact_Mevcut aktif personel sayımı.
    # Yönetim normu = yalnızca Fact_Norm toplamı.
    nmid=req(norm,'MağazaID','MagazaID'); nm=req(norm,'Mağaza','Magaza'); nb=req(norm,'Bölge Sorumlusu','Bolge Sorumlusu','Bölge'); nn=req(norm,'Norm Kadro','Norm')
    smid=req(staff,'MağazaID','MagazaID'); sm=req(staff,'Mağaza','Magaza'); sb=req(staff,'Bölge Sorumlusu','Bolge Sorumlusu','Bölge')
    nu=req(norm,'Unvan'); su=req(staff,'Unvan'); pname=req(staff,'İsim Soyisim','Isim Soyisim','Ad Soyad')
    staff_note_col=col(staff,'Açıklama','Aciklama','AÇIKLAMA','ACIKLAMA','Personel Açıklaması','Personel Aciklamasi')

    norm_stores=norm[[nmid,nm,nb]].copy(); norm_stores.columns=['MağazaID','Mağaza','Bölge Sorumlusu']
    staff_stores=staff[[smid,sm,sb]].copy(); staff_stores.columns=['MağazaID','Mağaza','Bölge Sorumlusu']
    stores=pd.concat([norm_stores,staff_stores],ignore_index=True).drop_duplicates('MağazaID',keep='first')
    if stores_filter is not None:
        stores=stores[stores['Bölge Sorumlusu'].map(canon).isin({canon(x) for x in stores_filter})]
    stores=stores.sort_values(['Bölge Sorumlusu','Mağaza']).reset_index(drop=True)

    compact_body=ParagraphStyle('compact_body',parent=body,fontName=f,fontSize=4.7,leading=5.4,alignment=0)
    compact_center=ParagraphStyle('compact_center',parent=compact_body,alignment=1)
    compact_head=ParagraphStyle('compact_head',parent=body,fontName=font(True),fontSize=5.0,leading=5.5,textColor=colors.white,alignment=1)
    compact_title=ParagraphStyle('compact_title',parent=body,fontName=font(True),fontSize=7.0,leading=7.6,textColor=colors.white,alignment=1)
    compact_sub=ParagraphStyle('compact_sub',parent=body,fontName=f,fontSize=4.8,leading=5.3,textColor=colors.HexColor('#374151'),alignment=1)

    def store_card(srow):
        sid=txt(srow['MağazaID']); sname=txt(srow['Mağaza']); region=txt(srow['Bölge Sorumlusu'])
        # MağazaID tekrarları bulunduğu için rapor filtresi mağaza adıyla yapılır.
        ns=norm[norm[nm].map(canon)==canon(sname)].copy()
        ps=staff[staff[sm].map(canon)==canon(sname)].copy()
        dep_col=req(staff,'Departman')

        # Mevcut sayımı norm ailesi üzerinden yapılır. UZMAN/ELİT gerçek unvanı
        # ana aileyi kesin olarak belirler; yanlışlıkla yardımcı departmana yazılmış
        # kayıtlar bu aşamada otomatik düzeltilir (ör. UZMAN ŞARKÜTERİ -> ŞARKÜTERİ).
        ps['_NormKey']=[_person_norm_key(u,d) for u,d in zip(ps[su],ps[dep_col])]
        msum=ps.groupby('_NormKey',dropna=False)[pname].count().reset_index(name='Mevcut').rename(columns={'_NormKey':'_Key'})

        nsum=ns.assign(_Key=ns[nu].map(_title_key)).groupby('_Key',dropna=False)[nn].sum().reset_index(name='Yönetim Normu')
        norm_role_names=ns.assign(_Key=ns[nu].map(_title_key)).drop_duplicates('_Key').set_index('_Key')[nu].to_dict()
        nsum['Unvan']=nsum['_Key'].map(norm_role_names).fillna(nsum['_Key'].map(lambda x:txt(x).upper()))
        title_data=nsum.merge(msum,on='_Key',how='outer')
        title_data['Eksik']=(numeric(title_data['Yönetim Normu'])-numeric(title_data['Mevcut'])).clip(lower=0)
        title_data['Fazla']=(numeric(title_data['Mevcut'])-numeric(title_data['Yönetim Normu'])).clip(lower=0)
        title_data['Unvan']=title_data.get('Unvan',pd.Series(index=title_data.index,dtype=object)).fillna(title_data['_Key'].map(lambda x:txt(x).upper()))
        for c in ['Mevcut','Yönetim Normu','Eksik','Fazla']:
            title_data[c]=numeric(title_data.get(c,pd.Series(index=title_data.index,dtype=float))).astype(int)
        # PDF, web paneliyle aynı dinamik state() sonucunu kullanır. Böylece kişi satırı
        # yanlışlıkla açık gösterilmez ve tüm çıktılar aynı hesap kaynağından beslenir.
        _store_tt=tt[tt['Mağaza'].map(canon)==canon(sname)].copy()
        if not _store_tt.empty:
            _store_tt['_Key']=_store_tt['Unvan'].map(_title_key)
            _e_map=_store_tt.groupby('_Key')['Norm Eksiği'].sum().to_dict()
            _f_map=_store_tt.groupby('_Key')['Norm Fazlası'].sum().to_dict()
            title_data['Eksik']=title_data['_Key'].map(_e_map).fillna(0).astype(int)
            title_data['Fazla']=title_data['_Key'].map(_f_map).fillna(0).astype(int)
        # Yönetici/yardımcı, Manav/yardımcı, Şarküteri/yardımcı ve Kasap/yardımcı
        # dağılımı tüm mağazalarda aile toplamı üzerinden dengelenir.
        title_data=balance_store_title_rows(
            title_data,key_col='_Key',norm_col='Yönetim Normu',current_col='Mevcut',
            deficit_col='Eksik',surplus_col='Fazla'
        )
        title_data=unvan_sirali(title_data,unvan_kolonu='Unvan')

        # Personel açıklamaları yalnız Fact_Mevcut.H/Açıklama alanından alınır.
        person_manual_notes=[]
        if staff_note_col and staff_note_col in ps.columns:
            for _, _pr in ps.iterrows():
                _note=txt(_pr.get(staff_note_col,'')).strip()
                _sentence=format_person_note(_pr.get(pname,''), _note)
                if _sentence:
                    person_manual_notes.append(_sentence)
        manual_notes=list(dict.fromkeys(person_manual_notes))

        current=int(len(ps)); norm_total=int(title_data['Yönetim Normu'].sum())
        deficit=int(title_data['Eksik'].sum()); excess=int(title_data['Fazla'].sum())
        # Gerçek unvan "UZMAN YÖNETİCİ" olsa da departmanı YÖNETİCİ olan kişi
        # mağaza yöneticisidir. Yardımcılar yönetici alanına alınmaz.
        department_key=ps[dep_col].map(canon)
        real_title_key=ps[su].map(canon)
        manager_mask=(
            department_key.isin({'yonetici','magaza yoneticisi','sube muduru'})
            | (
                real_title_key.str.contains('yonetici',na=False)
                & ~real_title_key.str.contains('yardimci',na=False)
            )
        )
        managers=ps.loc[manager_mask,pname].dropna().map(txt).drop_duplicates().tolist()
        override_managers={}
        override_path=runtime_root()/'config_magaza_yoneticileri.json'
        if override_path.is_file():
            try:
                override_managers=json.loads(override_path.read_text(encoding='utf-8'))
            except Exception as _exc:
                from services.safe_exec import log_swallowed
                log_swallowed(f"config_magaza_yoneticileri.json okunamadı: '{override_path}'", _exc)
                override_managers={}
        override_name=txt(override_managers.get(sname) or override_managers.get(sid)).strip()
        if override_name:
            manager_text=override_name
        elif managers:
            manager_text=', '.join(managers[:2])
        else:
            assistant_mask=department_key.isin({'yonetici yardimcisi','magaza yonetici yardimcisi'})
            assistants=ps.loc[assistant_mask,pname].dropna().map(txt).drop_duplicates().tolist()
            manager_text=(
                'Yönetici ataması yok — Yönetici yardımcıları: '+', '.join(assistants[:3])
                if assistants else
                'Yönetici ataması ve vekâlet bilgisi girilmemiş'
            )

        store_heading=f'{sid} - {sname}' if sid else sname
        top=[[Paragraph(_pdf_text(store_heading.upper()),compact_title)],
             [Paragraph(_pdf_text(f'Mağaza Yöneticisi: {manager_text}'),compact_sub)],
             [Paragraph(_pdf_text(f'Bölge Sorumlusu: {region}'),compact_sub)]]
        top_table=Table(top,colWidths=[132*mm],rowHeights=[8*mm,6*mm,6*mm])
        top_table.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(0,0),colors.HexColor('#102F64')),
            ('BACKGROUND',(0,1),(0,2),colors.HexColor('#EDF3F8')),
            ('BOX',(0,0),(-1,-1),.45,colors.HexColor('#7F8C9A')),
            ('LEFTPADDING',(0,0),(-1,-1),2),('RIGHTPADDING',(0,0),(-1,-1),2),
            ('TOPPADDING',(0,0),(-1,-1),1),('BOTTOMPADDING',(0,0),(-1,-1),1),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE')]))

        header=[Paragraph('GERÇEK UNVAN',compact_head),Paragraph('AD SOYAD',compact_head),
                Paragraph('M',compact_head),Paragraph('N',compact_head),
                Paragraph('E',compact_head),Paragraph('F',compact_head)]
        normal_rows=[]
        surplus_rows=[]
        normal_row_notes=[]
        normal_row_note_kinds=[]
        surplus_row_notes=[]
        surplus_row_note_kinds=[]
        surplus_unvan_sayaci={}
        entry_col=col(staff,'İşe Giriş','Ise Giris')
        for _,r in title_data.iterrows():
            _person_cols=[pname,su]+([staff_note_col] if staff_note_col else [])
            persons=ps[ps['_NormKey']==r['_Key']][_person_cols].dropna(subset=[pname])
            if persons.empty:
                normal_rows.append([
                    Paragraph(_pdf_text(r['Unvan']),compact_body),
                    Paragraph('BOŞ POZİSYON' if int(r['Eksik']) else '-',compact_body),
                    Paragraph('0',compact_center),
                    Paragraph(str(int(r['Yönetim Normu'])),compact_center),
                    Paragraph(str(int(r['Eksik'])) if int(r['Eksik']) else '-',compact_center),
                    Paragraph(str(int(r['Fazla'])) if int(r['Fazla']) else '-',compact_center),
                ])
                normal_row_notes.append('')
                normal_row_note_kinds.append('')
            else:
                if entry_col and entry_col in ps.columns:
                    _person_cols=[pname,su,entry_col]+([staff_note_col] if staff_note_col else [])
                    persons=ps[ps['_NormKey']==r['_Key']][_person_cols].dropna(subset=[pname]).copy()
                    persons['_Tarih']=pd.to_datetime(persons[entry_col],errors='coerce')
                    persons=persons.sort_values('_Tarih',ascending=False,na_position='last')
                excess_count=min(int(r['Fazla']),len(persons))
                excess_indexes=set(persons.head(excess_count).index)
                regular_people=persons.loc[~persons.index.isin(excess_indexes)]
                excess_people=persons.loc[persons.index.isin(excess_indexes)]
                for person_index,(_,pr) in enumerate(regular_people.iterrows()):
                    first=person_index==0
                    normal_rows.append([
                        Paragraph(_pdf_text(pr[su]),compact_body),
                        Paragraph(_pdf_text(pr[pname]),compact_body),
                        Paragraph('1',compact_center),
                        Paragraph(str(int(r['Yönetim Normu'])) if first else '',compact_center),
                        Paragraph('-',compact_center),
                        Paragraph('-',compact_center),
                    ])
                    _raw_note=txt(pr.get(staff_note_col,'')).strip() if staff_note_col else ''
                    normal_row_notes.append(format_person_note(pr.get(pname,''),_raw_note))
                    normal_row_note_kinds.append(note_kind(_raw_note))
                if int(r['Eksik'])>0:
                    normal_rows.append([
                        Paragraph(_pdf_text(r['Unvan']),compact_body),
                        Paragraph('BOŞ POZİSYON',compact_body),
                        Paragraph('0',compact_center),
                        Paragraph('',compact_center),
                        Paragraph(str(int(r['Eksik'])),compact_center),
                        Paragraph('-',compact_center),
                    ])
                    normal_row_notes.append('')
                    normal_row_note_kinds.append('')
                for _,pr in excess_people.iterrows():
                    unvan_metni=txt(pr[su])
                    surplus_unvan_sayaci[unvan_metni]=surplus_unvan_sayaci.get(unvan_metni,0)+1
                    surplus_rows.append([
                        Paragraph(_pdf_text(pr[su]),compact_body),
                        Paragraph(_pdf_text(pr[pname]),compact_body),
                        Paragraph('1',compact_center),
                        Paragraph('',compact_center),
                        Paragraph('-',compact_center),
                        Paragraph('1',compact_center),
                    ])
                    _raw_note=txt(pr.get(staff_note_col,'')).strip() if staff_note_col else ''
                    surplus_row_notes.append(format_person_note(pr.get(pname,''),_raw_note))
                    surplus_row_note_kinds.append(note_kind(_raw_note))
        rows=[header]+normal_rows
        row_notes=['']+normal_row_notes
        row_note_kinds=['']+normal_row_note_kinds
        surplus_start=None
        if surplus_rows:
            surplus_start=len(rows)
            rows.extend(surplus_rows)
            row_notes.extend(surplus_row_notes)
            row_note_kinds.extend(surplus_row_note_kinds)
        detail=Table(rows,colWidths=[45*mm,47*mm,10*mm,10*mm,10*mm,10*mm],repeatRows=1)
        detail_style=[
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#4472C4')),
            ('TEXTCOLOR',(0,0),(-1,0),colors.white),
            ('FONTNAME',(0,0),(-1,-1),f),
            ('GRID',(0,0),(-1,-1),.6,colors.HexColor('#595959')),
            ('BOX',(0,0),(-1,-1),1.1,colors.HexColor('#102F64')),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('LEFTPADDING',(0,0),(-1,-1),1.4),('RIGHTPADDING',(0,0),(-1,-1),1.4),
            ('TOPPADDING',(0,0),(-1,-1),1.0),('BOTTOMPADDING',(0,0),(-1,-1),1.0),
        ]
        for ri in range(1,len(rows)):
            eksik=txt(rows[ri][4].getPlainText())
            fazla=txt(rows[ri][5].getPlainText())
            if ri < len(row_notes) and txt(row_notes[ri]).strip():
                _fill='#F4CCCC' if ri < len(row_note_kinds) and row_note_kinds[ri]=='departure' else '#FFF2CC'
                detail_style.append(('BACKGROUND',(0,ri),(-1,ri),colors.HexColor(_fill)))
            elif eksik not in {'','-','0'}:
                detail_style.append(('BACKGROUND',(0,ri),(-1,ri),colors.HexColor('#D9EAF7')))
            elif (surplus_start is not None and ri>=surplus_start) or fazla not in {'','-','0'}:
                detail_style.append(('BACKGROUND',(0,ri),(-1,ri),colors.white))
            else:
                detail_style.append(('BACKGROUND',(0,ri),(-1,ri),colors.white))
        detail.setStyle(TableStyle(detail_style))

        net_difference=current-norm_total

        # AI önerisi korunur. Bunun ALTINA ayrıca mevcut norm durumu açıklaması eklenir.
        if ai is not None and not ai.empty and 'MağazaID' in ai:
            store_ai=ai[ai['MağazaID'].map(txt)==sid].copy()
        elif ai is not None and not ai.empty and 'Mağaza' in ai:
            store_ai=ai[ai['Mağaza'].map(canon)==canon(sname)].copy()
        else:
            store_ai=pd.DataFrame()
        ai_total=int(pd.to_numeric(store_ai.get('AI Önerilen Norm',pd.Series(dtype=float)),errors='coerce').fillna(0).sum()) if not store_ai.empty else norm_total
        ai_gap=ai_total-current
        if ai_gap>0:
            ai_action=f'AI ÖNERİSİ: {ai_total} kişi | {ai_gap} kişi kapasite açığı. Önce uygun transfer, kalan açık için işe alım.'
        elif ai_gap<0:
            ai_action=f'AI ÖNERİSİ: {ai_total} kişi | {abs(ai_gap)} kişi transfer havuzunda değerlendirilebilir.'
        else:
            ai_action=f'AI ÖNERİSİ: {ai_total} kişi | Mevcut kadro korunmalı.'
        if not store_ai.empty and 'Güven Skoru' in store_ai:
            confidence_values=pd.to_numeric(store_ai['Güven Skoru'],errors='coerce').dropna()
            if not confidence_values.empty:
                ai_action+=f' Ortalama veri güveni %{float(confidence_values.mean()):.0f}.'

        durum_parcalari=[]
        for _,_r in title_data[title_data['Eksik']>0].iterrows():
            durum_parcalari.append(f"{txt(_r['Unvan']).title()} unvanında {int(_r['Eksik'])} norm açığı var.")
        for _,_r in title_data[title_data['Fazla']>0].iterrows():
            durum_parcalari.append(f"{txt(_r['Unvan']).title()} unvanında {int(_r['Fazla'])} kişi norm üstü mevcut var.")
        # Yardımcı personel, kendi ayrı normu yoksa veya kendi normundan arta
        # kalıyorsa aynı ana ailenin açığını dengeleyebilir. Ana unvan personeli
        # ise yardımcı normunu kapatmaz. Bu açıklama hesap sonucunu şeffaflaştırır.
        denge_ciftleri=[
            ('YÖNETİCİ','YÖNETİCİ YARDIMCISI'),
            ('MANAV','MANAV YARDIMCISI'),
            ('KASAP','KASAP YARDIMCISI'),
            ('ŞARKÜTERİ','ŞARKÜTERİ YARDIMCISI'),
        ]
        for ana,yrd in denge_ciftleri:
            ak=_title_key(ana); yk=_title_key(yrd)
            ana_norm=int(title_data.loc[title_data['_Key'].eq(ak),'Yönetim Normu'].sum())
            yrd_norm=int(title_data.loc[title_data['_Key'].eq(yk),'Yönetim Normu'].sum())
            ana_mevcut=int((ps['_NormKey']==ak).sum())
            yrd_mevcut=int((ps['_NormKey']==yk).sum())
            aile_normu=ana_norm+yrd_norm
            aile_mevcut=ana_mevcut+yrd_mevcut
            dagilim_farkli=(ana_mevcut!=ana_norm or yrd_mevcut!=yrd_norm)
            if aile_normu>0 and aile_mevcut>=aile_normu and dagilim_farkli:
                durum_parcalari.append(
                    f'{ana.title()} normu {ana_norm}, {yrd.title()} normu {yrd_norm}; '
                    f'şubede {ana_mevcut} {ana.title()} ve {yrd_mevcut} {yrd.title()} mevcuttur. '
                    'Aynı aile içindeki mevcut kapasiteyle norm dengesi korunabilir; '
                    'bu denge norm eksiği toplamına dahil edilmemiştir.'
                )
        # H/Açıklama alanındaki kullanıcı notları mevcut durum metninin içinde de görünür.
        for _manual in manual_notes:
            durum_parcalari.append(_manual)
        if not durum_parcalari:
            durum_parcalari=['Tüm unvanlarda mevcut kadro yönetim normuyla uyumludur.']
        mevcut_aciklama='MEVCUT DURUM AÇIKLAMASI: '+' '.join(durum_parcalari)

        note_style=ParagraphStyle(
            'ai_and_status_note',parent=compact_body,fontName=font(True),fontSize=5.2,leading=6.0,
            textColor=colors.HexColor('#102F64'),alignment=0
        )
        note_rows=[
            [Paragraph(_pdf_text(ai_action),note_style)],
            [Paragraph(_pdf_text(mevcut_aciklama),note_style)],
        ]
        ai_note=Table(note_rows,colWidths=[132*mm])
        note_table_style=[
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#EAF2F8')),
            ('BACKGROUND',(0,1),(-1,1),colors.HexColor('#F7FBFE')),
            ('BOX',(0,0),(-1,-1),.4,colors.HexColor('#4472C4')),
            ('LINEBELOW',(0,0),(-1,0),.3,colors.HexColor('#A9C4DD')),
            ('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3),
            ('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),2),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ]
        ai_note.setStyle(TableStyle(note_table_style))
        totals=[
            [Paragraph('MEVCUT',compact_head),Paragraph('NORM',compact_head),Paragraph('EKSİK',compact_head),Paragraph('FAZLA',compact_head),Paragraph('NET FARK',compact_head)],
            [current,norm_total,deficit,excess,net_difference],
        ]
        total_table=Table(totals,colWidths=[26.4*mm]*5,rowHeights=[5*mm,5*mm])
        total_table.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#BF9000')),
            ('TEXTCOLOR',(0,0),(-1,0),colors.white),
            ('BACKGROUND',(0,1),(0,1),colors.white),
            ('BACKGROUND',(1,1),(1,1),colors.HexColor('#FFF2CC')),
            ('BACKGROUND',(2,1),(2,1),colors.HexColor('#D9EAF7')),
            ('BACKGROUND',(3,1),(3,1),colors.HexColor('#F2F2F2')),
            ('BACKGROUND',(4,1),(4,1),colors.HexColor('#F2F2F2')),
            ('FONTNAME',(0,0),(-1,-1),f),('FONTNAME',(0,0),(-1,0),font(True)),
            ('FONTSIZE',(0,1),(-1,1),6),('ALIGN',(0,0),(-1,-1),'CENTER'),
            ('GRID',(0,0),(-1,-1),.35,colors.HexColor('#7F7F7F')),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ]))
        fazla_ozet_metni=None
        if surplus_unvan_sayaci:
            parcalar=[f"{unvan} ({adet})" for unvan,adet in sorted(surplus_unvan_sayaci.items(), key=lambda kv: -kv[1])]
            fazla_ozet_metni=Paragraph(
                _pdf_text('Fazla personel unvanları: '+', '.join(parcalar)),
                ParagraphStyle('fazla_ozet',parent=body,fontName=font(True),fontSize=6.6,
                               textColor=colors.HexColor('#374151')),
            )
        kart_elemanlari=[top_table,detail]
        if fazla_ozet_metni is not None:
            kart_elemanlari.append(fazla_ozet_metni)
        kart_elemanlari += [ai_note,total_table]
        return kart_elemanlari

    # Personel ad-soyad ve gerçek unvanları okunabilsin diye bir sayfada 2 mağaza gösterilir.
    regions=stores['Bölge Sorumlusu'].dropna().map(txt).unique().tolist()
    for region_index,region in enumerate(regions):
        region_stores=stores[stores['Bölge Sorumlusu'].map(canon)==canon(region)].reset_index(drop=True)
        for page_start in range(0,len(region_stores),2):
            page_stores=region_stores.iloc[page_start:page_start+2]
            story.append(Paragraph(_pdf_text(f'{region.upper()} - MAĞAZA NORM KADRO KARŞILAŞTIRMASI'),
                ParagraphStyle('region_grid_head',parent=title_style,fontName=font(True),fontSize=11,spaceAfter=2*mm)))
            story.append(Paragraph('M = Fact_Mevcut aktif mevcut, N = Fact_Norm yönetim normu, E = norm eksiği, F = norm fazlası.',
                ParagraphStyle('grid_note',parent=body,fontName=f,fontSize=6.2,alignment=1,textColor=colors.HexColor('#555555'),spaceAfter=2*mm)))
            cards=[store_card(row) for _,row in page_stores.iterrows()]
            while len(cards)<2: cards.append([])
            grid=Table([cards],colWidths=[136*mm]*2,rowHeights=[165*mm],hAlign='CENTER')
            grid.setStyle(TableStyle([
                ('VALIGN',(0,0),(-1,-1),'TOP'),
                ('LEFTPADDING',(0,0),(-1,-1),1.5*mm),('RIGHTPADDING',(0,0),(-1,-1),1.5*mm),
                ('TOPPADDING',(0,0),(-1,-1),1.0*mm),('BOTTOMPADDING',(0,0),(-1,-1),1.0*mm),
            ]))
            story.append(grid)
            is_last_region=(region_index==len(regions)-1)
            is_last_page=(page_start+2>=len(region_stores))
            if not (is_last_region and is_last_page): story.append(PageBreak())
    doc.build(story,onFirstPage=_footer,onLaterPages=_footer)
    make_outlook_safe_pdf(path)
