"""Sunucuda uygulanan süreç kuralları: kör etiketleme, reviewer kısıtı ve meme durumu.

Bir meme'in annotation'ları iki tura ayrılır: ana tur ve kalibrasyon turu. "Grup", bir turdaki
atlanmamış annotation'lardır; gruptaki biri henüz göndermediyse grup "kör"dür ve gruptaki kişiler
birbirinin annotation'ını ve yorumlarını göremez (ADR-0003). Kendi annotation'ı açık olan kişi
(hangi turda olursa olsun) o meme'de başkalarının etiketlerini ve yorumlarını göremez, reviewer
da olamaz. Kurallar, meme'in annotator'ı olan admin için de geçerlidir.
"""

from typing import Iterable, Optional

from sqlmodel import Session, select

from app.models import (
    ATANDI,
    ATLANDI,
    DEVAM_EDIYOR,
    GONDERILDI,
    ONAYLANDI,
    REVIZYON_GEREKLI,
    Annotation,
    Comment,
    GoldRecord,
    User,
)
from app.yeniden_kontrol import yeniden_kontrol_listesi

BEKLEYEN_DURUMLAR = (ATANDI, DEVAM_EDIYOR, REVIZYON_GEREKLI)
GONDERILMIS_DURUMLAR = (GONDERILDI, ONAYLANDI)

# Sözleşmedeki MemeLabelStatus değerleri
ATANMADI = "atanmadi"
ETIKETLENIYOR = "etiketleniyor"
INCELEME_BEKLIYOR = "inceleme_bekliyor"
GOLD_HAZIR = "gold_hazir"
YENIDEN_KONTROL = "yeniden_kontrol"


def aktif_mi(annotation) -> bool:
    return annotation.durum_kodu != ATLANDI


def bekliyor_mu(annotation) -> bool:
    return annotation.durum_kodu in BEKLEYEN_DURUMLAR


def grubu(meme_annotationlari: Iterable, kalibrasyon: bool) -> list:
    return [a for a in meme_annotationlari if a.kalibrasyon == kalibrasyon and aktif_mi(a)]


def kor_mu(grup: list) -> bool:
    return any(bekliyor_mu(a) for a in grup)


def acik_annotationi_var_mi(kullanici_id: str, meme_annotationlari: list) -> bool:
    return any(a.annotator_id == kullanici_id and bekliyor_mu(a) for a in meme_annotationlari)


def gizli_yazarlar(kullanici_id: str, meme_annotationlari: list) -> set[str]:
    """Bu kullanıcının, bu meme'de yorumlarını göremeyeceği kişiler."""
    if acik_annotationi_var_mi(kullanici_id, meme_annotationlari):
        # Kendi etiketini bitirmeyen kişi meme'in diğer annotator'larının yorumlarını görmez.
        return {a.annotator_id for a in meme_annotationlari if a.annotator_id != kullanici_id}
    gizli: set[str] = set()
    for kendi in meme_annotationlari:
        if kendi.annotator_id != kullanici_id or not aktif_mi(kendi):
            continue
        if kor_mu(grubu(meme_annotationlari, kendi.kalibrasyon)):
            # Atlayan kişi de grubun parçasıydı; atlamadan önce yazdığı yorum da gizli kalır.
            gizli |= {
                a.annotator_id
                for a in meme_annotationlari
                if a.kalibrasyon == kendi.kalibrasyon and a.annotator_id != kullanici_id
            }
    return gizli


def annotation_gorebilir_mi(kullanici: User, annotation, meme_annotationlari: list) -> bool:
    """Sahibi her zaman görür. Kendi annotation'ı açık olan kimse görmez. Grup kör değilse
    (hepsi gönderildiyse) herkes görür; kör gruptaki annotation'ı yalnızca o gruba katılmayan admin görür."""
    if annotation.annotator_id == kullanici.id:
        return True
    if acik_annotationi_var_mi(kullanici.id, meme_annotationlari):
        return False
    grup = grubu(meme_annotationlari, annotation.kalibrasyon)
    if not kor_mu(grup):
        return True
    return kullanici.admin and all(a.annotator_id != kullanici.id for a in grup)


def gold_gorebilir_mi(kullanici_id: str, meme_annotationlari: list) -> bool:
    # Kendi annotation'ı gönderilmemiş annotator gold kaydını göremez.
    return not acik_annotationi_var_mi(kullanici_id, meme_annotationlari)


def reviewer_olabilir_mi(kullanici_id: str, meme_annotationlari: list) -> bool:
    # Kalibrasyonda herkes aynı meme'leri etiketler; reviewer kısıtı ana tura bakar. Kalibrasyon
    # annotation'ı hâlâ açık olan kişi de, başkalarının etiketlerini görmemesi için reviewer olamaz.
    if any(a.annotator_id == kullanici_id for a in grubu(meme_annotationlari, False)):
        return False
    return not acik_annotationi_var_mi(kullanici_id, meme_annotationlari)


def cift_etiket_mi(meme_annotationlari: list) -> bool:
    return any(a.cift_etiket for a in meme_annotationlari if not a.kalibrasyon)


def incelemeye_hazir_mi(meme_annotationlari: list) -> bool:
    """Ana turdaki annotation'ların hepsi gönderildi mi (çift etiketlide iki, tek etiketlide bir)."""
    grup = grubu(meme_annotationlari, False)
    gereken = 2 if cift_etiket_mi(meme_annotationlari) else 1
    return len(grup) >= gereken and all(a.durum_kodu == GONDERILDI for a in grup)


def meme_durumu(meme_annotationlari: list, gold_var: bool, yeniden_kontrol: bool = False) -> str:
    if yeniden_kontrol:
        return YENIDEN_KONTROL
    if gold_var:
        return GOLD_HAZIR
    if not grubu(meme_annotationlari, False):
        return ATANMADI
    if incelemeye_hazir_mi(meme_annotationlari):
        return INCELEME_BEKLIYOR
    return ETIKETLENIYOR


class MemeBaglami:
    """Meme listesi ve detayı için annotation, gold ve yorum özetlerini toplu yükler.

    Annotation içerikleri yüklenmez; durum türetmek için süreç alanları yeterli.
    """

    def __init__(self, session: Session, meme_idleri: Optional[list[str]] = None):
        annotation_sorgusu = select(
            Annotation.id,
            Annotation.meme_id,
            Annotation.annotator_id,
            Annotation.durum_kodu,
            Annotation.cift_etiket,
            Annotation.kalibrasyon,
            Annotation.atanma_zamani,
            Annotation.gonderme_zamani,
        ).order_by(Annotation.atanma_zamani, Annotation.id)
        gold_sorgusu = select(GoldRecord.meme_id, GoldRecord.icerik["ad"].as_string())
        yorum_sorgusu = select(Comment.meme_id, Comment.yazan_id).where(Comment.cozuldu == False)  # noqa: E712
        if meme_idleri is not None:
            annotation_sorgusu = annotation_sorgusu.where(Annotation.meme_id.in_(meme_idleri))
            gold_sorgusu = gold_sorgusu.where(GoldRecord.meme_id.in_(meme_idleri))
            yorum_sorgusu = yorum_sorgusu.where(Comment.meme_id.in_(meme_idleri))

        self.annotationlar: dict[str, list] = {}
        for satir in session.exec(annotation_sorgusu).all():
            self.annotationlar.setdefault(satir.meme_id, []).append(satir)
        self.gold_adlari: dict[str, Optional[str]] = dict(session.exec(gold_sorgusu).all())
        self.acik_yorumlar: dict[str, list[str]] = {}
        for meme_id, yazan_id in session.exec(yorum_sorgusu).all():
            self.acik_yorumlar.setdefault(meme_id, []).append(yazan_id)

        # Gold kaydı ya da gönderilmiş bir ana tur annotation'ı yeniden kontrol listesindeyse meme
        # yeniden_kontrol durumuna düşer. Taslaktaki pasif etiket ise gönderimde zaten yakalanır.
        gonderilmisler = {
            a.id for liste in self.annotationlar.values() for a in liste
            if a.durum_kodu in GONDERILMIS_DURUMLAR and not a.kalibrasyon
        }
        self.yeniden_kontrol = {
            kayit["meme_id"] for kayit in yeniden_kontrol_listesi(session)
            if kayit["kayit_tipi"] == "gold" or kayit["kayit_id"] in gonderilmisler
        }

    def meme_annotationlari(self, meme_id: str) -> list:
        return self.annotationlar.get(meme_id, [])

    def gold_var(self, meme_id: str) -> bool:
        return meme_id in self.gold_adlari

    def durum(self, meme_id: str) -> str:
        return meme_durumu(self.meme_annotationlari(meme_id), self.gold_var(meme_id), meme_id in self.yeniden_kontrol)

    def annotatorlar(self, meme_id: str) -> list[str]:
        idler: list[str] = []
        for annotation in self.meme_annotationlari(meme_id):
            if aktif_mi(annotation) and annotation.annotator_id not in idler:
                idler.append(annotation.annotator_id)
        return idler

    def cift_etiket(self, meme_id: str) -> bool:
        return cift_etiket_mi(self.meme_annotationlari(meme_id))

    def ad(self, meme_id: str) -> Optional[str]:
        return self.gold_adlari.get(meme_id)

    def acik_yorum_sayisi(self, meme_id: str, kullanici_id: str) -> int:
        gizli = gizli_yazarlar(kullanici_id, self.meme_annotationlari(meme_id))
        return sum(1 for yazan_id in self.acik_yorumlar.get(meme_id, []) if yazan_id not in gizli)


def meme_annotationlari(session: Session, meme_id: str) -> list:
    """Kural kontrolleri için bir meme'in annotation'larının süreç alanları."""
    sorgu = select(
        Annotation.id,
        Annotation.meme_id,
        Annotation.annotator_id,
        Annotation.durum_kodu,
        Annotation.cift_etiket,
        Annotation.kalibrasyon,
        Annotation.gonderme_zamani,
    ).where(Annotation.meme_id == meme_id)
    return session.exec(sorgu).all()


def gizli_yorum_yazarlari(session: Session, kullanici_id: str) -> dict[str, set[str]]:
    """meme_id → bu kullanıcıdan gizlenen yorum yazarları. Yalnızca kullanıcının
    annotation'ı olan meme'ler kör etiketlemeye girebilir."""
    meme_idleri = session.exec(select(Annotation.meme_id).where(Annotation.annotator_id == kullanici_id)).all()
    if not meme_idleri:
        return {}
    meme_bazinda: dict[str, list] = {}
    sorgu = select(Annotation.meme_id, Annotation.annotator_id, Annotation.durum_kodu, Annotation.kalibrasyon)
    for satir in session.exec(sorgu.where(Annotation.meme_id.in_(set(meme_idleri)))).all():
        meme_bazinda.setdefault(satir.meme_id, []).append(satir)
    gizli = {}
    for meme_id, annotationlar in meme_bazinda.items():
        yazarlar = gizli_yazarlar(kullanici_id, annotationlar)
        if yazarlar:
            gizli[meme_id] = yazarlar
    return gizli


def gold_katkicilari(session: Session, meme_id: str) -> set[str]:
    """Sızıntı kuralı (ADR-0002): gold kaydının kaynak annotation sahipleri ve reviewer'ı.

    Gold kaydı henüz yoksa katkı verecek olanlar, meme'in ana turdaki annotator'larıdır.
    """
    gold = session.get(GoldRecord, meme_id)
    if gold is None:
        return {a.annotator_id for a in grubu(meme_annotationlari(session, meme_id), False)}
    kaynaklar = set(gold.kaynak_annotationlar)
    sahipler = session.exec(select(Annotation.annotator_id).where(Annotation.id.in_(kaynaklar))).all() if kaynaklar else []
    return set(sahipler) | ({gold.reviewer_id} if gold.reviewer_id else set())
