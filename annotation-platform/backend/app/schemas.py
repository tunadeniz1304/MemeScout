from datetime import datetime, timezone
from typing import Annotated, Any, Literal, Optional

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


# ------------------------------------------------------------------ meme

MemeEtiketDurumu = Literal["atanmadi", "etiketleniyor", "inceleme_bekliyor", "gold_hazir", "yeniden_kontrol"]
DurumKodu = Literal["atandi", "devam_ediyor", "gonderildi", "revizyon_gerekli", "onaylandi", "atlandi"]


class MemeOut(BaseModel):
    id: str
    gorsel_url: str
    kucuk_gorsel_url: str
    sha256: str
    yukleyen: Optional[UserRefOut]
    yuklenme_zamani: Zaman
    etiket_durumu: MemeEtiketDurumu
    annotatorlar: list[UserRefOut]
    cift_etiket: bool
    gold_var: bool
    ad: Optional[str] = None
    acik_yorum_sayisi: int


class AnnotationSummaryOut(BaseModel):
    id: str
    meme_id: str
    annotator: Optional[UserRefOut]
    durum_kodu: DurumKodu
    cift_etiket: bool
    kalibrasyon: bool
    gonderme_zamani: Optional[Zaman] = None


class MemeDetailOut(MemeOut):
    annotasyonlar: list[AnnotationSummaryOut]


class MemePageOut(BaseModel):
    ogeler: list[MemeOut]
    toplam: int
    sayfa: int
    boyut: int


class RejectedFileOut(BaseModel):
    dosya_adi: str
    sebep: Literal["kopya", "desteklenmeyen_tur", "bozuk_dosya"]
    mevcut_meme_id: Optional[str] = None


class BulkUploadResultOut(BaseModel):
    yuklenen: list[MemeOut]
    reddedilen: list[RejectedFileOut]


# ------------------------------------------------------------------ atama

class AssignmentCreate(BaseModel):
    meme_ids: list[str] = Field(min_length=1)
    annotator_id: str
    cift_etiket: bool = False
    kalibrasyon: bool = False


class AutoAssignRequest(BaseModel):
    annotator_ids: list[str] = Field(min_length=2)
    cift_etiket_orani: float = Field(default=0.2, ge=0, le=1)
    dry_run: bool = True


class PlannedAssignmentOut(BaseModel):
    meme_id: str
    annotator_ids: list[str]


class PersonLoadOut(BaseModel):
    annotator: UserRefOut
    meme_sayisi: int


class PairLoadOut(BaseModel):
    ikili: list[UserRefOut]
    meme_sayisi: int


class AutoAssignPlanOut(BaseModel):
    dry_run: bool
    atamalar: list[PlannedAssignmentOut]
    kisi_basi: list[PersonLoadOut]
    ikili_dagilimi: list[PairLoadOut]


class ReassignRequest(BaseModel):
    yeni_annotator_id: str


# ------------------------------------------------------------------ annotation

# Taslakta kurallar uygulanmaz; yalnızca kötüye kullanıma karşı teknik bir üst sınır var.
TaslakMetni = Annotated[str, StringConstraints(max_length=5000)]
TaslakListesi = Annotated[list[TaslakMetni], Field(max_length=50)]


class AnnotationContentIn(BaseModel):
    """Taslak içeriği: tüm alanlar opsiyonel, yalnızca gönderilen alanlar güncellenir."""

    tur: Optional[TaslakMetni] = None
    ad: Optional[TaslakMetni] = None
    kaynak: Optional[TaslakMetni] = None
    vlm_aciklama: Optional[TaslakMetni] = None
    durum: Optional[TaslakMetni] = None
    ornek_durumlar: Optional[TaslakListesi] = None
    uygun_olmayan_durumlar: Optional[TaslakListesi] = None
    kulturel_bilgi: Optional[TaslakMetni] = None
    anahtar_kelimeler: Optional[TaslakListesi] = None
    duygu: Optional[TaslakListesi] = None
    niyet: Optional[TaslakListesi] = None
    mekanizma: Optional[TaslakListesi] = None
    uyari: Optional[TaslakListesi] = None
    notlar: Optional[TaslakMetni] = None


class AnnotationDraftIn(BaseModel):
    surum: int
    icerik: Optional[AnnotationContentIn] = None
    tanidiklik: Optional[int] = Field(default=None, ge=1, le=5)
    alan_guveni: Optional[dict[str, Annotated[int, Field(ge=1, le=3)]]] = None
    aktif_sure_artis_sn: Optional[int] = Field(default=None, ge=0)


class DraftSavedOut(BaseModel):
    surum: int
    guncellenme_zamani: Zaman
    harcanan_sure_sn: int


class SubmitIn(BaseModel):
    surum: int


class SkipRequestIn(BaseModel):
    gerekce: Literal["tanimiyorum", "tanidiklik_dusuk", "uygun_degil", "diger"]
    aciklama: Optional[str] = Field(default=None, max_length=1000)
    tanidiklik: Optional[int] = Field(default=None, ge=1, le=5)


class SkipInfoOut(BaseModel):
    gerekce: str
    aciklama: Optional[str] = None


class AnnotationOut(BaseModel):
    id: str
    meme_id: str
    annotator: Optional[UserRefOut]
    durum_kodu: DurumKodu
    cift_etiket: bool
    kalibrasyon: bool
    icerik: dict
    tanidiklik: Optional[int] = None
    alan_guveni: dict[str, int]
    atlandi: Optional[SkipInfoOut] = None
    revizyon_notu: Optional[str] = None
    atanma_zamani: Zaman
    baslama_zamani: Optional[Zaman] = None
    gonderme_zamani: Optional[Zaman] = None
    guncellenme_zamani: Optional[Zaman] = None
    harcanan_sure_sn: int
    sema_versiyonu: Optional[str] = None
    etiket_listesi_versiyonu: Optional[str] = None
    surum: int


class ValidationResultOut(BaseModel):
    gecerli: bool
    hatalar: list[FieldErrorOut]


class AnnotationVersionOut(BaseModel):
    surum: int
    zaman: Zaman
    degistiren: Optional[UserRefOut]
    durum_kodu: DurumKodu
    icerik: dict


class QueueItemOut(BaseModel):
    annotation_id: str
    meme_id: str
    kucuk_gorsel_url: str
    durum_kodu: DurumKodu
    cift_etiket: bool
    kalibrasyon: bool
    guncellenme_zamani: Optional[Zaman] = None
    revizyon_notu: Optional[str] = None


# ------------------------------------------------------------------ yorum

YorumTuru = Literal["soru", "kilavuz_onerisi", "kopya_suphesi", "hata"]


class CommentCreateIn(BaseModel):
    alan: Optional[str] = None
    metin: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    tur: YorumTuru


class CommentUpdateIn(BaseModel):
    cozuldu: bool


class CommentOut(BaseModel):
    id: str
    meme_id: str
    alan: Optional[str] = None
    yazan: Optional[UserRefOut]
    zaman: Zaman
    metin: str
    tur: YorumTuru
    cozuldu: bool


class CommentPageOut(BaseModel):
    ogeler: list[CommentOut]
    toplam: int
    sayfa: int
    boyut: int


# ------------------------------------------------------------------ review / gold

class ReviewQueueItemOut(BaseModel):
    meme_id: str
    kucuk_gorsel_url: str
    annotation_ids: list[str]
    cift_etiket: bool
    son_gonderme_zamani: Optional[Zaman] = None


class ComparisonOut(BaseModel):
    alan: str
    ayni: bool
    ortak_etiketler: Optional[list[str]] = None


class ReviewDetailOut(BaseModel):
    meme: MemeOut
    annotasyonlar: list[AnnotationOut]
    karsilastirma: list[ComparisonOut]


class GoldCreateIn(BaseModel):
    # İçerik alan alan sunucuda doğrulanır; hatalar gönderimdeki gibi alan adıyla döner.
    icerik: dict
    kaynak_annotationlar: list[str] = Field(min_length=1)
    cozum_notu: Optional[str] = Field(default=None, max_length=2000)


class GoldRecordOut(BaseModel):
    meme_id: str
    icerik: dict
    kaynak_annotationlar: list[str]
    reviewer: Optional[UserRefOut] = None
    cozum_notu: Optional[str] = None
    onay_zamani: Zaman
    sema_versiyonu: str
    etiket_listesi_versiyonu: str


class RevisionRequestIn(BaseModel):
    not_: DoluMetin = Field(alias="not")


# ------------------------------------------------------------------ test sorgusu

SorguModu = Literal["durum", "tarif"]
SorguMetni = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=2000)]


class TestQueryCreateIn(BaseModel):
    __test__ = False  # pytest bu sınıfı test sınıfı sanmasın

    metin: SorguMetni
    mod: SorguModu
    dogru_memeler: list[str] = Field(min_length=1)


class TestQueryUpdateIn(BaseModel):
    __test__ = False

    metin: Optional[SorguMetni] = None
    mod: Optional[SorguModu] = None
    dogru_memeler: Optional[list[str]] = Field(default=None, min_length=1)


class TestQueryOut(BaseModel):
    __test__ = False

    id: str
    metin: str
    mod: SorguModu
    dogru_memeler: list[str]
    yazan: Optional[UserRefOut]
    zaman: Zaman


# ------------------------------------------------------------------ istatistik

class OverallProgressOut(BaseModel):
    toplam_meme: int
    atanmamis: int
    gold_hazir: int
    inceleme_bekleyen: int
    yeniden_atama_bekleyen: int


class UserProgressOut(BaseModel):
    kullanici: UserRefOut
    atanan: int
    tamamlanan: int
    kalan: int
    atlanan: int
    revizyon_bekleyen: int
    ortalama_sure_sn: Optional[float] = None


class ProgressStatsOut(BaseModel):
    genel: OverallProgressOut
    kullanicilar: list[UserProgressOut]


class FieldAgreementOut(BaseModel):
    alan: Literal["tur", "duygu", "niyet", "mekanizma", "uyari"]
    metrik: Literal["cohen_kappa", "krippendorff_alpha_masi"]
    deger: Optional[float]
    n: int
    dusuk_uyum: bool


class LabelAgreementOut(BaseModel):
    alan: EtiketAlani
    etiket: str
    kappa: Optional[float]
    anlasmazlik_sayisi: int
    kullanim_sayisi: int


class AgreementStatsOut(BaseModel):
    hesaplama_zamani: Zaman
    cift_etiketli_meme_sayisi: int
    alanlar: list[FieldAgreementOut]
    etiketler: Optional[list[LabelAgreementOut]] = None


# ------------------------------------------------------------------ admin

KayitTipi = Literal["meme", "annotation", "gold", "yorum", "etiket_listesi", "test_sorgusu", "kullanici"]


class AffectedLabelOut(BaseModel):
    alan: EtiketAlani
    etiket: str
    degisiklik: Literal["pasiflestirildi", "tanim_degisti"]


class RecheckItemOut(BaseModel):
    kayit_tipi: Literal["annotation", "gold"]
    kayit_id: str
    meme_id: str
    eski_versiyon: str
    etkilenen_etiketler: list[AffectedLabelOut]


class AuditEntryOut(BaseModel):
    id: str
    zaman: Zaman
    kullanici: Optional[UserRefOut]
    kayit_tipi: KayitTipi
    kayit_id: str
    islem: Literal["olusturma", "guncelleme", "durum_degisikligi", "silme"]
    alan: Optional[str] = None
    eski_deger: Any = None
    yeni_deger: Any = None


class AuditPageOut(BaseModel):
    ogeler: list[AuditEntryOut]
    toplam: int
    sayfa: int
    boyut: int
