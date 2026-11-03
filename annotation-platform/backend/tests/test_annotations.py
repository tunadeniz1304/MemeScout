import pytest
from sqlmodel import select

from app.models import AnnotationVersion, AuditEntry
from app.schemas import AnnotationContentIn
from app.sema import ALAN_KURALLARI
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
def meme(meme_olustur, yonetici):
    return meme_olustur(yonetici)


def url(annotation_id, islem=""):
    return f"/api/v1/annotations/{annotation_id}" + (f"/{islem}" if islem else "")


def baslat(client, kisi, annotation_id):
    return client.post(url(annotation_id, "start"), headers=basliklar(kisi))


def taslak(client, kisi, annotation_id, surum, **veri):
    return client.patch(url(annotation_id, "draft"), json={"surum": surum, **veri}, headers=basliklar(kisi))


def gonder(client, kisi, annotation_id, surum):
    return client.post(url(annotation_id, "submit"), json={"surum": surum}, headers=basliklar(kisi))


def doldur_ve_gonder(client, kisi, annotation_id, icerik=None):
    surum = baslat(client, kisi, annotation_id).json()["surum"]
    surum = taslak(client, kisi, annotation_id, surum, icerik=icerik or gecerli_icerik(), tanidiklik=4).json()["surum"]
    yanit = gonder(client, kisi, annotation_id, surum)
    assert yanit.status_code == 200, yanit.json()
    return yanit.json()


def test_taslak_icerigi_semadaki_alanlarin_hepsini_tasir():
    assert list(AnnotationContentIn.model_fields) == list(ALAN_KURALLARI)


# ------------------------------------------------------------------ GET /me/queue

def test_kuyruk_varsayilan_olarak_uzerinde_calisilabilecek_isleri_doner(
    client, yonetici, ali, ayse, meme_olustur, annotation_olustur
):
    memeler = [meme_olustur(yonetici) for _ in range(6)]
    atandi = annotation_olustur(memeler[0], ali)
    devam = annotation_olustur(memeler[1], ali, durum_kodu="devam_ediyor")
    revizyon = annotation_olustur(memeler[2], ali, durum_kodu="revizyon_gerekli", revizyon_notu="Durumu soyutla")
    annotation_olustur(memeler[3], ali, durum_kodu="gonderildi")
    kalibrasyon = annotation_olustur(memeler[4], ali, kalibrasyon=True)
    annotation_olustur(memeler[5], ayse)

    yanit = client.get("/api/v1/me/queue", headers=basliklar(ali))
    assert yanit.status_code == 200
    kuyruk = yanit.json()
    assert [oge["annotation_id"] for oge in kuyruk] == [kalibrasyon.id, revizyon.id, devam.id, atandi.id]
    assert kuyruk[1]["revizyon_notu"] == "Durumu soyutla"
    assert kuyruk[0]["kalibrasyon"] is True
    assert kuyruk[3]["kucuk_gorsel_url"] == f"/api/v1/memes/{memeler[0].id}/image?boyut=kucuk"


def test_kuyruk_durum_filtresi(client, yonetici, ali, meme_olustur, annotation_olustur):
    gonderilen = annotation_olustur(meme_olustur(yonetici), ali, durum_kodu="gonderildi")
    atlanan = annotation_olustur(meme_olustur(yonetici), ali, durum_kodu="atlandi")
    annotation_olustur(meme_olustur(yonetici), ali)
    yanit = client.get("/api/v1/me/queue", params={"durum_kodu": "gonderildi, atlandi"}, headers=basliklar(ali))
    assert {oge["annotation_id"] for oge in yanit.json()} == {gonderilen.id, atlanan.id}
    hatali = client.get("/api/v1/me/queue", params={"durum_kodu": "bitti"}, headers=basliklar(ali))
    assert hatali.status_code == 422
    assert client.get("/api/v1/me/queue").status_code == 401


# ------------------------------------------------------------------ start

def test_baslatma_durumu_ve_versiyonlari_sabitler(client, ali, meme, annotation_olustur):
    annotation = annotation_olustur(meme, ali)
    yanit = baslat(client, ali, annotation.id)
    assert yanit.status_code == 200
    detay = yanit.json()
    assert detay["durum_kodu"] == "devam_ediyor"
    assert detay["baslama_zamani"] is not None
    assert (detay["sema_versiyonu"], detay["etiket_listesi_versiyonu"]) == ("1.0", "v1")
    assert detay["surum"] == 1
    assert detay["icerik"]["uyari"] is None and detay["icerik"]["anahtar_kelimeler"] == []

    tekrar = baslat(client, ali, annotation.id)
    assert tekrar.status_code == 200
    assert tekrar.json()["baslama_zamani"] == detay["baslama_zamani"]


def test_baslatma_kurallari(client, ali, ayse, meme, meme_olustur, yonetici, annotation_olustur):
    annotation = annotation_olustur(meme, ali)
    assert baslat(client, ayse, annotation.id).json()["hata"]["kod"] == "YASAK"
    gonderilmis = annotation_olustur(meme_olustur(yonetici), ali, durum_kodu="gonderildi")
    yanit = baslat(client, ali, gonderilmis.id)
    assert yanit.status_code == 409
    assert yanit.json()["hata"]["kod"] == "GECERSIZ_DURUM_GECISI"
    assert baslat(client, ali, "olmayan").status_code == 404


# ------------------------------------------------------------------ draft

def test_taslak_kismi_gunceller_surumu_artirir_ve_gecmise_yazar(client, session, ali, meme, annotation_olustur):
    annotation = annotation_olustur(meme, ali)
    baslat(client, ali, annotation.id)
    yanit = taslak(client, ali, annotation.id, 1, icerik={"durum": "kısa"}, aktif_sure_artis_sn=40)
    assert yanit.status_code == 200
    kayit = yanit.json()
    assert (kayit["surum"], kayit["harcanan_sure_sn"]) == (2, 40)
    assert kayit["guncellenme_zamani"].endswith("Z")

    yanit = taslak(client, ali, annotation.id, 2, icerik={"ad": "Hayırdır"}, aktif_sure_artis_sn=900)
    assert yanit.json()["harcanan_sure_sn"] == 340  # 300 sn üstü kırpılır

    detay = client.get(url(annotation.id), headers=basliklar(ali)).json()
    assert (detay["icerik"]["durum"], detay["icerik"]["ad"]) == ("kısa", "Hayırdır")
    assert detay["surum"] == 3

    gecmis = client.get(url(annotation.id, "versions"), headers=basliklar(ali)).json()
    assert [surum["surum"] for surum in gecmis] == [2, 3]
    assert gecmis[0]["icerik"]["durum"] == "kısa" and gecmis[0]["icerik"]["ad"] is None
    assert gecmis[1]["degistiren"]["id"] == ali.id and gecmis[1]["durum_kodu"] == "devam_ediyor"

    alanlar = [k.alan for k in session.exec(select(AuditEntry).where(AuditEntry.islem == "guncelleme").order_by(AuditEntry.id)).all()]
    assert alanlar == ["icerik.durum", "icerik.ad"]


def test_surum_eslesmezse_409(client, ali, meme, annotation_olustur):
    annotation = annotation_olustur(meme, ali)
    baslat(client, ali, annotation.id)
    taslak(client, ali, annotation.id, 1, icerik={"ad": "ilk sekme"})
    yanit = taslak(client, ali, annotation.id, 1, icerik={"ad": "ikinci sekme"})
    assert yanit.status_code == 409
    hata = yanit.json()["hata"]
    assert hata["kod"] == "SURUM_CAKISMASI"
    assert hata["detay"] == {"guncel_surum": 2}
    assert client.get(url(annotation.id), headers=basliklar(ali)).json()["icerik"]["ad"] == "ilk sekme"


def test_taslak_durum_ve_sahiplik_kurallari(client, ali, ayse, meme, meme_olustur, yonetici, annotation_olustur):
    annotation = annotation_olustur(meme, ali)
    assert taslak(client, ali, annotation.id, 1, icerik={"ad": "x"}).json()["hata"]["kod"] == "GECERSIZ_DURUM_GECISI"
    baslat(client, ali, annotation.id)
    assert taslak(client, ayse, annotation.id, 1, icerik={"ad": "x"}).json()["hata"]["kod"] == "YASAK"
    revizyon = annotation_olustur(meme_olustur(yonetici), ali, durum_kodu="revizyon_gerekli")
    assert taslak(client, ali, revizyon.id, 1, icerik={"ad": "x"}).status_code == 200


def test_taslak_tip_ve_aralik_dogrulamasi(client, ali, meme, annotation_olustur):
    annotation = annotation_olustur(meme, ali)
    baslat(client, ali, annotation.id)
    for veri, alan in [
        ({"tanidiklik": 0}, "tanidiklik"),
        ({"alan_guveni": {"durum": 4}}, "alan_guveni.durum"),
        ({"alan_guveni": {"renk": 2}}, "alan_guveni.renk"),
        ({"aktif_sure_artis_sn": -5}, "aktif_sure_artis_sn"),
        ({"icerik": {"ornek_durumlar": "liste değil"}}, "icerik.ornek_durumlar"),
    ]:
        yanit = taslak(client, ali, annotation.id, 1, **veri)
        assert yanit.status_code == 422, veri
        assert yanit.json()["hata"]["alanlar"][0]["alan"] == alan


def test_uyari_null_ve_bos_liste_ayri_tutulur(client, ali, meme, annotation_olustur):
    annotation = annotation_olustur(meme, ali)
    baslat(client, ali, annotation.id)
    taslak(client, ali, annotation.id, 1, icerik={"uyari": [], "ornek_durumlar": None})
    icerik = client.get(url(annotation.id), headers=basliklar(ali)).json()["icerik"]
    assert icerik["uyari"] == [] and icerik["ornek_durumlar"] == []
    taslak(client, ali, annotation.id, 2, icerik={"uyari": None})
    assert client.get(url(annotation.id), headers=basliklar(ali)).json()["icerik"]["uyari"] is None


def test_tanidiklik_ve_alan_guveni_kaydedilir_ve_temizlenir(client, session, ali, meme, annotation_olustur):
    annotation = annotation_olustur(meme, ali)
    baslat(client, ali, annotation.id)
    taslak(client, ali, annotation.id, 1, tanidiklik=4, alan_guveni={"kulturel_bilgi": 1, "mekanizma": 2})
    detay = client.get(url(annotation.id), headers=basliklar(ali)).json()
    assert (detay["tanidiklik"], detay["alan_guveni"]) == (4, {"kulturel_bilgi": 1, "mekanizma": 2})
    taslak(client, ali, annotation.id, 2, alan_guveni={})
    assert client.get(url(annotation.id), headers=basliklar(ali)).json()["alan_guveni"] == {}
    # İçerik değişmeyen kayıt revizyon geçmişine yeni satır eklemez.
    assert session.exec(select(AnnotationVersion)).all() == []


# ------------------------------------------------------------------ validate

def test_dogrulama_durumu_degistirmez(client, ali, meme, annotation_olustur):
    annotation = annotation_olustur(meme, ali)
    baslat(client, ali, annotation.id)
    eksik = client.post(url(annotation.id, "validate"), headers=basliklar(ali)).json()
    assert eksik["gecerli"] is False
    assert {"alan": "durum", "kural": "zorunlu", "mesaj": "Bu alan zorunlu."} in eksik["hatalar"]

    taslak(client, ali, annotation.id, 1, icerik=gecerli_icerik(), tanidiklik=2)
    dusuk = client.post(url(annotation.id, "validate"), headers=basliklar(ali)).json()
    assert [(hata["alan"], hata["kural"]) for hata in dusuk["hatalar"]] == [("tanidiklik", "aralik")]

    taslak(client, ali, annotation.id, 2, tanidiklik=3)
    tam = client.post(url(annotation.id, "validate"), headers=basliklar(ali)).json()
    assert tam == {"gecerli": True, "hatalar": []}
    assert client.get(url(annotation.id), headers=basliklar(ali)).json()["durum_kodu"] == "devam_ediyor"


# ------------------------------------------------------------------ submit

def test_gonderim_tek_etiketli_memei_ikinci_bakisa_gonderir(client, session, yonetici, ali, meme, annotation_olustur):
    annotation = annotation_olustur(meme, ali)
    sonuc = doldur_ve_gonder(client, ali, annotation.id)
    assert sonuc["durum_kodu"] == "gonderildi"
    assert sonuc["gonderme_zamani"] is not None
    meme_durumu = client.get(f"/api/v1/memes/{meme.id}", headers=basliklar(yonetici)).json()
    assert (meme_durumu["etiket_durumu"], meme_durumu["gold_var"]) == ("inceleme_bekliyor", False)
    gecisler = session.exec(select(AuditEntry).where(AuditEntry.alan == "durum_kodu").order_by(AuditEntry.id)).all()
    assert [(kayit.eski_deger, kayit.yeni_deger) for kayit in gecisler] == [
        ("atandi", "devam_ediyor"),
        ("devam_ediyor", "gonderildi"),
    ]


def test_gonderim_kurallari(client, ali, ayse, meme, annotation_olustur):
    annotation = annotation_olustur(meme, ali)
    assert gonder(client, ali, annotation.id, 1).json()["hata"]["kod"] == "GECERSIZ_DURUM_GECISI"
    baslat(client, ali, annotation.id)
    taslak(client, ali, annotation.id, 1, icerik=gecerli_icerik(durum="kısa", uyari=None))

    assert gonder(client, ayse, annotation.id, 2).json()["hata"]["kod"] == "YASAK"
    cakisma = gonder(client, ali, annotation.id, 1)
    assert (cakisma.status_code, cakisma.json()["hata"]["kod"]) == (409, "SURUM_CAKISMASI")

    eksik = gonder(client, ali, annotation.id, 2)
    assert eksik.status_code == 422
    assert eksik.json()["hata"]["kod"] == "DOGRULAMA"
    assert {(hata["alan"], hata["kural"]) for hata in eksik.json()["hata"]["alanlar"]} == {
        ("durum", "min_karakter"),
        ("uyari", "zorunlu"),
    }

    taslak(client, ali, annotation.id, 2, icerik=gecerli_icerik(), tanidiklik=1)
    dusuk = gonder(client, ali, annotation.id, 3)
    assert (dusuk.status_code, dusuk.json()["hata"]["kod"]) == (422, "TANIDIKLIK_DUSUK")
    assert client.get(url(annotation.id), headers=basliklar(ali)).json()["durum_kodu"] == "devam_ediyor"


def test_pasif_etiketle_gonderilemez_ve_versiyon_gonderimde_sabitlenir(client, yonetici, ali, meme, annotation_olustur):
    annotation = annotation_olustur(meme, ali)
    baslat(client, ali, annotation.id)
    taslak(client, ali, annotation.id, 1, icerik=gecerli_icerik(duygu=["panik"]))
    client.patch("/api/v1/label-lists/labels/duygu/panik", json={"aktif": False}, headers=basliklar(yonetici))

    yanit = gonder(client, ali, annotation.id, 2)
    assert yanit.status_code == 422
    assert yanit.json()["hata"]["alanlar"] == [
        {"alan": "duygu[0]", "kural": "pasif_etiket", "mesaj": "Bu etiket pasifleştirildi; başka bir etiket seç."}
    ]
    taslak(client, ali, annotation.id, 2, icerik={"duygu": ["suphe"]})
    sonuc = gonder(client, ali, annotation.id, 3).json()
    assert sonuc["etiket_listesi_versiyonu"] == "v2"


def test_revizyondaki_annotation_yeniden_gonderilir(client, ali, meme, annotation_olustur):
    annotation = annotation_olustur(meme, ali, durum_kodu="revizyon_gerekli", icerik=gecerli_icerik())
    assert gonder(client, ali, annotation.id, 1).json()["durum_kodu"] == "gonderildi"


# ------------------------------------------------------------------ skip

def test_atlama(client, session, ali, ayse, meme, meme_olustur, yonetici, annotation_olustur):
    annotation = annotation_olustur(meme, ali)
    assert client.post(url(annotation.id, "skip"), json={"gerekce": "tanimiyorum"}, headers=basliklar(ayse)).status_code == 403
    yanit = client.post(
        url(annotation.id, "skip"),
        json={"gerekce": "tanidiklik_dusuk", "aciklama": "Hiç görmedim", "tanidiklik": 1},
        headers=basliklar(ali),
    )
    assert yanit.status_code == 200
    sonuc = yanit.json()
    assert sonuc["durum_kodu"] == "atlandi"
    assert sonuc["atlandi"] == {"gerekce": "tanidiklik_dusuk", "aciklama": "Hiç görmedim"}
    assert sonuc["tanidiklik"] == 1
    assert client.get("/api/v1/me/queue", headers=basliklar(ali)).json() == []

    tekrar = client.post(url(annotation.id, "skip"), json={"gerekce": "diger"}, headers=basliklar(ali))
    assert tekrar.status_code == 409
    gecersiz = client.post(url(annotation.id, "skip"), json={"gerekce": "canim_istemedi"}, headers=basliklar(ali))
    assert gecersiz.status_code == 422

    devam_eden = annotation_olustur(meme_olustur(yonetici), ali, durum_kodu="devam_ediyor")
    assert client.post(url(devam_eden.id, "skip"), json={"gerekce": "uygun_degil"}, headers=basliklar(ali)).status_code == 200
    gonderilen = annotation_olustur(meme_olustur(yonetici), ali, durum_kodu="gonderildi")
    assert client.post(url(gonderilen.id, "skip"), json={"gerekce": "diger"}, headers=basliklar(ali)).status_code == 409


# ------------------------------------------------------------------ kör etiketleme

def test_cift_etiketli_memede_annotation_iki_taraf_gonderene_kadar_gizli(
    client, yonetici, ali, ayse, can, meme, annotation_olustur
):
    alinin = annotation_olustur(meme, ali, cift_etiket=True)
    aysenin = annotation_olustur(meme, ayse, cift_etiket=True)

    def kod(kisi, annotation_id):
        return client.get(url(annotation_id), headers=basliklar(kisi)).status_code

    doldur_ve_gonder(client, ali, alinin.id)
    assert kod(ayse, alinin.id) == 403  # Ayşe henüz göndermedi
    assert kod(ali, aysenin.id) == 403  # Ali gönderdi ama Ayşe göndermedi
    assert kod(can, alinin.id) == 403  # annotator olmayan, gönderim bitmeden göremez
    assert kod(yonetici, alinin.id) == 200  # bu meme'i etiketlemeyen admin görür
    assert client.get(url(alinin.id), headers=basliklar(ayse)).json()["hata"]["kod"] == "KOR_ETIKETLEME"
    assert client.get(url(alinin.id, "versions"), headers=basliklar(ayse)).status_code == 403
    assert client.post(url(alinin.id, "validate"), headers=basliklar(ayse)).status_code == 403

    doldur_ve_gonder(client, ayse, aysenin.id)
    assert kod(ayse, alinin.id) == 200
    assert kod(ali, aysenin.id) == 200
    assert kod(can, alinin.id) == 200


def test_memei_etiketleyen_admin_de_kor_etiketlemeye_tabidir(client, yonetici, ali, meme, annotation_olustur):
    annotation_olustur(meme, yonetici, cift_etiket=True, durum_kodu="devam_ediyor")
    alinin = annotation_olustur(meme, ali, cift_etiket=True, durum_kodu="devam_ediyor")
    assert client.get(url(alinin.id), headers=basliklar(yonetici)).status_code == 403


def test_tek_etiketli_annotation_gonderilince_herkes_gorur(client, ali, ayse, meme, annotation_olustur):
    annotation = annotation_olustur(meme, ali)
    assert client.get(url(annotation.id), headers=basliklar(ayse)).status_code == 403
    doldur_ve_gonder(client, ali, annotation.id)
    assert client.get(url(annotation.id), headers=basliklar(ayse)).status_code == 200
