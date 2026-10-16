from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

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

# ==========================================
# İÇERİK ŞEMASI (Hashtag ve Karakter Limitleri)
# ==========================================

class AnnotationIcerik(BaseModel):
    gorsel_tanim: str = Field(
        ..., 
        max_length=300, 
        description="Görselin nesnel, objektif tarifi. Kameranın gördükleri."
    )
    durum: str = Field(
        ..., 
        max_length=250, 
        description="Meme'in verdiği soyut duygu, ruh hali veya kullanıldığı bağlam."
    )
    anahtar_kelimeler: List[str] = Field(
        ..., 
        min_length=3, 
        max_length=10, 
        description="Embedder'ı destekleyecek hashtagler, argo ve kestirme terimler."
    )
    baglam_notu: Optional[str] = Field(
        default=None, 
        max_length=150, 
        description="Eğer meme spesifik bir olaya (ör: 2024 olimpiyatları) dayanıyorsa."
    )

# ==========================================
# ANNOTATION ŞEMALARI
# ==========================================

class AnnotationDraftRequest(BaseModel):
    surum: int  # Frontend'in elindeki son sürüm (Çakışma kontrolü için)
    icerik: AnnotationIcerik

class AnnotationSubmitRequest(BaseModel):
    surum: int

class AnnotationResponse(BaseModel):
    id: str
    meme_id: str
    annotator_id: str
    durum_kodu: str
    kalibrasyon: bool
    surum: int
    icerik: AnnotationIcerik
    revizyon_notu: Optional[str]
    gonderme_zamani: Optional[datetime]

# ==========================================
# COMMENT (YORUM) ŞEMALARI
# ==========================================

class CommentCreate(BaseModel):
    metin: str = Field(min_length=1)
    tur: str = "soru" # soru, kilavuz_onerisi, hata

class CommentResponse(BaseModel):
    id: str
    meme_id: str
    yazan_id: str
    metin: str
    tur: str
    cozuldu: bool
    zaman: datetime

# ==========================================
# RATING (PUANLAMA) ŞEMALARI
# ==========================================

class RatingCreate(BaseModel):
    puan: int = Field(ge=1, le=5)

class RatingResponse(BaseModel):
    id: str
    annotation_id: str
    veren_id: str
    puan: int
    zaman: datetime