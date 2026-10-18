from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Field, SQLModel

def simdi():
    return datetime.now(timezone.utc)

def yeni_id():
    return uuid4().hex

class User(SQLModel, table=True):
    id: str = Field(default_factory=yeni_id, primary_key=True)
    kullanici_adi: str = Field(unique=True, index=True)
    gorunen_ad: str
    takma_ad: str = Field(unique=True)
    sifre_hash: str
    admin: bool = False

class Meme(SQLModel, table=True):
    id: str = Field(primary_key=True)
    gorsel_yolu: str
    sha256: str = Field(unique=True, index=True)
    yukleyen_id: str = Field(foreign_key="user.id")
    yuklenme_zamani: datetime = Field(default_factory=simdi)
