"""Atlanan meme'in otomatik yeniden ataması ve tanıdıklık 3'te ikinci annotator (ADR-0013)."""

import pytest
from sqlmodel import select

from app.denetim import OLUSTURMA
from app.models import AiDraft, Annotation, AuditEntry
from app.routes.assignments import KIMSE_KALMADI_NOTU
from tests.yardimci import basliklar, gecerli_icerik


@pytest.fixture()
def yonetici(kullanici_olustur):
    return kullanici_olustur("yonetici", admin=True, takma_ad="a1")


@pytest.fixture()
def ekip(kullanici_olustur, yonetici):
    return [yonetici] + [kullanici_olustur(ad, takma_ad=f"a{sira}") for sira, ad in enumerate(["ali", "ayse", "can"], start=2)]


@pytest.fixture()
def is_ver(yonetici, meme_olustur, annotation_olustur):
    """Kişilere başka meme'lerde açık iş verir; ana turda işi olan kişi otomatik atamada aday olur."""
    def ver(*kisiler):
        for kisi in kisiler:
            annotation_olustur(meme_olustur(yonetici), kisi)
    return ver


def atla(client, kisi, annotation_id):
    return client.post(f"/api/v1/annotations/{annotation_id}/skip", json={"gerekce": "tanimiyorum"}, headers=basliklar(kisi))


def gonder(client, kisi, annotation_id, tanidiklik):
    yol = f"/api/v1/annotations/{annotation_id}"
    surum = client.post(f"{yol}/start", headers=basliklar(kisi)).json()["surum"]
    govde = {"surum": surum, "icerik": gecerli_icerik(), "tanidiklik": tanidiklik}
    surum = client.patch(f"{yol}/draft", json=govde, headers=basliklar(kisi)).json()["surum"]
    return client.post(f"{yol}/submit", json={"surum": surum}, headers=basliklar(kisi))


def meme_isleri(session, meme) -> dict[str, Annotation]:
    """annotator_id → kişinin meme'deki ana tur annotation'ı."""
    session.expire_all()
    sorgu = select(Annotation).where(Annotation.meme_id == meme.id, Annotation.kalibrasyon == False)  # noqa: E712
    return {annotation.annotator_id: annotation for annotation in session.exec(sorgu).all()}


def etiket_durumu(client, yonetici, meme):
    return client.get(f"/api/v1/memes/{meme.id}", headers=basliklar(yonetici)).json()["etiket_durumu"]


def havuz(client, yonetici):
    return [
        (oge["meme_id"], [(oy["takma_ad"], oy["sebep"], oy["not"]) for oy in oge["oylar"]])
        for oge in client.get("/api/v1/exclusion-pool", headers=basliklar(yonetici)).json()
    ]


# ------------------------------------------------------------------ atlama

def test_atlanan_meme_acik_isi_en_az_olana_gider(client, session, yonetici, ekip, meme_olustur, annotation_olustur, is_ver):
    ali, ayse, can = ekip[1:]
    # Can'ın ana turda hiç işi yok, aday olmaz; adaylardan açık işi en az olan Ayşe.
    is_ver(yonetici, yonetici, ayse)
    meme = meme_olustur(yonetici)
    atlanan = annotation_olustur(meme, ali)

    yanit = atla(client, ali, atlanan.id)
    assert yanit.status_code == 200
    assert yanit.json()["durum_kodu"] == "atlandi"
    isler = meme_isleri(session, meme)
    assert sorted(isler) == sorted([ali.id, ayse.id])
    yeni = isler[ayse.id]
    assert (yeni.durum_kodu, yeni.cift_etiket) == ("atandi", False)
    assert isler[ali.id].yerine_gecen_id == yeni.id
    assert meme.id in [is_["meme_id"] for is_ in client.get("/api/v1/me/queue", headers=basliklar(ayse)).json()]
    denetim = session.exec(select(AuditEntry).where(AuditEntry.kayit_id == yeni.id, AuditEntry.islem == OLUSTURMA)).one()
    assert denetim.kullanici_id == ali.id
    assert denetim.yeni_deger["otomatik"] is True
    assert denetim.yeni_deger["onceki_annotation_id"] == atlanan.id


def test_atlayan_atanmis_ve_test_sorgusu_yazan_aday_olmaz(
    client, session, yonetici, ekip, kullanici_olustur, meme_olustur, annotation_olustur, is_ver
):
    ali, ayse, can = ekip[1:]
    deniz = kullanici_olustur("deniz", takma_ad="a5")
    is_ver(*ekip, deniz, yonetici, yonetici)
    meme = meme_olustur(yonetici)
    annotation_olustur(meme, can, cift_etiket=True, durum_kodu="atlandi")
    annotation_olustur(meme, ali, cift_etiket=True)
    atlanan = annotation_olustur(meme, ayse, cift_etiket=True)
    sorgu = {"metin": "Ev sahibi kirayı konuşalım dedi", "mod": "durum", "dogru_memeler": [meme.id]}
    assert client.post("/api/v1/test-queries", json=sorgu, headers=basliklar(deniz)).status_code == 201

    assert atla(client, ayse, atlanan.id).status_code == 200
    # Can atladı, Ali zaten atanmış, Deniz test sorgusu yazdı: işi en çok olsa da yönetici alır.
    yeni = meme_isleri(session, meme)[yonetici.id]
    assert (yeni.durum_kodu, yeni.cift_etiket) == ("atandi", True)


def test_kimse_kalmayinca_meme_havuza_duser(client, session, yonetici, ekip, meme_olustur, annotation_olustur, is_ver):
    is_ver(*ekip)
    meme = meme_olustur(yonetici)
    for kisi in ekip[1:]:
        annotation_olustur(meme, kisi, durum_kodu="atlandi")
    son = annotation_olustur(meme, yonetici)

    assert atla(client, yonetici, son.id).status_code == 200
    isler = meme_isleri(session, meme)
    assert len(isler) == 4
    assert isler[yonetici.id].yerine_gecen_id is None
    assert havuz(client, yonetici) == [(meme.id, [("a1", "diger", KIMSE_KALMADI_NOTU)])]


def test_kararla_sonuclanmis_oy_yeniden_havuza_doner(client, yonetici, ekip, meme_olustur, annotation_olustur, is_ver):
    ali = ekip[1]
    is_ver(ali)
    meme = meme_olustur(yonetici)
    son = annotation_olustur(meme, ali)
    oy = client.put(f"/api/v1/memes/{meme.id}/exclusion-vote", json={"sebep": "kalitesiz_gorsel"}, headers=basliklar(ali))
    assert oy.status_code == 200
    karar = client.post(f"/api/v1/exclusion-pool/{meme.id}/decision", json={"karar": "kalsin"}, headers=basliklar(yonetici))
    assert karar.status_code == 201, karar.json()
    assert havuz(client, yonetici) == []

    assert atla(client, ali, son.id).status_code == 200
    assert havuz(client, yonetici) == [(meme.id, [("a2", "diger", KIMSE_KALMADI_NOTU)])]


def test_cift_etiketli_memede_kimse_kalmazsa_meme_tek_etiketle_surer(
    client, session, yonetici, ekip, meme_olustur, annotation_olustur, is_ver
):
    ali, ayse, can = ekip[1:]
    is_ver(*ekip)
    meme = meme_olustur(yonetici)
    for kisi in (yonetici, can):
        annotation_olustur(meme, kisi, cift_etiket=True, durum_kodu="atlandi")
    kalan = annotation_olustur(meme, ali, cift_etiket=True)
    atlanan = annotation_olustur(meme, ayse, cift_etiket=True)

    assert atla(client, ayse, atlanan.id).status_code == 200
    isler = meme_isleri(session, meme)
    assert len(isler) == 4
    assert not any(annotation.cift_etiket for annotation in isler.values())
    assert gonder(client, ali, kalan.id, 4).status_code == 200
    assert etiket_durumu(client, yonetici, meme) == "inceleme_bekliyor"
    # Meme'i bilen biri vardı; havuza düşmez.
    assert havuz(client, yonetici) == []


def test_kalibrasyonda_ve_cikarilan_memede_otomatik_atama_olmaz(
    client, session, yonetici, ekip, meme_olustur, annotation_olustur, is_ver
):
    ali = ekip[1]
    is_ver(*ekip)
    meme = meme_olustur(yonetici)
    kalibrasyon = annotation_olustur(meme, ali, kalibrasyon=True)
    assert atla(client, ali, kalibrasyon.id).status_code == 200
    session.refresh(kalibrasyon)
    assert kalibrasyon.yerine_gecen_id is None
    assert meme_isleri(session, meme) == {}

    cikarilan = meme_olustur(yonetici)
    atlanan = annotation_olustur(cikarilan, ali)
    client.put(f"/api/v1/memes/{cikarilan.id}/exclusion-vote", json={"sebep": "mem_degil"}, headers=basliklar(ali))
    client.post(f"/api/v1/exclusion-pool/{cikarilan.id}/decision", json={"karar": "cikarilsin"}, headers=basliklar(yonetici))
    assert atla(client, ali, atlanan.id).status_code == 200
    assert list(meme_isleri(session, cikarilan)) == [ali.id]


# ------------------------------------------------------------------ tanıdıklık 3

def test_tanidiklik_3_ile_gonderilen_meme_ikinci_kisiye_gider(
    client, session, yonetici, ekip, meme_olustur, annotation_olustur, is_ver
):
    ali, ayse, can = ekip[1:]
    is_ver(*ekip)
    is_ver(yonetici, can)
    meme = meme_olustur(yonetici)
    ilk = annotation_olustur(meme, ali)

    yanit = gonder(client, ali, ilk.id, 3)
    assert yanit.status_code == 200
    assert (yanit.json()["durum_kodu"], yanit.json()["cift_etiket"]) == ("gonderildi", True)
    ikinci = meme_isleri(session, meme)[ayse.id]
    assert (ikinci.durum_kodu, ikinci.cift_etiket) == ("atandi", True)
    assert etiket_durumu(client, yonetici, meme) == "etiketleniyor"
    # Kör etiketleme: ikinci kişi ilk etiketi görmez.
    assert client.get(f"/api/v1/annotations/{ilk.id}", headers=basliklar(ayse)).status_code == 403

    # İkinci kişi de 3 verirse üçüncü kişi eklenmez; reviewer iki etiketi birleştirir.
    assert gonder(client, ayse, ikinci.id, 3).status_code == 200
    assert len(meme_isleri(session, meme)) == 2
    assert etiket_durumu(client, yonetici, meme) == "inceleme_bekliyor"


def test_ikinci_kisi_eklenmeyen_durumlar(client, session, yonetici, ekip, meme_olustur, annotation_olustur, is_ver):
    ali = ekip[1]
    is_ver(*ekip)

    dort = meme_olustur(yonetici)
    assert gonder(client, ali, annotation_olustur(dort, ali).id, 4).json()["cift_etiket"] is False

    # AI taslaklı meme tek etiketli kalır; onu reviewer'ın ikinci bakışı karşılar (ADR-0010).
    taslakli = meme_olustur(yonetici)
    session.add(AiDraft(meme_id=taslakli.id, kaynak="llm", kart={}, icerik=gecerli_icerik(), yukleyen_id=yonetici.id))
    session.commit()
    assert gonder(client, ali, annotation_olustur(taslakli, ali).id, 3).json()["cift_etiket"] is False

    # Revizyondan dönen annotation'ı reviewer zaten gördü.
    revizyon = meme_olustur(yonetici)
    donen = annotation_olustur(revizyon, ali, durum_kodu="revizyon_gerekli", icerik=gecerli_icerik(), tanidiklik=3)
    yanit = client.post(f"/api/v1/annotations/{donen.id}/submit", json={"surum": 1}, headers=basliklar(ali))
    assert yanit.json()["cift_etiket"] is False

    for meme in (dort, taslakli, revizyon):
        assert list(meme_isleri(session, meme)) == [ali.id]
