"""Versiyonlu etiket listeleri (docs/annotation.md §3.6).

Her versiyon listenin tam halini saklar. İlk versiyon architecture.md §3.1'deki etiketlerle,
ADR-0008'deki sistem adlarıyla tohumlanır. Tanımlar etiketleme kılavuzu yazılana kadar kısa
taslaklardır; admin `PATCH /label-lists/labels/{alan}/{etiket}` ile düzeltir.
"""

import copy
from typing import Optional

from sqlalchemy import insert
from sqlalchemy import select as sa_select
from sqlmodel import Session, select

from app.models import LabelListVersion, simdi
from app.sema import ETIKET_ALANLARI

TOHUM_ETIKETLERI = {
    "duygu": [
        ("bikkinlik", "Bıkkınlık", "Tekrarlanan ya da uzayan bir durumdan usanmış, sıkılmış olmak."),
        ("saskinlik", "Şaşkınlık", "Beklenmedik bir şey karşısında şaşırıp kalmak."),
        ("suphe", "Şüphe", "Bir teklifin ya da davranışın ardında başka bir şey olduğunu düşünüp işkillenmek."),
        ("sevinc_zafer", "Sevinç/zafer", "Bir başarı ya da iyi bir gelişme karşısında sevinmek, zafer kazanmış gibi hissetmek."),
        ("utanc", "Utanç", "Mahcup olmak, rezil olmuş gibi hissetmek."),
        ("ofke", "Öfke", "Sinirlenmek, kızmak."),
        ("caresizlik", "Çaresizlik", "Elinden bir şey gelmemek, yapacak bir şey kalmamış gibi hissetmek."),
        ("ustunluk_kibir", "Üstünlük/kibir", "Kendini karşısındakinden üstün görmek, tepeden bakmak."),
        ("hayal_kirikligi", "Hayal kırıklığı", "Beklentinin karşılanmamasına üzülmek."),
        ("panik", "Panik", "Ani bir tehlike ya da baskı karşısında telaşa kapılmak."),
        ("sevimlilik", "Sevimlilik", "Tatlı, sevimli, içi ısıtan bir his."),
        ("umursamazlik", "Umursamazlık", "Olan biteni önemsememek, kayıtsız kalmak."),
    ],
    "niyet": [
        ("onaylama", "Onaylama", "Karşıdakine hak vermek, söyleneni onaylamak."),
        ("reddetme", "Reddetme", "Bir teklifi, fikri ya da isteği geri çevirmek."),
        ("alay_etme", "Alay etme", "Karşıdaki kişiyle ya da durumla dalga geçmek, iğnelemek."),
        ("tepki_gosterme", "Tepki gösterme", "Bir habere ya da duruma verilen anlık tepkiyi göstermek."),
        ("kendiyle_dalga_gecme", "Kendiyle dalga geçme", "Kendi hâliyle, hatasıyla ya da durumuyla dalga geçmek."),
        ("sikayet_isyan", "Şikayet/isyan", "Bir durumdan yakınmak, isyan etmek."),
        ("ovme", "Övme", "Karşıdakini ya da bir şeyi övmek, takdir etmek."),
        ("uyarma", "Uyarma", "Karşıdakini bir tehlikeye ya da hataya karşı uyarmak."),
        ("kabullenme", "Kabullenme", "Değiştirilemeyecek bir durumu boyun eğerek kabul etmek."),
        ("gecistirme", "Geçiştirme", "Konuyu kapatmak, cevap vermekten kaçınmak."),
    ],
    "mekanizma": [
        ("ironi", "İroni", "Söylenenle kastedilenin zıt olması."),
        ("abarti", "Abartı", "Durumu olduğundan çok daha büyük ya da küçük göstermek."),
        ("absurt", "Absürt", "Mantık dışı, saçma bir kurgu ya da görüntüden doğan mizah."),
        ("beklenti_gerceklik_zitligi", "Beklenti–gerçeklik zıtlığı", "Beklenen ile gerçekleşen arasındaki karşıtlık."),
        ("kendini_kucumseme", "Kendini küçümseme", "Kişinin kendini bilerek küçük düşürmesi."),
        ("karsilastirma", "Karşılaştırma (A vs B)", "İki şeyin yan yana konup karşılaştırılması."),
        ("bariz_olani_soyleme", "Bariz olanı söyleme", "Herkesin bildiği bir şeyi ciddiyetle söylemekten doğan mizah."),
        ("kulturel_gonderme", "Kültürel gönderme", "Bir filme, diziye, olaya ya da kişiye yapılan göndermeden doğan mizah."),
    ],
    "uyari": [
        ("politik", "Politik", "Siyasi bir kişi, parti, olay ya da görüş içeriyor."),
        ("kaba_argo", "Kaba/argo", "Küfür, kaba ya da argo ifade içeriyor."),
        ("hassas", "Hassas", "Din, ölüm, etnik köken gibi hassas konulara değiniyor."),
    ],
}


def yeni_etiket(etiket: str, gorunen_ad: str, tanim: str, ornekler: list[str], zaman) -> dict:
    return {
        "etiket": etiket,
        "gorunen_ad": gorunen_ad,
        "tanim": tanim,
        "ornekler": ornekler,
        "aktif": True,
        "eklenme_tarihi": zaman.isoformat(),
    }


def tohum_alanlari(zaman) -> dict:
    return {
        alan: [yeni_etiket(etiket, gorunen_ad, tanim, [], zaman) for etiket, gorunen_ad, tanim in TOHUM_ETIKETLERI[alan]]
        for alan in ETIKET_ALANLARI
    }


def etiket_listesi_tohumla(baglanti) -> bool:
    """Hiç etiket listesi yoksa ilk versiyonu (v1) yazar."""
    tablo = LabelListVersion.__table__
    if baglanti.execute(sa_select(tablo.c.sira).limit(1)).first() is not None:
        return False
    zaman = simdi()
    baglanti.execute(
        insert(tablo).values(
            sira=1,
            versiyon="v1",
            olusturma_zamani=zaman,
            olusturan_id=None,
            degisiklik_ozeti="İlk liste (architecture.md §3.1)",
            alanlar=tohum_alanlari(zaman),
        )
    )
    return True


def guncel_liste(session: Session, kilitle: bool = False) -> LabelListVersion:
    sorgu = select(LabelListVersion).order_by(LabelListVersion.sira.desc()).limit(1)
    if kilitle:
        # Aynı anda iki admin değişikliği aynı versiyon numarasını almasın.
        sorgu = sorgu.with_for_update()
    return session.exec(sorgu).one()


def liste_getir(session: Session, versiyon: str) -> Optional[LabelListVersion]:
    return session.exec(select(LabelListVersion).where(LabelListVersion.versiyon == versiyon)).first()


def etiket_bul(alanlar: dict, alan: str, etiket: str) -> Optional[dict]:
    return next((oge for oge in alanlar.get(alan, []) if oge["etiket"] == etiket), None)


def yeni_versiyon(session: Session, onceki: LabelListVersion, alanlar: dict, olusturan_id: str, ozet: str) -> LabelListVersion:
    sira = onceki.sira + 1
    versiyon = LabelListVersion(
        sira=sira,
        versiyon=f"v{sira}",
        olusturan_id=olusturan_id,
        degisiklik_ozeti=ozet,
        alanlar=copy.deepcopy(alanlar),
    )
    session.add(versiyon)
    return versiyon
