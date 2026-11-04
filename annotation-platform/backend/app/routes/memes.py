import hashlib
import re
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import Response
from sqlmodel import Session, select

from app import cikti, gorsel
from app.ai_taslak import karttan_icerik, taslak_engeli
from app.database import get_session
from app.denetim import GUNCELLEME, MEME, OLUSTURMA, denetle
from app.errors import ApiHatasi
from app.etiketler import guncel_liste
from app.havuz import cikarilmis_memeler
from app.kurallar import MemeBaglami
from app.metin import tr_kucuk
from app.models import AiDraft, Annotation, GoldRecord, Meme, MemeImage, User
from app.schemas import (
    AiDraftImportIn,
    AiDraftImportResultOut,
    BulkUploadResultOut,
    MemeDetailOut,
    MemeEtiketDurumu,
    MemeOut,
    MemePageOut,
    MemeUpdateIn,
)
from app.security import admin_kullanici, aktif_kullanici
from app.sema import icerik_dogrula

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
    test_seti: Optional[bool] = None,
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
        if test_seti is not None and meme.test_seti != test_seti:
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


@router.post("/ai-drafts", response_model=AiDraftImportResultOut)
def ai_taslaklarini_ekle(
    veri: AiDraftImportIn,
    session: Session = Depends(get_session),
    yonetici: User = Depends(admin_kullanici),
):
    """LLM kartlarını görselin sha256'sıyla meme'lere taslak olarak bağlar (ADR-0010)."""
    sha_listesi = {taslak.sha256 for taslak in veri.taslaklar}
    memeler = {meme.sha256: meme for meme in session.exec(select(Meme).where(Meme.sha256.in_(sha_listesi))).all()}
    meme_idleri = [meme.id for meme in memeler.values()]
    taslaklilar = set(session.exec(select(AiDraft.meme_id).where(AiDraft.meme_id.in_(meme_idleri))).all())
    goldlular = set(session.exec(select(GoldRecord.meme_id).where(GoldRecord.meme_id.in_(meme_idleri))).all())
    cikarilanlar = cikarilmis_memeler(session, meme_idleri)
    annotationlar: dict[str, list] = {}
    sorgu = select(Annotation.meme_id, Annotation.durum_kodu, Annotation.cift_etiket, Annotation.kalibrasyon)
    for satir in session.exec(sorgu.where(Annotation.meme_id.in_(meme_idleri))).all():
        annotationlar.setdefault(satir.meme_id, []).append(satir)
    etiketler = guncel_liste(session).alanlar

    eklenenler, reddedilenler, gorulenler = [], [], set()
    for taslak in veri.taslaklar:
        meme = memeler.get(taslak.sha256)
        if taslak.sha256 in gorulenler:
            sorun = ("tekrar", "Aynı görsel bu istekte birden fazla kartta geçiyor; ilki alındı.")
        elif meme is None:
            sorun = ("meme_yok", "Bu görselle yüklenmiş bir meme yok; görsel önce yüklenmeli.")
        elif meme.id in cikarilanlar:
            sorun = ("cikarildi", "Bu meme havuz kararıyla kullanımdan çıkarıldı.")
        else:
            sorun = taslak_engeli(meme.id in taslaklilar, meme.id in goldlular, annotationlar.get(meme.id, []))
        gorulenler.add(taslak.sha256)
        if sorun:
            reddedilenler.append({"sha256": taslak.sha256, "meme_id": meme.id if meme else None, "sebep": sorun[0], "mesaj": sorun[1]})
            continue

        icerik = karttan_icerik(taslak.kart)
        session.add(AiDraft(meme_id=meme.id, kaynak=taslak.kaynak, kart=taslak.kart, icerik=icerik, yukleyen_id=yonetici.id))
        taslaklilar.add(meme.id)
        denetle(session, yonetici.id, MEME, meme.id, OLUSTURMA, alan="ai_taslagi", yeni={"kaynak": taslak.kaynak})
        vlm_dolduruldu = meme.vlm_taslak is None and bool((icerik["vlm_aciklama"] or "").strip())
        if vlm_dolduruldu:
            # VLM taslağı bir kez dolar; zaten doluysa kartın tarifi onun yerine geçmez.
            meme.vlm_taslak = icerik["vlm_aciklama"]
            denetle(session, yonetici.id, MEME, meme.id, GUNCELLEME, alan="vlm_taslak", eski=None, yeni=meme.vlm_taslak)
        eklenenler.append({
            "sha256": taslak.sha256,
            "meme_id": meme.id,
            "vlm_taslak_dolduruldu": vlm_dolduruldu,
            # Kart kurallara uymasa da alınır; annotator gönderirken bu eksikleri düzeltir.
            "ihlaller": icerik_dogrula(icerik, etiketler),
        })
    session.commit()
    return {"eklenen": eklenenler, "reddedilen": reddedilenler}


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


@router.patch("/{meme_id}", response_model=MemeOut)
def meme_guncelle(
    meme_id: str,
    veri: MemeUpdateIn,
    session: Session = Depends(get_session),
    yonetici: User = Depends(admin_kullanici),
):
    meme = meme_getir(session, meme_id)
    if veri.test_seti is not None and veri.test_seti != meme.test_seti:
        # Test seti etiketlemeden ayrıdır (ADR-0012): etiketlenmeye başlanmış meme test setine alınamaz.
        if veri.test_seti and (
            session.exec(select(Annotation).where(Annotation.meme_id == meme_id)).first() is not None
            or session.get(GoldRecord, meme_id) is not None
        ):
            raise ApiHatasi(409, "GECERSIZ_DURUM_GECISI", "Etiketlenmeye başlanmış meme test setine alınamaz.")
        denetle(session, yonetici.id, MEME, meme.id, GUNCELLEME, alan="test_seti", eski=meme.test_seti, yeni=veri.test_seti)
        meme.test_seti = veri.test_seti
        session.commit()
        session.refresh(meme)
    return cikti.memeler(session, [meme], yonetici)[0]


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
