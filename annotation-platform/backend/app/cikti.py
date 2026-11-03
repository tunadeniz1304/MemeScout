"""Veritabanı kayıtlarından sözleşmedeki yanıt nesnelerini üreten yardımcılar."""

from typing import Optional

from sqlmodel import Session, select

from app.models import LabelListVersion, Meme, User
from app.sema import bos_icerik


def kullanicilar(session: Session) -> dict[str, User]:
    # Ekip küçük; kullanıcı adlarını tek sorguda almak her kayıt için ayrı sorgudan ucuz.
    return {kullanici.id: kullanici for kullanici in session.exec(select(User)).all()}


def kullanici_ref(kullanici: Optional[User]) -> Optional[dict]:
    if kullanici is None:
        return None
    return {"id": kullanici.id, "gorunen_ad": kullanici.gorunen_ad}


def etiket_listesi(liste: LabelListVersion) -> dict:
    return {"versiyon": liste.versiyon, "olusturma_zamani": liste.olusturma_zamani, "alanlar": liste.alanlar}


def meme(meme: Meme, baglam, kisiler: dict[str, User], kullanici: User) -> dict:
    return {
        "id": meme.id,
        "gorsel_url": f"/api/v1/memes/{meme.id}/image",
        "kucuk_gorsel_url": f"/api/v1/memes/{meme.id}/image?boyut=kucuk",
        "sha256": meme.sha256,
        "yukleyen": kullanici_ref(kisiler.get(meme.yukleyen_id)),
        "yuklenme_zamani": meme.yuklenme_zamani,
        "etiket_durumu": baglam.durum(meme.id),
        "annotatorlar": [kullanici_ref(kisiler.get(kisi_id)) for kisi_id in baglam.annotatorlar(meme.id)],
        "cift_etiket": baglam.cift_etiket(meme.id),
        "gold_var": baglam.gold_var(meme.id),
        "ad": baglam.ad(meme.id),
        "acik_yorum_sayisi": baglam.acik_yorum_sayisi(meme.id, kullanici.id),
    }


def annotation_ozeti(annotation, kisiler: dict[str, User]) -> dict:
    return {
        "id": annotation.id,
        "meme_id": annotation.meme_id,
        "annotator": kullanici_ref(kisiler.get(annotation.annotator_id)),
        "durum_kodu": annotation.durum_kodu,
        "cift_etiket": annotation.cift_etiket,
        "kalibrasyon": annotation.kalibrasyon,
        "gonderme_zamani": annotation.gonderme_zamani,
    }


def annotation(annotation, kisiler: dict[str, User]) -> dict:
    return {
        "id": annotation.id,
        "meme_id": annotation.meme_id,
        "annotator": kullanici_ref(kisiler.get(annotation.annotator_id)),
        "durum_kodu": annotation.durum_kodu,
        "cift_etiket": annotation.cift_etiket,
        "kalibrasyon": annotation.kalibrasyon,
        # Şemaya sonradan eklenen alanlar eski kayıtlarda da görünsün.
        "icerik": {**bos_icerik(), **annotation.icerik},
        "tanidiklik": annotation.tanidiklik,
        "alan_guveni": annotation.alan_guveni,
        "atlandi": annotation.atlandi,
        "revizyon_notu": annotation.revizyon_notu,
        "atanma_zamani": annotation.atanma_zamani,
        "baslama_zamani": annotation.baslama_zamani,
        "gonderme_zamani": annotation.gonderme_zamani,
        "guncellenme_zamani": annotation.guncellenme_zamani,
        "harcanan_sure_sn": annotation.harcanan_sure_sn,
        "sema_versiyonu": annotation.sema_versiyonu,
        "etiket_listesi_versiyonu": annotation.etiket_listesi_versiyonu,
        "surum": annotation.surum,
    }
