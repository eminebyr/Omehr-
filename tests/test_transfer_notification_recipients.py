from __future__ import annotations

import pandas as pd

from web.accounts import transfer_recipients


def test_transfer_notification_includes_source_and_target_branch_emails():
    accounts = pd.DataFrame([
        {"Yetki Kapsamı": "BÖLGE A", "E-posta": "bolgea@ornek.com"},
        {"Yetki Kapsamı": "BÖLGE B", "E-posta": "bolgeb@ornek.com"},
    ])
    sheets = {
        "Sube_Mail_Listesi": pd.DataFrame([
            {"Mağaza": "KAYNAK ŞUBE", "E-posta": "kaynak@ornek.com"},
            {"Mağaza": "HEDEF ŞUBE", "E-posta": "hedef@ornek.com"},
        ])
    }
    recipients = transfer_recipients(
        accounts,
        {
            "region": "BÖLGE A",
            "target_region": "BÖLGE B",
            "source_store": "KAYNAK ŞUBE",
            "target_store": "HEDEF ŞUBE",
        },
        sheets,
    )
    assert "kaynak@ornek.com" in recipients
    assert "hedef@ornek.com" in recipients
    assert "bolgea@ornek.com" in recipients
    assert "bolgeb@ornek.com" in recipients
    assert len(recipients) == len(set(recipients))


def test_root_rotation_example_is_not_required():
    from services.rotation_document import _template
    template = _template()
    assert template.name == "ROTASYON_BELGESI_SABLONU.docx"
    assert template.parent.name == "templates"
