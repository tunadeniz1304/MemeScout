from datetime import datetime, timezone
from typing import Annotated, Literal, Optional

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints


def _utc(zaman: datetime) -> datetime:
    # SQLite saat dilimini saklamaz; okunan naive zamanlar UTC kabul edilir.
    return zaman.replace(tzinfo=timezone.utc) if zaman.tzinfo is None else zaman.astimezone(timezone.utc)


# Yanıtlardaki zamanlar ISO 8601 UTC olarak yazılır (2026-10-15T08:58:00Z).
Zaman = Annotated[datetime, AfterValidator(_utc)]
DoluMetin = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
EtiketAlani = Literal["duygu", "niyet", "mekanizma", "uyari"]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kullanici_adi: str
    gorunen_ad: str
    takma_ad: str
    admin: bool


class UserCreate(BaseModel):
    kullanici_adi: str = Field(min_length=3)
    gorunen_ad: str
    sifre: str = Field(min_length=8)
    takma_ad: str
    admin: bool = False


class LoginRequest(BaseModel):
    kullanici_adi: str
    sifre: str


class RegisterRequest(BaseModel):
    kullanici_adi: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    sifre: str = Field(min_length=8, max_length=128)


class LoginResponse(BaseModel):
    erisim_token: str
    token_tipi: str = "bearer"
    sure_sn: int
    kullanici: UserOut


class UserRefOut(BaseModel):
    id: str
    gorunen_ad: str


class FieldErrorOut(BaseModel):
    alan: str
    kural: str
    mesaj: str


# ------------------------------------------------------------------ şema / etiketler

class AnnotationSchemaOut(BaseModel):
    sema_versiyonu: str
    alanlar: dict[str, dict]


class LabelOut(BaseModel):
    etiket: str
    gorunen_ad: str
    tanim: str
    ornekler: list[str] = []
    aktif: bool
    eklenme_tarihi: Optional[Zaman] = None


class LabelListOut(BaseModel):
    versiyon: str
    olusturma_zamani: Zaman
    alanlar: dict[EtiketAlani, list[LabelOut]]


class LabelListVersionSummaryOut(BaseModel):
    versiyon: str
    olusturma_zamani: Zaman
    olusturan: Optional[UserRefOut] = None
    degisiklik_ozeti: Optional[str] = None


class LabelCreate(BaseModel):
    alan: EtiketAlani
    etiket: str = Field(pattern=r"^[a-z0-9_]+$", max_length=64)
    gorunen_ad: DoluMetin
    tanim: DoluMetin
    ornekler: list[str] = Field(default=[], max_length=2)


class LabelUpdate(BaseModel):
    gorunen_ad: Optional[DoluMetin] = None
    tanim: Optional[DoluMetin] = None
    ornekler: Optional[list[str]] = Field(default=None, max_length=2)
    aktif: Optional[bool] = None
