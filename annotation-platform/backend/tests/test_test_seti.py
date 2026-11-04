"""Test seti ve sızıntı kuralının ters yönü (ADR-0012)."""

from datetime import timedelta

import pytest
from sqlmodel import select

from app.models import AuditEntry, simdi
from tests.yardimci import basliklar, gecerli_icerik


@pytest.fixture()
def yonetici(kullanici_olustur):
    return kullanici_olustur("yonetici", admin=True, takma_ad="a1")


@pytest.fixture()
def ekip(kullanici_olustur, yonetici):
    return [yonetici] + [kullanici_olustur(ad, takma_ad=f"a{sira}") for sira, ad in enumerate(["ali", "ayse", "can"], start=2)]


def sete_al(client, kisi, meme, deger=True):
    return client.patch(f"/api/v1/memes/{meme.id}", json={"test_seti": deger}, headers=basliklar(kisi))


def sorgu_yaz(client, kisi, meme, **ek):
    govde = {"metin": "Arkadaşım yine son dakika buluşmayı iptal etti", "mod": "durum", "dogru_memeler": [meme.id], **ek}
    return client.post("/api/v1/test-queries", json=govde, headers=basliklar(kisi))


def ata(client, yonetici, meme, kisi):
    return client.post("/api/v1/assignments", json={"meme_ids": [meme.id], "annotator_id": kisi.id}, headers=basliklar(yonetici))


def plan(client, yonetici, ekip, oran=0.0):
    govde = {"annotator_ids": [kisi.id for kisi in ekip], "cift_etiket_orani": oran, "dry_run": True}
    return client.post("/api/v1/assignments/auto", json=govde, headers=basliklar(yonetici)).json()


# ------------------------------------------------------------------ test seti

def test_admin_memeyi_test_setine_alir_ve_liste_suzer(client, session, yonetici, meme_olustur):
    meme, diger = meme_olustur(yonetici), meme_olustur(yonetici)
    yanit = sete_al(client, yonetici, meme)
    assert yanit.status_code == 200
    assert yanit.json()["test_seti"] is True

    def listele(deger):
        return [oge["id"] for oge in client.get("/api/v1/memes", params={"test_seti": deger}, headers=basliklar(yonetici)).json()["ogeler"]]

    assert listele(True) == [meme.id]
    assert listele(False) == [diger.id]
    denetim = session.exec(select(AuditEntry).where(AuditEntry.kayit_id == meme.id, AuditEntry.alan == "test_seti")).one()
    assert (denetim.eski_deger, denetim.yeni_deger) == (False, True)


def test_test_setine_almayi_yalniz_admin_yapar(client, yonetici, ekip, meme_olustur):
    assert sete_al(client, ekip[1], meme_olustur(yonetici)).status_code == 403


def test_etiketlenmeye_baslanmis_meme_test_setine_alinamaz(client, yonetici, ekip, meme_olustur, annotation_olustur):
    meme = meme_olustur(yonetici)
    annotation_olustur(meme, ekip[1])
    yanit = sete_al(client, yonetici, meme)
    assert yanit.status_code == 409
    assert yanit.json()["hata"]["kod"] == "GECERSIZ_DURUM_GECISI"


def test_test_setindeki_meme_atanmaz(client, yonetici, ekip, meme_olustur):
    meme, diger = meme_olustur(yonetici), meme_olustur(yonetici)
    sete_al(client, yonetici, meme)
    yanit = ata(client, yonetici, meme, ekip[1])
    assert yanit.status_code == 409
    assert yanit.json()["hata"]["kod"] == "TEST_SETI"
    assert [atama["meme_id"] for atama in plan(client, yonetici, ekip)["atamalar"]] == [diger.id]
    # Test setinden çıkarılan meme yeniden dağıtıma girer.
    sete_al(client, yonetici, meme, deger=False)
    assert sorted(atama["meme_id"] for atama in plan(client, yonetici, ekip)["atamalar"]) == [meme.id, diger.id]


def test_test_setindeki_memeye_herkes_sorgu_yazar(client, yonetici, ekip, meme_olustur):
    meme = meme_olustur(yonetici)
    sete_al(client, yonetici, meme)
    assert [sorgu_yaz(client, kisi, meme).status_code for kisi in ekip] == [201] * 4


# ------------------------------------------------------------------ sızıntının ters yönü

def test_sorgu_yazan_memeye_elle_atanamaz(client, yonetici, ekip, meme_olustur):
    meme = meme_olustur(yonetici)
    ali, ayse = ekip[1], ekip[2]
    assert sorgu_yaz(client, ali, meme).status_code == 201
    yanit = ata(client, yonetici, meme, ali)
    assert yanit.status_code == 409
    assert yanit.json()["hata"]["kod"] == "SIZINTI"
    assert yanit.json()["hata"]["detay"]["ihlal_eden_memeler"] == [meme.id]
    assert ata(client, yonetici, meme, ayse).status_code == 201


def test_otomatik_dagitim_sorgu_yazana_atamaz(client, yonetici, ekip, meme_olustur):
    memeler = [meme_olustur(yonetici) for _ in range(8)]
    ali = ekip[1]
    for meme in memeler:
        assert sorgu_yaz(client, ali, meme).status_code == 201
    atamalar = plan(client, yonetici, ekip, oran=0.5)["atamalar"]
    assert len(atamalar) == 8
    assert all(ali.id not in atama["annotator_ids"] for atama in atamalar)
    # Ali'yi içermeyen üç ikili kaldığı için memelerin yarısı yine çift etiketlenir.
    assert sum(len(atama["annotator_ids"]) == 2 for atama in atamalar) == 4


def test_kimseye_atanamayan_meme_dagitimda_kalir(client, yonetici, ekip, meme_olustur):
    meme = meme_olustur(yonetici)
    for kisi in ekip:
        assert sorgu_yaz(client, kisi, meme).status_code == 201
    assert plan(client, yonetici, ekip)["atamalar"] == []


def test_sorgu_yazan_reviewer_olamaz(client, yonetici, ekip, meme_olustur, annotation_olustur):
    meme = meme_olustur(yonetici)
    ali, ayse, can = ekip[1], ekip[2], ekip[3]
    annotation_olustur(
        meme, ali, durum_kodu="gonderildi", icerik=gecerli_icerik(), tanidiklik=4,
        gonderme_zamani=simdi() - timedelta(minutes=1),
    )
    assert sorgu_yaz(client, ayse, meme).status_code == 201

    def kuyruktakiler(kisi):
        return [oge["meme_id"] for oge in client.get("/api/v1/reviews", headers=basliklar(kisi)).json()]

    assert meme.id not in kuyruktakiler(ayse)
    assert meme.id in kuyruktakiler(can)
    yanit = client.get(f"/api/v1/reviews/{meme.id}", headers=basliklar(ayse))
    assert yanit.status_code == 403
    assert yanit.json()["hata"]["kod"] == "SIZINTI"


def test_sorgu_yazana_yeniden_atanamaz(client, yonetici, ekip, meme_olustur, annotation_olustur):
    meme = meme_olustur(yonetici)
    ali, ayse = ekip[1], ekip[2]
    atlanan = annotation_olustur(meme, ali, durum_kodu="atlandi", atlandi={"gerekce": "tanimiyorum"})
    assert sorgu_yaz(client, ayse, meme).status_code == 201
    yanit = client.post(
        f"/api/v1/annotations/{atlanan.id}/reassign", json={"yeni_annotator_id": ayse.id}, headers=basliklar(yonetici),
    )
    assert yanit.status_code == 409
    assert yanit.json()["hata"]["kod"] == "SIZINTI"


# ------------------------------------------------------------------ başkası adına sorgu

def test_admin_baskasi_adina_sorgu_ekler(client, session, yonetici, ekip, meme_olustur):
    meme = meme_olustur(yonetici)
    can = ekip[3]
    yanit = sorgu_yaz(client, yonetici, meme, yazan_id=can.id)
    assert yanit.status_code == 201
    assert yanit.json()["yazan"]["id"] == can.id
    denetim = session.exec(select(AuditEntry).where(AuditEntry.kayit_tipi == "test_sorgusu")).one()
    assert denetim.kullanici_id == yonetici.id
    assert denetim.yeni_deger["yazan_id"] == can.id
    # Sorgu Can'ın sayıldığı için meme ona atanamaz.
    assert ata(client, yonetici, meme, can).json()["hata"]["kod"] == "SIZINTI"


def test_admin_olmayan_baskasi_adina_sorgu_ekleyemez(client, yonetici, ekip, meme_olustur):
    yanit = sorgu_yaz(client, ekip[1], meme_olustur(yonetici), yazan_id=ekip[2].id)
    assert yanit.status_code == 403


def test_baskasi_adina_sorguda_kurallar_yazara_uygulanir(client, yonetici, ekip, meme_olustur, annotation_olustur):
    meme = meme_olustur(yonetici)
    annotation_olustur(meme, ekip[2])
    yanit = sorgu_yaz(client, yonetici, meme, yazan_id=ekip[2].id)
    assert yanit.status_code == 422
    assert yanit.json()["hata"]["kod"] == "SIZINTI"
    assert sorgu_yaz(client, yonetici, meme, yazan_id="yok").status_code == 422
