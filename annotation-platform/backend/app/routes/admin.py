import json
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import func
from sqlmodel import Session, select

from app import cikti
from app.database import get_session
from app.havuz import cikarilmis_memeler
from app.kurallar import annotation_gorebilir_mi, gold_gorebilir_mi
from app.models import AiDraft, Annotation, AuditEntry, GoldRecord, Meme, TestQuery, User
from app.schemas import AnnotationOut, AuditPageOut, KayitTipi, RecheckItemOut, TestQueryOut
from app.security import admin_kullanici, aktif_kullanici
from app.sema import ALAN_KURALLARI, bos_icerik
from app.yeniden_kontrol import yeniden_kontrol_listesi

router = APIRouter(prefix="/api/v1", tags=["admin"])


@router.get("/recheck", response_model=list[RecheckItemOut])
def yeniden_kontrol(
    session: Session = Depends(get_session),
    kullanici: User = Depends(aktif_kullanici),
):
    kayitlar = yeniden_kontrol_listesi(session)
    cikarilanlar = cikarilmis_memeler(session, {kayit["meme_id"] for kayit in kayitlar})
    kayitlar = [kayit for kayit in kayitlar if kayit["meme_id"] not in cikarilanlar]
    if not kayitlar:
        return []
    # Etkilenen etiketler kaydın içeriğini açığa çıkarır; kişi yalnızca görebildiği kayıtları görür.
    meme_bazinda: dict[str, list] = {}
    sorgu = select(Annotation.id, Annotation.meme_id, Annotation.annotator_id, Annotation.durum_kodu, Annotation.kalibrasyon)
    for satir in session.exec(sorgu.where(Annotation.meme_id.in_({kayit["meme_id"] for kayit in kayitlar}))).all():
        meme_bazinda.setdefault(satir.meme_id, []).append(satir)
    gorunenler = []
    for kayit in kayitlar:
        annotationlar = meme_bazinda.get(kayit["meme_id"], [])
        if kayit["kayit_tipi"] == "gold":
            gorunur = gold_gorebilir_mi(kullanici.id, annotationlar)
        else:
            hedef = next(a for a in annotationlar if a.id == kayit["kayit_id"])
            gorunur = annotation_gorebilir_mi(kullanici, hedef, annotationlar)
        if gorunur:
            gorunenler.append(kayit)
    return gorunenler


@router.get("/audit", response_model=AuditPageOut)
def denetim_kaydi(
    kayit_tipi: Optional[KayitTipi] = None,
    kayit_id: Optional[str] = None,
    kullanici_id: Optional[str] = None,
    sayfa: int = Query(1, ge=1),
    boyut: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
    _: User = Depends(admin_kullanici),
):
    kosullar = []
    if kayit_tipi:
        kosullar.append(AuditEntry.kayit_tipi == kayit_tipi)
    if kayit_id:
        kosullar.append(AuditEntry.kayit_id == kayit_id)
    if kullanici_id:
        kosullar.append(AuditEntry.kullanici_id == kullanici_id)
    toplam = session.exec(select(func.count()).select_from(AuditEntry).where(*kosullar)).one()
    kayitlar = session.exec(
        select(AuditEntry).where(*kosullar)
        .order_by(AuditEntry.zaman.desc(), AuditEntry.id.desc())
        .offset((sayfa - 1) * boyut)
        .limit(boyut)
    ).all()
    kisiler = cikti.kullanicilar(session)
    return {
        "ogeler": [
            {
                "id": str(kayit.id),
                "zaman": kayit.zaman,
                "kullanici": cikti.kullanici_ref(kisiler.get(kayit.kullanici_id)),
                "kayit_tipi": kayit.kayit_tipi,
                "kayit_id": kayit.kayit_id,
                "islem": kayit.islem,
                "alan": kayit.alan,
                "eski_deger": kayit.eski_deger,
                "yeni_deger": kayit.yeni_deger,
            }
            for kayit in kayitlar
        ],
        "toplam": toplam,
        "sayfa": sayfa,
        "boyut": boyut,
    }


# --- Dışa aktarım: kullanıcılar takma adla (takma_ad, ör. a1) yazılır; havuz kararıyla
# çıkarılan meme'ler dışa aktarılmaz (ADR-0011) ---

def _takma_ref(kisiler: dict[str, User], kullanici_id: Optional[str]) -> Optional[dict]:
    kisi = kisiler.get(kullanici_id)
    return None if kisi is None else {"id": kisi.takma_ad, "gorunen_ad": kisi.takma_ad}


def gold_satirlari(session: Session, kisiler: dict[str, User], cikarilanlar: set[str]) -> list[dict]:
    memeler = {meme.id: meme for meme in session.exec(select(Meme)).all()}
    sahipler = dict(session.exec(select(Annotation.id, Annotation.annotator_id)).all())
    satirlar = []
    for gold in session.exec(select(GoldRecord).order_by(GoldRecord.meme_id)).all():
        if gold.meme_id in cikarilanlar:
            continue
        icerik = {**bos_icerik(), **gold.icerik}
        icerik["uyari"] = icerik["uyari"] or []  # gold.jsonl'de uyari her zaman listedir (ADR-0004)
        annotatorlar = []
        for annotation_id in gold.kaynak_annotationlar:
            takma = _takma_ref(kisiler, sahipler.get(annotation_id))
            if takma and takma["id"] not in annotatorlar:
                annotatorlar.append(takma["id"])
        reviewer = _takma_ref(kisiler, gold.reviewer_id)
        satirlar.append({
            "id": gold.meme_id,
            "gorsel": memeler[gold.meme_id].gorsel_yolu,
            **{alan: icerik.get(alan) for alan in ALAN_KURALLARI},
            "annotator": annotatorlar,
            "reviewer": reviewer["id"] if reviewer else None,
            "sema_versiyonu": gold.sema_versiyonu,
            "etiket_listesi_versiyonu": gold.etiket_listesi_versiyonu,
        })
    return satirlar


def annotation_satirlari(session: Session, kisiler: dict[str, User], cikarilanlar: set[str]) -> list[dict]:
    satirlar = []
    for annotation in session.exec(select(Annotation).order_by(Annotation.meme_id, Annotation.atanma_zamani, Annotation.id)).all():
        if annotation.meme_id in cikarilanlar:
            continue
        satir = {**cikti.annotation(annotation, kisiler), "annotator": _takma_ref(kisiler, annotation.annotator_id)}
        satirlar.append(AnnotationOut.model_validate(satir).model_dump(mode="json"))
    return satirlar


def sorgu_seti_satirlari(session: Session, kisiler: dict[str, User], cikarilanlar: set[str]) -> list[dict]:
    satirlar = []
    for sorgu in session.exec(select(TestQuery).order_by(TestQuery.zaman, TestQuery.id)).all():
        satir = {**cikti.test_sorgusu(sorgu, kisiler, cikarilanlar), "yazan": _takma_ref(kisiler, sorgu.yazan_id)}
        if not satir["dogru_memeler"]:
            continue  # bütün doğru cevapları çıkarılan sorgu ölçülemez
        satirlar.append(TestQueryOut.model_validate(satir).model_dump(mode="json"))
    return satirlar


def ai_taslak_satirlari(session: Session, kisiler: dict[str, User], cikarilanlar: set[str]) -> list[dict]:
    memeler = {meme.id: meme for meme in session.exec(select(Meme)).all()}
    return [
        {
            "id": taslak.meme_id,
            "gorsel": memeler[taslak.meme_id].gorsel_yolu,
            "kaynak": taslak.kaynak,
            "kart": taslak.kart,
            "icerik": {**bos_icerik(), **taslak.icerik},
            "olusturma_zamani": cikti.iso_zaman(taslak.olusturma_zamani),
        }
        for taslak in session.exec(select(AiDraft).order_by(AiDraft.meme_id)).all()
        if taslak.meme_id not in cikarilanlar
    ]


DISA_AKTARIMLAR = {
    "gold.jsonl": gold_satirlari,
    "annotations_raw.jsonl": annotation_satirlari,
    "test_set.jsonl": sorgu_seti_satirlari,
    "ai_drafts.jsonl": ai_taslak_satirlari,
}


@router.get("/export/{dosya}")
def disa_aktar(
    dosya: Literal["gold.jsonl", "annotations_raw.jsonl", "test_set.jsonl", "ai_drafts.jsonl"],
    session: Session = Depends(get_session),
    _: User = Depends(admin_kullanici),
):
    satirlar = DISA_AKTARIMLAR[dosya](session, cikti.kullanicilar(session), cikarilmis_memeler(session))
    govde = "".join(json.dumps(satir, ensure_ascii=False) + "\n" for satir in satirlar)
    return Response(
        content=govde,
        media_type="application/x-ndjson",
        headers={"Content-Disposition": f'attachment; filename="{dosya}"'},
    )
