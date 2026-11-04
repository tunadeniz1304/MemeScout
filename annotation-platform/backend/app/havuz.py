"""Kullanılmasın oyu ve havuz kuralları (ADR-0011, docs/annotation.md §3.10).

Bir oy, onu sonuçlandıran bir karar yoksa (karar_id boş) geçerlidir ve meme'i havuza düşürür.
Admin'in kararı meme'in o ana kadarki bütün oylarını sonuçlandırır. Meme için geçerli olan, en
son verilen karardır; o karar "cikarilsin" ise meme kullanımdan çıkmıştır.
"""

from typing import Iterable, Optional, get_args

from sqlalchemy import func
from sqlmodel import Session, select

from app.errors import ApiHatasi
from app.models import MemeExclusionDecision
from app.schemas import KullanilmasinSebebi

KALSIN = "kalsin"
CIKARILSIN = "cikarilsin"
# Sözleşmedeki sıra; havuzda eşit sayıda oy alan sebepler bu sırayla listelenir.
SEBEPLER: tuple[str, ...] = get_args(KullanilmasinSebebi)


def son_kararlar(session: Session, meme_idleri: Optional[Iterable[str]] = None) -> dict[str, MemeExclusionDecision]:
    """meme_id → meme için verilen en son karar."""
    son_idler = select(func.max(MemeExclusionDecision.id))
    if meme_idleri is not None:
        son_idler = son_idler.where(MemeExclusionDecision.meme_id.in_(list(meme_idleri)))
    sorgu = select(MemeExclusionDecision).where(
        MemeExclusionDecision.id.in_(son_idler.group_by(MemeExclusionDecision.meme_id))
    )
    return {karar.meme_id: karar for karar in session.exec(sorgu).all()}


def cikarilmis_memeler(session: Session, meme_idleri: Optional[Iterable[str]] = None) -> set[str]:
    return {meme_id for meme_id, karar in son_kararlar(session, meme_idleri).items() if karar.karar == CIKARILSIN}


def cikarilmamis_olmali(session: Session, meme_id: str) -> None:
    if cikarilmis_memeler(session, [meme_id]):
        raise ApiHatasi(409, "MEME_CIKARILDI", "Bu meme havuz kararıyla kullanımdan çıkarıldı.")
