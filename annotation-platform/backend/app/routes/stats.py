from collections import Counter

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app import cikti
from app.database import get_session
from app.kurallar import (
    ATANMADI,
    BEKLEYEN_DURUMLAR,
    GONDERILMIS_DURUMLAR,
    INCELEME_BEKLIYOR,
    MemeBaglami,
    aktif_mi,
    cift_etiket_mi,
    grubu,
    kor_mu,
)
from app.models import ATLANDI, REVIZYON_GEREKLI, Annotation, GoldRecord, Meme, User, simdi
from app.olcum import DUSUK_UYUM_SINIRI, cohen_kappa, krippendorff_alpha, masi_mesafesi, yuvarla
from app.schemas import AgreementStatsOut, ProgressStatsOut
from app.security import aktif_kullanici
from app.sema import ETIKET_ALANLARI

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])


def yeniden_atama_bekleyen(baglam: MemeBaglami, yerine_gecmeyenler: set[str]) -> int:
    """Atlanmış, yerine kimse atanmamış ve meme'inde hâlâ annotator eksik olan ana tur annotation'ları."""
    sayi = 0
    for meme_id, annotationlar in baglam.annotationlar.items():
        if baglam.gold_var(meme_id):
            continue
        gereken = 2 if cift_etiket_mi(annotationlar) else 1
        eksik = gereken - len(grubu(annotationlar, False))
        atlananlar = [
            a for a in annotationlar
            if not a.kalibrasyon and a.durum_kodu == ATLANDI and a.id in yerine_gecmeyenler
        ]
        sayi += min(max(eksik, 0), len(atlananlar))
    return sayi


@router.get("/progress", response_model=ProgressStatsOut)
def ilerleme(
    session: Session = Depends(get_session),
    _: User = Depends(aktif_kullanici),
):
    baglam = MemeBaglami(session)
    meme_idleri = session.exec(select(Meme.id)).all()
    durumlar = Counter(baglam.durum(meme_id) for meme_id in meme_idleri)
    yerine_gecmeyenler = set(session.exec(
        select(Annotation.id).where(Annotation.durum_kodu == ATLANDI, Annotation.yerine_gecen_id == None)  # noqa: E711
    ).all())
    satirlar = session.exec(select(Annotation.annotator_id, Annotation.durum_kodu, Annotation.harcanan_sure_sn)).all()

    kisiler = []
    for kisi in sorted(cikti.kullanicilar(session).values(), key=lambda k: k.kullanici_adi):
        kendi = [satir for satir in satirlar if satir.annotator_id == kisi.id]
        tamamlanan = [satir for satir in kendi if satir.durum_kodu in GONDERILMIS_DURUMLAR]
        kisiler.append({
            "kullanici": cikti.kullanici_ref(kisi),
            "atanan": len(kendi),
            "tamamlanan": len(tamamlanan),
            "kalan": sum(1 for satir in kendi if satir.durum_kodu in BEKLEYEN_DURUMLAR),
            "atlanan": sum(1 for satir in kendi if satir.durum_kodu == ATLANDI),
            "revizyon_bekleyen": sum(1 for satir in kendi if satir.durum_kodu == REVIZYON_GEREKLI),
            "ortalama_sure_sn": (
                round(sum(satir.harcanan_sure_sn for satir in tamamlanan) / len(tamamlanan), 1) if tamamlanan else None
            ),
        })
    return {
        "genel": {
            "toplam_meme": len(meme_idleri),
            "atanmamis": durumlar[ATANMADI],
            "gold_hazir": len(session.exec(select(GoldRecord.meme_id)).all()),
            "inceleme_bekleyen": durumlar[INCELEME_BEKLIYOR],
            "yeniden_atama_bekleyen": yeniden_atama_bekleyen(baglam, yerine_gecmeyenler),
        },
        "kullanicilar": kisiler,
    }


def _alan_sonucu(alan: str, metrik: str, deger, n: int) -> dict:
    deger = yuvarla(deger)
    return {"alan": alan, "metrik": metrik, "deger": deger, "n": n, "dusuk_uyum": deger is not None and deger < DUSUK_UYUM_SINIRI}


@router.get("/agreement", response_model=AgreementStatsOut, response_model_exclude_unset=True)
def uyum(
    session: Session = Depends(get_session),
    kullanici: User = Depends(aktif_kullanici),
):
    ana_tur = session.exec(select(Annotation).where(Annotation.kalibrasyon == False)).all()  # noqa: E712
    meme_bazinda: dict[str, list[Annotation]] = {}
    for annotation in ana_tur:
        meme_bazinda.setdefault(annotation.meme_id, []).append(annotation)

    # Yalnızca iki annotation'ı da gönderilmiş çift etiketli meme'ler; kalibrasyon turu katılmaz.
    ciftler = []
    kor_etiketleme_suruyor = False
    for annotationlar in meme_bazinda.values():
        if not cift_etiket_mi(annotationlar):
            continue
        aktifler = [a for a in annotationlar if aktif_mi(a)]
        kor_etiketleme_suruyor = kor_etiketleme_suruyor or kor_mu(aktifler)
        if len(aktifler) == 2 and all(a.durum_kodu in GONDERILMIS_DURUMLAR for a in aktifler):
            ciftler.append(sorted(aktifler, key=lambda a: (a.gonderme_zamani, a.id)))

    tur_ciftleri = [
        (a.icerik.get("tur"), b.icerik.get("tur")) for a, b in ciftler
        if a.icerik.get("tur") is not None and b.icerik.get("tur") is not None
    ]
    alanlar = [_alan_sonucu("tur", "cohen_kappa", cohen_kappa(tur_ciftleri), len(tur_ciftleri))]
    etiketler = []
    for alan in ETIKET_ALANLARI:
        kume_ciftleri = [(frozenset(a.icerik.get(alan) or []), frozenset(b.icerik.get(alan) or [])) for a, b in ciftler]
        alanlar.append(_alan_sonucu(alan, "krippendorff_alpha_masi", krippendorff_alpha(kume_ciftleri, masi_mesafesi), len(kume_ciftleri)))
        kullanilanlar = sorted({etiket for a, b in kume_ciftleri for etiket in a | b})
        for etiket in kullanilanlar:
            ikili = [(etiket in a, etiket in b) for a, b in kume_ciftleri]
            etiketler.append({
                "alan": alan,
                "etiket": etiket,
                "kappa": yuvarla(cohen_kappa(ikili)),
                "anlasmazlik_sayisi": sum(1 for x, y in ikili if x != y),
                "kullanim_sayisi": sum(x + y for x, y in ikili),
            })

    sonuc = {"hesaplama_zamani": simdi(), "cift_etiketli_meme_sayisi": len(ciftler), "alanlar": alanlar}
    # Kör etiketleme sürerken etiket bazında ayrıntıyı yalnızca admin görür.
    if kullanici.admin or not kor_etiketleme_suruyor:
        sonuc["etiketler"] = sorted(
            etiketler, key=lambda satir: (-satir["anlasmazlik_sayisi"], -satir["kullanim_sayisi"], satir["alan"], satir["etiket"])
        )
    return sonuc
