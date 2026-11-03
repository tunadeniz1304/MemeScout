import hashlib
import os

# database.py motoru ve security.py anahtarı import anında okur; değerler uygulama import edilmeden önce verilmeli.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test-anahtari-en-az-otuz-iki-bayt-uzunlugunda"

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

from app.database import create_db_and_tables, engine
from app.main import app
from app.models import Annotation, Meme, MemeImage, User
from app.security import sifre_hashle
from tests.yardimci import png_olustur

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


@pytest.fixture()
def meme_olustur(session):
    sayac = {"n": 0}

    def olustur(yukleyen: User) -> Meme:
        sayac["n"] += 1
        numara = sayac["n"]
        veri = png_olustur(numara)
        meme = Meme(
            id=f"m{numara:04d}",
            gorsel_yolu=f"memes/m{numara:04d}.png",
            sha256=hashlib.sha256(veri).hexdigest(),
            yukleyen_id=yukleyen.id,
        )
        session.add(meme)
        session.flush()
        session.add(MemeImage(meme_id=meme.id, icerik_tipi="image/png", veri=veri))
        session.commit()
        session.refresh(meme)
        return meme

    return olustur


@pytest.fixture()
def annotation_olustur(session):
    def olustur(meme: Meme, annotator: User, **alanlar) -> Annotation:
        annotation = Annotation(meme_id=meme.id, annotator_id=annotator.id, **alanlar)
        session.add(annotation)
        session.commit()
        session.refresh(annotation)
        return annotation

    return olustur
