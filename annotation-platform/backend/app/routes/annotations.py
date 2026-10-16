from datetime import datetime, timezone
from typing import List

from app.services.guardrail import guardrail

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.errors import ApiHatasi
from app.models import User, Annotation, Comment, Rating
from app.schemas import (
    AnnotationDraftRequest, AnnotationSubmitRequest, AnnotationResponse,
    CommentCreate, CommentResponse, RatingCreate, RatingResponse
)
from app.security import aktif_kullanici

router = APIRouter(prefix="/api/v1/annotations", tags=["annotations"])

def simdi():
    return datetime.now(timezone.utc)

# -------------------------------------------------------------------
# 1. TASLAK KAYDETME (Optimistic Locking Korumalı)
# -------------------------------------------------------------------
@router.patch("/{id}/draft", response_model=AnnotationResponse)
def taslak_kaydet(
    id: str,
    req: AnnotationDraftRequest,
    session: Session = Depends(get_session),
    kullanici: User = Depends(aktif_kullanici)
):
    annotation = session.get(Annotation, id)
    if not annotation:
        raise ApiHatasi(404, "BULUNAMADI", "Annotation bulunamadı.")
    
    if annotation.annotator_id != kullanici.id:
        raise ApiHatasi(403, "YASAK", "Bu annotation size ait değil.")
        
    # ADR-0005: Sürüm Çakışması Kontrolü (Aynı dosya iki sekmede açıksa)
    if annotation.surum != req.surum:
        raise ApiHatasi(
            409, "SURUM_CAKISMASI", 
            "Veri başka bir sekmede güncellenmiş. Sayfayı yenileyin.",
            detay={"guncel_surum": annotation.surum}
        )

    # İlgili alanları güncelle ve sürümü 1 artır
    annotation.icerik = req.icerik
    annotation.surum += 1
    annotation.guncellenme_zamani = simdi()

    session.add(annotation)
    session.commit()
    session.refresh(annotation)
    
    return annotation

# -------------------------------------------------------------------
# 2. GÖNDERME (Submit)
# -------------------------------------------------------------------
# -------------------------------------------------------------------
# 2. GÖNDERME (Submit) ve BERT Guardrail
# -------------------------------------------------------------------
@router.post("/{id}/submit", response_model=AnnotationResponse)
def gonder(
    id: str,
    req: AnnotationSubmitRequest,
    session: Session = Depends(get_session),
    kullanici: User = Depends(aktif_kullanici)
):
    annotation = session.get(Annotation, id)
    if not annotation:
        raise ApiHatasi(404, "BULUNAMADI", "Annotation bulunamadı.")
        
    if annotation.surum != req.surum:
        raise ApiHatasi(409, "SURUM_CAKISMASI", "Sürüm uyumsuz.")

    # 1. Metinleri Sentezle
    # Pydantic'ten dict olarak veya obje olarak dönmesine göre uyarlama
    icerik_dict = annotation.icerik
    kontrol_metni = (
        f"{icerik_dict.get('gorsel_tanim', '')} "
        f"{icerik_dict.get('durum', '')} "
        f"{' '.join(icerik_dict.get('anahtar_kelimeler', []))}"
    )

    # 2. ADR-0013: BERT Guardrail Denetimi
    guvenli, ofansiflik_skoru = guardrail.denetle(kontrol_metni)
    
    if not guvenli:
        raise ApiHatasi(
            status_kodu=422, 
            kod="GUVENSIZ_ICERIK", 
            mesaj="Metin, Hugging Face BERT içerik denetim modeli tarafından zararlı veya uygunsuz olarak değerlendirildi.",
            detay={
                "model": "emrecan/bert-base-turkish-cased-offensive",
                "ofansiflik_skoru": ofansiflik_skoru
            }
        )

    # 3. Güvenliyse Gönder
    annotation.durum_kodu = "gonderildi"
    annotation.gonderme_zamani = simdi()
    annotation.surum += 1
    
    session.add(annotation)
    session.commit()
    session.refresh(annotation)
    
    return annotation
# -------------------------------------------------------------------
# 3. YORUM YAPMA (Diğer Ekip Üyeleri İçin Asenkron İletişim)
# -------------------------------------------------------------------
@router.post("/{id}/comments", response_model=CommentResponse)
def yorum_ekle(
    id: str,
    req: CommentCreate,
    session: Session = Depends(get_session),
    kullanici: User = Depends(aktif_kullanici)
):
    annotation = session.get(Annotation, id)
    if not annotation:
        raise ApiHatasi(404, "BULUNAMADI", "Annotation bulunamadı.")
        
    # Yorum nesnesini oluştur
    yeni_yorum = Comment(
        meme_id=annotation.meme_id,
        yazan_id=kullanici.id,
        metin=req.metin,
        tur=req.tur
    )
    session.add(yeni_yorum)
    session.commit()
    session.refresh(yeni_yorum)
    
    return yeni_yorum

# -------------------------------------------------------------------
# 4. PUANLAMA VE EŞİK KONTROLÜ (ADR-0010)
# -------------------------------------------------------------------
@router.post("/{id}/rate", response_model=RatingResponse)
def puan_ver(
    id: str,
    req: RatingCreate,
    session: Session = Depends(get_session),
    kullanici: User = Depends(aktif_kullanici)
):
    annotation = session.get(Annotation, id)
    if not annotation:
        raise ApiHatasi(404, "BULUNAMADI", "Annotation bulunamadı.")
        
    # Annotator kendi işine puan veremez!
    if annotation.annotator_id == kullanici.id:
        raise ApiHatasi(403, "YASAK", "Kendi etiketlemenize puan veremezsiniz.")

    # Puanı kaydet
    yeni_puan = Rating(
        annotation_id=annotation.id,
        veren_id=kullanici.id,
        puan=req.puan
    )
    session.add(yeni_puan)
    session.commit()

    # Eşik Algoritması: Tüm puanların ortalamasını al
    tum_puanlar = session.exec(select(Rating).where(Rating.annotation_id == id)).all()
    ortalama = sum(p.puan for p in tum_puanlar) / len(tum_puanlar)

    # ADR-0010 Kuralı İşletimi
    if ortalama < 2.0:
        annotation.durum_kodu = "reddedildi"
    elif ortalama < 2.5:
        annotation.durum_kodu = "tekrar_gozden_gecirilmeli"
        annotation.revizyon_notu = "Ekip ortalaması düşük, revizyon gerekli."
    else:
        annotation.durum_kodu = "onaylandi"

    session.add(annotation)
    session.commit()
    session.refresh(yeni_puan)
    
    return yeni_puan