from itertools import combinations

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app import cikti
from app.database import get_session
from app.denetim import ANNOTATION, GUNCELLEME, OLUSTURMA, denetle
from app.errors import ApiHatasi
from app.kurallar import aktif_mi, cift_etiket_mi, grubu
from app.models import ATLANDI, AiDraft, Annotation, GoldRecord, Meme, User
from app.schemas import (
    AnnotationSummaryOut,
    AssignmentCreate,
    AutoAssignPlanOut,
    AutoAssignRequest,
    ReassignRequest,
)
from app.security import admin_kullanici

router = APIRouter(prefix="/api/v1", tags=["assignments"])


def _alan_hatasi(alan: str, kural: str, mesaj: str) -> dict:
    return {"alan": alan, "kural": kural, "mesaj": mesaj}


def kullanicilari_dogrula(session: Session, idler: list[str], alan: str, tek: bool = False) -> list[User]:
    hatalar, bulunanlar = [], []
    for sira, kullanici_id in enumerate(idler):
        yol = alan if tek else f"{alan}[{sira}]"
        kullanici = session.get(User, kullanici_id)
        if idler.index(kullanici_id) != sira:
            hatalar.append(_alan_hatasi(yol, "tekrar", "Bu kişi listede tekrar ediyor."))
        elif kullanici is None:
            hatalar.append(_alan_hatasi(yol, "gecersiz_deger", f"'{kullanici_id}' adında bir kullanıcı yok."))
        else:
            bulunanlar.append(kullanici)
    if hatalar:
        raise ApiHatasi(422, "DOGRULAMA", "Bazı kullanıcılar geçersiz.", alanlar=hatalar)
    return bulunanlar


def annotation_kaydi(meme_id: str, annotator_id: str, cift_etiket: bool, kalibrasyon: bool) -> Annotation:
    return Annotation(meme_id=meme_id, annotator_id=annotator_id, cift_etiket=cift_etiket, kalibrasyon=kalibrasyon)


def olusturmayi_denetle(session: Session, yonetici: User, annotation: Annotation, **ek) -> None:
    denetle(
        session, yonetici.id, ANNOTATION, annotation.id, OLUSTURMA,
        yeni={
            "meme_id": annotation.meme_id,
            "annotator_id": annotation.annotator_id,
            "cift_etiket": annotation.cift_etiket,
            "kalibrasyon": annotation.kalibrasyon,
            **ek,
        },
    )


def annotationlari_meme_bazinda(session: Session, meme_idleri: list[str]) -> dict[str, list[Annotation]]:
    sonuc: dict[str, list[Annotation]] = {meme_id: [] for meme_id in meme_idleri}
    sorgu = select(Annotation).where(Annotation.meme_id.in_(meme_idleri)).order_by(Annotation.atanma_zamani, Annotation.id)
    for annotation in session.exec(sorgu).all():
        sonuc[annotation.meme_id].append(annotation)
    return sonuc


@router.post("/assignments", response_model=list[AnnotationSummaryOut], status_code=201)
def elle_ata(
    veri: AssignmentCreate,
    session: Session = Depends(get_session),
    yonetici: User = Depends(admin_kullanici),
):
    annotator = kullanicilari_dogrula(session, [veri.annotator_id], "annotator_id", tek=True)[0]
    hatalar = []
    for sira, meme_id in enumerate(veri.meme_ids):
        if veri.meme_ids.index(meme_id) != sira:
            hatalar.append(_alan_hatasi(f"meme_ids[{sira}]", "tekrar", "Bu meme listede tekrar ediyor."))
        elif session.get(Meme, meme_id) is None:
            hatalar.append(_alan_hatasi(f"meme_ids[{sira}]", "gecersiz_deger", f"'{meme_id}' adında bir meme yok."))
    if hatalar:
        raise ApiHatasi(422, "DOGRULAMA", "Bazı meme'ler geçersiz.", alanlar=hatalar)

    mevcutlar = annotationlari_meme_bazinda(session, veri.meme_ids)
    goldlu = set(session.exec(select(GoldRecord.meme_id).where(GoldRecord.meme_id.in_(veri.meme_ids))).all())
    if not veri.kalibrasyon and goldlu:
        raise ApiHatasi(
            409, "GECERSIZ_DURUM_GECISI", "Gold kaydı olan meme'e yeni annotator atanamaz.",
            detay={"meme_ids": sorted(goldlu)},
        )

    # AI taslağı olan meme tek etiketli kalır: kalibrasyona ve çift etiketlemeye alınmaz (ADR-0010).
    ai_memeler = set(session.exec(select(AiDraft.meme_id).where(AiDraft.meme_id.in_(veri.meme_ids))).all())
    engellenen = [
        meme_id for meme_id in veri.meme_ids
        if meme_id in ai_memeler
        and (veri.kalibrasyon or veri.cift_etiket or grubu(mevcutlar[meme_id], False))
    ]
    if engellenen:
        raise ApiHatasi(
            409, "AI_TASLAKLI_MEME",
            "AI taslağı olan meme kalibrasyona ya da çift etiketlemeye alınamaz.",
            detay={"meme_ids": engellenen},
        )

    zaten_atanmis, terfi_edecekler = [], []
    for meme_id in veri.meme_ids:
        tur = [a for a in mevcutlar[meme_id] if a.kalibrasyon == veri.kalibrasyon]
        if any(a.annotator_id == annotator.id for a in tur):
            zaten_atanmis.append(meme_id)
        elif not veri.kalibrasyon:
            aktifler = grubu(tur, False)
            if len(aktifler) >= 2:
                zaten_atanmis.append(meme_id)
            elif len(aktifler) == 1:
                terfi_edecekler.append(aktifler[0])
    if zaten_atanmis:
        raise ApiHatasi(
            409, "ZATEN_ATANMIS",
            "Bazı meme'ler bu kişiye zaten atanmış ya da iki annotator'ı dolmuş.",
            detay={"meme_ids": zaten_atanmis},
        )

    # Ana turda annotator'ı olan meme'e ikinci kişi eklemek onu çift etiketli yapar.
    ikinci_kisi_olanlar = {a.meme_id for a in terfi_edecekler}
    for mevcut in terfi_edecekler:
        if not mevcut.cift_etiket:
            mevcut.cift_etiket = True
            denetle(session, yonetici.id, ANNOTATION, mevcut.id, GUNCELLEME, alan="cift_etiket", eski=False, yeni=True)

    yeniler = []
    for meme_id in veri.meme_ids:
        cift = False if veri.kalibrasyon else veri.cift_etiket or meme_id in ikinci_kisi_olanlar
        annotation = annotation_kaydi(meme_id, annotator.id, cift, veri.kalibrasyon)
        session.add(annotation)
        olusturmayi_denetle(session, yonetici, annotation)
        yeniler.append(annotation)
    session.commit()
    kisiler = cikti.kullanicilar(session)
    return [cikti.annotation_ozeti(annotation, kisiler) for annotation in yeniler]


def dagitim_plani(memeler: list[Meme], cift_disi: set[str], annotatorlar: list[User], oran: float):
    """Atanmamış meme'leri böler; `oran` kadarını tüm ikililere dengeli dağıtarak çift etiketler.

    Plan veriye göre belirlenir: aynı veritabanında dry_run ile görülen plan uygulananla aynıdır.
    """
    ikililer = list(combinations([kisi.id for kisi in annotatorlar], 2))
    # Kalibrasyonda herkes birbirinin etiketini gördü, AI taslaklı meme'de form taslakla dolu gelir;
    # ikisi de bağımsız çift etiketlemeye uygun değil.
    adaylar = sorted((meme for meme in memeler if meme.id not in cift_disi), key=lambda meme: meme.sha256)
    cift_sayisi = min(int(len(memeler) * oran + 0.5), len(adaylar))
    ciftler = adaylar[:cift_sayisi]

    atamalar: dict[str, list[str]] = {}
    yuk = {kisi.id: 0 for kisi in annotatorlar}
    ikili_yuku = {ikili: 0 for ikili in ikililer}
    for sira, meme in enumerate(ciftler):
        ikili = ikililer[sira % len(ikililer)]
        atamalar[meme.id] = list(ikili)
        ikili_yuku[ikili] += 1
        for kisi_id in ikili:
            yuk[kisi_id] += 1

    cift_idleri = {meme.id for meme in ciftler}
    for meme in sorted(memeler, key=lambda meme: meme.id):
        if meme.id in cift_idleri:
            continue
        # Toplam yükü en az olan kişi alır; eşitlikte istekteki sıra belirler.
        kisi_id = min(yuk, key=lambda aday: yuk[aday])
        atamalar[meme.id] = [kisi_id]
        yuk[kisi_id] += 1
    return dict(sorted(atamalar.items())), yuk, ikili_yuku


@router.post("/assignments/auto", response_model=AutoAssignPlanOut)
def otomatik_ata(
    veri: AutoAssignRequest,
    session: Session = Depends(get_session),
    yonetici: User = Depends(admin_kullanici),
):
    annotatorlar = kullanicilari_dogrula(session, veri.annotator_ids, "annotator_ids")
    ana_turdakiler = set(session.exec(select(Annotation.meme_id).where(Annotation.kalibrasyon == False)).all())  # noqa: E712
    kalibrasyondakiler = set(session.exec(select(Annotation.meme_id).where(Annotation.kalibrasyon == True)).all())  # noqa: E712
    ai_memeler = set(session.exec(select(AiDraft.meme_id)).all())
    goldlu = set(session.exec(select(GoldRecord.meme_id)).all())
    atanmamislar = [
        meme for meme in session.exec(select(Meme).order_by(Meme.id)).all()
        if meme.id not in ana_turdakiler and meme.id not in goldlu
    ]
    atamalar, yuk, ikili_yuku = dagitim_plani(atanmamislar, kalibrasyondakiler | ai_memeler, annotatorlar, veri.cift_etiket_orani)

    if not veri.dry_run:
        for meme_id, kisi_idleri in atamalar.items():
            for kisi_id in kisi_idleri:
                annotation = annotation_kaydi(meme_id, kisi_id, len(kisi_idleri) == 2, False)
                session.add(annotation)
                olusturmayi_denetle(session, yonetici, annotation, otomatik=True)
        session.commit()

    kisiler = cikti.kullanicilar(session)
    return {
        "dry_run": veri.dry_run,
        "atamalar": [{"meme_id": meme_id, "annotator_ids": kisi_idleri} for meme_id, kisi_idleri in atamalar.items()],
        "kisi_basi": [{"annotator": cikti.kullanici_ref(kisi), "meme_sayisi": yuk[kisi.id]} for kisi in annotatorlar],
        "ikili_dagilimi": [
            {"ikili": [cikti.kullanici_ref(kisiler[a]), cikti.kullanici_ref(kisiler[b])], "meme_sayisi": sayi}
            for (a, b), sayi in ikili_yuku.items()
        ],
    }


@router.post("/annotations/{annotation_id}/reassign", response_model=AnnotationSummaryOut, status_code=201)
def yeniden_ata(
    annotation_id: str,
    veri: ReassignRequest,
    session: Session = Depends(get_session),
    yonetici: User = Depends(admin_kullanici),
):
    eski = session.exec(select(Annotation).where(Annotation.id == annotation_id).with_for_update()).first()
    if eski is None:
        raise ApiHatasi(404, "BULUNAMADI", "Annotation bulunamadı.")
    if eski.durum_kodu != ATLANDI:
        raise ApiHatasi(409, "GECERSIZ_DURUM_GECISI", "Yalnızca atlanan annotation yeniden atanabilir.")
    if eski.yerine_gecen_id is not None:
        raise ApiHatasi(409, "GECERSIZ_DURUM_GECISI", "Bu annotation zaten yeniden atanmış.", detay={"yerine_gecen_id": eski.yerine_gecen_id})
    yeni_kisi = kullanicilari_dogrula(session, [veri.yeni_annotator_id], "yeni_annotator_id", tek=True)[0]

    meme_annotationlari = annotationlari_meme_bazinda(session, [eski.meme_id])[eski.meme_id]
    tur = [a for a in meme_annotationlari if a.kalibrasyon == eski.kalibrasyon]
    if any(a.annotator_id == yeni_kisi.id for a in tur):
        raise ApiHatasi(409, "ZATEN_ATANMIS", "Bu meme bu kişiye zaten atanmış.")
    if not eski.kalibrasyon:
        if session.get(GoldRecord, eski.meme_id) is not None:
            raise ApiHatasi(409, "GECERSIZ_DURUM_GECISI", "Bu meme'in gold kaydı var.")
        gereken = 2 if cift_etiket_mi(meme_annotationlari) else 1
        if len([a for a in tur if aktif_mi(a)]) >= gereken:
            raise ApiHatasi(409, "ZATEN_ATANMIS", "Bu meme'in yeterli sayıda annotator'ı var.")

    yeni = annotation_kaydi(eski.meme_id, yeni_kisi.id, eski.cift_etiket, eski.kalibrasyon)
    session.add(yeni)
    session.flush()  # eski kayıt yenisine bağlanıyor; önce yeni kayıt yazılmalı
    eski.yerine_gecen_id = yeni.id
    olusturmayi_denetle(session, yonetici, yeni, onceki_annotation_id=eski.id)
    denetle(session, yonetici.id, ANNOTATION, eski.id, GUNCELLEME, alan="yerine_gecen_id", eski=None, yeni=yeni.id)
    session.commit()
    return cikti.annotation_ozeti(yeni, cikti.kullanicilar(session))
