import zipfile

import pytest
from sqlmodel import select

from app.import_memes import Gorsel, gorselleri_topla, main, parcalara_bol, yukle
from app.models import Meme
from tests.test_memes import JPEG, WEBP
from tests.yardimci import basliklar, png_olustur


@pytest.fixture()
def kaynak_klasoru(tmp_path):
    with zipfile.ZipFile(tmp_path / "1-sohbet.zip", "w") as arsiv:
        arsiv.writestr("_chat.txt", "mesajlar")
        arsiv.writestr("IMG-0001.png", png_olustur(1))
        arsiv.writestr("IMG-0002.PNG", png_olustur(2))
        arsiv.writestr("__MACOSX/._IMG-0001.png", b"apple double")
        arsiv.writestr("medya/IMG-0003.jpg", JPEG)
        arsiv.writestr("ses.opus", b"ses")
    with zipfile.ZipFile(tmp_path / "2-sohbet.zip", "w") as arsiv:
        arsiv.writestr("ayni-gorsel-baska-ad.png", png_olustur(1))
        arsiv.writestr("STK-0004.webp", WEBP)
    (tmp_path / "z-tek.png").write_bytes(png_olustur(5))
    (tmp_path / "notlar.txt").write_text("görsel değil", encoding="utf-8")
    return tmp_path


def test_gorseller_toplanir_ve_kopyalar_ayiklanir(kaynak_klasoru):
    gorseller, tekrarlar = gorselleri_topla([kaynak_klasoru])
    assert [gorsel.ad for gorsel in gorseller] == [
        "1-sohbet/IMG-0001.png",
        "1-sohbet/IMG-0002.PNG",
        "1-sohbet/IMG-0003.jpg",
        "2-sohbet/STK-0004.webp",
        "z-tek.png",
    ]
    assert tekrarlar == [("2-sohbet/ayni-gorsel-baska-ad.png", "1-sohbet/IMG-0001.png")]


def test_parcalar_bayt_ve_adet_sinirina_uyar():
    gorseller = [Gorsel(f"{sira}.png", b"x" * boyut, str(sira)) for sira, boyut in enumerate([400, 400, 300, 900, 50, 50, 50])]
    parcalar = parcalara_bol(gorseller, azami_bayt=1000, azami_adet=2)
    assert [[gorsel.ad for gorsel in parca] for parca in parcalar] == [
        ["0.png", "1.png"], ["2.png"], ["3.png", "4.png"], ["5.png", "6.png"],
    ]
    # Tek başına sınırı aşan görsel kendi parçasında gider.
    assert len(parcalara_bol([Gorsel("buyuk.png", b"x" * 5000, "b")], azami_bayt=1000)) == 1


def test_yukleme_api_uzerinden_yapilir_ve_tekrar_calistirilabilir(client, session, kullanici_olustur, kaynak_klasoru):
    yonetici = kullanici_olustur("yonetici", admin=True)

    def gonder(dosyalar):
        yanit = client.post("/api/v1/memes/bulk", files=dosyalar, headers=basliklar(yonetici))
        return yanit.status_code, yanit.json()

    gorseller, _ = gorselleri_topla([kaynak_klasoru])
    parcalar = parcalara_bol(gorseller, azami_adet=2)
    ozet = yukle(parcalar, gonder, yaz=lambda _: None)
    assert [meme["id"] for meme in ozet["yuklenen"]] == ["m0001", "m0002", "m0003", "m0004", "m0005"]
    assert ozet["reddedilen"] == [] and ozet["basarisiz"] == []
    assert len(session.exec(select(Meme)).all()) == 5

    ikinci = yukle(parcalar, gonder, yaz=lambda _: None)
    assert ikinci["yuklenen"] == []
    assert [red["sebep"] for red in ikinci["reddedilen"]] == ["kopya"] * 5


def test_gecici_hatalarda_tekrar_dener_kalici_hatada_vazgecer():
    parcalar = [[Gorsel("a.png", b"a", "a")], [Gorsel("b.png", b"b", "b")]]
    yanitlar = iter([
        (503, {"hata": {"mesaj": "Veritabanına şu an ulaşılamıyor."}}),
        (200, {"yuklenen": [{"id": "m0001"}], "reddedilen": []}),
        (403, {"hata": {"mesaj": "Bu işlem için admin yetkisi gerekiyor."}}),
    ])
    beklemeler = []
    ozet = yukle(parcalar, lambda _: next(yanitlar), bekle=beklemeler.append, yaz=lambda _: None)
    assert beklemeler == [2]
    assert ozet["yuklenen"] == [{"id": "m0001"}]
    assert ozet["basarisiz"] == [{"dosya_adi": "b.png", "durum": 403, "mesaj": "Bu işlem için admin yetkisi gerekiyor."}]


def test_deneme_modu_hicbir_sey_gondermez(kaynak_klasoru, capsys):
    assert main(["--deneme", str(kaynak_klasoru)]) == 0
    cikti = capsys.readouterr().out
    assert "6 görsel bulundu, 1 tanesi kaynaklarda tekrar ediyor" in cikti
    assert "5 farklı görsel" in cikti and "1 parçada" in cikti
