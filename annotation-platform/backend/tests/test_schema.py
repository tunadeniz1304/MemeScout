import re

import pytest
from sqlmodel import select

from app.etiketler import tohum_alanlari
from app.models import AuditEntry, LabelListVersion, Meme, simdi
from app.sema import ALAN_KURALLARI, icerik_dogrula
from tests.yardimci import basliklar, gecerli_icerik

ETIKETLER = tohum_alanlari(simdi())


@pytest.fixture()
def yonetici(kullanici_olustur):
    return kullanici_olustur("yonetici", admin=True)


@pytest.fixture()
def annotator(kullanici_olustur):
    return kullanici_olustur("ali")


def kurallar(hatalar):
    return {(hata["alan"], hata["kural"]) for hata in hatalar}


# ------------------------------------------------------------------ GET /schema/annotation

def test_sema_giris_ister(client):
    assert client.get("/api/v1/schema/annotation").status_code == 401


def test_sema_annotation_md_alanlarini_sirasiyla_doner(client, annotator):
    yanit = client.get("/api/v1/schema/annotation", headers=basliklar(annotator))
    assert yanit.status_code == 200
    sema = yanit.json()
    assert sema["sema_versiyonu"] == "1.0"
    assert list(sema["alanlar"]) == [
        "tur", "ad", "kaynak", "vlm_aciklama", "durum", "ornek_durumlar", "uygun_olmayan_durumlar",
        "kulturel_bilgi", "anahtar_kelimeler", "duygu", "niyet", "mekanizma", "uyari", "notlar",
    ]
    assert sema["alanlar"]["uyari"]["min_adet"] == 0
    assert sema["alanlar"]["ornek_durumlar"] == ALAN_KURALLARI["ornek_durumlar"]


# ------------------------------------------------------------------ GET /label-lists

def test_ilk_etiket_listesi_tohumlanir(client, annotator):
    yanit = client.get("/api/v1/label-lists", headers=basliklar(annotator))
    assert yanit.status_code == 200
    liste = yanit.json()
    assert liste["versiyon"] == "v1"
    assert liste["olusturma_zamani"].endswith("Z")
    sayilar = {alan: len(etiketler) for alan, etiketler in liste["alanlar"].items()}
    assert sayilar == {"duygu": 12, "niyet": 10, "mekanizma": 8, "uyari": 3}
    for etiketler in liste["alanlar"].values():
        for etiket in etiketler:
            assert re.fullmatch(r"[a-z0-9_]+", etiket["etiket"])
            assert etiket["aktif"] and etiket["tanim"] and etiket["ornekler"] == []
    uyarilar = [etiket["etiket"] for etiket in liste["alanlar"]["uyari"]]
    assert uyarilar == ["politik", "kaba_argo", "hassas"]


def test_bilinmeyen_versiyon_bulunamadi(client, annotator):
    yanit = client.get("/api/v1/label-lists", params={"versiyon": "v9"}, headers=basliklar(annotator))
    assert yanit.status_code == 404
    assert yanit.json()["hata"]["kod"] == "BULUNAMADI"


def test_tohumlama_tekrar_calisinca_ikinci_versiyon_acmaz(session):
    from app.database import create_db_and_tables

    create_db_and_tables()
    assert len(session.exec(select(LabelListVersion)).all()) == 1


# ------------------------------------------------------------------ POST /label-lists/labels

YENI_ETIKET = {"alan": "duygu", "etiket": "nostalji", "gorunen_ad": "Nostalji", "tanim": "Geçmişe özlem."}


def test_etiket_eklemek_admin_ister(client, annotator):
    yanit = client.post("/api/v1/label-lists/labels", json=YENI_ETIKET, headers=basliklar(annotator))
    assert yanit.status_code == 403
    assert yanit.json()["hata"]["kod"] == "YASAK"


def test_etiket_eklemek_yeni_versiyon_olusturur(client, session, yonetici):
    yanit = client.post("/api/v1/label-lists/labels", json=YENI_ETIKET, headers=basliklar(yonetici))
    assert yanit.status_code == 201
    liste = yanit.json()
    assert liste["versiyon"] == "v2"
    eklenen = liste["alanlar"]["duygu"][-1]
    assert eklenen["etiket"] == "nostalji" and eklenen["aktif"] is True

    eski = client.get("/api/v1/label-lists", params={"versiyon": "v1"}, headers=basliklar(yonetici)).json()
    assert "nostalji" not in [etiket["etiket"] for etiket in eski["alanlar"]["duygu"]]

    versiyonlar = client.get("/api/v1/label-lists/versions", headers=basliklar(yonetici)).json()
    assert [v["versiyon"] for v in versiyonlar] == ["v1", "v2"]
    assert versiyonlar[0]["olusturan"] is None
    assert versiyonlar[1]["olusturan"] == {"id": yonetici.id, "gorunen_ad": "Yonetici"}
    assert versiyonlar[1]["degisiklik_ozeti"] == "duygu: 'nostalji' eklendi"

    kayit = session.exec(select(AuditEntry).where(AuditEntry.kayit_tipi == "etiket_listesi")).one()
    assert (kayit.kayit_id, kayit.islem, kayit.alan) == ("v2", "olusturma", "duygu.nostalji")


def test_ayni_etiket_iki_kez_eklenemez(client, yonetici):
    istek = {**YENI_ETIKET, "etiket": "panik"}
    yanit = client.post("/api/v1/label-lists/labels", json=istek, headers=basliklar(yonetici))
    assert yanit.status_code == 409
    assert yanit.json()["hata"]["kod"] == "CAKISMA"


def test_sistem_adi_kalibina_uymayan_etiket_reddedilir(client, yonetici):
    istek = {**YENI_ETIKET, "etiket": "Özlem"}
    yanit = client.post("/api/v1/label-lists/labels", json=istek, headers=basliklar(yonetici))
    assert yanit.status_code == 422
    assert ("etiket", "gecersiz_deger") in kurallar(yanit.json()["hata"]["alanlar"])


def test_ornek_meme_var_olmali(client, session, yonetici):
    session.add(Meme(id="m0001", gorsel_yolu="memes/m0001.png", sha256="b" * 64, yukleyen_id=yonetici.id))
    session.commit()
    istek = {**YENI_ETIKET, "ornekler": ["m0001", "m9999"]}
    yanit = client.post("/api/v1/label-lists/labels", json=istek, headers=basliklar(yonetici))
    assert yanit.status_code == 422
    assert kurallar(yanit.json()["hata"]["alanlar"]) == {("ornekler[1]", "gecersiz_deger")}


# ------------------------------------------------------------------ PATCH /label-lists/labels/{alan}/{etiket}

def test_etiket_pasiflestirilir(client, session, yonetici):
    yanit = client.patch("/api/v1/label-lists/labels/duygu/panik", json={"aktif": False}, headers=basliklar(yonetici))
    assert yanit.status_code == 200
    liste = yanit.json()
    assert liste["versiyon"] == "v2"
    panik = next(etiket for etiket in liste["alanlar"]["duygu"] if etiket["etiket"] == "panik")
    assert panik["aktif"] is False

    versiyonlar = client.get("/api/v1/label-lists/versions", headers=basliklar(yonetici)).json()
    assert versiyonlar[-1]["degisiklik_ozeti"] == "duygu: 'panik' pasifleştirildi"
    kayit = session.exec(select(AuditEntry).where(AuditEntry.alan == "duygu.panik.aktif")).one()
    assert (kayit.eski_deger, kayit.yeni_deger) == (True, False)


def test_tanim_degisikligi_ozetlenir(client, yonetici):
    yanit = client.patch(
        "/api/v1/label-lists/labels/niyet/ovme",
        json={"tanim": "Bir şeyi abartılı biçimde övmek.", "gorunen_ad": "Övgü"},
        headers=basliklar(yonetici),
    )
    assert yanit.status_code == 200
    versiyonlar = client.get("/api/v1/label-lists/versions", headers=basliklar(yonetici)).json()
    assert versiyonlar[-1]["degisiklik_ozeti"] == "niyet: 'ovme' görünen adı değişti, tanımı değişti"


def test_degisiklik_yoksa_yeni_versiyon_acilmaz(client, yonetici):
    yanit = client.patch("/api/v1/label-lists/labels/duygu/panik", json={"aktif": True}, headers=basliklar(yonetici))
    assert yanit.status_code == 200
    assert yanit.json()["versiyon"] == "v1"


def test_olmayan_etiket_guncellenemez(client, yonetici):
    yanit = client.patch("/api/v1/label-lists/labels/duygu/yok_boyle", json={"aktif": False}, headers=basliklar(yonetici))
    assert yanit.status_code == 404


def test_gecersiz_alan_reddedilir(client, yonetici):
    yanit = client.patch("/api/v1/label-lists/labels/renk/panik", json={"aktif": False}, headers=basliklar(yonetici))
    assert yanit.status_code == 422


def test_etiket_guncellemek_admin_ister(client, annotator):
    yanit = client.patch("/api/v1/label-lists/labels/duygu/panik", json={"aktif": False}, headers=basliklar(annotator))
    assert yanit.status_code == 403


# ------------------------------------------------------------------ içerik doğrulaması

def test_gecerli_icerik_hatasiz():
    assert icerik_dogrula(gecerli_icerik(), ETIKETLER) == []


def test_bos_icerik_zorunlu_alanlari_listeler():
    hatalar = icerik_dogrula({}, ETIKETLER)
    zorunlular = {alan for alan, kural in ALAN_KURALLARI.items() if kural["zorunlu"]}
    assert kurallar(hatalar) == {(alan, "zorunlu") for alan in zorunlular}


def test_uyari_null_gonderilemez_bos_liste_gonderilebilir():
    assert kurallar(icerik_dogrula(gecerli_icerik(uyari=None), ETIKETLER)) == {("uyari", "zorunlu")}
    assert icerik_dogrula(gecerli_icerik(uyari=[]), ETIKETLER) == []
    assert icerik_dogrula(gecerli_icerik(uyari=["politik", "kaba_argo"]), ETIKETLER) == []


def test_karakter_sinirlari():
    hatalar = icerik_dogrula(
        gecerli_icerik(durum="Çok kısa", ad="a" * 61, vlm_aciklama="  kısa tarif  ", notlar="n" * 501),
        ETIKETLER,
    )
    assert kurallar(hatalar) == {
        ("durum", "min_karakter"),
        ("ad", "max_karakter"),
        ("vlm_aciklama", "min_karakter"),
        ("notlar", "max_karakter"),
    }


def test_liste_adetleri_ve_eleman_uzunlugu():
    hatalar = icerik_dogrula(
        gecerli_icerik(
            ornek_durumlar=["bir", "iki"],
            uygun_olmayan_durumlar=[],
            anahtar_kelimeler=["a", "b", "c", "d", "e", "f", "g", "h", "i"],
            duygu=["suphe", "saskinlik", "panik", "ofke"],
            mekanizma=["ironi", "x" * 3],
            niyet=["onaylama"],
        ),
        ETIKETLER,
    )
    assert kurallar(hatalar) == {
        ("ornek_durumlar", "min_adet"),
        ("uygun_olmayan_durumlar", "min_adet"),
        ("anahtar_kelimeler", "max_adet"),
        ("duygu", "max_adet"),
        ("mekanizma[1]", "gecersiz_etiket"),
    }
    uzun = icerik_dogrula(gecerli_icerik(anahtar_kelimeler=["bir", "iki", "k" * 41]), ETIKETLER)
    assert kurallar(uzun) == {("anahtar_kelimeler[2]", "max_karakter")}


def test_tekrarlar_turkce_buyuk_kucuk_harf_farkini_yok_sayar():
    hatalar = icerik_dogrula(
        gecerli_icerik(
            ornek_durumlar=["İstanbul trafiği", "Sınav sonucu", "istanbul trafiği "],
            duygu=["suphe", "suphe"],
        ),
        ETIKETLER,
    )
    assert kurallar(hatalar) == {("ornek_durumlar[2]", "tekrar"), ("duygu[1]", "tekrar")}


def test_bos_liste_elemani_ve_gecersiz_enum():
    hatalar = icerik_dogrula(gecerli_icerik(tur="video", ornek_durumlar=["bir", "  ", "üç"]), ETIKETLER)
    assert kurallar(hatalar) == {("tur", "gecersiz_etiket"), ("ornek_durumlar[1]", "zorunlu")}


def test_pasif_etiket_ayri_kuralla_bildirilir():
    etiketler = tohum_alanlari(simdi())
    next(etiket for etiket in etiketler["duygu"] if etiket["etiket"] == "panik")["aktif"] = False
    hatalar = icerik_dogrula(gecerli_icerik(duygu=["panik"]), etiketler)
    assert kurallar(hatalar) == {("duygu[0]", "pasif_etiket")}


def test_yanlis_tipler_gecersiz_deger_olarak_bildirilir():
    hatalar = icerik_dogrula(gecerli_icerik(ad=5, duygu="suphe", niyet=[3]), ETIKETLER)
    assert kurallar(hatalar) == {("ad", "gecersiz_deger"), ("duygu", "gecersiz_deger"), ("niyet[0]", "gecersiz_deger")}
