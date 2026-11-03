import pytest
from sqlmodel import select

from app.models import Annotation, AuditEntry
from tests.yardimci import basliklar


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
def meme(meme_olustur, yonetici):
    return meme_olustur(yonetici)


def yorum_yaz(client, kisi, meme_id, metin="Bu meme politik mi?", tur="soru", **ek):
    return client.post(
        f"/api/v1/memes/{meme_id}/comments",
        json={"metin": metin, "tur": tur, **ek},
        headers=basliklar(kisi),
    )


def yorum_metinleri(client, kisi, meme_id):
    # Sıraya bakılmaz: Windows'ta saat 15 ms adımla ilerler, art arda yazılan yorumların zamanı eşit çıkabilir.
    yanit = client.get(f"/api/v1/memes/{meme_id}/comments", headers=basliklar(kisi))
    assert yanit.status_code == 200
    return {yorum["metin"] for yorum in yanit.json()}


def test_yorum_eklenir_ve_denetlenir(client, session, ali, meme):
    yanit = yorum_yaz(client, ali, meme.id, metin="  Uyarı gerekir mi?  ", alan="uyari")
    assert yanit.status_code == 201
    yorum = yanit.json()
    assert (yorum["meme_id"], yorum["alan"], yorum["metin"], yorum["tur"], yorum["cozuldu"]) == (
        meme.id, "uyari", "Uyarı gerekir mi?", "soru", False,
    )
    assert yorum["yazan"] == {"id": ali.id, "gorunen_ad": "Ali"}
    assert yorum["zaman"].endswith("Z")
    kayit = session.exec(select(AuditEntry).where(AuditEntry.kayit_tipi == "yorum")).one()
    assert (kayit.kayit_id, kayit.islem) == (yorum["id"], "olusturma")


def test_yorum_dogrulamasi(client, ali, meme):
    assert yorum_yaz(client, ali, "m0404").status_code == 404
    for veri in [{"metin": "   "}, {"tur": "sohbet"}, {"alan": "renk"}]:
        yanit = yorum_yaz(client, ali, meme.id, **veri)
        assert yanit.status_code == 422, veri
        assert yanit.json()["hata"]["kod"] == "DOGRULAMA"


def test_kor_etiketlemede_diger_annotatorin_yorumu_gizli(client, session, yonetici, ali, ayse, can, meme, annotation_olustur):
    alinin = annotation_olustur(meme, ali, cift_etiket=True, durum_kodu="devam_ediyor")
    aysenin = annotation_olustur(meme, ayse, cift_etiket=True, durum_kodu="devam_ediyor")
    yorum_yaz(client, ali, meme.id, metin="Ali: politik bence")
    yorum_yaz(client, ayse, meme.id, metin="Ayşe: kaba argo var")
    yorum_yaz(client, can, meme.id, metin="Can: kopya olabilir", tur="kopya_suphesi")

    assert yorum_metinleri(client, ali, meme.id) == {"Ali: politik bence", "Can: kopya olabilir"}
    assert yorum_metinleri(client, ayse, meme.id) == {"Ayşe: kaba argo var", "Can: kopya olabilir"}
    assert len(yorum_metinleri(client, can, meme.id)) == 3
    assert len(yorum_metinleri(client, yonetici, meme.id)) == 3

    # Biri gönderdi; diğeri göndermedikçe kural sürer.
    alinin.durum_kodu = "gonderildi"
    session.add(alinin)
    session.commit()
    assert yorum_metinleri(client, ali, meme.id) == {"Ali: politik bence", "Can: kopya olabilir"}

    aysenin.durum_kodu = "gonderildi"
    session.add(aysenin)
    session.commit()
    assert len(yorum_metinleri(client, ali, meme.id)) == 3
    assert len(yorum_metinleri(client, ayse, meme.id)) == 3


def test_atlayan_kisinin_yorumu_da_gizli_kalir(client, session, ali, ayse, meme, annotation_olustur):
    annotation_olustur(meme, ali, cift_etiket=True, durum_kodu="devam_ediyor")
    annotation_olustur(meme, ayse, cift_etiket=True, durum_kodu="atlandi")
    yorum_yaz(client, ayse, meme.id, metin="Ayşe: tanımıyorum ama politik")
    assert yorum_metinleri(client, ali, meme.id) == set()
    # Atlayan kişi artık etiketlemiyor; diğerinin yorumlarını görebilir.
    yorum_yaz(client, ali, meme.id, metin="Ali: emin değilim")
    assert yorum_metinleri(client, ayse, meme.id) == {"Ayşe: tanımıyorum ama politik", "Ali: emin değilim"}


def test_kalibrasyon_turunda_da_yorumlar_gizli(client, ali, ayse, meme, annotation_olustur):
    annotation_olustur(meme, ali, kalibrasyon=True, durum_kodu="gonderildi")
    annotation_olustur(meme, ayse, kalibrasyon=True, durum_kodu="devam_ediyor")
    yorum_yaz(client, ali, meme.id, metin="Ali: ironi bence")
    assert yorum_metinleri(client, ayse, meme.id) == set()


def test_memei_etiketleyen_admin_de_yorumlari_goremez(client, yonetici, ali, meme, annotation_olustur):
    annotation_olustur(meme, yonetici, cift_etiket=True, durum_kodu="devam_ediyor")
    annotation_olustur(meme, ali, cift_etiket=True, durum_kodu="gonderildi")
    yorum_yaz(client, ali, meme.id, metin="Ali: sevimli")
    assert yorum_metinleri(client, yonetici, meme.id) == set()


def test_tum_yorumlar_listesi_filtrelenir_ve_sayfalanir(client, ali, ayse, can, meme_olustur, yonetici, annotation_olustur):
    kor_meme = meme_olustur(yonetici)
    annotation_olustur(kor_meme, ali, cift_etiket=True, durum_kodu="devam_ediyor")
    annotation_olustur(kor_meme, ayse, cift_etiket=True, durum_kodu="devam_ediyor")
    acik_meme = meme_olustur(yonetici)
    yorum_yaz(client, ayse, kor_meme.id, metin="gizli kalmalı")
    for sira in range(3):
        yorum_yaz(client, can, acik_meme.id, metin=f"soru {sira}")
    hata = yorum_yaz(client, can, acik_meme.id, metin="kırık görsel", tur="hata").json()
    client.patch(f"/api/v1/comments/{hata['id']}", json={"cozuldu": True}, headers=basliklar(can))

    def liste(kisi, **parametreler):
        return client.get("/api/v1/comments", params=parametreler, headers=basliklar(kisi)).json()

    hepsi = liste(ali)
    assert hepsi["toplam"] == 4
    assert "gizli kalmalı" not in [yorum["metin"] for yorum in hepsi["ogeler"]]
    zamanlar = [yorum["zaman"] for yorum in hepsi["ogeler"]]
    assert zamanlar == sorted(zamanlar, reverse=True)  # en yeni önce
    assert liste(can)["toplam"] == 5
    assert [yorum["metin"] for yorum in liste(can, tur="hata")["ogeler"]] == ["kırık görsel"]
    assert liste(can, cozuldu="false")["toplam"] == 4
    sayfa = liste(can, sayfa=2, boyut=2)
    assert (sayfa["toplam"], len(sayfa["ogeler"]), sayfa["sayfa"], sayfa["boyut"]) == (5, 2, 2, 2)


def test_yorum_cozuldu_isaretlenir(client, session, ali, ayse, meme, annotation_olustur):
    yorum = yorum_yaz(client, ali, meme.id).json()
    yanit = client.patch(f"/api/v1/comments/{yorum['id']}", json={"cozuldu": True}, headers=basliklar(ayse))
    assert yanit.status_code == 200
    assert yanit.json()["cozuldu"] is True
    kayit = session.exec(select(AuditEntry).where(AuditEntry.alan == "cozuldu")).one()
    assert (kayit.eski_deger, kayit.yeni_deger, kayit.kullanici_id) == (False, True, ayse.id)
    assert client.patch("/api/v1/comments/yok", json={"cozuldu": True}, headers=basliklar(ali)).status_code == 404


def test_goremedigi_yorum_guncellenemez(client, session, ali, ayse, meme, annotation_olustur):
    annotation_olustur(meme, ali, cift_etiket=True, durum_kodu="devam_ediyor")
    annotation_olustur(meme, ayse, cift_etiket=True, durum_kodu="devam_ediyor")
    yorum = yorum_yaz(client, ayse, meme.id).json()
    yanit = client.patch(f"/api/v1/comments/{yorum['id']}", json={"cozuldu": True}, headers=basliklar(ali))
    assert yanit.status_code == 404
    assert session.exec(select(Annotation)).first() is not None
