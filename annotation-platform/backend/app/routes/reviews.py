from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app import cikti
from app.database import get_session
from app.denetim import ANNOTATION, GOLD, GUNCELLEME, OLUSTURMA, denetle
from app.errors import ApiHatasi
from app.etiketler import guncel_liste
from app.kurallar import (
    MemeBaglami,
    annotation_gorebilir_mi,
    gold_gorebilir_mi,
    grubu,
    incelemeye_hazir_mi,
    meme_annotationlari,
    reviewer_olabilir_mi,
)
from app.models import GONDERILDI, ONAYLANDI, REVIZYON_GEREKLI, Annotation, GoldRecord, User
from app.routes.annotations import annotation_getir, durumda_olmali, durumu_degistir, kaydet_ve_don
from app.routes.memes import meme_getir
from app.schemas import AnnotationOut, GoldCreateIn, GoldRecordOut, RevisionRequestIn, ReviewDetailOut, ReviewQueueItemOut
from app.security import aktif_kullanici
from app.sema import ALAN_KURALLARI, SEMA_VERSIYONU, icerik_dogrula

router = APIRouter(prefix="/api/v1", tags=["reviews"])


def reviewer_olmali(kullanici: User, meme_annotationlari: list) -> None:
    if not reviewer_olabilir_mi(kullanici.id, meme_annotationlari):
        raise ApiHatasi(403, "REVIEWER_ANNOTATOR_OLAMAZ", "Bu meme'i etiketleyen kişi reviewer olamaz.")


def inceleme_annotationlari(session: Session, meme_id: str) -> list[Annotation]:
    """Ana turdaki atlanmamış annotation'lar, gönderilme sırasıyla."""
    annotationlar = session.exec(
        select(Annotation).where(Annotation.meme_id == meme_id, Annotation.kalibrasyon == False)  # noqa: E712
    ).all()
    return sorted(grubu(annotationlar, False), key=lambda a: (a.gonderme_zamani is None, a.gonderme_zamani, a.id))


def karsilastir(birinci: dict, ikinci: dict) -> list[dict]:
    sonuc = []
    for alan, kural in ALAN_KURALLARI.items():
        a, b = birinci.get(alan), ikinci.get(alan)
        if kural["tip"] == "etiket_listesi":
            a, b = a or [], b or []
            # Etiket alanlarında küme eşitliği; ortak etiketler ilk annotation'daki sırayla.
            sonuc.append({"alan": alan, "ayni": set(a) == set(b), "ortak_etiketler": [e for e in a if e in b]})
        else:
            sonuc.append({"alan": alan, "ayni": a == b})
    return sonuc


@router.get("/reviews", response_model=list[ReviewQueueItemOut])
def inceleme_kuyrugu(
    session: Session = Depends(get_session),
    kullanici: User = Depends(aktif_kullanici),
):
    baglam = MemeBaglami(session)
    kuyruk = []
    for meme_id, annotationlar in baglam.annotationlar.items():
        if baglam.gold_var(meme_id) or not incelemeye_hazir_mi(annotationlar):
            continue
        if not reviewer_olabilir_mi(kullanici.id, annotationlar):
            continue
        gonderilenler = grubu(annotationlar, False)
        kuyruk.append({
            "meme_id": meme_id,
            "kucuk_gorsel_url": f"/api/v1/memes/{meme_id}/image?boyut=kucuk",
            "annotation_ids": [a.id for a in gonderilenler],
            "cift_etiket": baglam.cift_etiket(meme_id),
            "son_gonderme_zamani": max(a.gonderme_zamani for a in gonderilenler),
        })
    # En uzun bekleyen önce.
    return sorted(kuyruk, key=lambda oge: (oge["son_gonderme_zamani"], oge["meme_id"]))


@router.get("/reviews/{meme_id}", response_model=ReviewDetailOut)
def inceleme_detayi(
    meme_id: str,
    session: Session = Depends(get_session),
    kullanici: User = Depends(aktif_kullanici),
):
    meme = meme_getir(session, meme_id)
    tum_annotationlar = meme_annotationlari(session, meme_id)
    reviewer_olmali(kullanici, tum_annotationlar)
    gold_var = session.get(GoldRecord, meme_id) is not None
    if not gold_var and not incelemeye_hazir_mi(tum_annotationlar):
        raise ApiHatasi(409, "GECERSIZ_DURUM_GECISI", "Bu meme'in annotation'ları henüz gönderilmedi.")

    annotationlar = inceleme_annotationlari(session, meme_id)
    kisiler = cikti.kullanicilar(session)
    karsilastirma = karsilastir(annotationlar[0].icerik, annotationlar[1].icerik) if len(annotationlar) == 2 else []
    return {
        "meme": cikti.memeler(session, [meme], kullanici)[0],
        "annotasyonlar": [cikti.annotation(a, kisiler) for a in annotationlar],
        "karsilastirma": karsilastirma,
    }


@router.post("/reviews/{meme_id}/gold", response_model=GoldRecordOut, status_code=201)
def gold_onayla(
    meme_id: str,
    veri: GoldCreateIn,
    session: Session = Depends(get_session),
    kullanici: User = Depends(aktif_kullanici),
):
    meme_getir(session, meme_id)
    tum_annotationlar = meme_annotationlari(session, meme_id)
    reviewer_olmali(kullanici, tum_annotationlar)
    if session.get(GoldRecord, meme_id) is not None:
        raise ApiHatasi(409, "GECERSIZ_DURUM_GECISI", "Bu meme'in gold kaydı zaten var.")
    if not incelemeye_hazir_mi(tum_annotationlar):
        raise ApiHatasi(409, "GECERSIZ_DURUM_GECISI", "Bu meme'in annotation'ları henüz gönderilmedi.")

    gonderilenler = session.exec(
        select(Annotation)
        .where(Annotation.meme_id == meme_id, Annotation.kalibrasyon == False, Annotation.durum_kodu == GONDERILDI)  # noqa: E712
        .with_for_update()
    ).all()
    gecerli_idler = {a.id for a in gonderilenler}
    hatalar = []
    for sira, annotation_id in enumerate(veri.kaynak_annotationlar):
        yol = f"kaynak_annotationlar[{sira}]"
        if veri.kaynak_annotationlar.index(annotation_id) != sira:
            hatalar.append({"alan": yol, "kural": "tekrar", "mesaj": "Bu annotation listede tekrar ediyor."})
        elif annotation_id not in gecerli_idler:
            hatalar.append({"alan": yol, "kural": "gecersiz_deger", "mesaj": "Bu meme'in gönderilmiş annotation'larından biri değil."})
    liste = guncel_liste(session)
    icerik = {alan: veri.icerik.get(alan) for alan in ALAN_KURALLARI}
    hatalar += icerik_dogrula(icerik, liste.alanlar)
    if hatalar:
        raise ApiHatasi(422, "DOGRULAMA", "Gold kaydı için bazı alanlar eksik veya hatalı.", alanlar=hatalar)

    kayit = GoldRecord(
        meme_id=meme_id,
        icerik=icerik,
        kaynak_annotationlar=veri.kaynak_annotationlar,
        reviewer_id=kullanici.id,
        cozum_notu=veri.cozum_notu,
        sema_versiyonu=SEMA_VERSIYONU,
        etiket_listesi_versiyonu=liste.versiyon,
    )
    session.add(kayit)
    denetle(session, kullanici.id, GOLD, meme_id, OLUSTURMA, yeni={
        "kaynak_annotationlar": veri.kaynak_annotationlar,
        "cozum_notu": veri.cozum_notu,
        "icerik": icerik,
    })
    for annotation in gonderilenler:
        durumu_degistir(session, annotation, ONAYLANDI, kullanici)
    session.commit()
    session.refresh(kayit)
    return cikti.gold(kayit, cikti.kullanicilar(session))


@router.post("/annotations/{annotation_id}/request-revision", response_model=AnnotationOut)
def revizyon_iste(
    annotation_id: str,
    veri: RevisionRequestIn,
    session: Session = Depends(get_session),
    kullanici: User = Depends(aktif_kullanici),
):
    annotation = annotation_getir(session, annotation_id, kilitle=True)
    tum_annotationlar = meme_annotationlari(session, annotation.meme_id)
    reviewer_olmali(kullanici, tum_annotationlar)
    if annotation.kalibrasyon:
        raise ApiHatasi(409, "GECERSIZ_DURUM_GECISI", "Kalibrasyon annotation'ları incelemeye girmez.")
    durumda_olmali(annotation, (GONDERILDI,), "revizyon isteği")
    if not annotation_gorebilir_mi(kullanici, annotation, tum_annotationlar):
        raise ApiHatasi(403, "KOR_ETIKETLEME", "Bu annotation, meme'in bütün annotation'ları gönderilene kadar gizli.")
    denetle(
        session, kullanici.id, ANNOTATION, annotation.id, GUNCELLEME,
        alan="revizyon_notu", eski=annotation.revizyon_notu, yeni=veri.not_,
    )
    annotation.revizyon_notu = veri.not_
    durumu_degistir(session, annotation, REVIZYON_GEREKLI, kullanici)
    return kaydet_ve_don(session, annotation)


@router.get("/memes/{meme_id}/gold", response_model=GoldRecordOut, tags=["memes"])
def meme_gold_kaydi(
    meme_id: str,
    session: Session = Depends(get_session),
    kullanici: User = Depends(aktif_kullanici),
):
    meme_getir(session, meme_id)
    if not gold_gorebilir_mi(kullanici.id, meme_annotationlari(session, meme_id)):
        raise ApiHatasi(403, "KOR_ETIKETLEME", "Kendi annotation'ını göndermeden bu meme'in gold kaydını göremezsin.")
    kayit = session.get(GoldRecord, meme_id)
    if kayit is None:
        raise ApiHatasi(404, "BULUNAMADI", "Bu meme'in gold kaydı yok.")
    return cikti.gold(kayit, cikti.kullanicilar(session))
