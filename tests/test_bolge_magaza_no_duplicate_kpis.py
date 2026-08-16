from pathlib import Path


def test_bolge_magaza_uses_one_canonical_kpi_set():
    src = Path('web/tab_modules/bolge_magaza.py').read_text(encoding='utf-8')
    assert 'store_view["Norm Kadro"]' in src
    assert 'store_view["Aktif Mevcut"]' in src
    assert 'store_view["Norm Eksiği"]' in src
    assert 'store_view["Norm Fazlası"]' in src
    assert 'store_view["Norm"]' not in src
    assert 'store_view["Mevcut"]' not in src
    assert 'store_view["Eksik"]' not in src
    assert 'store_view["Fazla"]' not in src


def test_rotation_approval_creates_documents_and_sends_mail():
    onay = Path('web/tab_modules/onaylar.py').read_text(encoding='utf-8')
    worker = Path('worker.py').read_text(encoding='utf-8')
    assert '_enqueue_and_process("TRANSFER_DECISION"' in onay
    assert '"approved":dec=="İK Onayladı"' in onay
    # DÜZELTME: Geçici Görevlendirme / Şube Destek Formu seçeneği eklendiğinde
    # bu satır dallanmalı hale geldi (PERMANENT/TEMPORARY) — artık tam eski
    # metni değil, HER İKİ dalın da var olduğunu ve onaylanmadığında hiçbir
    # belge üretilmediğini doğruluyoruz.
    assert 'documents = {}' in worker
    assert 'if payload.get("approved"):' in worker
    assert 'create_rotation_documents(row)' in worker
    assert 'create_temporary_assignment_documents(' in worker
    assert 'payload.get("document_type") == "TEMPORARY"' in worker
    assert 'attachments = [value for key, value in documents.items() if key in {"pdf", "docx"}' in worker
    assert 'send_idempotent(' in worker
    assert 'rotation_recipients' in worker
