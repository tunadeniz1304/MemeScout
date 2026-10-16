from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


def simdi():
    return datetime.now(timezone.utc)


def yeni_id():
    return uuid4().hex


# ---------------------------------------------------------
# 1. Mevcut Modeller (Değiştirilmedi)
# ---------------------------------------------------------
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


# ---------------------------------------------------------
# 2. Yeni Modeller: Tekil Annotator ve Denetim Sistemi
# ---------------------------------------------------------

class Annotation(SQLModel, table=True):
    """Tekil Annotator'ın etiketleme kaydını tutan tablo."""
    id: str = Field(default_factory=yeni_id, primary_key=True)
    meme_id: str = Field(foreign_key="meme.id", index=True)
    annotator_id: str = Field(foreign_key="user.id", index=True)
    
    # atandi, devam_ediyor, gonderildi, revizyon_gerekli, onaylandi, reddedildi
    durum_kodu: str = Field(default="atandi")
    
    # ADR-0005: Deneme amaçlı kalibrasyonları ayırmak için
    kalibrasyon: bool = Field(default=False)
    
    # ADR-0005: Sekme çakışmalarını önlemek için iyimser kilitleme (Optimistic Locking)
    surum: int = Field(default=1)
    
    # JSON sütunu: durum, gorsel_tanim, anahtar_kelimeler gibi esnek form alanlarını tutar
    icerik: dict = Field(default_factory=dict, sa_column=Column(JSON))
    
    # Ekip revizyon istediğinde annotator'ın göreceği not
    revizyon_notu: Optional[str] = None
    
    # Zaman damgaları
    atanma_zamani: datetime = Field(default_factory=simdi)
    baslama_zamani: Optional[datetime] = None
    gonderme_zamani: Optional[datetime] = None
    guncellenme_zamani: Optional[datetime] = None


class Comment(SQLModel, table=True):
    """Ekibin asenkron olarak bıraktığı revizyon ve hata bildirimleri."""
    id: str = Field(default_factory=yeni_id, primary_key=True)
    meme_id: str = Field(foreign_key="meme.id", index=True)
    yazan_id: str = Field(foreign_key="user.id")
    
    metin: str
    # soru, kilavuz_onerisi, hata, kopya_suphesi vb.
    tur: str = Field(default="soru")
    
    # Annotator bu yorumu görüp düzelttiğinde True olur
    cozuldu: bool = Field(default=False)
    zaman: datetime = Field(default_factory=simdi)


class Rating(SQLModel, table=True):
    """ADR-0010: Ekibin 5 üzerinden verdiği oyları tutar. (Ort. < 2.0 = Red)"""
    id: str = Field(default_factory=yeni_id, primary_key=True)
    annotation_id: str = Field(foreign_key="annotation.id", index=True)
    veren_id: str = Field(foreign_key="user.id")  # Puanı veren ekip üyesi
    
    # 1 ile 5 arası yıldız/puan
    puan: int = Field(ge=1, le=5)
    zaman: datetime = Field(default_factory=simdi)