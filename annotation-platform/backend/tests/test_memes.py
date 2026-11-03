import hashlib

import pytest
from sqlmodel import select

from app.models import AuditEntry, Comment, GoldRecord, MemeImage
from tests.yardimci import basliklar, gecerli_icerik, png_olustur

JPEG = b"\xff\xd8\xff\xe0" + b"\x00\x10JFIF" + b"jpeg verisi" + b"\xff\xd9"
WEBP = b"RIFF" + (12).to_bytes(4, "little") + b"WEBPVP8 " + b"\x00\x00\x00\x00"
GIF = b"GIF89a" + b"\x01\x00\x01\x00gif verisi" + b";"


@pytest.fixture()
def yonetici(kullanici_olustur):
    return kullanici_olustur("yonetici", admin=True)


@pytest.fixture()
def ali(kullanici_olustur):
    return kullanici_olustur("ali")


@pytest.fixture()
def ayse(kullanici_olustur):
    return kullanici_olustur("ayse")


def yukle(client, kullanici, ad, veri, tip="image/png"):
    return client.post("/api/v1/memes", files={"dosya": (ad, veri, tip)}, headers=basliklar(kullanici))


# ------------------------------------------------------------------ POST /memes

def test_yukleme_admin_ister(client, ali):
    assert client.post("/api/v1/memes", files={"dosya": ("a.png", png_olustur(1), "image/png")}).status_code == 401
    assert yukle(client, ali, "a.png", png_olustur(1)).status_code == 403


def test_tek_gorsel_yuklenir_ve_alanlar_otomatik_dolar(client, session, yonetici):
    veri = png_olustur(1)
    yanit = yukle(client, yonetici, "kemal.png", veri)
    assert yanit.status_code == 201
    meme = yanit.json()
    assert meme["id"] == "m0001"
    assert meme["sha256"] == hashlib.sha256(veri).hexdigest()
    assert meme["gorsel_url"] == "/api/v1/memes/m0001/image"
    assert meme["kucuk_gorsel_url"] == "/api/v1/memes/m0001/image?boyut=kucuk"
    assert meme["yukleyen"] == {"id": yonetici.id, "gorunen_ad": "Yonetici"}
    assert meme["yuklenme_zamani"].endswith("Z")
    assert meme["etiket_durumu"] == "atanmadi"
    assert (meme["annotatorlar"], meme["cift_etiket"], meme["gold_var"], meme["ad"], meme["acik_yorum_sayisi"]) == ([], False, False, None, 0)

    assert session.get(MemeImage, "m0001").veri == veri
    kayit = session.exec(select(AuditEntry).where(AuditEntry.kayit_tipi == "meme")).one()
    assert (kayit.kayit_id, kayit.islem, kayit.yeni_deger["dosya_adi"]) == ("m0001", "olusturma", "kemal.png")


def test_ayni_gorsel_ikinci_kez_yuklenemez(client, yonetici):
    yukle(client, yonetici, "bir.png", png_olustur(1))
    yanit = yukle(client, yonetici, "baska-ad.png", png_olustur(1))
    assert yanit.status_code == 409
    hata = yanit.json()["hata"]
    assert hata["kod"] == "KOPYA"
    assert hata["detay"] == {"mevcut_meme_id": "m0001"}


def test_desteklenmeyen_tur_415(client, yonetici):
    yanit = yukle(client, yonetici, "notlar.txt", b"duz metin", "text/plain")
    assert yanit.status_code == 415
    assert yanit.json()["hata"]["kod"] == "DESTEKLENMEYEN_TUR"


@pytest.mark.parametrize(
    "ad, veri",
    [
        ("bozuk.jpg", b"jpeg degil"),
        ("yarim.png", png_olustur(1)[:-12]),
        ("yarim.jpg", JPEG[:-2]),
        ("bos.webp", b""),
    ],
)
def test_bozuk_dosya_422(client, yonetici, ad, veri):
    yanit = yukle(client, yonetici, ad, veri, "application/octet-stream")
    assert yanit.status_code == 422
    assert yanit.json()["hata"]["kod"] == "BOZUK_DOSYA"


@pytest.mark.parametrize(
    "veri, tip, uzanti",
    [(JPEG, "image/jpeg", "jpg"), (WEBP, "image/webp", "webp"), (GIF, "image/gif", "gif")],
)
def test_tur_ilk_baytlardan_belirlenir(client, session, yonetici, veri, tip, uzanti):
    yanit = yukle(client, yonetici, "uzantisiz", veri, "application/octet-stream")
    assert yanit.status_code == 201
    kayit = session.get(MemeImage, "m0001")
    assert kayit.icerik_tipi == tip
    gorsel = client.get("/api/v1/memes/m0001/image", headers=basliklar(yonetici))
    assert gorsel.headers["content-type"] == tip
    assert session.exec(select(AuditEntry)).first().yeni_deger["gorsel_yolu"] == f"memes/m0001.{uzanti}"


# ------------------------------------------------------------------ POST /memes/bulk

def test_toplu_yukleme_kismi_basari(client, yonetici):
    yukle(client, yonetici, "ilk.png", png_olustur(1))
    dosyalar = [
        ("dosyalar", ("a.png", png_olustur(2), "image/png")),
        ("dosyalar", ("eski-kopya.png", png_olustur(1), "image/png")),
        ("dosyalar", ("b.jpg", JPEG, "image/jpeg")),
        ("dosyalar", ("ayni-istekte-kopya.png", png_olustur(2), "image/png")),
        ("dosyalar", ("sohbet.txt", b"merhaba", "text/plain")),
        ("dosyalar", ("bozuk.webp", b"RIFF", "image/webp")),
    ]
    yanit = client.post("/api/v1/memes/bulk", files=dosyalar, headers=basliklar(yonetici))
    assert yanit.status_code == 200
    sonuc = yanit.json()
    assert [meme["id"] for meme in sonuc["yuklenen"]] == ["m0002", "m0003"]
    assert sonuc["reddedilen"] == [
        {"dosya_adi": "eski-kopya.png", "sebep": "kopya", "mevcut_meme_id": "m0001"},
        {"dosya_adi": "ayni-istekte-kopya.png", "sebep": "kopya", "mevcut_meme_id": "m0002"},
        {"dosya_adi": "sohbet.txt", "sebep": "desteklenmeyen_tur", "mevcut_meme_id": None},
        {"dosya_adi": "bozuk.webp", "sebep": "bozuk_dosya", "mevcut_meme_id": None},
    ]
    liste = client.get("/api/v1/memes", headers=basliklar(yonetici)).json()
    assert liste["toplam"] == 3


def test_toplu_yukleme_admin_ister(client, ali):
    yanit = client.post(
        "/api/v1/memes/bulk",
        files=[("dosyalar", ("a.png", png_olustur(1), "image/png"))],
        headers=basliklar(ali),
    )
    assert yanit.status_code == 403


# ------------------------------------------------------------------ GET /memes/{id}/image

def test_gorsel_onbellek_basliklariyla_doner(client, yonetici, ali, meme_olustur):
    meme = meme_olustur(yonetici)
    yanit = client.get(f"/api/v1/memes/{meme.id}/image", headers=basliklar(ali))
    assert yanit.status_code == 200
    assert yanit.content == png_olustur(1)
    assert yanit.headers["content-type"] == "image/png"
    assert yanit.headers["cache-control"].startswith("private")
    assert yanit.headers["etag"] == f'"{meme.sha256}"'

    tekrar = client.get(
        f"/api/v1/memes/{meme.id}/image",
        headers={**basliklar(ali), "If-None-Match": yanit.headers["etag"]},
    )
    assert tekrar.status_code == 304

    kucuk = client.get(f"/api/v1/memes/{meme.id}/image", params={"boyut": "kucuk"}, headers=basliklar(ali))
    assert kucuk.content == yanit.content


def test_gorsel_giris_ister_ve_olmayan_meme_404(client, yonetici, meme_olustur):
    meme = meme_olustur(yonetici)
    assert client.get(f"/api/v1/memes/{meme.id}/image").status_code == 401
    assert client.get("/api/v1/memes/m9999/image", headers=basliklar(yonetici)).status_code == 404


# ------------------------------------------------------------------ GET /memes

def test_liste_sayfalanir(client, yonetici, meme_olustur):
    for _ in range(5):
        meme_olustur(yonetici)
    yanit = client.get("/api/v1/memes", params={"sayfa": 2, "boyut": 2}, headers=basliklar(yonetici))
    assert yanit.status_code == 200
    sayfa = yanit.json()
    assert (sayfa["toplam"], sayfa["sayfa"], sayfa["boyut"]) == (5, 2, 2)
    assert [meme["id"] for meme in sayfa["ogeler"]] == ["m0003", "m0004"]


def test_sayfa_boyutu_sinirli(client, yonetici):
    yanit = client.get("/api/v1/memes", params={"boyut": 201}, headers=basliklar(yonetici))
    assert yanit.status_code == 422
    assert yanit.json()["hata"]["alanlar"][0]["alan"] == "boyut"


def test_etiket_durumu_turetilir(client, session, yonetici, ali, ayse, meme_olustur, annotation_olustur):
    atanmamis = meme_olustur(yonetici)
    tek = meme_olustur(yonetici)
    annotation_olustur(tek, ali, durum_kodu="devam_ediyor")
    tek_gonderildi = meme_olustur(yonetici)
    annotation_olustur(tek_gonderildi, ali, durum_kodu="gonderildi")
    cift_yarim = meme_olustur(yonetici)
    annotation_olustur(cift_yarim, ali, durum_kodu="gonderildi", cift_etiket=True)
    annotation_olustur(cift_yarim, ayse, durum_kodu="devam_ediyor", cift_etiket=True)
    cift_tam = meme_olustur(yonetici)
    annotation_olustur(cift_tam, ali, durum_kodu="gonderildi", cift_etiket=True)
    annotation_olustur(cift_tam, ayse, durum_kodu="gonderildi", cift_etiket=True)
    atlanmis = meme_olustur(yonetici)
    annotation_olustur(atlanmis, ali, durum_kodu="atlandi")
    kalibrasyon = meme_olustur(yonetici)
    annotation_olustur(kalibrasyon, ali, durum_kodu="gonderildi", kalibrasyon=True)
    gold = meme_olustur(yonetici)
    annotation_olustur(gold, ali, durum_kodu="onaylandi")
    session.add(GoldRecord(meme_id=gold.id, icerik=gecerli_icerik(), sema_versiyonu="1.0", etiket_listesi_versiyonu="v1"))
    session.commit()

    memeler = client.get("/api/v1/memes", headers=basliklar(yonetici)).json()["ogeler"]
    durumlar = {meme["id"]: meme["etiket_durumu"] for meme in memeler}
    assert durumlar == {
        atanmamis.id: "atanmadi",
        tek.id: "etiketleniyor",
        tek_gonderildi.id: "inceleme_bekliyor",
        cift_yarim.id: "etiketleniyor",
        cift_tam.id: "inceleme_bekliyor",
        atlanmis.id: "atanmadi",
        kalibrasyon.id: "atanmadi",
        gold.id: "gold_hazir",
    }
    secilen = client.get("/api/v1/memes", params={"etiket_durumu": "inceleme_bekliyor"}, headers=basliklar(yonetici)).json()
    assert [meme["id"] for meme in secilen["ogeler"]] == [tek_gonderildi.id, cift_tam.id]
    altin = next(meme for meme in memeler if meme["id"] == gold.id)
    assert altin["gold_var"] is True and altin["ad"] == "Hayırdır inşallah"
    cift = next(meme for meme in memeler if meme["id"] == cift_tam.id)
    assert cift["cift_etiket"] is True
    assert {kisi["id"] for kisi in cift["annotatorlar"]} == {ali.id, ayse.id}
    assert next(meme for meme in memeler if meme["id"] == atlanmis.id)["annotatorlar"] == []


def test_annotator_ve_cift_etiket_filtreleri(client, yonetici, ali, ayse, meme_olustur, annotation_olustur):
    birinci = meme_olustur(yonetici)
    annotation_olustur(birinci, ali)
    ikinci = meme_olustur(yonetici)
    annotation_olustur(ikinci, ali, cift_etiket=True)
    annotation_olustur(ikinci, ayse, cift_etiket=True)
    meme_olustur(yonetici)

    def idler(**parametreler):
        yanit = client.get("/api/v1/memes", params=parametreler, headers=basliklar(yonetici))
        return [meme["id"] for meme in yanit.json()["ogeler"]]

    assert idler(annotator_id=ali.id) == [birinci.id, ikinci.id]
    assert idler(annotator_id=ayse.id) == [ikinci.id]
    assert idler(cift_etiket="true") == [ikinci.id]
    assert idler(cift_etiket="false") == [birinci.id, "m0003"]


def test_arama_id_ve_gold_adinda_yapilir(client, session, yonetici, meme_olustur):
    meme_olustur(yonetici)
    adli = meme_olustur(yonetici)
    session.add(GoldRecord(meme_id=adli.id, icerik=gecerli_icerik(ad="İnek Şaban"), sema_versiyonu="1.0", etiket_listesi_versiyonu="v1"))
    session.commit()

    def idler(q):
        return [meme["id"] for meme in client.get("/api/v1/memes", params={"q": q}, headers=basliklar(yonetici)).json()["ogeler"]]

    assert idler("m0001") == ["m0001"]
    assert idler("inek şaban") == [adli.id]
    assert idler("İNEK") == [adli.id]
    assert idler("yok") == []


def test_acik_yorum_sayisi_kor_etiketlemeye_uyar(client, session, yonetici, ali, ayse, meme_olustur, annotation_olustur):
    meme = meme_olustur(yonetici)
    annotation_olustur(meme, ali, durum_kodu="devam_ediyor", cift_etiket=True)
    annotation_olustur(meme, ayse, durum_kodu="devam_ediyor", cift_etiket=True)
    session.add(Comment(meme_id=meme.id, yazan_id=ayse.id, metin="Bence politik", tur="soru"))
    session.add(Comment(meme_id=meme.id, yazan_id=yonetici.id, metin="Kopya olabilir", tur="kopya_suphesi"))
    session.add(Comment(meme_id=meme.id, yazan_id=yonetici.id, metin="Çözüldü", tur="soru", cozuldu=True))
    session.commit()

    def sayi(kullanici):
        return client.get("/api/v1/memes", headers=basliklar(kullanici)).json()["ogeler"][0]["acik_yorum_sayisi"]

    assert sayi(yonetici) == 2
    assert sayi(ayse) == 2
    assert sayi(ali) == 1  # Ayşe'nin yorumu kör etiketleme sürerken Ali'den gizli


# ------------------------------------------------------------------ GET /memes/{id}

def test_detay_admin_icin_tum_annotationlari_digerleri_icin_kendisininkini_icerir(
    client, yonetici, ali, ayse, meme_olustur, annotation_olustur
):
    meme = meme_olustur(yonetici)
    alinin = annotation_olustur(meme, ali, cift_etiket=True)
    aysenin = annotation_olustur(meme, ayse, cift_etiket=True)

    admin_gorunumu = client.get(f"/api/v1/memes/{meme.id}", headers=basliklar(yonetici)).json()
    assert {ozet["id"] for ozet in admin_gorunumu["annotasyonlar"]} == {alinin.id, aysenin.id}
    assert next(ozet for ozet in admin_gorunumu["annotasyonlar"] if ozet["id"] == alinin.id) == {
        "id": alinin.id,
        "meme_id": meme.id,
        "annotator": {"id": ali.id, "gorunen_ad": "Ali"},
        "durum_kodu": "atandi",
        "cift_etiket": True,
        "kalibrasyon": False,
        "gonderme_zamani": None,
    }
    ali_gorunumu = client.get(f"/api/v1/memes/{meme.id}", headers=basliklar(ali)).json()
    assert [ozet["id"] for ozet in ali_gorunumu["annotasyonlar"]] == [alinin.id]


def test_olmayan_meme_detayi_404(client, ali):
    yanit = client.get("/api/v1/memes/m0404", headers=basliklar(ali))
    assert yanit.status_code == 404
    assert yanit.json()["hata"]["kod"] == "BULUNAMADI"
