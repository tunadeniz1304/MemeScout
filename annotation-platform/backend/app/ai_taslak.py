"""AI taslakları (ADR-0010): LLM'in hazırladığı kartlar meme'lere taslak olarak bağlanır.

Taslak gold olmaz. AI taslağı olan meme tek etiketli kalır; atanan annotator etiketlemeye
başlarken formu taslakla dolu bulur, düzeltir ve gönderir.
"""

from typing import Optional

from sqlmodel import Session

from app.kurallar import cift_etiket_mi
from app.models import ATANDI, ATLANDI, AiDraft, Annotation, Meme
from app.sema import ALAN_KURALLARI, LISTE_TIPLERI, bos_icerik

AI_TASLAGI = "ai_taslagi"
VLM_TASLAGI = "vlm_taslagi"


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


def on_doldurma(session: Session, annotation: Annotation) -> Optional[tuple[str, dict]]:
    """Etiketlemeye başlarken forma ne doldurulacağını döner: (kaynak, içerik) ya da None.

    AI taslağı yalnızca tek etiketli ana tur annotation'ına uygulanır; çift etiketlemede ve
    kalibrasyonda form taslaksız başlar. VLM taslağı yalnızca görsel tarifi doldurur ve iki
    annotator'a da aynı geldiği için kör etiketlemeyi bozmaz (annotation.md §4.3).
    """
    if annotation.icerik != bos_icerik():
        return None  # dokunulmuş içerik ezilmez
    if not annotation.kalibrasyon and not annotation.cift_etiket:
        taslak = session.get(AiDraft, annotation.meme_id)
        if taslak is not None:
            return AI_TASLAGI, taslak.icerik
    meme = session.get(Meme, annotation.meme_id)
    if meme is not None and meme.vlm_taslak:
        return VLM_TASLAGI, {"vlm_aciklama": meme.vlm_taslak}
    return None
