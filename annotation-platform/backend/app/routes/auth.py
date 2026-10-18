from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.errors import ApiHatasi
from app.models import User
from app.schemas import LoginRequest, LoginResponse, RegisterRequest, UserOut
from app.security import TOKEN_SURESI_SN, aktif_kullanici, sifre_dogru_mu, sifre_hashle, token_olustur

import uuid

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

@router.post("/register", response_model=LoginResponse, status_code=201)
def register(istek: RegisterRequest, session: Session = Depends(get_session)):
    mevcut = session.exec(
        select(User).where(User.kullanici_adi == istek.kullanici_adi)
    ).first()
    if mevcut is not None:
        raise ApiHatasi(409, "CAKISMA", "Bu kullanıcı adı zaten kullanılıyor.")

    kullanici = User(
        kullanici_adi=istek.kullanici_adi,
        gorunen_ad=istek.kullanici_adi,
        takma_ad=f"u{uuid.uuid4().hex[:10]}",
        sifre_hash=sifre_hashle(istek.sifre),
        admin=False,
    )
    session.add(kullanici)
    session.commit()
    session.refresh(kullanici)
    return LoginResponse(
        erisim_token=token_olustur(kullanici.id),
        sure_sn=TOKEN_SURESI_SN,
        kullanici=UserOut.model_validate(kullanici),
    )

@router.post("/login", response_model=LoginResponse)
def login(istek: LoginRequest, session: Session = Depends(get_session)):
    kullanici = session.exec(
        select(User).where(User.kullanici_adi == istek.kullanici_adi)
    ).first()
    if kullanici is None or not sifre_dogru_mu(istek.sifre, kullanici.sifre_hash):
        raise ApiHatasi(401, "YETKISIZ", "Kullanıcı adı veya şifre hatalı.")
    return LoginResponse(
        erisim_token=token_olustur(kullanici.id),
        sure_sn=TOKEN_SURESI_SN,
        kullanici=UserOut.model_validate(kullanici),
    )

@router.get("/me", response_model=UserOut)
def me(kullanici: User = Depends(aktif_kullanici)):
    return kullanici
