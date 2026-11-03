import hashlib
import re
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import Response
from sqlmodel import Session, select

from app import cikti, gorsel
from app.database import get_session
from app.denetim import MEME, OLUSTURMA, denetle
from app.errors import ApiHatasi
from app.kurallar import MemeBaglami
from app.metin import tr_kucuk
from app.models import Annotation, Meme, MemeImage, User
from app.schemas import BulkUploadResultOut, MemeDetailOut, MemeEtiketDurumu, MemeOut, MemePageOut
from app.security import admin_kullanici, aktif_kullanici

router = APIRouter(prefix="/api/v1/memes", tags=["memes"])

# Görsel bir meme'e bağlandıktan sonra değişmez (sha256 sabit); tarayıcı uzun süre saklayabilir.
GORSEL_ONBELLEGI = "private, max-age=604800, immutable"


def meme_getir(session: Session, meme_id: str) -> Meme:
    meme = session.get(Meme, meme_id)
    if meme is None:
        raise ApiHatasi(404, "BULUNAMADI", f"'{meme_id}' adında bir meme yok.")
    return meme


def sonraki_numara(session: Session) -> int:
    numaralar = [int(meme_id[1:]) for meme_id in session.exec(select(Meme.id)).all() if re.fullmatch(r"m\d+", meme_id)]
    return max(numaralar, default=0) + 1


class _Yukleme:
    """Bir istekteki dosyaları sırayla kaydeder; kopyaları hem veritabanında hem istek içinde yakalar."""

    def __init__(self, session: Session, yukleyen: User):
        self.session = session
        self.yukleyen = yukleyen
        self.numara = sonraki_numara(session)
        self.mevcutlar = dict(session.exec(select(Meme.sha256, Meme.id)).all())
        self.yeniler: list[tuple[Meme, MemeImage, str]] = []

    def ekle(self, dosya: UploadFile) -> tuple[Optional[Meme], Optional[dict]]:
        veri = dosya.file.read()
        tur, sorun = gorsel.incele(dosya.filename, dosya.content_type, veri)
        if sorun:
            return None, {"dosya_adi": dosya.filename or "", "sebep": sorun, "mevcut_meme_id": None}
        sha256 = hashlib.sha256(veri).hexdigest()
        if sha256 in self.mevcutlar:
            return None, {"dosya_adi": dosya.filename or "", "sebep": gorsel.KOPYA, "mevcut_meme_id": self.mevcutlar[sha256]}
        meme_id = f"m{self.numara:04d}"
        self.numara += 1
        meme = Meme(
            id=meme_id,
            gorsel_yolu=f"memes/{meme_id}.{gorsel.UZANTILAR[tur]}",
            sha256=sha256,
            yukleyen_id=self.yukleyen.id,
        )
        self.mevcutlar[sha256] = meme_id
        self.yeniler.append((meme, MemeImage(meme_id=meme_id, icerik_tipi=tur, veri=veri), dosya.filename or ""))
        return meme, None

    def kaydet(self) -> None:
        for meme, _, _ in self.yeniler:
            self.session.add(meme)
        self.session.flush()  # görseller meme'lere bağlı; önce meme satırları yazılmalı
        for meme, gorsel_kaydi, dosya_adi in self.yeniler:
            self.session.add(gorsel_kaydi)
            denetle(
                self.session, self.yukleyen.id, MEME, meme.id, OLUSTURMA,
                yeni={"sha256": meme.sha256, "gorsel_yolu": meme.gorsel_yolu, "dosya_adi": dosya_adi},
            )
        self.session.commit()


@router.get("", response_model=MemePageOut)
def memeleri_listele(
    etiket_durumu: Optional[MemeEtiketDurumu] = None,
    annotator_id: Optional[str] = None,
    cift_etiket: Optional[bool] = None,
    q: Optional[str] = None,
    sayfa: int = Query(1, ge=1),
    boyut: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
    kullanici: User = Depends(aktif_kullanici),
):
    baglam = MemeBaglami(session)
    aranan = tr_kucuk(q.strip()) if q and q.strip() else None
    secilenler = []
    for meme in session.exec(select(Meme).order_by(Meme.id)).all():
        if etiket_durumu and baglam.durum(meme.id) != etiket_durumu:
            continue
        if annotator_id and annotator_id not in baglam.annotatorlar(meme.id):
            continue
        if cift_etiket is not None and baglam.cift_etiket(meme.id) != cift_etiket:
            continue
        if aranan and aranan not in meme.id.lower() and aranan not in tr_kucuk(baglam.ad(meme.id) or ""):
            continue
        secilenler.append(meme)

    kisiler = cikti.kullanicilar(session)
    sayfadakiler = secilenler[(sayfa - 1) * boyut : sayfa * boyut]
    return {
        "ogeler": [cikti.meme(meme, baglam, kisiler, kullanici) for meme in sayfadakiler],
        "toplam": len(secilenler),
        "sayfa": sayfa,
        "boyut": boyut,
    }


@router.post("", response_model=MemeOut, status_code=201)
def meme_yukle(
    dosya: UploadFile = File(...),
    session: Session = Depends(get_session),
    yonetici: User = Depends(admin_kullanici),
):
    yukleme = _Yukleme(session, yonetici)
    meme, red = yukleme.ekle(dosya)
    if red:
        if red["sebep"] == gorsel.KOPYA:
            raise ApiHatasi(409, "KOPYA", "Bu görsel zaten yüklenmiş.", detay={"mevcut_meme_id": red["mevcut_meme_id"]})
        if red["sebep"] == gorsel.BOZUK_DOSYA:
            raise ApiHatasi(422, "BOZUK_DOSYA", "Dosya okunamadı ya da eksik inmiş.")
        raise ApiHatasi(415, "DESTEKLENMEYEN_TUR", "Yalnızca jpg, png, webp ve gif dosyaları yüklenebilir.")
    yukleme.kaydet()
    return cikti.memeler(session, [meme], yonetici)[0]


@router.post("/bulk", response_model=BulkUploadResultOut)
def toplu_yukle(
    dosyalar: list[UploadFile] = File(...),
    session: Session = Depends(get_session),
    yonetici: User = Depends(admin_kullanici),
):
    yukleme = _Yukleme(session, yonetici)
    yuklenenler, reddedilenler = [], []
    for dosya in dosyalar:
        meme, red = yukleme.ekle(dosya)
        if red:
            reddedilenler.append(red)
        else:
            yuklenenler.append(meme)
    yukleme.kaydet()
    return {"yuklenen": cikti.memeler(session, yuklenenler, yonetici), "reddedilen": reddedilenler}


@router.get("/{meme_id}", response_model=MemeDetailOut)
def meme_detayi(
    meme_id: str,
    session: Session = Depends(get_session),
    kullanici: User = Depends(aktif_kullanici),
):
    meme = meme_getir(session, meme_id)
    sorgu = select(Annotation).where(Annotation.meme_id == meme_id).order_by(Annotation.atanma_zamani, Annotation.id)
    if not kullanici.admin:
        # Admin dışındaki kullanıcılar yalnızca kendi annotation'larını görür.
        sorgu = sorgu.where(Annotation.annotator_id == kullanici.id)
    kisiler = cikti.kullanicilar(session)
    return {
        **cikti.memeler(session, [meme], kullanici)[0],
        "annotasyonlar": [cikti.annotation_ozeti(annotation, kisiler) for annotation in session.exec(sorgu).all()],
    }


@router.get("/{meme_id}/image")
def meme_gorseli(
    meme_id: str,
    request: Request,
    boyut: Literal["orijinal", "kucuk"] = "orijinal",
    session: Session = Depends(get_session),
    _: User = Depends(aktif_kullanici),
):
    # Küçük boy için yeni bir bağımlılık eklemeden orijinal görsel döner; tarayıcı önbelleği yükü azaltır.
    meme = meme_getir(session, meme_id)
    basliklar = {"Cache-Control": GORSEL_ONBELLEGI, "ETag": f'"{meme.sha256}"'}
    if request.headers.get("if-none-match") == basliklar["ETag"]:
        return Response(status_code=304, headers=basliklar)
    kayit = session.get(MemeImage, meme_id)
    if kayit is None:
        raise ApiHatasi(404, "BULUNAMADI", "Bu meme'in görseli yok.")
    return Response(content=kayit.veri, media_type=kayit.icerik_tipi, headers=basliklar)
