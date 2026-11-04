import json
from datetime import timedelta

import pytest
from sqlmodel import select

from app.models import GoldRecord, simdi
from tests.yardimci import basliklar, gecerli_icerik


@pytest.fixture()
def yonetici(kullanici_olustur):
    return kullanici_olustur("yonetici", admin=True, takma_ad="a1")


@pytest.fixture()
def ali(kullanici_olustur):
    return kullanici_olustur("ali", takma_ad="a2")


@pytest.fixture()
def ayse(kullanici_olustur):
    return kullanici_olustur("ayse", takma_ad="a3")


@pytest.fixture()
def can(kullanici_olustur):
    return kullanici_olustur("can", takma_ad="a4")


@pytest.fixture()
def gonderilmis(annotation_olustur):
    def olustur(meme, kisi, dakika_once=0, **alanlar):
        varsayilan = {
            "durum_kodu": "gonderildi",
            "icerik": gecerli_icerik(),
            "gonderme_zamani": simdi() - timedelta(minutes=dakika_once),
            "etiket_listesi_versiyonu": "v1",
            "sema_versiyonu": "1.0",
        }
        return annotation_olustur(meme, kisi, **{**varsayilan, **alanlar})

    return olustur


def gold_ekle(session, meme, kaynaklar, reviewer, **icerik):
    session.add(GoldRecord(
        meme_id=meme.id, icerik=gecerli_icerik(**icerik), kaynak_annotationlar=[a.id for a in kaynaklar],
        reviewer_id=reviewer.id, sema_versiyonu="1.0", etiket_listesi_versiyonu="v1",
    ))
    session.commit()


# ------------------------------------------------------------------ GET /stats/progress

def test_ilerleme_panosu(client, session, yonetici, ali, ayse, can, meme_olustur, annotation_olustur, gonderilmis):
    memeler = [meme_olustur(yonetici) for _ in range(6)]
    gonderilmis(memeler[0], ali, harcanan_sure_sn=100)
    annotation_olustur(memeler[1], ali, durum_kodu="onaylandi", harcanan_sure_sn=200)
    gold_ekle(session, memeler[1], [], ayse)
    annotation_olustur(memeler[2], ali, durum_kodu="revizyon_gerekli")
    annotation_olustur(memeler[3], ali, durum_kodu="atlandi", cift_etiket=True)
    annotation_olustur(memeler[3], ayse, durum_kodu="devam_ediyor", cift_etiket=True)
    annotation_olustur(memeler[4], ayse)

    yanit = client.get("/api/v1/stats/progress", headers=basliklar(can))
    assert yanit.status_code == 200
    istatistik = yanit.json()
    assert istatistik["genel"] == {
        "toplam_meme": 6,
        "atanmamis": 1,
        "gold_hazir": 1,
        "inceleme_bekleyen": 1,
        "yeniden_atama_bekleyen": 1,
        "cikarilan": 0,
    }
    kisiler = {satir["kullanici"]["id"]: satir for satir in istatistik["kullanicilar"]}
    assert kisiler[ali.id] == {
        "kullanici": {"id": ali.id, "gorunen_ad": "Ali"},
        "atanan": 4, "tamamlanan": 2, "kalan": 1, "atlanan": 1, "revizyon_bekleyen": 1, "ortalama_sure_sn": 150.0,
    }
    assert (kisiler[ayse.id]["atanan"], kisiler[ayse.id]["kalan"], kisiler[ayse.id]["ortalama_sure_sn"]) == (2, 2, None)
    assert kisiler[can.id]["atanan"] == 0


# ------------------------------------------------------------------ GET /stats/agreement

def test_uyum_panosu_yalnizca_iki_tarafi_gonderilmis_cift_etiketlileri_sayar(
    client, yonetici, ali, ayse, can, meme_olustur, annotation_olustur, gonderilmis
):
    ornekler = [
        (dict(tur="template", duygu=["suphe"]), dict(tur="template", duygu=["suphe"])),
        (dict(tur="template", duygu=["suphe", "panik"]), dict(tur="hazir_meme", duygu=["suphe"])),
        (dict(tur="hazir_meme", duygu=["ofke"]), dict(tur="hazir_meme", duygu=["utanc"])),
    ]
    for birinci, ikinci in ornekler:
        meme = meme_olustur(yonetici)
        gonderilmis(meme, ali, cift_etiket=True, dakika_once=2, icerik=gecerli_icerik(**birinci))
        gonderilmis(meme, ayse, cift_etiket=True, dakika_once=1, icerik=gecerli_icerik(**ikinci))
    yarim = meme_olustur(yonetici)
    gonderilmis(yarim, ali, cift_etiket=True)
    annotation_olustur(yarim, can, cift_etiket=True, durum_kodu="devam_ediyor")
    kalibrasyon = meme_olustur(yonetici)
    gonderilmis(kalibrasyon, ali, kalibrasyon=True)
    gonderilmis(kalibrasyon, ayse, kalibrasyon=True)

    uyum = client.get("/api/v1/stats/agreement", headers=basliklar(yonetici)).json()
    assert uyum["cift_etiketli_meme_sayisi"] == 3
    assert uyum["hesaplama_zamani"].endswith("Z")
    alanlar = {satir["alan"]: satir for satir in uyum["alanlar"]}
    # tur: p_o = 2/3; birinci (2 template, 1 hazır), ikinci (1, 2) → p_e = 4/9 → kappa = 0.4
    assert alanlar["tur"] == {"alan": "tur", "metrik": "cohen_kappa", "deger": 0.4, "n": 3, "dusuk_uyum": False}
    assert alanlar["duygu"]["metrik"] == "krippendorff_alpha_masi"
    assert alanlar["duygu"]["dusuk_uyum"] is True
    # niyet, mekanizma ve uyari her çiftte aynı tek değer: çeşitlilik yok, alpha tanımsız.
    assert alanlar["niyet"]["deger"] is None and alanlar["niyet"]["dusuk_uyum"] is False

    etiketler = uyum["etiketler"]
    assert [(satir["etiket"], satir["anlasmazlik_sayisi"]) for satir in etiketler[:3]] == [("ofke", 1), ("panik", 1), ("utanc", 1)]
    suphe = next(satir for satir in etiketler if satir["etiket"] == "suphe")
    assert (suphe["anlasmazlik_sayisi"], suphe["kullanim_sayisi"]) == (0, 4)

    # Kör etiketleme sürerken annotator etiket ayrıntısını göremez; admin görür.
    annotator_gorunumu = client.get("/api/v1/stats/agreement", headers=basliklar(ali)).json()
    assert "etiketler" not in annotator_gorunumu
    assert annotator_gorunumu["alanlar"] == uyum["alanlar"]


def test_kor_etiketleme_bitince_etiket_ayrintisi_herkese_acik(client, yonetici, ali, ayse, meme_olustur, gonderilmis):
    meme = meme_olustur(yonetici)
    gonderilmis(meme, ali, cift_etiket=True)
    gonderilmis(meme, ayse, cift_etiket=True)
    assert "etiketler" in client.get("/api/v1/stats/agreement", headers=basliklar(ali)).json()


# ------------------------------------------------------------------ GET /recheck

def test_yeniden_kontrol_listesi_ve_meme_durumu(client, session, yonetici, ali, ayse, can, meme_olustur, gonderilmis):
    birinci = meme_olustur(yonetici)
    panikli = gonderilmis(birinci, ali, icerik=gecerli_icerik(duygu=["panik"]))
    ikinci = meme_olustur(yonetici)
    kaynak = gonderilmis(ikinci, ali, durum_kodu="onaylandi", icerik=gecerli_icerik(niyet=["ovme"]))
    gold_ekle(session, ikinci, [kaynak], ayse, niyet=["ovme"])
    ucuncu = meme_olustur(yonetici)
    gonderilmis(ucuncu, ali)
    assert client.get("/api/v1/recheck", headers=basliklar(yonetici)).json() == []

    client.patch("/api/v1/label-lists/labels/duygu/panik", json={"aktif": False}, headers=basliklar(yonetici))
    client.patch("/api/v1/label-lists/labels/niyet/ovme", json={"tanim": "Abartılı övgü."}, headers=basliklar(yonetici))
    liste = client.get("/api/v1/recheck", headers=basliklar(yonetici)).json()
    assert liste == [
        {
            "kayit_tipi": "annotation", "kayit_id": panikli.id, "meme_id": birinci.id, "eski_versiyon": "v1",
            "etkilenen_etiketler": [{"alan": "duygu", "etiket": "panik", "degisiklik": "pasiflestirildi"}],
        },
        {
            "kayit_tipi": "gold", "kayit_id": ikinci.id, "meme_id": ikinci.id, "eski_versiyon": "v1",
            "etkilenen_etiketler": [{"alan": "niyet", "etiket": "ovme", "degisiklik": "tanim_degisti"}],
        },
        {
            "kayit_tipi": "annotation", "kayit_id": kaynak.id, "meme_id": ikinci.id, "eski_versiyon": "v1",
            "etkilenen_etiketler": [{"alan": "niyet", "etiket": "ovme", "degisiklik": "tanim_degisti"}],
        },
    ]
    durumlar = {meme["id"]: meme["etiket_durumu"] for meme in client.get("/api/v1/memes", headers=basliklar(can)).json()["ogeler"]}
    assert durumlar == {birinci.id: "yeniden_kontrol", ikinci.id: "yeniden_kontrol", ucuncu.id: "inceleme_bekliyor"}


def test_yeniden_kontrol_kor_etiketlemeye_uyar(client, yonetici, ali, ayse, meme_olustur, annotation_olustur, gonderilmis):
    meme = meme_olustur(yonetici)
    alinin = gonderilmis(meme, ali, cift_etiket=True, icerik=gecerli_icerik(duygu=["panik"]))
    annotation_olustur(meme, ayse, cift_etiket=True, durum_kodu="devam_ediyor")
    client.patch("/api/v1/label-lists/labels/duygu/panik", json={"aktif": False}, headers=basliklar(yonetici))
    assert [kayit["kayit_id"] for kayit in client.get("/api/v1/recheck", headers=basliklar(ali)).json()] == [alinin.id]
    assert client.get("/api/v1/recheck", headers=basliklar(ayse)).json() == []
    assert len(client.get("/api/v1/recheck", headers=basliklar(yonetici)).json()) == 1


# ------------------------------------------------------------------ GET /audit

def test_denetim_kaydi_admin_icindir_ve_filtrelenir(client, yonetici, ali, meme_olustur):
    meme = meme_olustur(yonetici)
    client.post(f"/api/v1/memes/{meme.id}/comments", json={"metin": "Soru", "tur": "soru"}, headers=basliklar(ali))
    client.post("/api/v1/assignments", json={"meme_ids": [meme.id], "annotator_id": ali.id}, headers=basliklar(yonetici))
    client.patch("/api/v1/label-lists/labels/duygu/panik", json={"aktif": False}, headers=basliklar(yonetici))

    assert client.get("/api/v1/audit", headers=basliklar(ali)).status_code == 403
    hepsi = client.get("/api/v1/audit", headers=basliklar(yonetici)).json()
    assert hepsi["toplam"] == 3
    assert [kayit["kayit_tipi"] for kayit in hepsi["ogeler"]] == ["etiket_listesi", "annotation", "yorum"]
    assert all(isinstance(kayit["id"], str) for kayit in hepsi["ogeler"])

    def tipler(**parametreler):
        sayfa = client.get("/api/v1/audit", params=parametreler, headers=basliklar(yonetici)).json()
        return [kayit["kayit_tipi"] for kayit in sayfa["ogeler"]]

    assert tipler(kullanici_id=ali.id) == ["yorum"]
    assert tipler(kayit_tipi="etiket_listesi") == ["etiket_listesi"]
    assert tipler(kayit_id="v2") == ["etiket_listesi"]
    assert tipler(sayfa=2, boyut=2) == ["yorum"]
    assert client.get("/api/v1/audit", params={"kayit_tipi": "bilinmeyen"}, headers=basliklar(yonetici)).status_code == 422


# ------------------------------------------------------------------ GET /export/{dosya}

def indir(client, kisi, dosya):
    yanit = client.get(f"/api/v1/export/{dosya}", headers=basliklar(kisi))
    assert yanit.status_code == 200
    assert yanit.headers["content-type"].startswith("application/x-ndjson")
    assert yanit.headers["content-disposition"] == f'attachment; filename="{dosya}"'
    return [json.loads(satir) for satir in yanit.text.splitlines()]


def test_gold_disa_aktarimi_takma_ad_kullanir(client, session, yonetici, ali, ayse, can, meme_olustur, gonderilmis):
    meme = meme_olustur(yonetici)
    a = gonderilmis(meme, ali, cift_etiket=True, durum_kodu="onaylandi")
    b = gonderilmis(meme, ayse, cift_etiket=True, durum_kodu="onaylandi")
    gold_ekle(session, meme, [a, b], can)
    kayit = session.get(GoldRecord, meme.id)
    kayit.icerik = {**kayit.icerik, "uyari": None}  # eski kayıtta null kalmış olsa bile listeye çevrilir
    session.add(kayit)
    session.commit()

    satirlar = indir(client, yonetici, "gold.jsonl")
    assert len(satirlar) == 1
    satir = satirlar[0]
    assert list(satir) == [
        "id", "gorsel", "tur", "ad", "kaynak", "vlm_aciklama", "durum", "ornek_durumlar", "uygun_olmayan_durumlar",
        "kulturel_bilgi", "anahtar_kelimeler", "duygu", "niyet", "mekanizma", "uyari", "notlar",
        "annotator", "reviewer", "sema_versiyonu", "etiket_listesi_versiyonu",
    ]
    assert (satir["id"], satir["gorsel"]) == (meme.id, f"memes/{meme.id}.png")
    assert (satir["annotator"], satir["reviewer"], satir["uyari"]) == (["a2", "a3"], "a4", [])


def test_ham_annotation_ve_test_seti_disa_aktarimi(client, yonetici, ali, ayse, can, meme_olustur, annotation_olustur, gonderilmis):
    meme = meme_olustur(yonetici)
    gonderilmis(meme, ali)
    annotation_olustur(meme_olustur(yonetici), ayse)
    client.post("/api/v1/test-queries", json={"metin": "Sınav sonucu açıklandı", "mod": "durum", "dogru_memeler": [meme.id]}, headers=basliklar(can))

    annotationlar = indir(client, yonetici, "annotations_raw.jsonl")
    assert sorted(satir["annotator"]["id"] for satir in annotationlar) == ["a2", "a3"]
    assert all(satir["annotator"]["id"] == satir["annotator"]["gorunen_ad"] for satir in annotationlar)
    assert annotationlar[0]["atanma_zamani"].endswith("Z")
    assert "icerik" in annotationlar[0] and "surum" in annotationlar[0]

    sorgular = indir(client, yonetici, "test_set.jsonl")
    assert [(s["yazan"], s["dogru_memeler"]) for s in sorgular] == [({"id": "a4", "gorunen_ad": "a4"}, [meme.id])]


def test_disa_aktarim_admin_icindir(client, yonetici, ali):
    assert client.get("/api/v1/export/gold.jsonl", headers=basliklar(ali)).status_code == 403
    assert client.get("/api/v1/export/sifreler.txt", headers=basliklar(yonetici)).status_code == 422
