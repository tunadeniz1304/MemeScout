from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlmodel import Session, select

from app import cikti
from app.database import get_session
from app.denetim import GUNCELLEME, OLUSTURMA, SILME, TEST_SORGUSU, denetle
from app.errors import ApiHatasi
from app.havuz import cikarilmis_memeler
from app.kurallar import gold_katkicilari
from app.models import Meme, TestQuery, User
from app.schemas import SorguModu, TestQueryCreateIn, TestQueryOut, TestQueryUpdateIn
from app.security import aktif_kullanici

router = APIRouter(prefix="/api/v1/test-queries", tags=["test-queries"])


def dogru_memeleri_dogrula(session: Session, yazan_id: str, meme_idleri: list[str]) -> None:
    hatalar = []
    cikarilanlar = cikarilmis_memeler(session, meme_idleri)
    for sira, meme_id in enumerate(meme_idleri):
        if meme_idleri.index(meme_id) != sira:
            hatalar.append({"alan": f"dogru_memeler[{sira}]", "kural": "tekrar", "mesaj": "Bu meme listede tekrar ediyor."})
        elif session.get(Meme, meme_id) is None:
            hatalar.append({"alan": f"dogru_memeler[{sira}]", "kural": "gecersiz_deger", "mesaj": f"'{meme_id}' adında bir meme yok."})
        elif meme_id in cikarilanlar:
            hatalar.append({
                "alan": f"dogru_memeler[{sira}]", "kural": "gecersiz_deger", "mesaj": "Bu meme havuz kararıyla kullanımdan çıkarıldı.",
            })
    if hatalar:
        raise ApiHatasi(422, "DOGRULAMA", "Doğru cevap listesi geçersiz.", alanlar=hatalar)
    # Kural, sorguyu düzenleyen kişiye değil sorguyu yazana bakar.
    ihlal = [meme_id for meme_id in meme_idleri if yazan_id in gold_katkicilari(session, meme_id)]
    if ihlal:
        raise ApiHatasi(
            422, "SIZINTI",
            "Sorgunun yazarı, doğru cevap olarak gösterdiği meme'lerin gold kaydına katkı vermiş olamaz.",
            detay={"ihlal_eden_memeler": ihlal},
        )


def sorgu_getir(session: Session, query_id: str, kullanici: User) -> TestQuery:
    sorgu = session.get(TestQuery, query_id)
    if sorgu is None:
        raise ApiHatasi(404, "BULUNAMADI", "Test sorgusu bulunamadı.")
    if sorgu.yazan_id != kullanici.id and not kullanici.admin:
        raise ApiHatasi(403, "YASAK", "Test sorgusunu yalnızca yazan kişi veya admin değiştirebilir.")
    return sorgu


def sorgu_degeri(sorgu: TestQuery) -> dict:
    return {"metin": sorgu.metin, "mod": sorgu.mod, "dogru_memeler": sorgu.dogru_memeler}


@router.get("", response_model=list[TestQueryOut])
def sorgulari_listele(
    yazan_id: Optional[str] = None,
    mod: Optional[SorguModu] = None,
    session: Session = Depends(get_session),
    _: User = Depends(aktif_kullanici),
):
    sorgu = select(TestQuery).order_by(TestQuery.zaman.desc(), TestQuery.id)
    if yazan_id:
        sorgu = sorgu.where(TestQuery.yazan_id == yazan_id)
    if mod:
        sorgu = sorgu.where(TestQuery.mod == mod)
    kisiler = cikti.kullanicilar(session)
    cikarilanlar = cikarilmis_memeler(session)
    return [cikti.test_sorgusu(kayit, kisiler, cikarilanlar) for kayit in session.exec(sorgu).all()]


@router.post("", response_model=TestQueryOut, status_code=201)
def sorgu_ekle(
    veri: TestQueryCreateIn,
    session: Session = Depends(get_session),
    kullanici: User = Depends(aktif_kullanici),
):
    yazan_id = kullanici.id
    if veri.yazan_id and veri.yazan_id != kullanici.id:
        # Ekip dışında yazılmış sorgular (ör. bir belgedeki) yazarları adına admin tarafından eklenir.
        if not kullanici.admin:
            raise ApiHatasi(403, "YASAK", "Başkası adına test sorgusunu yalnızca admin ekleyebilir.")
        if session.get(User, veri.yazan_id) is None:
            raise ApiHatasi(422, "DOGRULAMA", "Yazar bulunamadı.", alanlar=[
                {"alan": "yazan_id", "kural": "gecersiz_deger", "mesaj": f"'{veri.yazan_id}' adında bir kullanıcı yok."},
            ])
        yazan_id = veri.yazan_id
    dogru_memeleri_dogrula(session, yazan_id, veri.dogru_memeler)
    sorgu = TestQuery(metin=veri.metin, mod=veri.mod, dogru_memeler=veri.dogru_memeler, yazan_id=yazan_id)
    session.add(sorgu)
    yeni = sorgu_degeri(sorgu) | ({"yazan_id": yazan_id} if yazan_id != kullanici.id else {})
    denetle(session, kullanici.id, TEST_SORGUSU, sorgu.id, OLUSTURMA, yeni=yeni)
    session.commit()
    session.refresh(sorgu)
    return cikti.test_sorgusu(sorgu, cikti.kullanicilar(session), set())


@router.patch("/{query_id}", response_model=TestQueryOut)
def sorgu_guncelle(
    query_id: str,
    veri: TestQueryUpdateIn,
    session: Session = Depends(get_session),
    kullanici: User = Depends(aktif_kullanici),
):
    sorgu = sorgu_getir(session, query_id, kullanici)
    degisiklikler = veri.model_dump(exclude_none=True)
    if "dogru_memeler" in degisiklikler:
        dogru_memeleri_dogrula(session, sorgu.yazan_id, degisiklikler["dogru_memeler"])
    eski = sorgu_degeri(sorgu)
    for alan, deger in degisiklikler.items():
        if eski[alan] != deger:
            denetle(session, kullanici.id, TEST_SORGUSU, sorgu.id, GUNCELLEME, alan=alan, eski=eski[alan], yeni=deger)
            setattr(sorgu, alan, deger)
    session.commit()
    session.refresh(sorgu)
    return cikti.test_sorgusu(sorgu, cikti.kullanicilar(session), cikarilmis_memeler(session, sorgu.dogru_memeler))


@router.delete("/{query_id}", status_code=204)
def sorgu_sil(
    query_id: str,
    session: Session = Depends(get_session),
    kullanici: User = Depends(aktif_kullanici),
):
    sorgu = sorgu_getir(session, query_id, kullanici)
    denetle(session, kullanici.id, TEST_SORGUSU, sorgu.id, SILME, eski={**sorgu_degeri(sorgu), "yazan_id": sorgu.yazan_id})
    session.delete(sorgu)
    session.commit()
    return Response(status_code=204)
