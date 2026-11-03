import os

# database.py motoru ve security.py anahtarı import anında okur; değerler uygulama import edilmeden önce verilmeli.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test-anahtari-en-az-otuz-iki-bayt-uzunlugunda"

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

from app.database import create_db_and_tables, engine
from app.main import app
from app.models import User
from app.security import sifre_hashle

TEST_SIFRESI = "TestSifre123"
# Argon2 bilerek yavaş; her test kullanıcısı için yeniden hesaplamamak için bir kez üretilir.
TEST_SIFRE_HASH = sifre_hashle(TEST_SIFRESI)


@pytest.fixture(autouse=True)
def temiz_veritabani():
    # Her test boş bir veritabanıyla başlar.
    SQLModel.metadata.drop_all(engine)
    create_db_and_tables()
    yield


@pytest.fixture()
def session():
    with Session(engine) as session:
        yield session


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def kullanici_olustur(session):
    def olustur(kullanici_adi: str, admin: bool = False, takma_ad: str | None = None) -> User:
        kullanici = User(
            kullanici_adi=kullanici_adi,
            gorunen_ad=kullanici_adi.capitalize(),
            takma_ad=takma_ad or kullanici_adi,
            sifre_hash=TEST_SIFRE_HASH,
            admin=admin,
        )
        session.add(kullanici)
        session.commit()
        session.refresh(kullanici)
        return kullanici

    return olustur
