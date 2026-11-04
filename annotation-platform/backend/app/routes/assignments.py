from collections import Counter
from itertools import combinations
from typing import Optional

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app import cikti
from app.database import get_session
from app.denetim import ANNOTATION, GUNCELLEME, MEME, OLUSTURMA, denetle
from app.errors import ApiHatasi
from app.havuz import cikarilmamis_olmali, cikarilmis_memeler
from app.kurallar import BEKLEYEN_DURUMLAR, aktif_mi, cift_etiket_mi, grubu, test_sorgusu_yazarlari
from app.models import ATLANDI, AiDraft, Annotation, GoldRecord, Meme, MemeExclusionVote, User, simdi
from app.routes.exclusions import OY_ALANI, meme_kilitle, oy_degeri
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
    cikarilanlar = cikarilmis_memeler(session, veri.meme_ids)
    if cikarilanlar:
        raise ApiHatasi(
            409, "MEME_CIKARILDI", "Havuz kararıyla çıkarılan meme'e annotator atanamaz.",
            detay={"meme_ids": [meme_id for meme_id in veri.meme_ids if meme_id in cikarilanlar]},
        )
    test_setindekiler = [meme_id for meme_id in veri.meme_ids if session.get(Meme, meme_id).test_seti]
    if test_setindekiler:
        raise ApiHatasi(409, "TEST_SETI", "Test setindeki meme'e annotator atanamaz.", detay={"meme_ids": test_setindekiler})
    yazarlar = test_sorgusu_yazarlari(session, veri.meme_ids)
    ihlal = [meme_id for meme_id in veri.meme_ids if annotator.id in yazarlar[meme_id]]
    if ihlal:
        raise ApiHatasi(
            409, "SIZINTI", "Bir meme'e test sorgusu yazan kişi o meme'i etiketleyemez.",
            detay={"ihlal_eden_memeler": ihlal},
        )

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


def dagitim_plani(memeler: list[Meme], cift_disi: set[str], annotatorlar: list[User], oran: float,
                  yasakli: Optional[dict[str, set[str]]] = None):
    """Atanmamış meme'leri böler; `oran` kadarını tüm ikililere dengeli dağıtarak çift etiketler.

    `yasakli`, meme'e test sorgusu yazdığı için o meme'e atanamayacak kişilerdir (ADR-0012).
    Uygun ikilisi olmayan meme tek etiketliye, uygun kimsesi olmayan meme atanmadan kalır.
    Plan veriye göre belirlenir: aynı veritabanında dry_run ile görülen plan uygulananla aynıdır.
    """
    yasakli = yasakli or {}
    ikililer = list(combinations([kisi.id for kisi in annotatorlar], 2))
    # Kalibrasyonda herkes birbirinin etiketini gördü, AI taslaklı meme'de form taslakla dolu gelir;
    # ikisi de bağımsız çift etiketlemeye uygun değil.
    adaylar = sorted((meme for meme in memeler if meme.id not in cift_disi), key=lambda meme: meme.sha256)
    cift_sayisi = min(int(len(memeler) * oran + 0.5), len(adaylar))
    ciftler = adaylar[:cift_sayisi]

    atamalar: dict[str, list[str]] = {}
    yuk = {kisi.id: 0 for kisi in annotatorlar}
    ikili_yuku = {ikili: 0 for ikili in ikililer}
    cift_idleri = set()
    for sira, meme in enumerate(ciftler):
        # Sıradaki ikiliden başlanır; meme'e test sorgusu yazan birini içeren ikili atlanır.
        sirali = ikililer[sira % len(ikililer):] + ikililer[:sira % len(ikililer)]
        ikili = next((aday for aday in sirali if not yasakli.get(meme.id, set()) & set(aday)), None)
        if ikili is None:
            continue
        atamalar[meme.id] = list(ikili)
        cift_idleri.add(meme.id)
        ikili_yuku[ikili] += 1
        for kisi_id in ikili:
            yuk[kisi_id] += 1

    for meme in sorted(memeler, key=lambda meme: meme.id):
        if meme.id in cift_idleri:
            continue
        uygunlar = [kisi_id for kisi_id in yuk if kisi_id not in yasakli.get(meme.id, set())]
        if not uygunlar:
            continue
        # Toplam yükü en az olan kişi alır; eşitlikte istekteki sıra belirler.
        kisi_id = min(uygunlar, key=lambda aday: yuk[aday])
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
    cikarilanlar = cikarilmis_memeler(session)
    atanmamislar = [
        meme for meme in session.exec(select(Meme).order_by(Meme.id)).all()
        if meme.id not in ana_turdakiler and meme.id not in goldlu and meme.id not in cikarilanlar and not meme.test_seti
    ]
    yasakli = test_sorgusu_yazarlari(session, [meme.id for meme in atanmamislar])
    atamalar, yuk, ikili_yuku = dagitim_plani(
        atanmamislar, kalibrasyondakiler | ai_memeler, annotatorlar, veri.cift_etiket_orani, yasakli,
    )

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
    cikarilmamis_olmali(session, eski.meme_id)
    if eski.durum_kodu != ATLANDI:
        raise ApiHatasi(409, "GECERSIZ_DURUM_GECISI", "Yalnızca atlanan annotation yeniden atanabilir.")
    if eski.yerine_gecen_id is not None:
        raise ApiHatasi(409, "GECERSIZ_DURUM_GECISI", "Bu annotation zaten yeniden atanmış.", detay={"yerine_gecen_id": eski.yerine_gecen_id})
    yeni_kisi = kullanicilari_dogrula(session, [veri.yeni_annotator_id], "yeni_annotator_id", tek=True)[0]

    meme_annotationlari = annotationlari_meme_bazinda(session, [eski.meme_id])[eski.meme_id]
    tur = [a for a in meme_annotationlari if a.kalibrasyon == eski.kalibrasyon]
    if any(a.annotator_id == yeni_kisi.id for a in tur):
        raise ApiHatasi(409, "ZATEN_ATANMIS", "Bu meme bu kişiye zaten atanmış.")
    if yeni_kisi.id in test_sorgusu_yazarlari(session, [eski.meme_id])[eski.meme_id]:
        raise ApiHatasi(
            409, "SIZINTI", "Bir meme'e test sorgusu yazan kişi o meme'i etiketleyemez.",
            detay={"ihlal_eden_memeler": [eski.meme_id]},
        )
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


# ------------------------------------------------------------------ otomatik atama (ADR-0013)

# Atlanan meme'e atanabilecek kimse kalmayınca son atlayan kişi adına verilen kullanılmasın oyunun notu
KIMSE_KALMADI_NOTU = "Otomatik: meme'i atlayanlar dışında atanabilecek kimse kalmadı."


def siradaki_annotator(session: Session, meme_id: str) -> Optional[str]:
    """Meme'i alacak kişi: ana turda işi olan, bu meme'e atanmamış (atlamış da sayılır) ve ona test
    sorgusu yazmamış kişilerden açık işi en az olan; eşitlikte toplam işi az olan, sonra id sırası."""
    satirlar = session.exec(
        select(Annotation.annotator_id, Annotation.meme_id, Annotation.durum_kodu, Annotation.kalibrasyon)
    ).all()
    # Ana turda hiç işi olmayan hesap (ör. deneme hesabı) aday olmaz.
    adaylar = {satir.annotator_id for satir in satirlar if not satir.kalibrasyon}
    adaylar -= {satir.annotator_id for satir in satirlar if satir.meme_id == meme_id and not satir.kalibrasyon}
    adaylar -= test_sorgusu_yazarlari(session, [meme_id])[meme_id]
    if not adaylar:
        return None
    acik = Counter(satir.annotator_id for satir in satirlar if satir.durum_kodu in BEKLEYEN_DURUMLAR)
    toplam = Counter(satir.annotator_id for satir in satirlar)
    return min(sorted(adaylar), key=lambda kisi_id: (acik[kisi_id], toplam[kisi_id]))


def otomatik_atanabilir_mi(session: Session, meme_id: str) -> bool:
    # Meme kilitlenir: aynı meme'de aynı anda atlayan iki kişi aynı yeni kişiyi seçmesin.
    meme = meme_kilitle(session, meme_id)
    return not meme.test_seti and session.get(GoldRecord, meme_id) is None and not cikarilmis_memeler(session, [meme_id])


def havuza_dusur(session: Session, meme_id: str, kullanici: User) -> None:
    """Son atlayan kişi adına kullanılmasın oyu verilir; meme admin'in havuzuna düşer (ADR-0011)."""
    yeni = {"sebep": "diger", "not": KIMSE_KALMADI_NOTU, "karar": None}
    oy = session.get(MemeExclusionVote, (meme_id, kullanici.id))
    if oy is None:
        session.add(MemeExclusionVote(meme_id=meme_id, kullanici_id=kullanici.id, sebep="diger", notu=KIMSE_KALMADI_NOTU))
        denetle(session, kullanici.id, MEME, meme_id, OLUSTURMA, alan=OY_ALANI, yeni=yeni)
    elif oy.karar_id is not None:
        # Kişinin kararla sonuçlanmış oyu yeniden geçerli olur; sonuçlanmamış oy zaten havuzdadır.
        denetle(session, kullanici.id, MEME, meme_id, GUNCELLEME, alan=OY_ALANI, eski=oy_degeri(session, oy), yeni=yeni)
        oy.sebep, oy.notu, oy.zaman, oy.karar_id = "diger", KIMSE_KALMADI_NOTU, simdi(), None


def atlananin_yerine_ata(session: Session, eski: Annotation, kullanici: User) -> Optional[Annotation]:
    """Ana turda atlanan annotation'ın yerine sıradaki uygun kişiyi atar.

    Uygun kimse kalmazsa meme'in başka annotator'ı da yoksa meme havuza düşer. Çift etiketli
    meme'de bir annotator kaldıysa meme onunla tek etiketli sürer, reviewer ikinci bakışı yapar
    (ADR-0009). Kalibrasyon turundaki atlama admin'in elle yeniden atamasına kalır.
    """
    if eski.kalibrasyon or not otomatik_atanabilir_mi(session, eski.meme_id):
        return None
    ana_tur = [a for a in annotationlari_meme_bazinda(session, [eski.meme_id])[eski.meme_id] if not a.kalibrasyon]
    aktifler = [a for a in ana_tur if aktif_mi(a)]
    cift = cift_etiket_mi(ana_tur)
    if len(aktifler) >= (2 if cift else 1):
        return None
    kisi_id = siradaki_annotator(session, eski.meme_id)
    if kisi_id is None:
        if not aktifler:
            havuza_dusur(session, eski.meme_id, kullanici)
            return None
        for annotation in ana_tur:
            if annotation.cift_etiket:
                annotation.cift_etiket = False
                denetle(session, kullanici.id, ANNOTATION, annotation.id, GUNCELLEME, alan="cift_etiket", eski=True, yeni=False)
        return None

    yeni = annotation_kaydi(eski.meme_id, kisi_id, cift, False)
    session.add(yeni)
    session.flush()  # eski kayıt yenisine bağlanıyor; önce yeni kayıt yazılmalı
    eski.yerine_gecen_id = yeni.id
    olusturmayi_denetle(session, kullanici, yeni, otomatik=True, onceki_annotation_id=eski.id)
    denetle(session, kullanici.id, ANNOTATION, eski.id, GUNCELLEME, alan="yerine_gecen_id", eski=None, yeni=yeni.id)
    return yeni


def ikinci_annotator_ekle(session: Session, annotation: Annotation, kullanici: User) -> Optional[Annotation]:
    """Tanıdıklığı 3 olan tek etiketli annotation'ın meme'ine sıradaki uygun kişiyi de atar.

    Meme çift etiketli olur, reviewer iki etiketi birleştirir. AI taslaklı meme tek etiketli kalır;
    onu reviewer'ın ikinci bakışı karşılar (ADR-0010). Uygun kimse yoksa meme tek etiketli sürer.
    """
    if annotation.kalibrasyon or annotation.cift_etiket or session.get(AiDraft, annotation.meme_id) is not None:
        return None
    if not otomatik_atanabilir_mi(session, annotation.meme_id):
        return None
    kisi_id = siradaki_annotator(session, annotation.meme_id)
    if kisi_id is None:
        return None
    annotation.cift_etiket = True
    denetle(session, kullanici.id, ANNOTATION, annotation.id, GUNCELLEME, alan="cift_etiket", eski=False, yeni=True)
    yeni = annotation_kaydi(annotation.meme_id, kisi_id, True, False)
    session.add(yeni)
    olusturmayi_denetle(session, kullanici, yeni, otomatik=True)
    return yeni
