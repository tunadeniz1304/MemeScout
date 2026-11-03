import copy
from typing import Optional

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app import cikti
from app.database import get_session
from app.denetim import ETIKET_LISTESI, GUNCELLEME, OLUSTURMA, denetle
from app.errors import ApiHatasi
from app.etiketler import etiket_bul, guncel_liste, liste_getir, yeni_etiket, yeni_versiyon
from app.models import LabelListVersion, Meme, User, simdi
from app.schemas import (
    AnnotationSchemaOut,
    EtiketAlani,
    LabelCreate,
    LabelListOut,
    LabelListVersionSummaryOut,
    LabelUpdate,
)
from app.security import admin_kullanici, aktif_kullanici
from app.sema import ALAN_KURALLARI, SEMA_VERSIYONU

router = APIRouter(prefix="/api/v1", tags=["schema"])

DEGISIKLIK_ADLARI = {
    "gorunen_ad": "görünen adı değişti",
    "tanim": "tanımı değişti",
    "ornekler": "örnekleri değişti",
}


@router.get("/schema/annotation", response_model=AnnotationSchemaOut)
def annotation_semasi(_: User = Depends(aktif_kullanici)):
    return {"sema_versiyonu": SEMA_VERSIYONU, "alanlar": ALAN_KURALLARI}


@router.get("/label-lists", response_model=LabelListOut)
def etiket_listesini_getir(
    versiyon: Optional[str] = None,
    session: Session = Depends(get_session),
    _: User = Depends(aktif_kullanici),
):
    liste = liste_getir(session, versiyon) if versiyon else guncel_liste(session)
    if liste is None:
        raise ApiHatasi(404, "BULUNAMADI", f"'{versiyon}' adında bir etiket listesi versiyonu yok.")
    return cikti.etiket_listesi(liste)


@router.get("/label-lists/versions", response_model=list[LabelListVersionSummaryOut])
def etiket_listesi_versiyonlari(
    session: Session = Depends(get_session),
    _: User = Depends(aktif_kullanici),
):
    kisiler = cikti.kullanicilar(session)
    versiyonlar = session.exec(select(LabelListVersion).order_by(LabelListVersion.sira)).all()
    return [
        {
            "versiyon": versiyon.versiyon,
            "olusturma_zamani": versiyon.olusturma_zamani,
            "olusturan": cikti.kullanici_ref(kisiler.get(versiyon.olusturan_id)),
            "degisiklik_ozeti": versiyon.degisiklik_ozeti,
        }
        for versiyon in versiyonlar
    ]


def ornekleri_dogrula(session: Session, ornekler: list[str]) -> None:
    hatalar = []
    for sira, meme_id in enumerate(ornekler):
        if ornekler.index(meme_id) != sira:
            hatalar.append({"alan": f"ornekler[{sira}]", "kural": "tekrar", "mesaj": "Bu meme listede tekrar ediyor."})
        elif session.get(Meme, meme_id) is None:
            hatalar.append({"alan": f"ornekler[{sira}]", "kural": "gecersiz_deger", "mesaj": f"'{meme_id}' adında bir meme yok."})
    if hatalar:
        raise ApiHatasi(422, "DOGRULAMA", "Örnek meme'ler geçersiz.", alanlar=hatalar)


@router.post("/label-lists/labels", response_model=LabelListOut, status_code=201)
def etiket_ekle(
    veri: LabelCreate,
    session: Session = Depends(get_session),
    yonetici: User = Depends(admin_kullanici),
):
    onceki = guncel_liste(session, kilitle=True)
    if etiket_bul(onceki.alanlar, veri.alan, veri.etiket) is not None:
        raise ApiHatasi(409, "CAKISMA", f"{veri.alan} listesinde '{veri.etiket}' zaten var.")
    ornekleri_dogrula(session, veri.ornekler)

    alanlar = copy.deepcopy(onceki.alanlar)
    etiket = yeni_etiket(veri.etiket, veri.gorunen_ad, veri.tanim, veri.ornekler, simdi())
    alanlar[veri.alan].append(etiket)
    versiyon = yeni_versiyon(session, onceki, alanlar, yonetici.id, f"{veri.alan}: '{veri.etiket}' eklendi")
    denetle(session, yonetici.id, ETIKET_LISTESI, versiyon.versiyon, OLUSTURMA, alan=f"{veri.alan}.{veri.etiket}", yeni=etiket)
    session.commit()
    session.refresh(versiyon)
    return cikti.etiket_listesi(versiyon)


@router.patch("/label-lists/labels/{alan}/{etiket}", response_model=LabelListOut)
def etiket_guncelle(
    alan: EtiketAlani,
    etiket: str,
    veri: LabelUpdate,
    session: Session = Depends(get_session),
    yonetici: User = Depends(admin_kullanici),
):
    onceki = guncel_liste(session, kilitle=True)
    mevcut = etiket_bul(onceki.alanlar, alan, etiket)
    if mevcut is None:
        raise ApiHatasi(404, "BULUNAMADI", f"{alan} listesinde '{etiket}' yok.")
    istenen = veri.model_dump(exclude_none=True)
    if "ornekler" in istenen:
        ornekleri_dogrula(session, istenen["ornekler"])
    farklar = {anahtar: deger for anahtar, deger in istenen.items() if mevcut.get(anahtar) != deger}
    if not farklar:
        # Değişiklik yoksa yeni versiyon açılmaz.
        return cikti.etiket_listesi(onceki)

    alanlar = copy.deepcopy(onceki.alanlar)
    etiket_bul(alanlar, alan, etiket).update(farklar)
    ozetler = []
    if "aktif" in farklar:
        ozetler.append("pasifleştirildi" if not farklar["aktif"] else "yeniden etkinleştirildi")
    ozetler += [DEGISIKLIK_ADLARI[anahtar] for anahtar in DEGISIKLIK_ADLARI if anahtar in farklar]
    versiyon = yeni_versiyon(session, onceki, alanlar, yonetici.id, f"{alan}: '{etiket}' " + ", ".join(ozetler))
    for anahtar, deger in farklar.items():
        denetle(
            session, yonetici.id, ETIKET_LISTESI, versiyon.versiyon, GUNCELLEME,
            alan=f"{alan}.{etiket}.{anahtar}", eski=mevcut.get(anahtar), yeni=deger,
        )
    session.commit()
    session.refresh(versiyon)
    return cikti.etiket_listesi(versiyon)
