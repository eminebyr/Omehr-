"""AI PERFORMANS GERİ BESLEME — arka uç testleri (services/ai_feedback.py).

web/tab_modules/ai_geri_bildirim.py'nin kendisi Streamlit'e bağımlı olduğu için
bu sandbox'ta test edilemiyor; arkasındaki tüm karar kaydı/sorgu mantığı
saf Python + sqlite3 olduğu için tam olarak test edilebiliyor.
"""
from __future__ import annotations

import pytest

from services.exceptions import TransferConflictError


def test_record_decision_returns_new_row_id(isolated_root):
    from services.ai_feedback import record_decision

    fid = record_decision(1, "A Mağazası", "U1", "KASİYER", 5, 4, 82.5, "Kabul Edildi", "ik_direktoru")
    assert isinstance(fid, int)
    assert fid > 0


def test_record_decision_rejects_unknown_karar_value(isolated_root):
    from services.ai_feedback import record_decision

    with pytest.raises(TransferConflictError):
        record_decision(1, "A", "U1", "X", 1, 1, 50, "GEÇERSİZ", "kullanici")


def test_record_decision_rejects_blank_karar_veren(isolated_root):
    from services.ai_feedback import record_decision

    with pytest.raises(TransferConflictError):
        record_decision(1, "A", "U1", "X", 1, 1, 50, "Kabul Edildi", "   ")


def test_history_returns_most_recent_first(isolated_root):
    from services.ai_feedback import record_decision, history

    record_decision(1, "A Mağazası", "U1", "KASİYER", 5, 4, 82.5, "Kabul Edildi", "u1")
    record_decision(2, "B Mağazası", "U2", "MANAV", 8, 6, 45.0, "Reddedildi", "u2", "saha etüdü bekleniyor")

    gecmis = history()
    assert len(gecmis) == 2
    assert gecmis[0]["magaza"] == "B Mağazası"  # en son eklenen ilk sırada
    assert gecmis[0]["gerekce"] == "saha etüdü bekleniyor"


def test_history_can_filter_by_store(isolated_root):
    from services.ai_feedback import record_decision, history

    record_decision(1, "A Mağazası", "U1", "KASİYER", 5, 4, 82.5, "Kabul Edildi", "u1")
    record_decision(2, "B Mağazası", "U2", "MANAV", 8, 6, 45.0, "Reddedildi", "u2")

    sonuc = history(magaza="A Mağazası")
    assert len(sonuc) == 1
    assert sonuc[0]["magaza"] == "A Mağazası"


def test_acceptance_summary_computes_correct_rate(isolated_root):
    from services.ai_feedback import record_decision, acceptance_summary

    record_decision(1, "A", "U1", "X", 1, 1, 50, "Kabul Edildi", "u")
    record_decision(1, "A", "U1", "X", 1, 1, 50, "Kabul Edildi", "u")
    record_decision(1, "A", "U1", "X", 1, 1, 50, "Reddedildi", "u")

    ozet = acceptance_summary()
    assert ozet["toplam_karar"] == 3
    assert ozet["kabul_orani"] == pytest.approx(2 / 3, abs=0.001)
    assert ozet["karar_dagilimi"] == {"Kabul Edildi": 2, "Reddedildi": 1}


def test_acceptance_summary_handles_no_decisions_yet(isolated_root):
    from services.ai_feedback import acceptance_summary

    ozet = acceptance_summary()
    assert ozet == {"toplam_karar": 0, "kabul_orani": None, "karar_dagilimi": {}}


def test_update_outcome_only_changes_outcome_fields(isolated_root):
    """update_outcome() karar/gerekçe alanlarına DOKUNMAMALI — yalnız
    sonuç (actual_norm_after vb.) alanlarını değiştirmeli."""
    from services.ai_feedback import record_decision, update_outcome, history

    fid = record_decision(1, "A Mağazası", "U1", "KASİYER", 5, 4, 82.5, "Kabul Edildi", "ik_direktoru", "ilk gerekçe")
    update_outcome(fid, actual_norm_after=5, overtime_hours_before=40, overtime_hours_after=18, recorded_by="ik_direktoru")

    kayit = next(h for h in history() if h["id"] == fid)
    assert kayit["actual_norm_after"] == 5
    assert kayit["overtime_hours_before"] == 40
    assert kayit["overtime_hours_after"] == 18
    assert kayit["karar"] == "Kabul Edildi"
    assert kayit["gerekce"] == "ilk gerekçe"


def test_update_outcome_with_no_fields_is_a_no_op(isolated_root):
    from services.ai_feedback import record_decision, update_outcome, history

    fid = record_decision(1, "A", "U1", "X", 1, 1, 50, "Kabul Edildi", "u")
    update_outcome(fid)  # hiçbir alan verilmedi
    kayit = next(h for h in history() if h["id"] == fid)
    assert kayit["actual_norm_after"] is None


def test_ai_feedback_uses_same_database_as_action_log(isolated_root):
    """ai_feedback_log, services/web_runtime.py ile AYNI veritabanı
    dosyasını (v16_management.db) kullanmalı — ayrı bir DB dosyası
    yaratıp veri dağınıklığına yol açmamalı."""
    from services.ai_feedback import record_decision, _connect
    from services.web_runtime import connect_web_db

    record_decision(1, "A", "U1", "X", 1, 1, 50, "Kabul Edildi", "u")
    connect_web_db().close()  # action_log tablosunu da aynı dosyada oluştur

    con = _connect()
    tablolar = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    con.close()
    assert "ai_feedback_log" in tablolar
    assert "action_log" in tablolar
