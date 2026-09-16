from __future__ import annotations

"""
MERKEZİ SÜRÜM SABİTLERİ (P2 — reviewer önerisi)
=====================================================
Paket genelinde uygulama, model ve rapor şeması sürümlerini tek bir merkezde tutar.
Çıktı metadata, lineage ve log kayıtları bu sabitleri kullanır; böylece farklı
modüllerde birbiriyle çelişen sürüm bilgileri oluşmaz.
"""

APP_VERSION = "19.21.29"
MODEL_VERSION = "GB-CONTROL-1.0"  # ai_operations_engine.py'deki GradientBoostingClassifier sürümü
REPORT_SCHEMA_VERSION = "4"

# "CURRENT" etiketi: dosya adlarındaki (CURRENT_Yonetici_Raporu.pdf gibi)
# "her zaman en son başarılı çalıştırmayı gösteren manifest" anlamına gelir
# — bu bir SÜRÜM NUMARASI değildir, ayrı bir kavramdır, bilerek APP_VERSION
# ile karıştırılmaz.
CURRENT_OUTPUT_LABEL = "CURRENT"
