from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select
from typing import List, Dict, Any

from app.database import get_session
from app.errors import ApiHatasi
from app.models import Meme, Annotation
from app.services.guardrail import guardrail

router = APIRouter(prefix="/api/v1/search", tags=["search"])

@router.get("/")
def ara(
    q: str = Query(..., min_length=1, description="Kullanıcının arama sorgusu"),
    limit: int = Query(10, le=50),
    offset: int = 0,
    session: Session = Depends(get_session)
):
    # 1. Guardrail Denetimi: Kullanıcı küfürlü/ofansif bir şey aratıyor mu?
    guvenli, ofansiflik_skoru = guardrail.denetle(q)
    
    if not guvenli:
        raise ApiHatasi(
            status_kodu=400, # Arama için 400 Bad Request daha uygundur
            kod="GUVENSIZ_SORGU",
            mesaj="Arama sorgunuz topluluk kurallarına aykırı ifadeler içeriyor.",
            detay={
                "model": "emrecan/bert-base-turkish-cased-offensive",
                "ofansiflik_skoru": ofansiflik_skoru
            }
        )

    # 2. Onaylanmış Verileri Çekme (Sadece onaylananlar aranabilir, kalibrasyonlar hariç)
    statement = select(Annotation, Meme).join(Meme).where(
        Annotation.durum_kodu == "onaylandi",
        Annotation.kalibrasyon == False
    )
    
    tum_onaylilar = session.exec(statement).all()
    eslesenler = []

    # 3. Vektör Metni Sentezi ve Eşleştirme
    for annotation, meme in tum_onaylilar:
        icerik = annotation.icerik
        
        # Arama motorunun kullanacağı optimize edilmiş metin sentezi
        vektor_metni = (
            f"{icerik.get('gorsel_tanim', '')}. "
            f"{icerik.get('durum', '')}. "
            f"Etiketler: {' '.join(icerik.get('anahtar_kelimeler', []))}"
        )
        
        # Geçici Basit Arama (İleride burası ytu-ce-cosmos ile cosine_similarity olacak)
        if q.lower() in vektor_metni.lower():
            eslesenler.append({
                "meme_id": meme.id,
                "gorsel_yolu": meme.gorsel_yolu,
                "sentezlenen_metin": vektor_metni,
                "skor": 1.0  # Şimdilik sabit, ileride vektör benzerlik skoru olacak
            })
            
    # Sayfalama (Pagination)
    sayfalanmis = eslesenler[offset : offset + limit]
    
    return {
        "sorgu": q,
        "toplam_sonuc": len(eslesenler),
        "sonuclar": sayfalanmis
    }