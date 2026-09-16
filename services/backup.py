"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/ops/backup.py

services/ops/ bounded-context'ine taşındı (bkz. SERVICE_BOUNDARIES.md
"Operasyon / İzleme / Denetim" alanı). `_max_backups`, `_backup_dir`,
`_restore_audit_log` (private) ve `DEFAULT_MAX_BACKUPS`, testler
tarafından doğrudan içe aktarılır/erişilir — bu yüzden açıkça yeniden
dışa aktarılır.
"""
from services.ops.backup import *  # noqa: F401,F403
from services.ops.backup import (
    DEFAULT_MAX_BACKUPS,
    _backup_dir,
    _max_backups,
    _restore_audit_log,
    backup_input_file,
    list_backups,
    restore_audit_history,
    restore_backup,
    verify_backup_integrity,
)
