from datetime import timedelta

import pytest
from sqlmodel import select

from app.models import Annotation, AuditEntry, GoldRecord, simdi
from tests.yardimci import basliklar, gecerli_icerik


@pytest.fixture()
def yonetici(kullanici_olustur):
    return kullanici_olustur("yonetici", admin=True)


@pytest.fixture()
def ali(kullanici_olustur):
    return kullanici_olustur("ali")


@pytest.fixture()
def ayse(kullanici_olustur):
    return kullanici_olustur("ayse")


@pytest.fixture()
def can(kullanici_olustur):
    return kullanici_olustur("can")


@pytest.fixture()
def gonderilmis(annotation_olustur):
    def olustur(meme, kisi, dakika_once=0, **alanlar):
        varsayilan = {
            "durum_kodu": "gonderildi",
            "icerik": gecerli_icerik(),
            "tanidiklik": 4,
            "gonderme_zamani": simdi() - timedelta(minutes=dakika_once),
        }
        return annotation_olustur(meme, kisi, **{**varsayilan, **alanlar})

    return olustur


def kuyruk(client, kisi):
    yanit = client.get("/api/v1/reviews", headers=basliklar(kisi))
    assert yanit.status_code == 200
    return yanit.json()


def gold_gonder(client, kisi, meme_id, kaynaklar, icerik=None, **ek):
    return client.post(
        f"/api/v1/reviews/{meme_id}/gold",
        json={"icerik": icerik or gecerli_icerik(), "kaynak_annotationlar": kaynaklar, **ek},
        headers=basliklar(kisi),
    )


# ------------------------------------------------------------------ GET /reviews

def test_inceleme_kuyrugu_annotator_olmayanlara_hazir_memeleri_gosterir(
    client, session, yonetici, ali, ayse, can, meme_olustur, annotation_olustur, gonderilmis
):
    tek = meme_olustur(yonetici)
    tek_annotation = gonderilmis(tek, ali, dakika_once=5)
    cift = meme_olustur(yonetici)
    cift_a = gonderilmis(cift, ali, cift_etiket=True, dakika_once=10)
    cift_b = gonderilmis(cift, ayse, cift_etiket=True, dakika_once=20)
    yarim = meme_olustur(yonetici)
    gonderilmis(yarim, ali, cift_etiket=True)
    annotation_olustur(yarim, can, cift_etiket=True, durum_kodu="devam_ediyor")
    kalibrasyon = meme_olustur(yonetici)
    gonderilmis(kalibrasyon, ali, kalibrasyon=True)
    goldlu = meme_olustur(yonetici)
    gonderilmis(goldlu, ali, durum_kodu="onaylandi")
    session.add(GoldRecord(meme_id=goldlu.id, icerik=gecerli_icerik(), sema_versiyonu="1.0", etiket_listesi_versiyonu="v1"))
    session.commit()

    can_kuyrugu = kuyruk(client, can)
    assert [(oge["meme_id"], oge["cift_etiket"]) for oge in can_kuyrugu] == [(cift.id, True), (tek.id, False)]
    assert set(can_kuyrugu[0]["annotation_ids"]) == {cift_a.id, cift_b.id}
    assert can_kuyrugu[1]["annotation_ids"] == [tek_annotation.id]
    assert can_kuyrugu[1]["kucuk_gorsel_url"] == f"/api/v1/memes/{tek.id}/image?boyut=kucuk"
    assert [oge["meme_id"] for oge in kuyruk(client, ayse)] == [tek.id]
    assert kuyruk(client, ali) == []
    assert [oge["meme_id"] for oge in kuyruk(client, yonetici)] == [cift.id, tek.id]


# ------------------------------------------------------------------ GET /reviews/{meme_id}

def test_anlasmazlik_ekrani_alan_bazinda_karsilastirir(client, yonetici, ali, ayse, can, meme_olustur, gonderilmis):
    meme = meme_olustur(yonetici)
    gonderilmis(meme, ali, cift_etiket=True, dakika_once=2, icerik=gecerli_icerik(duygu=["suphe", "saskinlik"], niyet=["onaylama"]))
    gonderilmis(meme, ayse, cift_etiket=True, icerik=gecerli_icerik(duygu=["saskinlik", "suphe"], niyet=["reddetme"], durum="Bambaşka bir durum iskeleti burada."))

    yanit = client.get(f"/api/v1/reviews/{meme.id}", headers=basliklar(can))
    assert yanit.status_code == 200
    detay = yanit.json()
    assert detay["meme"]["id"] == meme.id and detay["meme"]["etiket_durumu"] == "inceleme_bekliyor"
    assert len(detay["annotasyonlar"]) == 2
    karsilastirma = {satir["alan"]: satir for satir in detay["karsilastirma"]}
    assert karsilastirma["duygu"] == {"alan": "duygu", "ayni": True, "ortak_etiketler": ["suphe", "saskinlik"]}
    assert karsilastirma["niyet"] == {"alan": "niyet", "ayni": False, "ortak_etiketler": []}
    assert karsilastirma["durum"]["ayni"] is False
    assert karsilastirma["ad"]["ayni"] is True and karsilastirma["ad"]["ortak_etiketler"] is None


def test_inceleme_ekrani_kurallari(client, yonetici, ali, can, meme_olustur, annotation_olustur, gonderilmis):
    tek = meme_olustur(yonetici)
    gonderilmis(tek, ali)
    detay = client.get(f"/api/v1/reviews/{tek.id}", headers=basliklar(can)).json()
    assert len(detay["annotasyonlar"]) == 1 and detay["karsilastirma"] == []

    yanit = client.get(f"/api/v1/reviews/{tek.id}", headers=basliklar(ali))
    assert (yanit.status_code, yanit.json()["hata"]["kod"]) == (403, "REVIEWER_ANNOTATOR_OLAMAZ")

    hazir_degil = meme_olustur(yonetici)
    annotation_olustur(hazir_degil, ali, durum_kodu="devam_ediyor")
    assert client.get(f"/api/v1/reviews/{hazir_degil.id}", headers=basliklar(can)).status_code == 409
    assert client.get("/api/v1/reviews/m0404", headers=basliklar(can)).status_code == 404


# ------------------------------------------------------------------ POST /reviews/{meme_id}/gold

def test_reviewer_cift_etiketli_meme_icin_gold_onaylar(client, session, yonetici, ali, ayse, can, meme_olustur, gonderilmis):
    meme = meme_olustur(yonetici)
    a = gonderilmis(meme, ali, cift_etiket=True)
    b = gonderilmis(meme, ayse, cift_etiket=True)
    birlesik = gecerli_icerik(duygu=["suphe"], notlar="İki annotation birleştirildi")
    yanit = gold_gonder(client, can, meme.id, [a.id, b.id], icerik=birlesik, cozum_notu="duygu ortak alındı")
    assert yanit.status_code == 201
    gold = yanit.json()
    assert gold["reviewer"] == {"id": can.id, "gorunen_ad": "Can"}
    assert gold["kaynak_annotationlar"] == [a.id, b.id]
    assert gold["icerik"]["duygu"] == ["suphe"] and gold["cozum_notu"] == "duygu ortak alındı"
    assert (gold["sema_versiyonu"], gold["etiket_listesi_versiyonu"]) == ("1.0", "v1")

    session.expire_all()
    assert {x.durum_kodu for x in session.exec(select(Annotation)).all()} == {"onaylandi"}
    meme_bilgisi = client.get(f"/api/v1/memes/{meme.id}", headers=basliklar(can)).json()
    assert (meme_bilgisi["etiket_durumu"], meme_bilgisi["gold_var"], meme_bilgisi["ad"]) == ("gold_hazir", True, "Hayırdır inşallah")
    assert kuyruk(client, can) == []
    assert session.exec(select(AuditEntry).where(AuditEntry.kayit_tipi == "gold")).one().kayit_id == meme.id

    tekrar = gold_gonder(client, yonetici, meme.id, [a.id])
    assert (tekrar.status_code, tekrar.json()["hata"]["kod"]) == (409, "GECERSIZ_DURUM_GECISI")


def test_tek_etiketli_meme_ikinci_bakisla_kesinlesir(client, session, yonetici, ali, ayse, meme_olustur, gonderilmis):
    meme = meme_olustur(yonetici)
    annotation = gonderilmis(meme, ali)
    gold = gold_gonder(client, ayse, meme.id, [annotation.id]).json()
    assert gold["reviewer"]["id"] == ayse.id
    session.refresh(annotation)
    assert annotation.durum_kodu == "onaylandi"


def test_annotator_ve_memei_etiketleyen_admin_gold_onaylayamaz(client, yonetici, ali, ayse, meme_olustur, gonderilmis):
    meme = meme_olustur(yonetici)
    a = gonderilmis(meme, yonetici, cift_etiket=True)
    gonderilmis(meme, ali, cift_etiket=True)
    for kisi in (ali, yonetici):
        yanit = gold_gonder(client, kisi, meme.id, [a.id])
        assert (yanit.status_code, yanit.json()["hata"]["kod"]) == (403, "REVIEWER_ANNOTATOR_OLAMAZ")
    assert gold_gonder(client, ayse, meme.id, [a.id]).status_code == 201


def test_gold_icerigi_ve_kaynaklari_dogrulanir(client, yonetici, ali, ayse, can, meme_olustur, annotation_olustur, gonderilmis):
    meme = meme_olustur(yonetici)
    a = gonderilmis(meme, ali)
    baska = annotation_olustur(meme_olustur(yonetici), ayse, durum_kodu="gonderildi")
    yanit = gold_gonder(client, can, meme.id, [a.id, baska.id, a.id], icerik=gecerli_icerik(uyari=None, mekanizma=[]))
    assert yanit.status_code == 422
    assert {(hata["alan"], hata["kural"]) for hata in yanit.json()["hata"]["alanlar"]} == {
        ("kaynak_annotationlar[1]", "gecersiz_deger"),
        ("kaynak_annotationlar[2]", "tekrar"),
        ("uyari", "zorunlu"),
        ("mekanizma", "min_adet"),
    }
    assert gold_gonder(client, can, meme.id, []).status_code == 422


def test_hazir_olmayan_memeye_gold_onaylanamaz(client, yonetici, ali, ayse, can, meme_olustur, annotation_olustur, gonderilmis):
    meme = meme_olustur(yonetici)
    a = gonderilmis(meme, ali, cift_etiket=True)
    annotation_olustur(meme, ayse, cift_etiket=True, durum_kodu="devam_ediyor")
    yanit = gold_gonder(client, can, meme.id, [a.id])
    assert (yanit.status_code, yanit.json()["hata"]["kod"]) == (409, "GECERSIZ_DURUM_GECISI")


# ------------------------------------------------------------------ request-revision

def revizyon(client, kisi, annotation_id, notu="Durum alanı fazla somut"):
    return client.post(f"/api/v1/annotations/{annotation_id}/request-revision", json={"not": notu}, headers=basliklar(kisi))


def test_revizyon_istegi_annotatorun_kuyruguna_notla_doner(client, yonetici, ali, ayse, meme_olustur, gonderilmis):
    meme = meme_olustur(yonetici)
    annotation = gonderilmis(meme, ali)
    yanit = revizyon(client, ayse, annotation.id)
    assert yanit.status_code == 200
    assert (yanit.json()["durum_kodu"], yanit.json()["revizyon_notu"]) == ("revizyon_gerekli", "Durum alanı fazla somut")
    assert kuyruk(client, ayse) == []
    ali_kuyrugu = client.get("/api/v1/me/queue", headers=basliklar(ali)).json()
    assert [(oge["annotation_id"], oge["durum_kodu"], oge["revizyon_notu"]) for oge in ali_kuyrugu] == [
        (annotation.id, "revizyon_gerekli", "Durum alanı fazla somut")
    ]

    # Annotator düzeltip yeniden gönderince meme yine inceleme kuyruğuna düşer.
    surum = client.patch(
        f"/api/v1/annotations/{annotation.id}/draft",
        json={"surum": 1, "icerik": {"durum": "Daha soyut bir durum iskeleti yazıldı."}},
        headers=basliklar(ali),
    ).json()["surum"]
    client.post(f"/api/v1/annotations/{annotation.id}/submit", json={"surum": surum}, headers=basliklar(ali))
    assert [oge["meme_id"] for oge in kuyruk(client, ayse)] == [meme.id]


def test_revizyon_istegi_kurallari(client, yonetici, ali, ayse, can, meme_olustur, annotation_olustur, gonderilmis):
    meme = meme_olustur(yonetici)
    annotation = gonderilmis(meme, ali)
    assert revizyon(client, ali, annotation.id).json()["hata"]["kod"] == "REVIEWER_ANNOTATOR_OLAMAZ"
    assert revizyon(client, ayse, annotation.id, notu="  ").status_code == 422
    devam_eden = annotation_olustur(meme_olustur(yonetici), ali, durum_kodu="devam_ediyor")
    assert revizyon(client, ayse, devam_eden.id).json()["hata"]["kod"] == "GECERSIZ_DURUM_GECISI"

    cift = meme_olustur(yonetici)
    yarim = gonderilmis(cift, ali, cift_etiket=True)
    annotation_olustur(cift, ayse, cift_etiket=True, durum_kodu="devam_ediyor")
    assert revizyon(client, can, yarim.id).json()["hata"]["kod"] == "KOR_ETIKETLEME"

    kalibrasyon = gonderilmis(meme_olustur(yonetici), ali, kalibrasyon=True)
    assert revizyon(client, can, kalibrasyon.id).json()["hata"]["kod"] == "GECERSIZ_DURUM_GECISI"
    assert revizyon(client, can, "yok").status_code == 404


# ------------------------------------------------------------------ GET /memes/{meme_id}/gold

def test_gold_kaydi_kendi_annotationini_gondermeyene_gizli(client, session, yonetici, ali, ayse, can, meme_olustur, annotation_olustur, gonderilmis):
    meme = meme_olustur(yonetici)
    a = gonderilmis(meme, ali)
    assert client.get(f"/api/v1/memes/{meme.id}/gold", headers=basliklar(ayse)).status_code == 404
    gold_gonder(client, ayse, meme.id, [a.id])
    # Sonradan aynı meme'e atanmış ve henüz göndermemiş biri gold kaydını göremez.
    annotation_olustur(meme, can, durum_kodu="devam_ediyor", kalibrasyon=True)

    gorunen = client.get(f"/api/v1/memes/{meme.id}/gold", headers=basliklar(ali))
    assert gorunen.status_code == 200
    assert gorunen.json()["reviewer"]["id"] == ayse.id
    gizli = client.get(f"/api/v1/memes/{meme.id}/gold", headers=basliklar(can))
    assert (gizli.status_code, gizli.json()["hata"]["kod"]) == (403, "KOR_ETIKETLEME")
    assert client.get("/api/v1/memes/m0404/gold", headers=basliklar(ali)).status_code == 404
