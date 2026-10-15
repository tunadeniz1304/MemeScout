from pydantic import BaseModel, ConfigDict, Field


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
