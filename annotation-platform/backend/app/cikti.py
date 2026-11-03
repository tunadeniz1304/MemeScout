"""Veritabanı kayıtlarından sözleşmedeki yanıt nesnelerini üreten yardımcılar."""

from typing import Optional

from sqlmodel import Session, select

from app.models import LabelListVersion, User


def kullanicilar(session: Session) -> dict[str, User]:
    # Ekip küçük; kullanıcı adlarını tek sorguda almak her kayıt için ayrı sorgudan ucuz.
    return {kullanici.id: kullanici for kullanici in session.exec(select(User)).all()}


def kullanici_ref(kullanici: Optional[User]) -> Optional[dict]:
    if kullanici is None:
        return None
    return {"id": kullanici.id, "gorunen_ad": kullanici.gorunen_ad}


def etiket_listesi(liste: LabelListVersion) -> dict:
    return {"versiyon": liste.versiyon, "olusturma_zamani": liste.olusturma_zamani, "alanlar": liste.alanlar}
