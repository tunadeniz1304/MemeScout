from collections import Counter

import pytest
from sqlmodel import select

from app.models import Annotation, AuditEntry, GoldRecord
from tests.yardimci import basliklar, gecerli_icerik


@pytest.fixture()
def yonetici(kullanici_olustur):
    return kullanici_olustur("yonetici", admin=True, takma_ad="a1")


@pytest.fixture()
def ekip(kullanici_olustur, yonetici):
    return [yonetici] + [kullanici_olustur(ad, takma_ad=f"a{sira}") for sira, ad in enumerate(["ali", "ayse", "can"], start=2)]


def ata(client, yonetici, **veri):
    return client.post("/api/v1/assignments", json=veri, headers=basliklar(yonetici))


def annotationlar(session):
    session.expire_all()
    return session.exec(select(Annotation).order_by(Annotation.atanma_zamani)).all()


# ------------------------------------------------------------------ POST /assignments

def test_elle_atama_annotation_olusturur(client, session, yonetici, ekip, meme_olustur):
    ali = ekip[1]
    memeler = [meme_olustur(yonetici), meme_olustur(yonetici)]
    yanit = ata(client, yonetici, meme_ids=[meme.id for meme in memeler], annotator_id=ali.id)
    assert yanit.status_code == 201
    ozetler = yanit.json()
    assert [(ozet["meme_id"], ozet["durum_kodu"], ozet["cift_etiket"], ozet["kalibrasyon"]) for ozet in ozetler] == [
        ("m0001", "atandi", False, False),
        ("m0002", "atandi", False, False),
    ]
    assert ozetler[0]["annotator"] == {"id": ali.id, "gorunen_ad": "Ali"}
    assert len(session.exec(select(AuditEntry).where(AuditEntry.kayit_tipi == "annotation")).all()) == 2


def test_elle_atama_admin_ister(client, ekip, yonetici, meme_olustur):
    meme = meme_olustur(yonetici)
    yanit = ata(client, ekip[1], meme_ids=[meme.id], annotator_id=ekip[1].id)
    assert yanit.status_code == 403


def test_gecersiz_meme_ve_kisi_422(client, yonetici, ekip, meme_olustur):
    meme = meme_olustur(yonetici)
    yanit = ata(client, yonetici, meme_ids=[meme.id, "m0404", meme.id], annotator_id=ekip[1].id)
    assert yanit.status_code == 422
    assert {(hata["alan"], hata["kural"]) for hata in yanit.json()["hata"]["alanlar"]} == {
        ("meme_ids[1]", "gecersiz_deger"),
        ("meme_ids[2]", "tekrar"),
    }
    yanit = ata(client, yonetici, meme_ids=[meme.id], annotator_id="yok")
    assert yanit.status_code == 422
    assert yanit.json()["hata"]["alanlar"][0]["alan"] == "annotator_id"
    assert ata(client, yonetici, meme_ids=[], annotator_id=ekip[1].id).status_code == 422


def test_ayni_kisiye_ikinci_atama_reddedilir_ve_hicbiri_olusmaz(client, session, yonetici, ekip, meme_olustur):
    ali = ekip[1]
    birinci, ikinci = meme_olustur(yonetici), meme_olustur(yonetici)
    ata(client, yonetici, meme_ids=[birinci.id], annotator_id=ali.id)
    yanit = ata(client, yonetici, meme_ids=[ikinci.id, birinci.id], annotator_id=ali.id)
    assert yanit.status_code == 409
    hata = yanit.json()["hata"]
    assert hata["kod"] == "ZATEN_ATANMIS"
    assert hata["detay"] == {"meme_ids": [birinci.id]}
    assert len(annotationlar(session)) == 1


def test_ikinci_kisi_memei_cift_etiketli_yapar(client, session, yonetici, ekip, meme_olustur):
    ali, ayse, can = ekip[1:]
    meme = meme_olustur(yonetici)
    ata(client, yonetici, meme_ids=[meme.id], annotator_id=ali.id)
    yanit = ata(client, yonetici, meme_ids=[meme.id], annotator_id=ayse.id)
    assert yanit.status_code == 201
    assert yanit.json()[0]["cift_etiket"] is True
    assert [a.cift_etiket for a in annotationlar(session)] == [True, True]
    terfi = session.exec(select(AuditEntry).where(AuditEntry.alan == "cift_etiket")).one()
    assert (terfi.eski_deger, terfi.yeni_deger) == (False, True)

    ucuncu = ata(client, yonetici, meme_ids=[meme.id], annotator_id=can.id)
    assert ucuncu.status_code == 409
    assert ucuncu.json()["hata"]["kod"] == "ZATEN_ATANMIS"


def test_gold_kaydi_olan_meme_atanamaz(client, session, yonetici, ekip, meme_olustur):
    meme = meme_olustur(yonetici)
    session.add(GoldRecord(meme_id=meme.id, icerik=gecerli_icerik(), sema_versiyonu="1.0", etiket_listesi_versiyonu="v1"))
    session.commit()
    yanit = ata(client, yonetici, meme_ids=[meme.id], annotator_id=ekip[1].id)
    assert yanit.status_code == 409
    assert yanit.json()["hata"]["kod"] == "GECERSIZ_DURUM_GECISI"


def test_kalibrasyon_turu_ayri_tutulur(client, session, yonetici, ekip, meme_olustur):
    meme = meme_olustur(yonetici)
    for kisi in ekip:
        yanit = ata(client, yonetici, meme_ids=[meme.id], annotator_id=kisi.id, kalibrasyon=True, cift_etiket=True)
        assert yanit.status_code == 201
        assert (yanit.json()[0]["kalibrasyon"], yanit.json()[0]["cift_etiket"]) == (True, False)
    tekrar = ata(client, yonetici, meme_ids=[meme.id], annotator_id=ekip[1].id, kalibrasyon=True)
    assert tekrar.status_code == 409
    # Kalibrasyondaki kişi aynı meme'i ana turda da etiketleyebilir.
    ana_tur = ata(client, yonetici, meme_ids=[meme.id], annotator_id=ekip[1].id)
    assert ana_tur.status_code == 201
    assert ana_tur.json()[0]["cift_etiket"] is False


# ------------------------------------------------------------------ POST /assignments/auto

def otomatik(client, yonetici, ekip, **veri):
    istek = {"annotator_ids": [kisi.id for kisi in ekip], **veri}
    return client.post("/api/v1/assignments/auto", json=istek, headers=basliklar(yonetici))


def test_otomatik_dagitim_dengeli_ve_dry_run_kayit_olusturmaz(client, session, yonetici, ekip, meme_olustur):
    for _ in range(60):
        meme_olustur(yonetici)
    yanit = otomatik(client, yonetici, ekip, cift_etiket_orani=0.2)
    assert yanit.status_code == 200
    plan = yanit.json()
    assert plan["dry_run"] is True
    assert annotationlar(session) == []

    assert len(plan["atamalar"]) == 60
    ciftler = [atama for atama in plan["atamalar"] if len(atama["annotator_ids"]) == 2]
    assert len(ciftler) == 12
    assert all(len(set(atama["annotator_ids"])) == len(atama["annotator_ids"]) for atama in plan["atamalar"])
    assert [kisi["meme_sayisi"] for kisi in plan["kisi_basi"]] == [18, 18, 18, 18]
    assert len(plan["ikili_dagilimi"]) == 6
    assert [ikili["meme_sayisi"] for ikili in plan["ikili_dagilimi"]] == [2] * 6
    assert {kisi["id"] for kisi in plan["ikili_dagilimi"][0]["ikili"]} == {ekip[0].id, ekip[1].id}


def test_otomatik_dagitim_uygulaninca_plandaki_annotationlar_olusur(client, session, yonetici, ekip, meme_olustur):
    for _ in range(25):
        meme_olustur(yonetici)
    plan = otomatik(client, yonetici, ekip).json()
    uygulanan = otomatik(client, yonetici, ekip, dry_run=False).json()
    assert uygulanan["dry_run"] is False
    assert uygulanan["atamalar"] == plan["atamalar"]

    olusan = annotationlar(session)
    assert len(olusan) == sum(len(atama["annotator_ids"]) for atama in plan["atamalar"])
    beklenen = {(atama["meme_id"], kisi) for atama in plan["atamalar"] for kisi in atama["annotator_ids"]}
    assert {(a.meme_id, a.annotator_id) for a in olusan} == beklenen
    ciftler = {atama["meme_id"] for atama in plan["atamalar"] if len(atama["annotator_ids"]) == 2}
    assert all(a.cift_etiket == (a.meme_id in ciftler) for a in olusan)
    yukler = Counter(a.annotator_id for a in olusan)
    assert max(yukler.values()) - min(yukler.values()) <= 1

    # Hepsi atandı; ikinci çalıştırmada dağıtılacak meme kalmaz.
    assert otomatik(client, yonetici, ekip).json()["atamalar"] == []


def test_otomatik_dagitim_atanmis_memeleri_atlar_kalibrasyonlulari_cift_yapmaz(
    client, yonetici, ekip, meme_olustur, annotation_olustur
):
    atanmis = meme_olustur(yonetici)
    annotation_olustur(atanmis, ekip[1])
    kalibrasyonlu = [meme_olustur(yonetici) for _ in range(4)]
    for meme in kalibrasyonlu:
        annotation_olustur(meme, ekip[2], kalibrasyon=True, durum_kodu="gonderildi")
    plan = otomatik(client, yonetici, ekip, cift_etiket_orani=1).json()
    memeler = {atama["meme_id"]: atama["annotator_ids"] for atama in plan["atamalar"]}
    assert atanmis.id not in memeler
    assert all(len(memeler[meme.id]) == 1 for meme in kalibrasyonlu)


def test_otomatik_dagitim_dogrulamasi(client, yonetici, ekip, meme_olustur):
    assert otomatik(client, ekip[1], ekip).status_code == 403
    assert otomatik(client, yonetici, ekip[:1]).status_code == 422
    assert otomatik(client, yonetici, [ekip[1], ekip[1]]).status_code == 422
    assert otomatik(client, yonetici, ekip, cift_etiket_orani=1.5).status_code == 422


# ------------------------------------------------------------------ POST /annotations/{id}/reassign

def yeniden_ata(client, kullanici, annotation_id, kisi_id):
    return client.post(
        f"/api/v1/annotations/{annotation_id}/reassign",
        json={"yeni_annotator_id": kisi_id},
        headers=basliklar(kullanici),
    )


def test_atlanan_annotation_baska_birine_atanir(client, session, yonetici, ekip, meme_olustur, annotation_olustur):
    ali, ayse, can = ekip[1:]
    meme = meme_olustur(yonetici)
    annotation_olustur(meme, ali, cift_etiket=True, durum_kodu="devam_ediyor")
    atlanan = annotation_olustur(meme, ayse, cift_etiket=True, durum_kodu="atlandi", atlandi={"gerekce": "tanimiyorum"})

    yanit = yeniden_ata(client, yonetici, atlanan.id, can.id)
    assert yanit.status_code == 201
    yeni = yanit.json()
    assert (yeni["meme_id"], yeni["durum_kodu"], yeni["cift_etiket"]) == (meme.id, "atandi", True)
    assert yeni["annotator"]["id"] == can.id
    session.refresh(atlanan)
    assert atlanan.durum_kodu == "atlandi"
    assert atlanan.yerine_gecen_id == yeni["id"]

    ikinci_kez = yeniden_ata(client, yonetici, atlanan.id, yonetici.id)
    assert ikinci_kez.status_code == 409


def test_yeniden_atama_kurallari(client, yonetici, ekip, meme_olustur, annotation_olustur):
    ali, ayse = ekip[1:3]
    meme = meme_olustur(yonetici)
    devam_eden = annotation_olustur(meme, ali, cift_etiket=True, durum_kodu="devam_ediyor")
    atlanan = annotation_olustur(meme, ayse, cift_etiket=True, durum_kodu="atlandi")

    assert yeniden_ata(client, yonetici, devam_eden.id, ekip[3].id).json()["hata"]["kod"] == "GECERSIZ_DURUM_GECISI"
    assert yeniden_ata(client, yonetici, atlanan.id, ali.id).json()["hata"]["kod"] == "ZATEN_ATANMIS"
    assert yeniden_ata(client, yonetici, atlanan.id, ayse.id).json()["hata"]["kod"] == "ZATEN_ATANMIS"
    assert yeniden_ata(client, yonetici, atlanan.id, "yok").status_code == 422
    assert yeniden_ata(client, yonetici, "yok", ali.id).status_code == 404
    assert yeniden_ata(client, ali, atlanan.id, ekip[3].id).status_code == 403
