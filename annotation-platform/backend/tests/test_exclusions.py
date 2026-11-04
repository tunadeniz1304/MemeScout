import json

import pytest
from sqlmodel import select

from app.models import AiDraft, Annotation, AuditEntry, GoldRecord, MemeExclusionVote, simdi
from tests.yardimci import basliklar, gecerli_icerik


@pytest.fixture()
def yonetici(kullanici_olustur):
    return kullanici_olustur("yonetici", admin=True, takma_ad="a0")


@pytest.fixture()
def ali(kullanici_olustur):
    return kullanici_olustur("ali", takma_ad="a1")


@pytest.fixture()
def ayse(kullanici_olustur):
    return kullanici_olustur("ayse", takma_ad="a2")


@pytest.fixture()
def can(kullanici_olustur):
    return kullanici_olustur("can", takma_ad="a3")


@pytest.fixture()
def meme(meme_olustur, yonetici):
    return meme_olustur(yonetici)


def oy_ver(client, kisi, meme_id, sebep="kopya", **ek):
    return client.put(f"/api/v1/memes/{meme_id}/exclusion-vote", json={"sebep": sebep, **ek}, headers=basliklar(kisi))


def oyum(client, kisi, meme_id):
    return client.get(f"/api/v1/memes/{meme_id}/exclusion-vote", headers=basliklar(kisi))


def oyu_geri_cek(client, kisi, meme_id):
    return client.delete(f"/api/v1/memes/{meme_id}/exclusion-vote", headers=basliklar(kisi))


def karar_ver(client, kisi, meme_id, karar, **ek):
    return client.post(f"/api/v1/exclusion-pool/{meme_id}/decision", json={"karar": karar, **ek}, headers=basliklar(kisi))


def havuz(client, kisi, durum=None):
    parametreler = {"durum": durum} if durum else {}
    return client.get("/api/v1/exclusion-pool", params=parametreler, headers=basliklar(kisi))


def hata_kodu(yanit) -> str:
    return yanit.json()["hata"]["kod"]


# ------------------------------------------------------------------ oy

def test_oy_verilir_ve_kisi_kendi_oyunu_gorur(client, ali, meme):
    yanit = oy_ver(client, ali, meme.id, sebep="kopya", **{"not": "  m0002 ile aynı  "})
    assert yanit.status_code == 200
    oy = yanit.json()
    assert oy["meme_id"] == meme.id
    assert oy["sebep"] == "kopya"
    assert oy["not"] == "m0002 ile aynı"
    assert oy["karar"] is None
    assert oy["zaman"].endswith("Z")

    assert oyum(client, ali, meme.id).json() == oy


def test_ikinci_istek_oyu_gunceller(client, session, ali, meme):
    oy_ver(client, ali, meme.id, sebep="kopya", **{"not": "aynısı var"})
    yanit = oy_ver(client, ali, meme.id, sebep="anlasilmaz")
    assert yanit.status_code == 200
    assert yanit.json()["sebep"] == "anlasilmaz"
    assert yanit.json()["not"] is None

    oylar = session.exec(select(MemeExclusionVote)).all()
    assert [(oy.kullanici_id, oy.sebep) for oy in oylar] == [(ali.id, "anlasilmaz")]


def test_bos_not_kaydedilmez(client, ali, meme):
    assert oy_ver(client, ali, meme.id, **{"not": "   "}).json()["not"] is None


def test_not_300_karakteri_gecemez(client, ali, meme):
    assert oy_ver(client, ali, meme.id, **{"not": "a" * 300}).status_code == 200
    yanit = oy_ver(client, ali, meme.id, **{"not": "a" * 301})
    assert yanit.status_code == 422
    assert hata_kodu(yanit) == "DOGRULAMA"
    assert yanit.json()["hata"]["alanlar"][0]["alan"] == "not"


def test_bilinmeyen_sebep_reddedilir(client, ali, meme):
    yanit = oy_ver(client, ali, meme.id, sebep="sikici")
    assert yanit.status_code == 422
    assert yanit.json()["hata"]["alanlar"][0]["alan"] == "sebep"


def test_oy_yoksa_ya_da_meme_yoksa_404(client, ali, meme):
    assert oyum(client, ali, meme.id).status_code == 404
    assert oyu_geri_cek(client, ali, meme.id).status_code == 404
    assert oy_ver(client, ali, "m9999").status_code == 404
    assert oyum(client, ali, "m9999").status_code == 404


def test_oy_geri_cekilir(client, ali, yonetici, meme):
    oy_ver(client, ali, meme.id)
    assert oyu_geri_cek(client, ali, meme.id).status_code == 204
    assert oyum(client, ali, meme.id).status_code == 404
    assert havuz(client, yonetici).json() == []


def test_oy_etiketlemeyi_durdurmaz(client, ali, meme, annotation_olustur):
    annotation = annotation_olustur(meme, ali)
    assert oy_ver(client, ali, meme.id).status_code == 200

    kuyruk = client.get("/api/v1/me/queue", headers=basliklar(ali)).json()
    assert [is_["annotation_id"] for is_ in kuyruk] == [annotation.id]
    assert client.get(f"/api/v1/annotations/{annotation.id}", headers=basliklar(ali)).json()["durum_kodu"] == "atandi"


def test_kisi_baskasinin_oyunu_goremez(client, ali, ayse, meme):
    oy_ver(client, ali, meme.id, **{"not": "bulanık"})
    assert oyum(client, ayse, meme.id).status_code == 404
    detay = client.get(f"/api/v1/memes/{meme.id}", headers=basliklar(ayse)).json()
    assert "bulanık" not in str(detay)
    assert havuz(client, ayse).status_code == 403


def test_oy_islemleri_denetim_kaydina_yazilir(client, session, ali, meme):
    oy_ver(client, ali, meme.id, sebep="kopya")
    oy_ver(client, ali, meme.id, sebep="kopya")  # değişiklik yok, kayıt da yok
    oy_ver(client, ali, meme.id, sebep="diger", **{"not": "bulanık"})
    oyu_geri_cek(client, ali, meme.id)

    kayitlar = session.exec(
        select(AuditEntry).where(AuditEntry.alan == "kullanilmasin_oyu").order_by(AuditEntry.id)
    ).all()
    assert [(k.kayit_tipi, k.kayit_id, k.kullanici_id, k.islem) for k in kayitlar] == [
        ("meme", meme.id, ali.id, "olusturma"),
        ("meme", meme.id, ali.id, "guncelleme"),
        ("meme", meme.id, ali.id, "silme"),
    ]
    assert kayitlar[0].yeni_deger == {"sebep": "kopya", "not": None, "karar": None}
    assert kayitlar[1].eski_deger == {"sebep": "kopya", "not": None, "karar": None}
    assert kayitlar[1].yeni_deger == {"sebep": "diger", "not": "bulanık", "karar": None}
    assert kayitlar[2].eski_deger == {"sebep": "diger", "not": "bulanık", "karar": None}


def test_kararla_sonuclanan_oyun_yeniden_verilmesi_denetlenir(client, session, ali, yonetici, meme):
    oy_ver(client, ali, meme.id, sebep="kopya")
    karar_ver(client, yonetici, meme.id, "kalsin")
    oy_ver(client, ali, meme.id, sebep="kopya")

    [kayit] = session.exec(
        select(AuditEntry).where(AuditEntry.alan == "kullanilmasin_oyu", AuditEntry.islem == "guncelleme")
    ).all()
    assert kayit.eski_deger == {"sebep": "kopya", "not": None, "karar": "kalsin"}
    assert kayit.yeni_deger == {"sebep": "kopya", "not": None, "karar": None}


# ------------------------------------------------------------------ havuz

def test_tek_oy_meme_i_havuza_dusurur(client, ali, yonetici, meme):
    oy_ver(client, ali, meme.id, sebep="kalitesiz_gorsel", **{"not": "çok bulanık"})

    [oge] = havuz(client, yonetici).json()
    assert oge["meme_id"] == meme.id
    assert oge["kucuk_gorsel_url"] == f"/api/v1/memes/{meme.id}/image?boyut=kucuk"
    assert oge["etiket_durumu"] == "atanmadi"
    assert oge["oy_sayisi"] == 1
    assert oge["sebepler"] == [{"sebep": "kalitesiz_gorsel", "sayi": 1}]
    assert [(oy["takma_ad"], oy["sebep"], oy["not"]) for oy in oge["oylar"]] == [("a1", "kalitesiz_gorsel", "çok bulanık")]
    assert oge["son_karar"] is None


def test_havuz_en_cok_oy_alani_once_listeler(client, ali, ayse, can, yonetici, meme_olustur):
    tek_oylu = meme_olustur(yonetici)
    cok_oylu = meme_olustur(yonetici)
    oy_ver(client, ali, tek_oylu.id, sebep="mem_degil")
    oy_ver(client, ali, cok_oylu.id, sebep="kopya")
    oy_ver(client, ayse, cok_oylu.id, sebep="diger")
    oy_ver(client, can, cok_oylu.id, sebep="kopya")

    ogeler = havuz(client, yonetici).json()
    assert [oge["meme_id"] for oge in ogeler] == [cok_oylu.id, tek_oylu.id]
    assert ogeler[0]["oy_sayisi"] == 3
    assert ogeler[0]["sebepler"] == [{"sebep": "kopya", "sayi": 2}, {"sebep": "diger", "sayi": 1}]
    assert {oy["takma_ad"] for oy in ogeler[0]["oylar"]} == {"a1", "a2", "a3"}


def test_havuz_admin_disinda_kapali(client, ali, meme):
    oy_ver(client, ali, meme.id)
    assert havuz(client, ali).status_code == 403
    assert karar_ver(client, ali, meme.id, "cikarilsin").status_code == 403


def test_bilinmeyen_havuz_durumu_reddedilir(client, yonetici):
    assert havuz(client, yonetici, durum="hepsi").status_code == 422


# ------------------------------------------------------------------ karar

def test_kalsin_meme_i_havuzdan_cikarir(client, ali, yonetici, meme):
    oy_ver(client, ali, meme.id)
    yanit = karar_ver(client, yonetici, meme.id, "kalsin", **{"not": "Toplantıda konuşuldu, kopya değil."})
    assert yanit.status_code == 201
    karar = yanit.json()
    assert karar["meme_id"] == meme.id
    assert karar["karar"] == "kalsin"
    assert karar["not"] == "Toplantıda konuşuldu, kopya değil."
    assert karar["karar_veren"] == {"id": yonetici.id, "gorunen_ad": "Yonetici"}

    assert havuz(client, yonetici).json() == []
    assert oyum(client, ali, meme.id).json()["karar"] == "kalsin"


def test_kalsindan_sonra_guncellenen_oy_havuzu_yeniden_acar(client, ali, ayse, yonetici, meme):
    oy_ver(client, ali, meme.id, sebep="kopya")
    karar_ver(client, yonetici, meme.id, "kalsin")
    oy_ver(client, ayse, meme.id, sebep="uygunsuz")

    [oge] = havuz(client, yonetici).json()
    assert [oy["takma_ad"] for oy in oge["oylar"]] == ["a2"]
    assert oge["son_karar"]["karar"] == "kalsin"
    assert oyum(client, ali, meme.id).json()["karar"] == "kalsin"
    assert oyum(client, ayse, meme.id).json()["karar"] is None

    # Kararı görmüş biri oyunu yeniden verirse oyu yeniden geçerli olur.
    oy_ver(client, ali, meme.id, sebep="kopya")
    [oge] = havuz(client, yonetici).json()
    assert oge["oy_sayisi"] == 2
    assert oyum(client, ali, meme.id).json()["karar"] is None


def test_cikarilsin_meme_i_kullanimdan_dusurur(client, ali, ayse, yonetici, meme):
    oy_ver(client, ali, meme.id, sebep="mem_degil")
    oy_ver(client, ayse, meme.id, sebep="mem_degil", **{"not": "reklam görseli"})
    assert karar_ver(client, yonetici, meme.id, "cikarilsin").status_code == 201

    assert havuz(client, yonetici).json() == []
    [oge] = havuz(client, yonetici, durum="cikarildi").json()
    assert oge["meme_id"] == meme.id
    assert oge["etiket_durumu"] == "cikarildi"
    assert oge["oy_sayisi"] == 2
    assert oge["sebepler"] == [{"sebep": "mem_degil", "sayi": 2}]
    assert oge["son_karar"]["karar"] == "cikarilsin"
    assert oyum(client, ayse, meme.id).json()["karar"] == "cikarilsin"
    assert client.get(f"/api/v1/memes/{meme.id}", headers=basliklar(ali)).json()["etiket_durumu"] == "cikarildi"


def test_cikarilmis_meme_in_oylari_donar(client, ali, ayse, yonetici, meme):
    oy_ver(client, ali, meme.id)
    karar_ver(client, yonetici, meme.id, "cikarilsin")

    for yanit in (oy_ver(client, ayse, meme.id), oy_ver(client, ali, meme.id, sebep="diger"), oyu_geri_cek(client, ali, meme.id)):
        assert yanit.status_code == 409
        assert hata_kodu(yanit) == "MEME_CIKARILDI"
    assert oyum(client, ali, meme.id).json()["sebep"] == "kopya"


def test_kalsin_cikarmayi_geri_alir(client, ali, yonetici, meme, annotation_olustur):
    annotation_olustur(meme, ali)
    oy_ver(client, ali, meme.id)
    karar_ver(client, yonetici, meme.id, "cikarilsin")
    assert karar_ver(client, yonetici, meme.id, "kalsin").status_code == 201

    assert havuz(client, yonetici, durum="cikarildi").json() == []
    assert havuz(client, yonetici).json() == []
    assert client.get(f"/api/v1/memes/{meme.id}", headers=basliklar(ali)).json()["etiket_durumu"] == "etiketleniyor"
    assert oyum(client, ali, meme.id).json()["karar"] == "kalsin"
    assert oy_ver(client, ali, meme.id).status_code == 200


def test_havuzda_olmayan_meme_e_karar_verilmez(client, ali, yonetici, meme):
    yanit = karar_ver(client, yonetici, meme.id, "cikarilsin")
    assert yanit.status_code == 409
    assert hata_kodu(yanit) == "HAVUZDA_DEGIL"

    oy_ver(client, ali, meme.id)
    karar_ver(client, yonetici, meme.id, "kalsin")
    assert hata_kodu(karar_ver(client, yonetici, meme.id, "kalsin")) == "HAVUZDA_DEGIL"


def test_cikarilmis_meme_yeniden_cikarilamaz(client, ali, yonetici, meme):
    oy_ver(client, ali, meme.id)
    karar_ver(client, yonetici, meme.id, "cikarilsin")
    yanit = karar_ver(client, yonetici, meme.id, "cikarilsin")
    assert yanit.status_code == 409
    assert hata_kodu(yanit) == "MEME_CIKARILDI"


def test_karar_dogrulanir(client, ali, yonetici, meme):
    oy_ver(client, ali, meme.id)
    assert karar_ver(client, yonetici, "m9999", "kalsin").status_code == 404
    assert karar_ver(client, yonetici, meme.id, "belki").status_code == 422
    assert karar_ver(client, yonetici, meme.id, "kalsin", **{"not": "a" * 1001}).status_code == 422


def test_karar_denetim_kaydina_yazilir(client, session, ali, yonetici, meme):
    oy_ver(client, ali, meme.id)
    karar_ver(client, yonetici, meme.id, "cikarilsin", **{"not": "Mem değil."})

    [kayit] = session.exec(select(AuditEntry).where(AuditEntry.alan == "havuz_karari")).all()
    assert (kayit.kayit_tipi, kayit.kayit_id, kayit.kullanici_id, kayit.islem) == ("meme", meme.id, yonetici.id, "olusturma")
    assert kayit.yeni_deger == {"karar": "cikarilsin", "not": "Mem değil."}


def test_karar_annotation_lari_silmez(client, session, ali, yonetici, meme, annotation_olustur):
    annotation = annotation_olustur(meme, ali)
    oy_ver(client, ali, meme.id)
    assert karar_ver(client, yonetici, meme.id, "cikarilsin").status_code == 201
    session.expire_all()
    assert session.get(Annotation, annotation.id) is not None


# ------------------------------------------------------------------ çıkarılan meme'in etkileri

@pytest.fixture()
def cikar(client, yonetici):
    def cikar(meme):
        assert oy_ver(client, yonetici, meme.id).status_code == 200
        assert karar_ver(client, yonetici, meme.id, "cikarilsin").status_code == 201

    return cikar


@pytest.fixture()
def gonderilmis(annotation_olustur):
    def olustur(meme, kisi, **alanlar):
        varsayilan = {
            "durum_kodu": "gonderildi",
            "icerik": gecerli_icerik(),
            "tanidiklik": 4,
            "gonderme_zamani": simdi(),
            "etiket_listesi_versiyonu": "v1",
            "sema_versiyonu": "1.0",
        }
        return annotation_olustur(meme, kisi, **{**varsayilan, **alanlar})

    return olustur


def gold_ekle(session, meme, kaynaklar, reviewer):
    session.add(GoldRecord(
        meme_id=meme.id, icerik=gecerli_icerik(), kaynak_annotationlar=[a.id for a in kaynaklar],
        reviewer_id=reviewer.id, sema_versiyonu="1.0", etiket_listesi_versiyonu="v1",
    ))
    session.commit()


def sorgu_yaz(client, kisi, dogru_memeler):
    return client.post(
        "/api/v1/test-queries",
        json={"metin": "Sınav sonucu açıklandı", "mod": "durum", "dogru_memeler": dogru_memeler},
        headers=basliklar(kisi),
    )


def test_cikarilan_meme_kuyruktan_duser(client, ali, yonetici, meme_olustur, annotation_olustur, cikar):
    cikarilan, kalan = meme_olustur(yonetici), meme_olustur(yonetici)
    annotation_olustur(cikarilan, ali)
    kalanin = annotation_olustur(kalan, ali)
    cikar(cikarilan)

    kuyruk = client.get("/api/v1/me/queue", headers=basliklar(ali)).json()
    assert [is_["annotation_id"] for is_ in kuyruk] == [kalanin.id]

    karar_ver(client, yonetici, cikarilan.id, "kalsin")
    assert len(client.get("/api/v1/me/queue", headers=basliklar(ali)).json()) == 2


def test_cikarilan_meme_etiketlenemez_ama_atlanabilir(client, ali, yonetici, meme_olustur, annotation_olustur, cikar):
    meme = meme_olustur(yonetici)
    baslanmamis = annotation_olustur(meme, ali, cift_etiket=True)
    cikar(meme)

    yanit = client.post(f"/api/v1/annotations/{baslanmamis.id}/start", headers=basliklar(ali))
    assert (yanit.status_code, hata_kodu(yanit)) == (409, "MEME_CIKARILDI")

    ikinci = meme_olustur(yonetici)
    yarim = annotation_olustur(ikinci, ali, durum_kodu="devam_ediyor", icerik=gecerli_icerik(), tanidiklik=4)
    cikar(ikinci)
    taslak = client.patch(f"/api/v1/annotations/{yarim.id}/draft", json={"surum": 1, "tanidiklik": 3}, headers=basliklar(ali))
    gonderim = client.post(f"/api/v1/annotations/{yarim.id}/submit", json={"surum": 1}, headers=basliklar(ali))
    for yanit in (taslak, gonderim):
        assert (yanit.status_code, hata_kodu(yanit)) == (409, "MEME_CIKARILDI")

    atlama = client.post(f"/api/v1/annotations/{yarim.id}/skip", json={"gerekce": "diger"}, headers=basliklar(ali))
    assert atlama.status_code == 200
    assert atlama.json()["durum_kodu"] == "atlandi"


def test_cikarilan_meme_atanamaz(client, ali, ayse, yonetici, meme_olustur, annotation_olustur, cikar):
    meme, diger = meme_olustur(yonetici), meme_olustur(yonetici)
    atlanan = annotation_olustur(meme, ali, durum_kodu="atlandi")
    cikar(meme)

    yanit = client.post(
        "/api/v1/assignments", json={"annotator_id": ayse.id, "meme_ids": [diger.id, meme.id]}, headers=basliklar(yonetici)
    )
    assert (yanit.status_code, hata_kodu(yanit)) == (409, "MEME_CIKARILDI")
    assert yanit.json()["hata"]["detay"] == {"meme_ids": [meme.id]}

    yanit = client.post(
        f"/api/v1/annotations/{atlanan.id}/reassign", json={"yeni_annotator_id": ayse.id}, headers=basliklar(yonetici)
    )
    assert (yanit.status_code, hata_kodu(yanit)) == (409, "MEME_CIKARILDI")


def test_otomatik_dagitim_cikarilan_memeleri_atlar(client, ali, ayse, yonetici, meme_olustur, cikar):
    cikarilan, kalan = meme_olustur(yonetici), meme_olustur(yonetici)
    cikar(cikarilan)

    plan = client.post(
        "/api/v1/assignments/auto",
        json={"annotator_ids": [ali.id, ayse.id], "cift_etiket_orani": 0, "dry_run": False},
        headers=basliklar(yonetici),
    ).json()
    assert [atama["meme_id"] for atama in plan["atamalar"]] == [kalan.id]


def test_cikarilan_meme_incelemeye_girmez(client, ali, can, yonetici, meme_olustur, gonderilmis, cikar):
    meme = meme_olustur(yonetici)
    annotation = gonderilmis(meme, ali)
    assert [oge["meme_id"] for oge in client.get("/api/v1/reviews", headers=basliklar(can)).json()] == [meme.id]
    cikar(meme)

    assert client.get("/api/v1/reviews", headers=basliklar(can)).json() == []
    detay = client.get(f"/api/v1/reviews/{meme.id}", headers=basliklar(can))
    gold = client.post(
        f"/api/v1/reviews/{meme.id}/gold",
        json={"icerik": gecerli_icerik(), "kaynak_annotationlar": [annotation.id]},
        headers=basliklar(can),
    )
    revizyon = client.post(
        f"/api/v1/annotations/{annotation.id}/request-revision", json={"not": "Durum alanı eksik."}, headers=basliklar(can)
    )
    for yanit in (detay, gold, revizyon):
        assert (yanit.status_code, hata_kodu(yanit)) == (409, "MEME_CIKARILDI")


def test_cikarilan_meme_test_sorgusuna_cevap_olarak_yazilamaz(client, ali, yonetici, meme_olustur, cikar):
    meme = meme_olustur(yonetici)
    cikar(meme)
    yanit = sorgu_yaz(client, ali, [meme.id])
    assert (yanit.status_code, hata_kodu(yanit)) == (422, "DOGRULAMA")
    assert yanit.json()["hata"]["alanlar"] == [
        {"alan": "dogru_memeler[0]", "kural": "gecersiz_deger", "mesaj": "Bu meme havuz kararıyla kullanımdan çıkarıldı."}
    ]


def test_cikarilan_meme_test_sorgularinin_cevaplarindan_duser(client, ali, yonetici, meme_olustur, cikar):
    cikarilan, kalan = meme_olustur(yonetici), meme_olustur(yonetici)
    sorgu_yaz(client, ali, [cikarilan.id, kalan.id])
    sorgu_yaz(client, ali, [cikarilan.id])
    cikar(cikarilan)

    cevaplar = sorted(sorgu["dogru_memeler"] for sorgu in client.get("/api/v1/test-queries", headers=basliklar(ali)).json())
    assert cevaplar == [[], [kalan.id]]

    # Karar geri alınınca cevaplar olduğu gibi döner; veritabanındaki liste değişmez.
    karar_ver(client, yonetici, cikarilan.id, "kalsin")
    cevaplar = sorted(sorgu["dogru_memeler"] for sorgu in client.get("/api/v1/test-queries", headers=basliklar(ali)).json())
    assert cevaplar == [[cikarilan.id], [cikarilan.id, kalan.id]]


def test_cikarilan_meme_disa_aktarilmaz(client, session, ali, ayse, can, yonetici, meme_olustur, gonderilmis, cikar):
    cikarilan, kalan = meme_olustur(yonetici), meme_olustur(yonetici)
    for meme in (cikarilan, kalan):
        gold_ekle(session, meme, [gonderilmis(meme, ali, durum_kodu="onaylandi")], ayse)
        session.add(AiDraft(meme_id=meme.id, kaynak="llm", kart={}, icerik=gecerli_icerik(), yukleyen_id=yonetici.id))
    session.commit()
    sorgu_yaz(client, can, [cikarilan.id, kalan.id])
    sorgu_yaz(client, can, [cikarilan.id])
    cikar(cikarilan)

    def indir(dosya):
        yanit = client.get(f"/api/v1/export/{dosya}", headers=basliklar(yonetici))
        assert yanit.status_code == 200
        return [json.loads(satir) for satir in yanit.text.splitlines()]

    assert [satir["id"] for satir in indir("gold.jsonl")] == [kalan.id]
    assert [satir["meme_id"] for satir in indir("annotations_raw.jsonl")] == [kalan.id]
    assert [satir["id"] for satir in indir("ai_drafts.jsonl")] == [kalan.id]
    # Cevabı kalmayan sorgu yazılmaz.
    assert [satir["dogru_memeler"] for satir in indir("test_set.jsonl")] == [[kalan.id]]


def test_ilerleme_cikarilan_memeleri_ayri_sayar(client, ali, yonetici, meme_olustur, annotation_olustur, cikar):
    bos, atanmis, kalan = meme_olustur(yonetici), meme_olustur(yonetici), meme_olustur(yonetici)
    annotation_olustur(atanmis, ali)
    cikar(bos)
    cikar(atanmis)

    istatistik = client.get("/api/v1/stats/progress", headers=basliklar(ali)).json()
    assert istatistik["genel"] == {
        "toplam_meme": 1,
        "atanmamis": 1,
        "gold_hazir": 0,
        "inceleme_bekleyen": 0,
        "yeniden_atama_bekleyen": 0,
        "cikarilan": 2,
    }
    kisiler = {satir["kullanici"]["id"]: satir for satir in istatistik["kullanicilar"]}
    assert (kisiler[ali.id]["atanan"], kisiler[ali.id]["kalan"]) == (0, 0)


def test_uyum_cikarilan_memeleri_saymaz(client, ali, ayse, yonetici, meme_olustur, annotation_olustur, gonderilmis, cikar):
    cift = meme_olustur(yonetici)
    gonderilmis(cift, ali, cift_etiket=True)
    gonderilmis(cift, ayse, cift_etiket=True)
    yarim = meme_olustur(yonetici)
    gonderilmis(yarim, ali, cift_etiket=True)
    annotation_olustur(yarim, ayse, cift_etiket=True, durum_kodu="devam_ediyor")
    assert "etiketler" not in client.get("/api/v1/stats/agreement", headers=basliklar(ali)).json()

    # Çıkarılan meme'in yarım kalan çift etiketlemesi kör etiketlemeyi sürdürmez.
    cikar(yarim)
    uyum = client.get("/api/v1/stats/agreement", headers=basliklar(ali)).json()
    assert uyum["cift_etiketli_meme_sayisi"] == 1
    assert "etiketler" in uyum

    cikar(cift)
    assert client.get("/api/v1/stats/agreement", headers=basliklar(ali)).json()["cift_etiketli_meme_sayisi"] == 0


def test_yeniden_kontrol_cikarilan_memeleri_listelemez(client, ali, yonetici, meme_olustur, gonderilmis, cikar):
    meme = meme_olustur(yonetici)
    gonderilmis(meme, ali, icerik=gecerli_icerik(duygu=["panik"]))
    client.patch("/api/v1/label-lists/labels/duygu/panik", json={"aktif": False}, headers=basliklar(yonetici))
    assert len(client.get("/api/v1/recheck", headers=basliklar(yonetici)).json()) == 1

    cikar(meme)
    assert client.get("/api/v1/recheck", headers=basliklar(yonetici)).json() == []


def test_cikarilan_meme_e_ai_taslagi_eklenmez(client, yonetici, meme_olustur, cikar):
    meme = meme_olustur(yonetici)
    cikar(meme)
    yanit = client.post(
        "/api/v1/memes/ai-drafts",
        json={"taslaklar": [{"sha256": meme.sha256, "kaynak": "llm", "kart": gecerli_icerik()}]},
        headers=basliklar(yonetici),
    )
    assert yanit.json()["eklenen"] == []
    assert [(red["meme_id"], red["sebep"]) for red in yanit.json()["reddedilen"]] == [(meme.id, "cikarildi")]


def test_cikarilan_memeler_listede_durumlariyla_gorunur(client, ali, yonetici, meme_olustur, cikar):
    cikarilan, kalan = meme_olustur(yonetici), meme_olustur(yonetici)
    cikar(cikarilan)

    sayfa = client.get("/api/v1/memes", params={"etiket_durumu": "cikarildi"}, headers=basliklar(ali)).json()
    assert [meme["id"] for meme in sayfa["ogeler"]] == [cikarilan.id]
    assert len(client.get("/api/v1/memes", headers=basliklar(ali)).json()["ogeler"]) == 2
