"""Denetim kaydı: kim, ne zaman, hangi kaydın hangi alanını değiştirdi (docs/annotation.md §3.8)."""

from typing import Any, Optional

from sqlmodel import Session

from app.models import AuditEntry

# Sözleşmedeki RecordType değerleri
MEME = "meme"
ANNOTATION = "annotation"
GOLD = "gold"
YORUM = "yorum"
ETIKET_LISTESI = "etiket_listesi"
TEST_SORGUSU = "test_sorgusu"
KULLANICI = "kullanici"

# Sözleşmedeki AuditEntry.islem değerleri
OLUSTURMA = "olusturma"
GUNCELLEME = "guncelleme"
DURUM_DEGISIKLIGI = "durum_degisikligi"
SILME = "silme"


def denetle(
    session: Session,
    kullanici_id: str,
    kayit_tipi: str,
    kayit_id: str,
    islem: str,
    alan: Optional[str] = None,
    eski: Any = None,
    yeni: Any = None,
) -> None:
    session.add(
        AuditEntry(
            kullanici_id=kullanici_id,
            kayit_tipi=kayit_tipi,
            kayit_id=str(kayit_id),
            islem=islem,
            alan=alan,
            eski_deger=eski,
            yeni_deger=yeni,
        )
    )


def farklari_denetle(
    session: Session,
    kullanici_id: str,
    kayit_tipi: str,
    kayit_id: str,
    eski: dict,
    yeni: dict,
    onek: str = "",
) -> list[str]:
    """Değişen her alan için ayrı bir kayıt yazar; değişen alan adlarını döner."""
    degisenler = [alan for alan in yeni if eski.get(alan) != yeni.get(alan)]
    for alan in degisenler:
        denetle(session, kullanici_id, kayit_tipi, kayit_id, GUNCELLEME, f"{onek}{alan}", eski.get(alan), yeni.get(alan))
    return degisenler


def kullanici_degeri(kullanici) -> dict:
    # Şifre hash'i denetim kaydına yazılmaz.
    return {
        "kullanici_adi": kullanici.kullanici_adi,
        "gorunen_ad": kullanici.gorunen_ad,
        "takma_ad": kullanici.takma_ad,
        "admin": kullanici.admin,
    }
