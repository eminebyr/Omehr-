"""services.exceptions testleri — özel hata sınıfı hiyerarşisi."""
from __future__ import annotations

import pytest

from services.exceptions import (
    AuthorizationError,
    OmehrError,
    ConfigurationError,
    MailDeliveryError,
    TransferConflictError,
    WorkbookError,
)


@pytest.mark.parametrize(
    "exc_cls",
    [WorkbookError, MailDeliveryError, TransferConflictError, ConfigurationError, AuthorizationError],
)
def test_each_domain_exception_is_a_omehr_error(exc_cls):
    assert issubclass(exc_cls, OmehrError)
    assert issubclass(exc_cls, Exception)


def test_omehr_error_can_be_caught_generically():
    """Tek bir 'except OmehrError' ile TÜM bilinen/beklenen hata türleri
    yakalanabilmeli — bu sınıfların asıl var oluş amacı budur."""
    for exc_cls in (WorkbookError, MailDeliveryError, TransferConflictError, ConfigurationError, AuthorizationError):
        with pytest.raises(OmehrError):
            raise exc_cls("test")


def test_unrelated_builtin_errors_are_not_omehr_errors():
    """Gerçek programlama hataları (KeyError, TypeError vb.) OmehrError
    ailesinden DEĞİLDİR — 'except OmehrError' bunları yakalamamalı,
    olduğu gibi yükselmeli."""
    assert not issubclass(KeyError, OmehrError)
    assert not issubclass(TypeError, OmehrError)


def test_exception_message_is_preserved():
    exc = MailDeliveryError("SMTP sunucusuna bağlanılamadı")
    assert str(exc) == "SMTP sunucusuna bağlanılamadı"
