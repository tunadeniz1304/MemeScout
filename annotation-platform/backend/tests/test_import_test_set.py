import json

import pytest
from sqlmodel import select

from app.import_test_set import isaretle, main, meme_haritasi, sorgulari_ekle
from app.models import Meme, TestQuery
from tests.yardimci import basliklar, png_olustur


@pytest.fixture()
def yonetici(kullanici_olustur):
    return kullanici_olustur("yonetici", admin=True)


@pytest.fixture()
def istek(client, yonetici):
    # Betik canlıda requests ile konuşur; testte aynı çağrılar uygulamaya gider.
    return lambda yontem, yol, **ek: client.request(yontem, f"/api/v1{yol}", headers=basliklar(yonetici), **ek)


@pytest.fixture()
def klasor(tmp_path, yonetici, meme_olustur):
    """final/m1..m3 platformdaki m0001..m0003'ün görselleri; final/m9.png platformda yok."""
    (tmp_path / "final").mkdir()
    for numara in (1, 2, 3):
        meme_olustur(yonetici)
        (tmp_path / "final" / f"m{numara}.png").write_bytes(png_olustur(numara))
    (tmp_path / "final" / "m9.png").write_bytes(png_olustur(9))
    return tmp_path


def test_setine_alma_tekrar_calistirilabilir(session, istek, klasor):
    yollar = ["final/m1.png", "final/m2.png", "final/m9.png"]
    sonuc = isaretle(istek, klasor, yollar, meme_haritasi(istek))
    assert sonuc["isaretlenen"] == ["m0001", "m0002"]
    assert sonuc["bulunamayan"] == ["final/m9.png"]
    session.expire_all()
    assert sorted(meme.id for meme in session.exec(select(Meme).where(Meme.test_seti == True)).all()) == ["m0001", "m0002"]  # noqa: E712
    tekrar = isaretle(istek, klasor, yollar, meme_haritasi(istek))
    assert (tekrar["isaretlenen"], tekrar["zaten"]) == ([], ["m0001", "m0002"])


def test_sorgular_yazari_adina_eklenir_ve_tekrarlanmaz(client, session, yonetici, kullanici_olustur, istek, klasor):
    esma = kullanici_olustur("esmacalis")
    veri = {"yazan": "esmacalis", "sorgular": [
        {"gorsel": "final/m1.png", "mod": "durum", "metin": "Arkadaşım yine son dakika iptal etti"},
        {"gorsel": "final/m2.png", "metin": "Sınavdan bir gece önce panik"},
        {"gorsel": "final/m9.png", "metin": "Platformda olmayan bir mem"},
    ]}
    sonuc = sorgulari_ekle(istek, klasor, veri, meme_haritasi(istek))
    assert (sonuc["eklenen"], sonuc["bulunamayan"], sonuc["basarisiz"]) == (2, ["final/m9.png"], [])
    sorgular = session.exec(select(TestQuery).order_by(TestQuery.metin)).all()
    assert [(sorgu.yazan_id, sorgu.dogru_memeler) for sorgu in sorgular] == [(esma.id, ["m0001"]), (esma.id, ["m0002"])]
    assert sorgulari_ekle(istek, klasor, veri, meme_haritasi(istek))["atlanan"] == 2
    # Cümleleri yazan kişi o meme'leri etiketleyemez.
    yanit = client.post("/api/v1/assignments", json={"meme_ids": ["m0001"], "annotator_id": esma.id}, headers=basliklar(yonetici))
    assert yanit.json()["hata"]["kod"] == "SIZINTI"


def test_deneme_eksik_gorseli_bildirir(tmp_path, klasor, capsys):
    dosya = tmp_path / "sorgular.json"
    dosya.write_text(json.dumps({"yazan": "esmacalis", "sorgular": [{"gorsel": "final/m1.png", "metin": "Geç kalan arkadaş"}]}), encoding="utf-8")
    assert main(["--deneme", "--gorseller", str(klasor), "--sorgular", str(dosya)]) == 0
    dosya.write_text(json.dumps({"yazan": "esmacalis", "sorgular": [{"gorsel": "final/yok.png", "metin": "Geç kalan arkadaş"}]}), encoding="utf-8")
    assert main(["--deneme", "--gorseller", str(klasor), "--sorgular", str(dosya)]) == 1
    assert "Görsel bulunamadı: final/yok.png" in capsys.readouterr().out


def test_api_hatasi_nedeniyle_durur():
    class Yanit:
        status_code = 500

        def json(self):
            return {"hata": {"kod": "SUNUCU_HATASI", "mesaj": "Sunucuda beklenmeyen bir hata oluştu."}}

    with pytest.raises(SystemExit, match=r"Meme listesi okunamadı \(500\): Sunucuda beklenmeyen bir hata oluştu\."):
        meme_haritasi(lambda yontem, yol, **ek: Yanit())
