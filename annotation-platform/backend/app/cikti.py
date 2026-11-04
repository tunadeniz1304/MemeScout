"""Veritabanı kayıtlarından sözleşmedeki yanıt nesnelerini üreten yardımcılar."""

from collections import Counter
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session, select

from app.havuz import SEBEPLER
from app.kurallar import MemeBaglami
from app.models import LabelListVersion, Meme, User
from app.sema import bos_icerik


def iso_zaman(zaman: datetime) -> str:
    """JSON satırları için ISO 8601 UTC (2026-10-15T08:58:00Z); SQLite'tan gelen naive zaman UTC sayılır."""
    zaman = zaman.replace(tzinfo=timezone.utc) if zaman.tzinfo is None else zaman.astimezone(timezone.utc)
    return zaman.isoformat().replace("+00:00", "Z")


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
        "vlm_taslak": meme.vlm_taslak,
        "ai_taslagi_var": meme.id in baglam.ai_taslaklari,
    }


def memeler(session: Session, kayitlar: list[Meme], kullanici: User) -> list[dict]:
    baglam = MemeBaglami(session, [kayit.id for kayit in kayitlar])
    kisiler = kullanicilar(session)
    return [meme(kayit, baglam, kisiler, kullanici) for kayit in kayitlar]


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
        "on_doldurma": annotation.on_doldurma,
    }


def yorum(yorum, kisiler: dict[str, User]) -> dict:
    return {
        "id": yorum.id,
        "meme_id": yorum.meme_id,
        "alan": yorum.alan,
        "yazan": kullanici_ref(kisiler.get(yorum.yazan_id)),
        "zaman": yorum.zaman,
        "metin": yorum.metin,
        "tur": yorum.tur,
        "cozuldu": yorum.cozuldu,
    }


def gold(kayit, kisiler: dict[str, User]) -> dict:
    return {
        "meme_id": kayit.meme_id,
        "icerik": {**bos_icerik(), **kayit.icerik},
        "kaynak_annotationlar": kayit.kaynak_annotationlar,
        "reviewer": kullanici_ref(kisiler.get(kayit.reviewer_id)),
        "cozum_notu": kayit.cozum_notu,
        "onay_zamani": kayit.onay_zamani,
        "sema_versiyonu": kayit.sema_versiyonu,
        "etiket_listesi_versiyonu": kayit.etiket_listesi_versiyonu,
    }


def test_sorgusu(sorgu, kisiler: dict[str, User], cikarilanlar: set[str]) -> dict:
    return {
        "id": sorgu.id,
        "metin": sorgu.metin,
        "mod": sorgu.mod,
        # Çıkarılan meme doğru cevaplarda görünmez; kayıttaki liste değişmez, karar geri alınırsa döner.
        "dogru_memeler": [meme_id for meme_id in sorgu.dogru_memeler if meme_id not in cikarilanlar],
        "yazan": kullanici_ref(kisiler.get(sorgu.yazan_id)),
        "zaman": sorgu.zaman,
    }


def kullanilmasin_oyu(oy, karar: Optional[str]) -> dict:
    return {"meme_id": oy.meme_id, "sebep": oy.sebep, "not": oy.notu, "zaman": oy.zaman, "karar": karar}


def havuz_karari(karar, kisiler: dict[str, User]) -> dict:
    return {
        "meme_id": karar.meme_id,
        "karar": karar.karar,
        "not": karar.notu,
        "karar_veren": kullanici_ref(kisiler.get(karar.karar_veren_id)),
        "zaman": karar.zaman,
    }


def havuz_ogesi(meme_id: str, etiket_durumu: str, oylar: list, son_karar, kisiler: dict[str, User]) -> dict:
    sayilar = Counter(oy.sebep for oy in oylar)
    return {
        "meme_id": meme_id,
        "kucuk_gorsel_url": f"/api/v1/memes/{meme_id}/image?boyut=kucuk",
        "etiket_durumu": etiket_durumu,
        "oy_sayisi": len(oylar),
        "sebepler": [
            {"sebep": sebep, "sayi": sayi}
            for sebep, sayi in sorted(sayilar.items(), key=lambda oge: (-oge[1], SEBEPLER.index(oge[0])))
        ],
        "oylar": [
            {"takma_ad": kisiler[oy.kullanici_id].takma_ad, "sebep": oy.sebep, "not": oy.notu, "zaman": oy.zaman}
            for oy in sorted(oylar, key=lambda oy: (oy.zaman, oy.kullanici_id))
        ],
        "son_karar": havuz_karari(son_karar, kisiler) if son_karar else None,
    }
