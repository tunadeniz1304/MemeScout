import pytest
from sqlmodel import select

from app.models import AuditEntry, GoldRecord
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
def gold_meme(session, meme_olustur, annotation_olustur, yonetici):
    """Kaynak annotation'ı `annotator`'a, onayı `reviewer`'a ait gold kayıtlı meme."""

    def olustur(annotator, reviewer):
        meme = meme_olustur(yonetici)
        kaynak = annotation_olustur(meme, annotator, durum_kodu="onaylandi", icerik=gecerli_icerik())
        session.add(GoldRecord(
            meme_id=meme.id, icerik=gecerli_icerik(), kaynak_annotationlar=[kaynak.id],
            reviewer_id=reviewer.id, sema_versiyonu="1.0", etiket_listesi_versiyonu="v1",
        ))
        session.commit()
        return meme

    return olustur


def sorgu_ekle(client, kisi, dogru_memeler, metin="Patron cuma 17:55'e toplantı koydu", mod="durum"):
    return client.post(
        "/api/v1/test-queries",
        json={"metin": metin, "mod": mod, "dogru_memeler": dogru_memeler},
        headers=basliklar(kisi),
    )


def test_katki_vermeyen_kisi_sorgu_yazar(client, session, ali, ayse, can, gold_meme):
    meme = gold_meme(ali, ayse)
    yanit = sorgu_ekle(client, can, [meme.id])
    assert yanit.status_code == 201
    sorgu = yanit.json()
    assert (sorgu["metin"], sorgu["mod"], sorgu["dogru_memeler"]) == ("Patron cuma 17:55'e toplantı koydu", "durum", [meme.id])
    assert sorgu["yazan"] == {"id": can.id, "gorunen_ad": "Can"}
    assert sorgu["zaman"].endswith("Z")
    kayit = session.exec(select(AuditEntry).where(AuditEntry.kayit_tipi == "test_sorgusu")).one()
    assert (kayit.kayit_id, kayit.islem) == (sorgu["id"], "olusturma")


def test_sizinti_kurali_annotator_ve_reviewer_icin_gecerli(client, ali, ayse, can, gold_meme):
    alinin = gold_meme(ali, ayse)
    serbest = gold_meme(ayse, ali)
    for yazar in (ali, ayse):
        yanit = sorgu_ekle(client, yazar, [alinin.id, serbest.id])
        assert yanit.status_code == 422
        hata = yanit.json()["hata"]
        assert hata["kod"] == "SIZINTI"
        assert hata["detay"] == {"ihlal_eden_memeler": [alinin.id, serbest.id]}
    assert sorgu_ekle(client, can, [alinin.id, serbest.id]).status_code == 201


def test_gold_kaydi_olmayan_memede_annotatorlar_katkici_sayilir(client, yonetici, ali, ayse, can, meme_olustur, annotation_olustur):
    meme = meme_olustur(yonetici)
    annotation_olustur(meme, ali, durum_kodu="gonderildi")
    annotation_olustur(meme, ayse, durum_kodu="atlandi")
    annotation_olustur(meme, can, durum_kodu="gonderildi", kalibrasyon=True)
    assert sorgu_ekle(client, ali, [meme.id]).json()["hata"]["kod"] == "SIZINTI"
    # Atlayan ve yalnızca kalibrasyonda etiketleyen kişi gold kaydına katkı vermez.
    assert sorgu_ekle(client, ayse, [meme.id]).status_code == 201
    assert sorgu_ekle(client, can, [meme.id]).status_code == 201


def test_sorgu_dogrulamasi(client, can, ali, ayse, gold_meme):
    meme = gold_meme(ali, ayse)
    for veri, beklenen in [
        ({"metin": "  kısa "}, ("metin", "min_karakter")),
        ({"mod": "sohbet"}, ("mod", "gecersiz_deger")),
        ({"dogru_memeler": []}, ("dogru_memeler", "min_adet")),
        ({"dogru_memeler": [meme.id, "m0404"]}, ("dogru_memeler[1]", "gecersiz_deger")),
        ({"dogru_memeler": [meme.id, meme.id]}, ("dogru_memeler[1]", "tekrar")),
    ]:
        istek = {"metin": "Sınav sonuçları açıklandı", "mod": "durum", "dogru_memeler": [meme.id], **veri}
        yanit = client.post("/api/v1/test-queries", json=istek, headers=basliklar(can))
        assert yanit.status_code == 422, veri
        assert yanit.json()["hata"]["kod"] == "DOGRULAMA"
        assert (yanit.json()["hata"]["alanlar"][0]["alan"], yanit.json()["hata"]["alanlar"][0]["kural"]) == beklenen


def test_sorgular_filtrelenir(client, ali, ayse, can, yonetici, gold_meme):
    meme = gold_meme(ali, ayse)
    durum = sorgu_ekle(client, can, [meme.id]).json()
    tarif = sorgu_ekle(client, can, [meme.id], metin="Kaşlarını kaldırmış adam", mod="tarif").json()
    baskasi = sorgu_ekle(client, yonetici, [meme.id]).json()

    def idler(**parametreler):
        return {s["id"] for s in client.get("/api/v1/test-queries", params=parametreler, headers=basliklar(ali)).json()}

    assert idler() == {durum["id"], tarif["id"], baskasi["id"]}
    assert idler(yazan_id=can.id) == {durum["id"], tarif["id"]}
    assert idler(yazan_id=can.id, mod="tarif") == {tarif["id"]}


def test_sorguyu_yalnizca_yazan_ve_admin_duzenler(client, session, yonetici, ali, ayse, can, gold_meme):
    meme = gold_meme(ali, ayse)
    sorgu = sorgu_ekle(client, can, [meme.id]).json()
    url = f"/api/v1/test-queries/{sorgu['id']}"

    assert client.patch(url, json={"mod": "tarif"}, headers=basliklar(ali)).status_code == 403
    yanit = client.patch(url, json={"metin": "Patron cumartesi de çağırdı"}, headers=basliklar(can))
    assert yanit.status_code == 200
    assert yanit.json()["metin"] == "Patron cumartesi de çağırdı"
    assert client.patch(url, json={"mod": "tarif"}, headers=basliklar(yonetici)).json()["mod"] == "tarif"
    assert client.patch(url, json={"metin": "kısa"}, headers=basliklar(can)).status_code == 422
    assert client.patch("/api/v1/test-queries/yok", json={"mod": "tarif"}, headers=basliklar(can)).status_code == 404

    alanlar = [k.alan for k in session.exec(select(AuditEntry).where(AuditEntry.islem == "guncelleme").order_by(AuditEntry.id)).all()]
    assert alanlar == ["metin", "mod"]


def test_admin_duzenlerken_sizinti_kurali_yazana_bakar(client, yonetici, ali, ayse, can, gold_meme):
    serbest = gold_meme(ali, ayse)
    canin = gold_meme(can, ayse)
    sorgu = sorgu_ekle(client, can, [serbest.id]).json()
    yanit = client.patch(f"/api/v1/test-queries/{sorgu['id']}", json={"dogru_memeler": [serbest.id, canin.id]}, headers=basliklar(yonetici))
    assert yanit.status_code == 422
    assert yanit.json()["hata"]["detay"] == {"ihlal_eden_memeler": [canin.id]}


def test_sorgu_silinir(client, session, yonetici, ali, ayse, can, gold_meme):
    meme = gold_meme(ali, ayse)
    birinci = sorgu_ekle(client, can, [meme.id]).json()
    ikinci = sorgu_ekle(client, can, [meme.id]).json()

    assert client.delete(f"/api/v1/test-queries/{birinci['id']}", headers=basliklar(ali)).status_code == 403
    yanit = client.delete(f"/api/v1/test-queries/{birinci['id']}", headers=basliklar(can))
    assert (yanit.status_code, yanit.content) == (204, b"")
    assert client.delete(f"/api/v1/test-queries/{ikinci['id']}", headers=basliklar(yonetici)).status_code == 204
    assert client.delete(f"/api/v1/test-queries/{ikinci['id']}", headers=basliklar(yonetici)).status_code == 404
    assert client.get("/api/v1/test-queries", headers=basliklar(can)).json() == []

    silme = session.exec(select(AuditEntry).where(AuditEntry.islem == "silme").order_by(AuditEntry.id)).all()
    assert [k.kayit_id for k in silme] == [birinci["id"], ikinci["id"]]
    assert silme[0].eski_deger["yazan_id"] == can.id
