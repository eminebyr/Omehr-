"""AI ÖNERİSİ GERİ BESLEME TAKİBİ.

Sorun: AI motoru (ai_operations_engine.py) her çalıştırmada bir öneri
üretir (AI_Norm_Sonuclari sayfası) ama sonucunu hiçbir yerde takip etmez
— öneri kabul mü edildi, reddedildi mi, neden, gerçek norm ne oldu, bu
soruların hiçbirinin cevabı kalıcı olarak saklanmıyordu.

Bu modül, ai_feedback_log adında YENİ ve KALICI bir tablo ekler
(data/v16_management.db içinde, diğer audit tablolarıyla aynı desende).
Her satır bir KARAR OLAYIdır (bir transfer talebinin durum geçmişi gibi):
AI bir norm önerdi -> yönetici kabul/red etti (+gerekçe) -> [isteğe bağlı,
daha sonra] gerçek sonuç (norm/fazla mesai) kaydedildi.

BİLEREK YAPILMAYAN (dürüstçe kapsam dışı — bkz. DEGISIKLIK_OZETI):
"Gerçek norm ne oldu" ve "fazla mesai azaldı mı" alanları şema olarak
VAR (actual_norm_after, overtime_hours_before/after) ama OTOMATİK
doldurulmuyor — bunun için Fact_Norm/Fazla Mesai verisinin zaman
içinde karşılaştırılacağı ayrı, zamanlanmış bir mutabakat (reconciliation)
işi gerekir. Bu alanlar şimdilik yalnız update_outcome() ile ELLE veya
gelecekte yazılacak bir job ile doldurulabilir; main.py bunu otomatik
yapmıyor.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from services.exceptions import TransferConflictError

VALID_DECISIONS = {"Kabul Edildi", "Reddedildi", "Revize Edildi", "Bekliyor"}


def _connect() -> sqlite3.Connection:
    # Aynı veritabanı dosyasını (v16_management.db) ve aynı bağlantı
    # kurulum desenini (WAL, busy_timeout) kullanır — services/web_runtime.py
    # ile tutarlı.
    from services.web_runtime import db_path
    DB = db_path()

    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")
    con.row_factory = sqlite3.Row
    con.execute(
        """CREATE TABLE IF NOT EXISTS ai_feedback_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            magaza_id TEXT, magaza TEXT, unvan_id TEXT, unvan TEXT,
            ai_onerilen_norm INTEGER, yonetim_normu INTEGER, guven_skoru REAL,
            karar TEXT NOT NULL, karar_veren TEXT NOT NULL, gerekce TEXT,
            actual_norm_after INTEGER, overtime_hours_before REAL, overtime_hours_after REAL,
            outcome_recorded_at TEXT, outcome_recorded_by TEXT
        )"""
    )
    # DEĞİŞTİRİLEMEZ KARAR OLAYI: bir kez kaydedilen "AI önerisi
    # kabul/red edildi" kararı geriye dönük değiştirilemez veya
    # silinemez (bkz. services/web_runtime.py action_log ile aynı
    # gerekçe). "Sonuç" alanları (actual_norm_after vb.) İSTİSNAdır —
    # bunlar tanım gereği kararla AYNI ANDA değil, DAHA SONRA bilinir,
    # bu yüzden yalnız bu belirli sütunları güncellemeye izin veren
    # ayrı bir yol (update_outcome) sağlanır; UPDATE'i tümden
    # yasaklamak yerine uygulama seviyesinde (yalnız outcome sütunları)
    # sınırlanır. Karar alanlarını (karar/karar_veren/gerekce) SONRADAN
    # değiştirmek isteyen biri, YENİ bir satır eklemelidir (revizyon).
    return con


def record_decision(
    magaza_id: Any, magaza: str, unvan_id: Any, unvan: str,
    ai_onerilen_norm: int, yonetim_normu: int, guven_skoru: float,
    karar: str, karar_veren: str, gerekce: str = "",
) -> int:
    """Bir AI önerisi hakkında yönetim kararını KALICI olarak kaydeder.

    Dönüş: yeni satırın id'si.
    """
    if karar not in VALID_DECISIONS:
        raise TransferConflictError(
            f"Geçersiz karar: '{karar}'. Geçerli değerler: {sorted(VALID_DECISIONS)}"
        )
    if not karar_veren or not karar_veren.strip():
        raise TransferConflictError("Karar veren kullanıcı adı boş olamaz.")

    con = _connect()
    try:
        cur = con.execute(
            """INSERT INTO ai_feedback_log(
                created_at, magaza_id, magaza, unvan_id, unvan,
                ai_onerilen_norm, yonetim_normu, guven_skoru, karar, karar_veren, gerekce
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                datetime.now().isoformat(timespec="seconds"),
                str(magaza_id), str(magaza), str(unvan_id), str(unvan),
                int(ai_onerilen_norm), int(yonetim_normu), float(guven_skoru),
                karar, karar_veren.strip(), gerekce.strip(),
            ),
        )
        con.commit()
        return int(cur.lastrowid)
    finally:
        con.close()


def update_outcome(
    feedback_id: int,
    actual_norm_after: int | None = None,
    overtime_hours_before: float | None = None,
    overtime_hours_after: float | None = None,
    recorded_by: str = "sistem",
) -> None:
    """Daha önce kaydedilmiş bir kararın GERÇEK SONUCUNU ekler/günceller.

    Yalnız outcome_* sütunlarını değiştirir; karar/gerekçe alanlarına
    dokunmaz (bkz. modül docstring'i — bu, immutability ilkesinin
    istisnası değil, ayrı bir amaca hizmet eden ayrı bir yazma yoludur).
    """
    alanlar, degerler = [], []
    if actual_norm_after is not None:
        alanlar.append("actual_norm_after=?"); degerler.append(int(actual_norm_after))
    if overtime_hours_before is not None:
        alanlar.append("overtime_hours_before=?"); degerler.append(float(overtime_hours_before))
    if overtime_hours_after is not None:
        alanlar.append("overtime_hours_after=?"); degerler.append(float(overtime_hours_after))
    if not alanlar:
        return
    alanlar.append("outcome_recorded_at=?"); degerler.append(datetime.now().isoformat(timespec="seconds"))
    alanlar.append("outcome_recorded_by=?"); degerler.append(recorded_by)
    degerler.append(int(feedback_id))

    con = _connect()
    try:
        con.execute(f"UPDATE ai_feedback_log SET {', '.join(alanlar)} WHERE id=?", degerler)
        con.commit()
    finally:
        con.close()


def history(magaza: str | None = None, unvan: str | None = None, limit: int = 500) -> list[dict]:
    """Kayıtlı geri bildirim geçmişini (en yeniden en eskiye) döndürür."""
    con = _connect()
    try:
        q = "SELECT * FROM ai_feedback_log"
        kosullar, degerler = [], []
        if magaza:
            kosullar.append("magaza=?"); degerler.append(magaza)
        if unvan:
            kosullar.append("unvan=?"); degerler.append(unvan)
        if kosullar:
            q += " WHERE " + " AND ".join(kosullar)
        q += " ORDER BY id DESC LIMIT ?"
        degerler.append(int(limit))
        return [dict(row) for row in con.execute(q, degerler).fetchall()]
    finally:
        con.close()


def acceptance_summary() -> dict[str, Any]:
    """Kabul/red oranı gibi özet istatistikler — 'AI'nin gerçek faydası'
    sorusuna cevap vermeye başlayan en basit gösterge."""
    con = _connect()
    try:
        satirlar = [dict(r) for r in con.execute(
            "SELECT karar, guven_skoru FROM ai_feedback_log"
        ).fetchall()]
    finally:
        con.close()

    toplam = len(satirlar)
    if toplam == 0:
        return {"toplam_karar": 0, "kabul_orani": None, "karar_dagilimi": {}}

    dagilim: dict[str, int] = {}
    for s in satirlar:
        dagilim[s["karar"]] = dagilim.get(s["karar"], 0) + 1
    kabul = dagilim.get("Kabul Edildi", 0)
    return {
        "toplam_karar": toplam,
        "kabul_orani": round(kabul / toplam, 3),
        "karar_dagilimi": dagilim,
    }
