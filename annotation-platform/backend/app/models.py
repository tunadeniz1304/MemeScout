from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import JSON, Column, LargeBinary
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.sema import bos_icerik

# PostgreSQL'de JSONB, testlerdeki SQLite'ta düz JSON.
JSON_TIPI = JSON().with_variant(JSONB(), "postgresql")

def simdi():
    return datetime.now(timezone.utc)

def yeni_id():
    return uuid4().hex

def json_sutunu(nullable: bool = False) -> Column:
    return Column(JSON_TIPI, nullable=nullable)

# Annotation durumları (README "Durum geçişleri")
ATANDI = "atandi"
DEVAM_EDIYOR = "devam_ediyor"
GONDERILDI = "gonderildi"
REVIZYON_GEREKLI = "revizyon_gerekli"
ONAYLANDI = "onaylandi"
ATLANDI = "atlandi"
DURUM_KODLARI = (ATANDI, DEVAM_EDIYOR, GONDERILDI, REVIZYON_GEREKLI, ONAYLANDI, ATLANDI)

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
    # Görselin yorumsuz tarifi (VLM ya da AI taslağından); bir kez dolar, sonra değişmez.
    # Canlıdaki tabloya sonradan eklendi: ALTER TABLE meme ADD COLUMN vlm_taslak VARCHAR
    vlm_taslak: Optional[str] = None

class MemeImage(SQLModel, table=True):
    # Görsel ayrı tabloda tutulur; meme listesi sorguları baytları taşımaz.
    __tablename__ = "meme_image"

    meme_id: str = Field(primary_key=True, foreign_key="meme.id")
    icerik_tipi: str
    veri: bytes = Field(sa_column=Column(LargeBinary, nullable=False))

class AiDraft(SQLModel, table=True):
    # LLM'in hazırladığı kart (ADR-0010). Ham kart değiştirilmeden saklanır; annotator'ın ne kadar
    # düzelttiği bununla ölçülür. `icerik`, kartın şema alanlarıdır ve formu önceden doldurur.
    __tablename__ = "ai_draft"

    meme_id: str = Field(primary_key=True, foreign_key="meme.id")
    kaynak: str
    kart: dict = Field(sa_column=json_sutunu())
    icerik: dict = Field(sa_column=json_sutunu())
    yukleyen_id: str = Field(foreign_key="user.id")
    olusturma_zamani: datetime = Field(default_factory=simdi)

class Annotation(SQLModel, table=True):
    id: str = Field(default_factory=yeni_id, primary_key=True)
    meme_id: str = Field(foreign_key="meme.id", index=True)
    annotator_id: str = Field(foreign_key="user.id", index=True)
    durum_kodu: str = Field(default=ATANDI, index=True)
    cift_etiket: bool = False
    kalibrasyon: bool = False
    icerik: dict = Field(default_factory=bos_icerik, sa_column=json_sutunu())
    tanidiklik: Optional[int] = None
    alan_guveni: dict = Field(default_factory=dict, sa_column=json_sutunu())
    atlandi: Optional[dict] = Field(default=None, sa_column=json_sutunu(nullable=True))
    revizyon_notu: Optional[str] = None
    atanma_zamani: datetime = Field(default_factory=simdi)
    baslama_zamani: Optional[datetime] = None
    gonderme_zamani: Optional[datetime] = None
    guncellenme_zamani: Optional[datetime] = None
    harcanan_sure_sn: int = 0
    sema_versiyonu: Optional[str] = None
    etiket_listesi_versiyonu: Optional[str] = None
    surum: int = 1
    # Form etiketlemeye başlarken neyle dolu geldi: "ai_taslagi", "vlm_taslagi" ya da boş (None).
    on_doldurma: Optional[str] = None
    # Yeniden atamada eski annotation atlandi kalır ve yerine geçen kayda bağlanır.
    yerine_gecen_id: Optional[str] = Field(default=None, foreign_key="annotation.id")

class AnnotationVersion(SQLModel, table=True):
    __tablename__ = "annotation_version"

    id: Optional[int] = Field(default=None, primary_key=True)
    annotation_id: str = Field(foreign_key="annotation.id", index=True)
    surum: int
    zaman: datetime = Field(default_factory=simdi)
    degistiren_id: str = Field(foreign_key="user.id")
    durum_kodu: str
    icerik: dict = Field(sa_column=json_sutunu())

class GoldRecord(SQLModel, table=True):
    __tablename__ = "gold_record"

    meme_id: str = Field(primary_key=True, foreign_key="meme.id")
    icerik: dict = Field(sa_column=json_sutunu())
    kaynak_annotationlar: list = Field(default_factory=list, sa_column=json_sutunu())
    reviewer_id: Optional[str] = Field(default=None, foreign_key="user.id")
    cozum_notu: Optional[str] = None
    onay_zamani: datetime = Field(default_factory=simdi)
    sema_versiyonu: str
    etiket_listesi_versiyonu: str

class Comment(SQLModel, table=True):
    id: str = Field(default_factory=yeni_id, primary_key=True)
    meme_id: str = Field(foreign_key="meme.id", index=True)
    alan: Optional[str] = None
    yazan_id: str = Field(foreign_key="user.id", index=True)
    zaman: datetime = Field(default_factory=simdi)
    metin: str
    tur: str
    cozuldu: bool = False

class LabelListVersion(SQLModel, table=True):
    # Her versiyon listenin tam halini tutar; eski versiyonla etiketlenen kayıtlar bununla karşılaştırılır.
    __tablename__ = "label_list_version"

    sira: int = Field(primary_key=True, sa_column_kwargs={"autoincrement": False})
    versiyon: str = Field(unique=True)
    olusturma_zamani: datetime = Field(default_factory=simdi)
    olusturan_id: Optional[str] = Field(default=None, foreign_key="user.id")
    degisiklik_ozeti: Optional[str] = None
    alanlar: dict = Field(sa_column=json_sutunu())

class TestQuery(SQLModel, table=True):
    __tablename__ = "test_query"
    __test__ = False  # pytest bu sınıfı test sınıfı sanmasın

    id: str = Field(default_factory=yeni_id, primary_key=True)
    metin: str
    mod: str
    dogru_memeler: list = Field(default_factory=list, sa_column=json_sutunu())
    yazan_id: str = Field(foreign_key="user.id", index=True)
    zaman: datetime = Field(default_factory=simdi)

class AuditEntry(SQLModel, table=True):
    __tablename__ = "audit_entry"

    id: Optional[int] = Field(default=None, primary_key=True)
    zaman: datetime = Field(default_factory=simdi, index=True)
    kullanici_id: str = Field(foreign_key="user.id", index=True)
    kayit_tipi: str = Field(index=True)
    kayit_id: str = Field(index=True)
    islem: str
    alan: Optional[str] = None
    eski_deger: Optional[Any] = Field(default=None, sa_column=json_sutunu(nullable=True))
    yeni_deger: Optional[Any] = Field(default=None, sa_column=json_sutunu(nullable=True))
