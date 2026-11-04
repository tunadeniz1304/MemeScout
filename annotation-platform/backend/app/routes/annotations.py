from typing import Optional

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app import cikti
from app.ai_taslak import on_doldurma
from app.database import get_session
from app.denetim import ANNOTATION, DURUM_DEGISIKLIGI, GUNCELLEME, denetle, farklari_denetle
from app.errors import ApiHatasi
from app.etiketler import guncel_liste
from app.havuz import cikarilmamis_olmali, cikarilmis_memeler
from app.kurallar import BEKLEYEN_DURUMLAR, annotation_gorebilir_mi, meme_annotationlari
from app.models import (
    ATANDI,
    ATLANDI,
    DEVAM_EDIYOR,
    DURUM_KODLARI,
    GONDERILDI,
    REVIZYON_GEREKLI,
    Annotation,
    AnnotationVersion,
    User,
    simdi,
)
from app.routes.assignments import atlananin_yerine_ata, ikinci_annotator_ekle
from app.schemas import (
    AnnotationDraftIn,
    AnnotationOut,
    AnnotationVersionOut,
    DraftSavedOut,
    QueueItemOut,
    SkipRequestIn,
    SubmitIn,
    ValidationResultOut,
)
from app.security import aktif_kullanici
from app.sema import ALAN_KURALLARI, LISTE_TIPLERI, SEMA_VERSIYONU, bos_icerik, icerik_dogrula

router = APIRouter(prefix="/api/v1", tags=["annotations"])

DUZENLENEBILIR = (DEVAM_EDIYOR, REVIZYON_GEREKLI)
# Kuyrukta önce revizyon bekleyenler, sonra yarım kalanlar gelir.
KUYRUK_SIRASI = {REVIZYON_GEREKLI: 0, DEVAM_EDIYOR: 1, ATANDI: 2}
# aktif_sure_artis_sn bundan büyükse kırpılır (sekme açık unutulduysa süre şişmesin).
AZAMI_SURE_ARTISI = 300


def annotation_getir(session: Session, annotation_id: str, kilitle: bool = False) -> Annotation:
    sorgu = select(Annotation).where(Annotation.id == annotation_id)
    if kilitle:
        # Aynı annotation'a aynı anda gelen iki istek sürümü birlikte geçemesin.
        sorgu = sorgu.with_for_update()
    annotation = session.exec(sorgu).first()
    if annotation is None:
        raise ApiHatasi(404, "BULUNAMADI", "Annotation bulunamadı.")
    return annotation


def sahibi_olmali(annotation: Annotation, kullanici: User) -> None:
    if annotation.annotator_id != kullanici.id:
        raise ApiHatasi(403, "YASAK", "Bu işlemi yalnızca annotation'ın sahibi yapabilir.")


def gorebilmeli(session: Session, annotation: Annotation, kullanici: User) -> None:
    if not annotation_gorebilir_mi(kullanici, annotation, meme_annotationlari(session, annotation.meme_id)):
        raise ApiHatasi(
            403, "KOR_ETIKETLEME",
            "Kör etiketleme sürüyor: bu annotation, meme'in bütün annotation'ları gönderilene kadar gizli.",
        )


def durumda_olmali(annotation: Annotation, durumlar: tuple, islem: str) -> None:
    if annotation.durum_kodu not in durumlar:
        raise ApiHatasi(
            409, "GECERSIZ_DURUM_GECISI",
            f"'{annotation.durum_kodu}' durumundaki annotation için {islem} yapılamaz.",
            detay={"durum_kodu": annotation.durum_kodu},
        )


def surum_eslesmeli(annotation: Annotation, surum: int) -> None:
    if annotation.surum != surum:
        raise ApiHatasi(
            409, "SURUM_CAKISMASI",
            "Bu annotation başka bir sekmede güncellendi.",
            detay={"guncel_surum": annotation.surum},
        )


def durumu_degistir(session: Session, annotation: Annotation, yeni_durum: str, kullanici: User) -> None:
    denetle(
        session, kullanici.id, ANNOTATION, annotation.id, DURUM_DEGISIKLIGI,
        alan="durum_kodu", eski=annotation.durum_kodu, yeni=yeni_durum,
    )
    annotation.durum_kodu = yeni_durum
    annotation.guncellenme_zamani = simdi()


def kaydet_ve_don(session: Session, annotation: Annotation) -> dict:
    session.commit()
    session.refresh(annotation)
    return cikti.annotation(annotation, cikti.kullanicilar(session))


def dogrulama_hatalari(session: Session, annotation: Annotation) -> list[dict]:
    hatalar = icerik_dogrula(annotation.icerik, guncel_liste(session).alanlar)
    if annotation.tanidiklik in (1, 2):
        hatalar.insert(0, {
            "alan": "tanidiklik",
            "kural": "aralik",
            "mesaj": "Tanıdıklık 1 veya 2 iken annotation gönderilemez; bu işi atla, başka birine atanır.",
        })
    return hatalar


@router.get("/me/queue", response_model=list[QueueItemOut])
def kuyrugum(
    durum_kodu: Optional[str] = None,
    session: Session = Depends(get_session),
    kullanici: User = Depends(aktif_kullanici),
):
    if durum_kodu:
        durumlar = [parca.strip() for parca in durum_kodu.split(",") if parca.strip()]
        bilinmeyen = [durum for durum in durumlar if durum not in DURUM_KODLARI]
        if bilinmeyen:
            raise ApiHatasi(422, "DOGRULAMA", "Bilinmeyen durum kodu.", alanlar=[
                {"alan": "durum_kodu", "kural": "gecersiz_deger", "mesaj": f"Geçerli değerler: {', '.join(DURUM_KODLARI)}."}
            ])
    else:
        durumlar = list(BEKLEYEN_DURUMLAR)
    satirlar = session.exec(
        select(
            Annotation.id,
            Annotation.meme_id,
            Annotation.durum_kodu,
            Annotation.cift_etiket,
            Annotation.kalibrasyon,
            Annotation.guncellenme_zamani,
            Annotation.revizyon_notu,
            Annotation.atanma_zamani,
        ).where(Annotation.annotator_id == kullanici.id, Annotation.durum_kodu.in_(durumlar))
    ).all()
    # Havuz kararıyla çıkarılan meme'lerin işleri kuyrukta görünmez (ADR-0011).
    cikarilanlar = cikarilmis_memeler(session, {satir.meme_id for satir in satirlar})
    # Kalibrasyon turu ana turdan önce yapılır.
    satirlar = sorted(
        (satir for satir in satirlar if satir.meme_id not in cikarilanlar),
        key=lambda satir: (not satir.kalibrasyon, KUYRUK_SIRASI.get(satir.durum_kodu, 9), satir.atanma_zamani, satir.meme_id),
    )
    return [
        {
            "annotation_id": satir.id,
            "meme_id": satir.meme_id,
            "kucuk_gorsel_url": f"/api/v1/memes/{satir.meme_id}/image?boyut=kucuk",
            "durum_kodu": satir.durum_kodu,
            "cift_etiket": satir.cift_etiket,
            "kalibrasyon": satir.kalibrasyon,
            "guncellenme_zamani": satir.guncellenme_zamani,
            "revizyon_notu": satir.revizyon_notu,
        }
        for satir in satirlar
    ]


@router.get("/annotations/{annotation_id}", response_model=AnnotationOut)
def annotation_detayi(
    annotation_id: str,
    session: Session = Depends(get_session),
    kullanici: User = Depends(aktif_kullanici),
):
    annotation = annotation_getir(session, annotation_id)
    gorebilmeli(session, annotation, kullanici)
    return cikti.annotation(annotation, cikti.kullanicilar(session))


@router.post("/annotations/{annotation_id}/start", response_model=AnnotationOut)
def baslat(
    annotation_id: str,
    session: Session = Depends(get_session),
    kullanici: User = Depends(aktif_kullanici),
):
    annotation = annotation_getir(session, annotation_id, kilitle=True)
    sahibi_olmali(annotation, kullanici)
    cikarilmamis_olmali(session, annotation.meme_id)
    if annotation.durum_kodu in DUZENLENEBILIR:
        # Zaten başlamış: aynı annotation döner.
        return cikti.annotation(annotation, cikti.kullanicilar(session))
    durumda_olmali(annotation, (ATANDI,), "başlatma")
    durumu_degistir(session, annotation, DEVAM_EDIYOR, kullanici)
    annotation.baslama_zamani = annotation.guncellenme_zamani
    annotation.sema_versiyonu = SEMA_VERSIYONU
    annotation.etiket_listesi_versiyonu = guncel_liste(session).versiyon
    doldurma = on_doldurma(session, annotation)
    if doldurma:
        kaynak, icerik = doldurma
        annotation.icerik = {**bos_icerik(), **icerik}
        annotation.on_doldurma = kaynak
        denetle(session, kullanici.id, ANNOTATION, annotation.id, GUNCELLEME, alan="on_doldurma", eski=None, yeni=kaynak)
        # Taslak revizyon geçmişinin ilk sürümü olur; annotator'ın ne kadar düzelttiği görülür.
        session.add(AnnotationVersion(
            annotation_id=annotation.id,
            surum=annotation.surum,
            degistiren_id=kullanici.id,
            durum_kodu=annotation.durum_kodu,
            icerik=annotation.icerik,
        ))
    return kaydet_ve_don(session, annotation)


def _icerik_degisikligi(veri: AnnotationDraftIn) -> dict:
    if veri.icerik is None:
        return {}
    degisiklik = veri.icerik.model_dump(exclude_unset=True)
    for alan, deger in degisiklik.items():
        # uyari dışındaki listelerde null "boş liste" demektir; uyari'da null "cevaplanmadı"dır.
        if deger is None and ALAN_KURALLARI[alan]["tip"] in LISTE_TIPLERI and alan != "uyari":
            degisiklik[alan] = []
    return degisiklik


@router.patch("/annotations/{annotation_id}/draft", response_model=DraftSavedOut)
def taslak_kaydet(
    annotation_id: str,
    veri: AnnotationDraftIn,
    session: Session = Depends(get_session),
    kullanici: User = Depends(aktif_kullanici),
):
    annotation = annotation_getir(session, annotation_id, kilitle=True)
    sahibi_olmali(annotation, kullanici)
    cikarilmamis_olmali(session, annotation.meme_id)
    durumda_olmali(annotation, DUZENLENEBILIR, "taslak kaydı")
    surum_eslesmeli(annotation, veri.surum)
    if veri.alan_guveni is not None:
        bilinmeyen = [alan for alan in veri.alan_guveni if alan not in ALAN_KURALLARI]
        if bilinmeyen:
            raise ApiHatasi(422, "DOGRULAMA", "Bilinmeyen alan için güven verildi.", alanlar=[
                {"alan": f"alan_guveni.{alan}", "kural": "gecersiz_deger", "mesaj": "Böyle bir içerik alanı yok."}
                for alan in bilinmeyen
            ])

    eski_icerik = {**bos_icerik(), **annotation.icerik}
    yeni_icerik = {**eski_icerik, **_icerik_degisikligi(veri)}
    icerik_degisti = bool(farklari_denetle(session, kullanici.id, ANNOTATION, annotation.id, eski_icerik, yeni_icerik, onek="icerik."))
    if veri.tanidiklik is not None and veri.tanidiklik != annotation.tanidiklik:
        denetle(session, kullanici.id, ANNOTATION, annotation.id, GUNCELLEME, alan="tanidiklik", eski=annotation.tanidiklik, yeni=veri.tanidiklik)
        annotation.tanidiklik = veri.tanidiklik
    if veri.alan_guveni is not None and veri.alan_guveni != annotation.alan_guveni:
        # Frontend işaretli alanların tamamını gönderir; boş sözlük tüm işaretleri kaldırır.
        denetle(session, kullanici.id, ANNOTATION, annotation.id, GUNCELLEME, alan="alan_guveni", eski=annotation.alan_guveni, yeni=veri.alan_guveni)
        annotation.alan_guveni = dict(veri.alan_guveni)

    annotation.icerik = yeni_icerik
    annotation.harcanan_sure_sn += min(veri.aktif_sure_artis_sn or 0, AZAMI_SURE_ARTISI)
    annotation.surum += 1
    annotation.guncellenme_zamani = simdi()
    if icerik_degisti:
        session.add(AnnotationVersion(
            annotation_id=annotation.id,
            surum=annotation.surum,
            degistiren_id=kullanici.id,
            durum_kodu=annotation.durum_kodu,
            icerik=yeni_icerik,
        ))
    session.commit()
    session.refresh(annotation)
    return {
        "surum": annotation.surum,
        "guncellenme_zamani": annotation.guncellenme_zamani,
        "harcanan_sure_sn": annotation.harcanan_sure_sn,
    }


@router.post("/annotations/{annotation_id}/validate", response_model=ValidationResultOut)
def dogrula(
    annotation_id: str,
    session: Session = Depends(get_session),
    kullanici: User = Depends(aktif_kullanici),
):
    annotation = annotation_getir(session, annotation_id)
    gorebilmeli(session, annotation, kullanici)
    hatalar = dogrulama_hatalari(session, annotation)
    return {"gecerli": not hatalar, "hatalar": hatalar}


@router.post("/annotations/{annotation_id}/submit", response_model=AnnotationOut)
def gonder(
    annotation_id: str,
    veri: SubmitIn,
    session: Session = Depends(get_session),
    kullanici: User = Depends(aktif_kullanici),
):
    annotation = annotation_getir(session, annotation_id, kilitle=True)
    sahibi_olmali(annotation, kullanici)
    cikarilmamis_olmali(session, annotation.meme_id)
    durumda_olmali(annotation, DUZENLENEBILIR, "gönderim")
    surum_eslesmeli(annotation, veri.surum)
    if annotation.tanidiklik in (1, 2):
        raise ApiHatasi(
            422, "TANIDIKLIK_DUSUK",
            "Tanıdıklık 1 veya 2 iken annotation gönderilemez; bu işi atla, başka birine atanır.",
        )
    liste = guncel_liste(session)
    hatalar = icerik_dogrula(annotation.icerik, liste.alanlar)
    if hatalar:
        raise ApiHatasi(422, "DOGRULAMA", "Gönderim için bazı alanlar eksik veya hatalı.", alanlar=hatalar)

    # Gold kaydı yalnızca reviewer onayıyla oluşur; tek etiketli meme de ikinci bakışa gider (ADR-0009).
    ilk_gonderim = annotation.durum_kodu == DEVAM_EDIYOR
    durumu_degistir(session, annotation, GONDERILDI, kullanici)
    annotation.gonderme_zamani = annotation.guncellenme_zamani
    # İçerik bu anki listeye göre doğrulandı; kayıt da bu versiyona sabitlenir.
    annotation.sema_versiyonu = SEMA_VERSIYONU
    annotation.etiket_listesi_versiyonu = liste.versiyon
    # Tanıdıklık 3 orta güvendir: ilk gönderimde meme ikinci bir kişiye de gider (ADR-0013).
    # Revizyondan dönen annotation'ı reviewer zaten görmüştür; ona ikinci kişi eklenmez.
    if ilk_gonderim and annotation.tanidiklik == 3:
        ikinci_annotator_ekle(session, annotation, kullanici)
    return kaydet_ve_don(session, annotation)


@router.post("/annotations/{annotation_id}/skip", response_model=AnnotationOut)
def atla(
    annotation_id: str,
    veri: SkipRequestIn,
    session: Session = Depends(get_session),
    kullanici: User = Depends(aktif_kullanici),
):
    annotation = annotation_getir(session, annotation_id, kilitle=True)
    sahibi_olmali(annotation, kullanici)
    durumda_olmali(annotation, (ATANDI, DEVAM_EDIYOR), "atlama")
    atlama = {"gerekce": veri.gerekce, "aciklama": veri.aciklama}
    durumu_degistir(session, annotation, ATLANDI, kullanici)
    denetle(session, kullanici.id, ANNOTATION, annotation.id, GUNCELLEME, alan="atlandi", eski=None, yeni=atlama)
    annotation.atlandi = atlama
    if veri.tanidiklik is not None and veri.tanidiklik != annotation.tanidiklik:
        denetle(session, kullanici.id, ANNOTATION, annotation.id, GUNCELLEME, alan="tanidiklik", eski=annotation.tanidiklik, yeni=veri.tanidiklik)
        annotation.tanidiklik = veri.tanidiklik
    # Ana turda atlanan meme sıradaki uygun kişiye gider (ADR-0013).
    atlananin_yerine_ata(session, annotation, kullanici)
    return kaydet_ve_don(session, annotation)


@router.get("/annotations/{annotation_id}/versions", response_model=list[AnnotationVersionOut])
def surumler(
    annotation_id: str,
    session: Session = Depends(get_session),
    kullanici: User = Depends(aktif_kullanici),
):
    annotation = annotation_getir(session, annotation_id)
    gorebilmeli(session, annotation, kullanici)
    kisiler = cikti.kullanicilar(session)
    kayitlar = session.exec(
        select(AnnotationVersion).where(AnnotationVersion.annotation_id == annotation_id).order_by(AnnotationVersion.surum)
    ).all()
    return [
        {
            "surum": kayit.surum,
            "zaman": kayit.zaman,
            "degistiren": cikti.kullanici_ref(kisiler.get(kayit.degistiren_id)),
            "durum_kodu": kayit.durum_kodu,
            "icerik": {**bos_icerik(), **kayit.icerik},
        }
        for kayit in kayitlar
    ]
