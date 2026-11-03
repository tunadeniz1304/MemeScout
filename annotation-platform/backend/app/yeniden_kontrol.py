"""Yeniden kontrol listesi: eski etiket listesi versiyonuyla etiketlenmiş ve o zamandan beri
pasifleştirilen ya da tanımı değişen etiketleri kullanan annotation ve gold kayıtları
(docs/annotation.md §3.6).
"""

from sqlmodel import Session, select

from app.models import ATLANDI, Annotation, GoldRecord, LabelListVersion
from app.sema import ETIKET_ALANLARI

PASIFLESTIRILDI = "pasiflestirildi"
TANIM_DEGISTI = "tanim_degisti"


def etiket_farklari(eski_alanlar: dict, guncel_alanlar: dict) -> dict[tuple[str, str], str]:
    """Eski versiyonda etkin olup güncel versiyonda pasifleşen ya da tanımı değişen etiketler."""
    farklar = {}
    for alan in ETIKET_ALANLARI:
        guncel = {etiket["etiket"]: etiket for etiket in guncel_alanlar.get(alan, [])}
        for eski in eski_alanlar.get(alan, []):
            if not eski["aktif"]:
                continue
            yeni = guncel.get(eski["etiket"])
            if yeni is None or not yeni["aktif"]:
                farklar[(alan, eski["etiket"])] = PASIFLESTIRILDI
            elif yeni["tanim"] != eski["tanim"]:
                farklar[(alan, eski["etiket"])] = TANIM_DEGISTI
    return farklar


def _etkilenenler(icerik: dict, farklar: dict) -> list[dict]:
    etkilenen = []
    for alan in ETIKET_ALANLARI:
        for etiket in icerik.get(alan) or []:
            degisiklik = farklar.get((alan, etiket)) if isinstance(etiket, str) else None
            if degisiklik:
                etkilenen.append({"alan": alan, "etiket": etiket, "degisiklik": degisiklik})
    return etkilenen


def yeniden_kontrol_listesi(session: Session) -> list[dict]:
    versiyonlar = session.exec(select(LabelListVersion).order_by(LabelListVersion.sira)).all()
    guncel = versiyonlar[-1]
    farklar = {
        versiyon.versiyon: fark
        for versiyon in versiyonlar[:-1]
        if (fark := etiket_farklari(versiyon.alanlar, guncel.alanlar))
    }
    if not farklar:
        # Etiket listesi hiç değişmediyse içerikleri yüklemeye gerek yok.
        return []

    kayitlar = []
    annotationlar = session.exec(
        select(Annotation).where(Annotation.etiket_listesi_versiyonu.in_(farklar), Annotation.durum_kodu != ATLANDI)
    ).all()
    for annotation in annotationlar:
        etkilenen = _etkilenenler(annotation.icerik, farklar[annotation.etiket_listesi_versiyonu])
        if etkilenen:
            kayitlar.append({
                "kayit_tipi": "annotation",
                "kayit_id": annotation.id,
                "meme_id": annotation.meme_id,
                "eski_versiyon": annotation.etiket_listesi_versiyonu,
                "etkilenen_etiketler": etkilenen,
            })
    for gold in session.exec(select(GoldRecord).where(GoldRecord.etiket_listesi_versiyonu.in_(farklar))).all():
        etkilenen = _etkilenenler(gold.icerik, farklar[gold.etiket_listesi_versiyonu])
        if etkilenen:
            kayitlar.append({
                "kayit_tipi": "gold",
                "kayit_id": gold.meme_id,
                "meme_id": gold.meme_id,
                "eski_versiyon": gold.etiket_listesi_versiyonu,
                "etkilenen_etiketler": etkilenen,
            })
    return sorted(kayitlar, key=lambda kayit: (kayit["meme_id"], kayit["kayit_tipi"] != "gold", kayit["kayit_id"]))
