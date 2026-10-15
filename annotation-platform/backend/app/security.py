import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlmodel import Session

from app.database import get_session
from app.errors import ApiHatasi
from app.models import User

SECRET_KEY = os.getenv("SECRET_KEY", "gelistirme-anahtari-degistir")
ALGORITHM = "HS256"
TOKEN_SURESI_SN = 60 * 60 * 12  # 12 saat

sifreleyici = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)


def sifre_hashle(sifre: str) -> str:
    return sifreleyici.hash(sifre)


def sifre_dogru_mu(sifre: str, sifre_hash: str) -> bool:
    return sifreleyici.verify(sifre, sifre_hash)


def token_olustur(kullanici_id: str) -> str:
    bitis = datetime.now(timezone.utc) + timedelta(seconds=TOKEN_SURESI_SN)
    return jwt.encode({"sub": kullanici_id, "exp": bitis}, SECRET_KEY, algorithm=ALGORITHM)


def aktif_kullanici(
    kimlik: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    session: Session = Depends(get_session),
) -> User:
    if kimlik is None:
        raise ApiHatasi(401, "YETKISIZ", "Giriş yapmanız gerekiyor.")
    try:
        veri = jwt.decode(kimlik.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise ApiHatasi(401, "YETKISIZ", "Oturumunuz geçersiz veya süresi dolmuş.")
    kullanici = session.get(User, veri.get("sub"))
    if kullanici is None:
        raise ApiHatasi(401, "YETKISIZ", "Kullanıcı bulunamadı.")
    return kullanici


def admin_kullanici(kullanici: User = Depends(aktif_kullanici)) -> User:
    if not kullanici.admin:
        raise ApiHatasi(403, "YASAK", "Bu işlem için admin yetkisi gerekiyor.")
    return kullanici
