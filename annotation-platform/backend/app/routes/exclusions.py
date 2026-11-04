"""Kullanılmasın oyu ve admin havuzu (ADR-0011)."""

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Response
from sqlmodel import Session, select

from app import cikti
from app.database import get_session
from app.denetim import GUNCELLEME, MEME, OLUSTURMA, SILME, denetle
from app.errors import ApiHatasi
from app.havuz import CIKARILSIN, cikarilmamis_olmali, son_kararlar
from app.kurallar import MemeBaglami
from app.models import Meme, MemeExclusionDecision, MemeExclusionVote, User, simdi
from app.schemas import (
    ExclusionDecisionIn,
    ExclusionDecisionOut,
    ExclusionPoolItemOut,
    ExclusionVoteIn,
    ExclusionVoteOut,
)
from app.security import admin_kullanici, aktif_kullanici

router = APIRouter(prefix="/api/v1")

# Denetim kaydında meme kaydının hangi alanının değiştiği
OY_ALANI = "kullanilmasin_oyu"
KARAR_ALANI = "havuz_karari"


def meme_kilitle(session: Session, meme_id: str) -> Meme:
    # Karar o ana kadarki oyları sonuçlandırdığı için aynı meme'deki oy ve karar sırayla işlenir.
    meme = session.exec(select(Meme).where(Meme.id == meme_id).with_for_update()).first()
    if meme is None:
        raise ApiHatasi(404, "BULUNAMADI", f"'{meme_id}' adında bir meme yok.")
    return meme


def oyun_karari(session: Session, oy: MemeExclusionVote) -> Optional[str]:
    if oy.karar_id is None:
        return None
    return session.get(MemeExclusionDecision, oy.karar_id).karar


def oy_degeri(session: Session, oy: MemeExclusionVote) -> dict:
    return {"sebep": oy.sebep, "not": oy.notu, "karar": oyun_karari(session, oy)}


def oy_getir(session: Session, meme_id: str, kullanici_id: str) -> MemeExclusionVote:
    oy = session.get(MemeExclusionVote, (meme_id, kullanici_id))
    if oy is None:
        raise ApiHatasi(404, "BULUNAMADI", "Bu meme için oyunuz yok.")
    return oy


@router.get("/memes/{meme_id}/exclusion-vote", response_model=ExclusionVoteOut, tags=["memes"])
def oyum(
    meme_id: str,
    session: Session = Depends(get_session),
    kullanici: User = Depends(aktif_kullanici),
):
    # Kör etiketleme: kişi yalnızca kendi oyunu görür.
    if session.get(Meme, meme_id) is None:
        raise ApiHatasi(404, "BULUNAMADI", f"'{meme_id}' adında bir meme yok.")
    oy = oy_getir(session, meme_id, kullanici.id)
    return cikti.kullanilmasin_oyu(oy, oyun_karari(session, oy))


@router.put("/memes/{meme_id}/exclusion-vote", response_model=ExclusionVoteOut, tags=["memes"])
def oy_ver(
    meme_id: str,
    veri: ExclusionVoteIn,
    session: Session = Depends(get_session),
    kullanici: User = Depends(aktif_kullanici),
):
    meme_kilitle(session, meme_id)
    cikarilmamis_olmali(session, meme_id)
    yeni = {"sebep": veri.sebep, "not": veri.not_, "karar": None}
    oy = session.get(MemeExclusionVote, (meme_id, kullanici.id))
    if oy is None:
        oy = MemeExclusionVote(meme_id=meme_id, kullanici_id=kullanici.id, sebep=veri.sebep, notu=veri.not_)
        session.add(oy)
        denetle(session, kullanici.id, MEME, meme_id, OLUSTURMA, alan=OY_ALANI, yeni=yeni)
    else:
        eski = oy_degeri(session, oy)
        # Kararla sonuçlanmış oy yeniden verilirse yeniden geçerli olur ve meme havuza döner.
        if eski != yeni:
            denetle(session, kullanici.id, MEME, meme_id, GUNCELLEME, alan=OY_ALANI, eski=eski, yeni=yeni)
            oy.sebep, oy.notu, oy.zaman, oy.karar_id = veri.sebep, veri.not_, simdi(), None
    session.commit()
    session.refresh(oy)
    return cikti.kullanilmasin_oyu(oy, None)


@router.delete("/memes/{meme_id}/exclusion-vote", status_code=204, tags=["memes"])
def oyu_geri_cek(
    meme_id: str,
    session: Session = Depends(get_session),
    kullanici: User = Depends(aktif_kullanici),
):
    meme_kilitle(session, meme_id)
    oy = oy_getir(session, meme_id, kullanici.id)
    # Çıkarılan meme'in oyları kararın dayanağıdır; karar geri alınmadan değişmez.
    cikarilmamis_olmali(session, meme_id)
    denetle(session, kullanici.id, MEME, meme_id, SILME, alan=OY_ALANI, eski=oy_degeri(session, oy))
    session.delete(oy)
    session.commit()
    return Response(status_code=204)


@router.get("/exclusion-pool", response_model=list[ExclusionPoolItemOut], tags=["admin"])
def havuz(
    durum: Literal["bekliyor", "cikarildi"] = "bekliyor",
    session: Session = Depends(get_session),
    kullanici: User = Depends(admin_kullanici),
):
    # Admin aracıdır; kör etiketleme kuralına göre süzülmez (ADR-0011).
    kararlar = son_kararlar(session)
    cikarilanlar = {meme_id: karar for meme_id, karar in kararlar.items() if karar.karar == CIKARILSIN}
    oylar: dict[str, list[MemeExclusionVote]] = {}
    if durum == "bekliyor":
        sorgu = select(MemeExclusionVote).where(MemeExclusionVote.karar_id.is_(None))
        for oy in session.exec(sorgu).all():
            if oy.meme_id not in cikarilanlar:
                oylar.setdefault(oy.meme_id, []).append(oy)
        sira = sorted(oylar, key=lambda meme_id: (-len(oylar[meme_id]), meme_id))
    else:
        karar_idleri = [karar.id for karar in cikarilanlar.values()]
        for oy in session.exec(select(MemeExclusionVote).where(MemeExclusionVote.karar_id.in_(karar_idleri))).all():
            oylar.setdefault(oy.meme_id, []).append(oy)
        sira = sorted(cikarilanlar, key=lambda meme_id: -cikarilanlar[meme_id].id)
    baglam = MemeBaglami(session, sira)
    kisiler = cikti.kullanicilar(session)
    return [
        cikti.havuz_ogesi(meme_id, baglam.durum(meme_id), oylar.get(meme_id, []), kararlar.get(meme_id), kisiler)
        for meme_id in sira
    ]


@router.post(
    "/exclusion-pool/{meme_id}/decision",
    response_model=ExclusionDecisionOut,
    status_code=201,
    tags=["admin"],
)
def karar_ver(
    meme_id: str,
    veri: ExclusionDecisionIn,
    session: Session = Depends(get_session),
    kullanici: User = Depends(admin_kullanici),
):
    meme_kilitle(session, meme_id)
    onceki = son_kararlar(session, [meme_id]).get(meme_id)
    cikarilmis = onceki is not None and onceki.karar == CIKARILSIN
    if cikarilmis and veri.karar == CIKARILSIN:
        raise ApiHatasi(409, "MEME_CIKARILDI", "Bu meme zaten kullanımdan çıkarıldı.")
    oylar = session.exec(select(MemeExclusionVote).where(MemeExclusionVote.meme_id == meme_id)).all()
    # Çıkarılmamış meme, karar bekleyen bir oyu varsa havuzdadır.
    if not cikarilmis and all(oy.karar_id is not None for oy in oylar):
        raise ApiHatasi(409, "HAVUZDA_DEGIL", "Bu meme havuzda değil; karar bekleyen oyu yok.")

    karar = MemeExclusionDecision(meme_id=meme_id, karar=veri.karar, notu=veri.not_, karar_veren_id=kullanici.id)
    session.add(karar)
    session.flush()
    # Karar, meme'in o ana kadarki bütün oylarını sonuçlandırır; "kalsın" ile geri alınan
    # çıkarmanın oyları da yeni karara bağlanır.
    for oy in oylar:
        oy.karar_id = karar.id
    denetle(session, kullanici.id, MEME, meme_id, OLUSTURMA, alan=KARAR_ALANI, yeni={"karar": veri.karar, "not": veri.not_})
    session.commit()
    session.refresh(karar)
    return cikti.havuz_karari(karar, cikti.kullanicilar(session))
