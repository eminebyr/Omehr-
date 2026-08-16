from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path


def test_no_activity_record_is_not_treated_as_expired():
    from services.session_guard import oturum_suresi_doldu_mu
    doldu, gecen = oturum_suresi_doldu_mu(None)
    assert doldu is False
    assert gecen == 0.0


def test_recent_activity_does_not_expire_session():
    from services.session_guard import oturum_suresi_doldu_mu
    simdi = datetime.now()
    doldu, _ = oturum_suresi_doldu_mu(simdi.isoformat(), simdi=simdi)
    assert doldu is False


def test_activity_just_under_timeout_does_not_expire():
    from services.session_guard import oturum_suresi_doldu_mu, idle_timeout_dakika
    simdi = datetime.now()
    son_aktivite = simdi - timedelta(minutes=idle_timeout_dakika() - 1)
    doldu, _ = oturum_suresi_doldu_mu(son_aktivite.isoformat(), simdi=simdi)
    assert doldu is False


def test_activity_just_over_timeout_expires_session():
    from services.session_guard import oturum_suresi_doldu_mu, idle_timeout_dakika
    simdi = datetime.now()
    son_aktivite = simdi - timedelta(minutes=idle_timeout_dakika() + 1)
    doldu, gecen = oturum_suresi_doldu_mu(son_aktivite.isoformat(), simdi=simdi)
    assert doldu is True
    assert gecen > idle_timeout_dakika()


def test_idle_timeout_respects_env_override(monkeypatch):
    monkeypatch.setenv("BASDAS_SESSION_IDLE_TIMEOUT_MIN", "30")
    from services.session_guard import idle_timeout_dakika
    assert idle_timeout_dakika() == 30


def test_malformed_timestamp_does_not_crash_or_expire():
    from services.session_guard import oturum_suresi_doldu_mu
    doldu, gecen = oturum_suresi_doldu_mu("bu-geçerli-bir-tarih-değil")
    assert doldu is False
    assert gecen == 0.0


def test_web_app_actually_wires_idle_timeout_into_authenticated_flow():
    """Saf mantık fonksiyonunun kendisi doğru olsa da, web/app.py bunu
    GERÇEKTEN çağırmıyorsa hiçbir işe yaramaz — bu, entegrasyonun
    unutulmadığını doğrulayan bir güvenlik ağı."""
    kaynak = Path(__file__).resolve().parents[1] / "web" / "app.py"
    metin = kaynak.read_text(encoding="utf-8")
    assert "from services.session_guard import oturum_suresi_doldu_mu" in metin
    assert "oturum_suresi_doldu_mu(st.session_state.get" in metin
    assert '"_son_aktivite"' in metin
    assert "SESSION_IDLE_TIMEOUT" in metin
