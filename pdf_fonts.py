from __future__ import annotations
"""Merkezi PDF font kaydı.

Dağıtım paketine font dosyası eklemez. İşletim sisteminde kurulu, Türkçe
karakterleri destekleyen fontları güvenli sırayla bulur ve ReportLab'e kaydeder.
"""
import os
from pathlib import Path
from reportlab import rl_config
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

rl_config.ttfAsciiReadable = 1
_PDF_FONTS_READY=False
_PDF_FONT_ERROR=''
_SELECTED_FILES=[]
REQUIRED_TURKISH_GLYPHS='ÇĞİÖŞÜçğıöşü₺'

def _candidate_pairs():
    windir=Path(os.environ.get('WINDIR','C:/Windows'))
    return [
        (windir/'Fonts'/'arial.ttf', windir/'Fonts'/'arialbd.ttf'),
        (windir/'Fonts'/'calibri.ttf', windir/'Fonts'/'calibrib.ttf'),
        (windir/'Fonts'/'segoeui.ttf', windir/'Fonts'/'segoeuib.ttf'),
        (Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'), Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')),
        (Path('/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf'), Path('/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf')),
    ]

def _find_pair():
    for regular,bold in _candidate_pairs():
        if regular.is_file() and bold.is_file() and regular.stat().st_size>50000 and bold.stat().st_size>50000:
            return regular,bold
    raise RuntimeError('Türkçe uyumlu sistem fontu bulunamadı (Arial/Calibri/Segoe UI/DejaVu Sans).')

def font(bold: bool=False)->str:
    global _PDF_FONTS_READY,_PDF_FONT_ERROR,_SELECTED_FILES
    if not _PDF_FONTS_READY:
        try:
            regular,bold_path=_find_pair()
            pdfmetrics.registerFont(TTFont('BasdasPDF',str(regular),validate=1,asciiReadable=True))
            pdfmetrics.registerFont(TTFont('BasdasPDF-Bold',str(bold_path),validate=1,asciiReadable=True))
            pdfmetrics.registerFontFamily('BasdasPDF',normal='BasdasPDF',bold='BasdasPDF-Bold',italic='BasdasPDF',boldItalic='BasdasPDF-Bold')
            face=pdfmetrics.getFont('BasdasPDF').face
            absent=[ch for ch in REQUIRED_TURKISH_GLYPHS if ord(ch) not in face.charWidths]
            if absent:
                raise RuntimeError('Seçilen sistem fontunda Türkçe glif eksik: '+''.join(absent))
            _SELECTED_FILES=[str(regular),str(bold_path)]
            _PDF_FONTS_READY=True
        except Exception as exc:
            _PDF_FONT_ERROR=str(exc)
            raise RuntimeError('PDF font kaydı başarısız: '+str(exc)) from exc
    return 'BasdasPDF-Bold' if bold else 'BasdasPDF'

def font_status()->dict:
    return {'ready':_PDF_FONTS_READY,'error':_PDF_FONT_ERROR,'files':[{'name':Path(p).name,'path':p,'exists':Path(p).is_file()} for p in _SELECTED_FILES]}
