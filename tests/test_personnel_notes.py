from services.personnel_notes import format_person_note, note_kind

def test_personnel_note_sentences():
    assert format_person_note("Şeyma Aslan", "10.08.2026 tarihine kadar raporlu") == "Şeyma Aslan 10.08.2026 tarihine kadar raporludur."
    assert format_person_note("Şeyma Aslan", "Gezici") == "Şeyma Aslan gezicidir."
    assert format_person_note("Şeyma Aslan", "20.08.2026 ayrılacak") == "Şeyma Aslan 20.08.2026 tarihinde ayrılacaktır."
    assert note_kind("20.08.2026 ayrılacak") == "departure"
    assert note_kind("raporlu") == "info"
