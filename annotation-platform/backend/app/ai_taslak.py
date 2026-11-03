"""AI taslakları (ADR-0010): LLM'in hazırladığı kartlar meme'lere taslak olarak bağlanır.

Taslak gold olmaz. AI taslağı olan meme tek etiketli kalır; atanan annotator etiketlemeye
başlarken formu taslakla dolu bulur, düzeltir ve gönderir.
"""

from typing import Optional

from app.kurallar import cift_etiket_mi
from app.models import ATANDI, ATLANDI
from app.sema import ALAN_KURALLARI, LISTE_TIPLERI


def karttan_icerik(kart: dict) -> dict:
    """Kartın şema alanlarını annotation içeriğine çevirir; değerler değiştirilmez, yalnızca türü düzeltilir."""
    icerik = {}
    for alan, kural in ALAN_KURALLARI.items():
        deger = kart.get(alan)
        if kural["tip"] in LISTE_TIPLERI:
            if deger is None:
                # uyari'da null "cevaplanmadı", [] "uyarı yok" demektir (ADR-0004).
                deger = None if alan == "uyari" else []
            elif isinstance(deger, list):
                deger = [str(oge) for oge in deger if oge is not None]
            else:
                deger = [str(deger)]
        elif deger is not None:
            deger = str(deger)
        icerik[alan] = deger
    return icerik


def taslak_engeli(taslak_var: bool, gold_var: bool, meme_annotationlari: list) -> Optional[tuple[str, str]]:
    """Meme'e AI taslağı eklenemiyorsa (sebep, mesaj) döner."""
    if taslak_var:
        return "zaten_var", "Bu meme'in AI taslağı zaten var; taslak sonradan değişmez."
    if gold_var:
        return "gold_var", "Bu meme'in gold kaydı var."
    if any(a.kalibrasyon for a in meme_annotationlari):
        return "kalibrasyonda", "Kalibrasyon turundaki meme'e AI taslağı eklenmez."
    if cift_etiket_mi(meme_annotationlari):
        return "cift_etiketli", "Çift etiketli meme'e AI taslağı eklenmez."
    if any(not a.kalibrasyon and a.durum_kodu not in (ATANDI, ATLANDI) for a in meme_annotationlari):
        return "etiketleme_baslamis", "Bu meme'in etiketlenmesine başlanmış; taslak forma uygulanamaz."
    return None
