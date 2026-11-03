from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from app import cikti
from app.database import get_session
from app.denetim import GUNCELLEME, OLUSTURMA, YORUM, denetle
from app.errors import ApiHatasi
from app.kurallar import gizli_yorum_yazarlari
from app.models import Comment, Meme, User
from app.schemas import CommentCreateIn, CommentOut, CommentPageOut, CommentUpdateIn, YorumTuru
from app.security import aktif_kullanici
from app.sema import ALAN_KURALLARI

router = APIRouter(prefix="/api/v1", tags=["comments"])


def gorunur_mu(yorum: Comment, gizli: dict[str, set[str]]) -> bool:
    # Kör etiketleme sürerken diğer annotator'ın yorumları gizlenir (ADR-0003).
    return yorum.yazan_id not in gizli.get(yorum.meme_id, set())


@router.get("/memes/{meme_id}/comments", response_model=list[CommentOut])
def meme_yorumlari(
    meme_id: str,
    session: Session = Depends(get_session),
    kullanici: User = Depends(aktif_kullanici),
):
    if session.get(Meme, meme_id) is None:
        raise ApiHatasi(404, "BULUNAMADI", f"'{meme_id}' adında bir meme yok.")
    gizli = gizli_yorum_yazarlari(session, kullanici.id)
    yorumlar = session.exec(select(Comment).where(Comment.meme_id == meme_id).order_by(Comment.zaman, Comment.id)).all()
    kisiler = cikti.kullanicilar(session)
    return [cikti.yorum(yorum, kisiler) for yorum in yorumlar if gorunur_mu(yorum, gizli)]


@router.post("/memes/{meme_id}/comments", response_model=CommentOut, status_code=201)
def yorum_ekle(
    meme_id: str,
    veri: CommentCreateIn,
    session: Session = Depends(get_session),
    kullanici: User = Depends(aktif_kullanici),
):
    if session.get(Meme, meme_id) is None:
        raise ApiHatasi(404, "BULUNAMADI", f"'{meme_id}' adında bir meme yok.")
    alan = (veri.alan or "").strip() or None
    if alan is not None and alan not in ALAN_KURALLARI:
        raise ApiHatasi(422, "DOGRULAMA", "Yorum bilinmeyen bir alana bağlanamaz.", alanlar=[
            {"alan": "alan", "kural": "gecersiz_deger", "mesaj": "Annotation şemasında böyle bir alan yok."}
        ])
    yorum = Comment(meme_id=meme_id, alan=alan, yazan_id=kullanici.id, metin=veri.metin, tur=veri.tur)
    session.add(yorum)
    denetle(session, kullanici.id, YORUM, yorum.id, OLUSTURMA, yeni={"meme_id": meme_id, "alan": alan, "tur": veri.tur, "metin": veri.metin})
    session.commit()
    session.refresh(yorum)
    return cikti.yorum(yorum, cikti.kullanicilar(session))


@router.get("/comments", response_model=CommentPageOut)
def yorumlari_listele(
    cozuldu: Optional[bool] = None,
    tur: Optional[YorumTuru] = None,
    sayfa: int = Query(1, ge=1),
    boyut: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
    kullanici: User = Depends(aktif_kullanici),
):
    sorgu = select(Comment).order_by(Comment.zaman.desc(), Comment.id)
    if cozuldu is not None:
        sorgu = sorgu.where(Comment.cozuldu == cozuldu)
    if tur is not None:
        sorgu = sorgu.where(Comment.tur == tur)
    gizli = gizli_yorum_yazarlari(session, kullanici.id)
    # Gizli yorumlar sayfalamadan önce ayıklanır; toplam yalnızca görünenleri sayar.
    gorunenler = [yorum for yorum in session.exec(sorgu).all() if gorunur_mu(yorum, gizli)]
    kisiler = cikti.kullanicilar(session)
    return {
        "ogeler": [cikti.yorum(yorum, kisiler) for yorum in gorunenler[(sayfa - 1) * boyut : sayfa * boyut]],
        "toplam": len(gorunenler),
        "sayfa": sayfa,
        "boyut": boyut,
    }


@router.patch("/comments/{comment_id}", response_model=CommentOut)
def yorum_cozuldu(
    comment_id: str,
    veri: CommentUpdateIn,
    session: Session = Depends(get_session),
    kullanici: User = Depends(aktif_kullanici),
):
    yorum = session.get(Comment, comment_id)
    # Kör etiketleme yüzünden göremediği yorumun varlığı da açığa çıkmasın.
    if yorum is None or not gorunur_mu(yorum, gizli_yorum_yazarlari(session, kullanici.id)):
        raise ApiHatasi(404, "BULUNAMADI", "Yorum bulunamadı.")
    if yorum.cozuldu != veri.cozuldu:
        denetle(session, kullanici.id, YORUM, yorum.id, GUNCELLEME, alan="cozuldu", eski=yorum.cozuldu, yeni=veri.cozuldu)
        yorum.cozuldu = veri.cozuldu
        session.commit()
        session.refresh(yorum)
    return cikti.yorum(yorum, cikti.kullanicilar(session))
