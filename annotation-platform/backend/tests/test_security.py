import pytest
from datetime import datetime, timedelta, timezone
import jwt
from fastapi.security import HTTPAuthorizationCredentials

from app.security import (
    sifre_hashle,
    sifre_dogru_mu,
    token_olustur,
    aktif_kullanici,
    admin_kullanici,
    TOKEN_SURESI_SN,
    SECRET_KEY,
    ALGORITHM,
)
from app.errors import ApiHatasi
from app.models import User

class DummySession:
    def __init__(self, user):
        self.user = user

    def get(self, model, key):
        # Basit get implementation
        if model == User and key == self.user.id:
            return self.user
        return None

def test_password_hashing_and_verification():
    password = "StrongPass123!"
    hashed = sifre_hashle(password)
    assert sifre_dogru_mu(password, hashed)
    assert not sifre_dogru_mu("WrongPass", hashed)

def test_token_creation_and_structure():
    user_id = "user123"
    token = token_olustur(user_id)
    decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert decoded["sub"] == user_id
    assert "exp" in decoded

def test_aktif_kullanici_valid_token():
    user = User(id="u1", kullanici_adi="testuser", gorunen_ad="Test", takma_ad="t1", sifre_hash="hashed", admin=False)
    token = token_olustur(user.id)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    session = DummySession(user)

    # aktif_kullanici senkron fonksiyon ise direkt çağırılır
    result = aktif_kullanici(kimlik=credentials, session=session)
    assert result == user

def test_aktif_kullanici_no_token():
    with pytest.raises(ApiHatasi) as exc:
        aktif_kullanici(kimlik=None, session=None)
    assert exc.value.status_kodu == 401

def test_aktif_kullanici_invalid_token():
    bad_token = "bad.token.value"
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=bad_token)
    with pytest.raises(ApiHatasi) as exc:
        aktif_kullanici(kimlik=credentials, session=None)
    assert exc.value.status_kodu == 401

def test_admin_kullanici_access_granted():
    user = User(id="u1", kullanici_adi="admin", gorunen_ad="Admin", takma_ad="a1", sifre_hash="hashed", admin=True)
    result = admin_kullanici(kullanici=user)
    assert result == user

def test_admin_kullanici_access_denied():
    user = User(id="u2", kullanici_adi="user", gorunen_ad="User", takma_ad="u2", sifre_hash="hashed", admin=False)
    with pytest.raises(ApiHatasi) as exc:
        admin_kullanici(kullanici=user)
    assert exc.value.status_kodu == 403
