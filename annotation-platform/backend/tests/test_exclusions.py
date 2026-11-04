import pytest
from sqlmodel import select

from app.models import Annotation, AuditEntry, MemeExclusionVote
from tests.yardimci import basliklar


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
