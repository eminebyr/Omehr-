"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/personnel/personnel_exit.py

services/personnel/ bounded-context'ine taşındı (bkz. SERVICE_BOUNDARIES.md
"Personel Yaşam Döngüsü" alanı). Bu dosya, mevcut `from services.personnel_exit
import X` şeklindeki tüm çağıranların hiçbir değişiklik gerektirmeden
çalışmaya devam etmesi için bırakılmıştır.
"""
from services.personnel.personnel_exit import *  # noqa: F401,F403
from services.personnel.personnel_exit import (
    add_personnel,
    add_personnel_bulk,
    aktif_personel_karti_verisi,
    cikis_nedenleri,
    is_active,
    load_personnel_view,
    process_exit,
    process_exits_bulk,
    undo_exit,
    update_personnel,
    # DÜZELTME (regresyon — bizzat bulundu): services/multi_pc_sync.py
    # bu private fonksiyonu `from services.personnel_exit import
    # _invalidate_current_reports` ile içeri alıyor, ama çağrı bir
    # try/except Exception içinde olduğu için (invalidate_local_
    # reports_if_shared_input_changed), bu isim yeniden dışa
    # aktarılmadığında ImportError SESSİZCE yutuluyordu — 3-PC'li
    # paylaşımlı Excel kullanımında başka bir bilgisayarın işlem
    # sonrası bu bilgisayardaki eski personel raporlarının
    # temizlenmesi sessizce atlanıyordu, hiçbir hata görünmüyordu.
    _invalidate_current_reports,
)
