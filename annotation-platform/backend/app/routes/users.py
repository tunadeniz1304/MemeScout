from fastapi import APIRouter, Depends
from sqlmodel import Session, or_, select

from app.database import get_session
from app.errors import ApiHatasi
from app.models import User
from app.schemas import UserCreate, UserOut
from app.security import admin_kullanici, aktif_kullanici, sifre_hashle

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def kullanicilari_listele(
    session: Session = Depends(get_session),
    _: User = Depends(aktif_kullanici),
):
    return session.exec(select(User)).all()


@router.post("", response_model=UserOut, status_code=201)
def kullanici_olustur(
    veri: UserCreate,
    session: Session = Depends(get_session),
    _: User = Depends(admin_kullanici),
):
    mevcut = session.exec(
        select(User).where(
            or_(User.kullanici_adi == veri.kullanici_adi, User.takma_ad == veri.takma_ad)
        )
    ).first()
    if mevcut:
        raise ApiHatasi(409, "CAKISMA", "Bu kullanıcı adı veya takma ad zaten kullanılıyor.")

    kullanici = User(
        kullanici_adi=veri.kullanici_adi,
        gorunen_ad=veri.gorunen_ad,
        takma_ad=veri.takma_ad,
        sifre_hash=sifre_hashle(veri.sifre),
        admin=veri.admin,
    )
    session.add(kullanici)
    session.commit()
    session.refresh(kullanici)
    return kullanici