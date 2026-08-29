from __future__ import annotations

"""
DÜZELTME (StreamlitDuplicateElementKey: 'dark_mode_toggle'):
Bu fonksiyon eskiden web/app.py içindeydi. raporlar.py (ve olası diğer
tab_modules dosyaları) çalışma zamanında `from web.app import
_enqueue_without_waiting` yapıyordu. Streamlit app.py'yi ana script olarak
(`__main__`) çalıştırdığı için, bu import Python'a göre FARKLI bir modül
kimliği (`web.app`) arıyordu ve sys.modules önbelleğinde bulamayınca
app.py'yi BAŞTAN SONA İKİNCİ KEZ çalıştırıyordu — bu da app.py içindeki
`st.checkbox(..., key="dark_mode_toggle")` satırının iki kez tetiklenmesine
ve StreamlitDuplicateElementKey hatasına yol açıyordu.

Çözüm: bu fonksiyonu app.py'den tamamen bağımsız bir modüle taşımak.
Artık ne app.py ne de tab_modules/*.py birbirini import etmek zorunda
kalmıyor; ikisi de sadece bu dosyadan import ediyor.
"""

import subprocess
import sys
from pathlib import Path

from services.job_queue import enqueue
from services.safe_exec import log_swallowed

CODE_ROOT = Path(__file__).resolve().parents[1]


def _enqueue_without_waiting(job_type, payload, tenant):
    """DÜZELTME (kritik UX hatası — canlı ortamda doğrulandı): hem
    refresh_all() hem raporlar.py'deki 'yeniden üret' butonu, işi
    kuyruğa aldıktan sonra kendi kendine 5-6 dakikaya kadar SENKRON
    (`while` + `time.sleep`) bekliyordu. Bu süre boyunca Streamlit
    sayfası tarayıcıyla HİÇ konuşmuyor — sayfa donuyor, mobil
    tarayıcılarda/Railway'in proxy'sinde uzun süre yanıtsız kalan
    bağlantı KOPUYOR, kullanıcı tekrar bağlanınca oturumu (session)
    sıfırlanmış oluyor ve giriş ekranına düşüyor. Bu fonksiyon işi
    kuyruğa alır, worker'ı başlatır ve HEMEN döner — bekleme YOKTUR,
    sayfa donmaz. Sonucu görmek için kullanıcının birkaç dakika sonra
    sayfayı manuel yenilemesi/tekrar butona bakması gerekir."""
    job_id = enqueue(job_type, payload, tenant)
    try:
        py = CODE_ROOT / ".venv" / "Scripts" / "python.exe"
        executable = str(py) if py.exists() else sys.executable
        subprocess.Popen([executable, str(CODE_ROOT / "worker.py"), "--once"], cwd=CODE_ROOT)
    except Exception as _exc:
        log_swallowed("web.queue_utils._enqueue_without_waiting: beklenmeyen hata", _exc)
    return job_id


def enqueue_report_refresh() -> str:
    """Güncel kiracı için raporları arka planda yeniden üretir."""
    from services.tenant_context import current_tenant_id

    return _enqueue_without_waiting("RUN_REPORTS", {}, current_tenant_id())
