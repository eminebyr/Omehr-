"""Transfer e-posta gövdesi yardımcıları.

Bu modül Streamlit bağımlılığı taşımaz. Böylece e-posta metni kuralları,
web arayüzü kurulmadan da bağımsız olarak test edilebilir.
"""
from __future__ import annotations

from typing import Mapping, Any


def transfer_bilgi_govdesi(
    row: Mapping[str, Any],
    karar_basligi: str,
    ek_not: str = "",
    rotasyon_var: bool = False,
) -> str:
    """Transfer karar e-postası için açık ve eksiksiz metin oluşturur."""
    kisi = row.get("person_name") or row.get("person_id") or "Belirtilmemiş"
    kaynak = row.get("source_store") or "?"
    hedef = row.get("target_store") or "?"
    satirlar = [
        f"Personel: {kisi}",
        f"Devreden şube (mevcut): {kaynak}",
        f"Devralan şube (yeni): {hedef}",
        f"Karar: {karar_basligi}",
    ]
    if ek_not:
        satirlar.append(f"Not/Gerekçe: {ek_not}")
    if rotasyon_var:
        satirlar.append(
            "\nBu e-postaya rotasyon belgesi (DOCX ve PDF) eklenmiştir — hem devreden "
            "hem devralan şube yetkilisi tarafından imzalanıp İK'ya iletilmelidir."
        )
    satirlar.append(
        "\nBu e-posta, hem devreden hem devralan şubeye otomatik olarak gönderilmiştir."
    )
    return "\n".join(satirlar)
