import csv
import hashlib

import pytest
import yaml
from sqlmodel import select

from app.import_ai_drafts import CSV_AYRACI, aktar, kartlari_hazirla, kartlari_oku, main, rapor
from app.models import AiDraft, Meme
from tests.yardimci import basliklar, gecerli_icerik, png_olustur

KAYIT_BILGISI = {
    "annotator": ["llm-auto"],
    "reviewer": None,
    "sema_versiyonu": "1.0",
    "etiket_listesi_versiyonu": "1.0",
    "ocr_metin": None,
    "genisletilmis_durumlar": None,
    "gecmis_sorgular": None,
}


def kart(kimlik, gorsel, **degisiklikler):
    return {"id": kimlik, "gorsel": gorsel, **gecerli_icerik(), **KAYIT_BILGISI, **degisiklikler}


def yaml_yaz(yol, kartlar):
    yol.write_text(yaml.safe_dump(kartlar, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return yol


def csv_yaz(yol, kartlar):
    with yol.open("w", encoding="utf-8", newline="") as dosya:
        yazici = csv.DictWriter(dosya, fieldnames=list(kartlar[0]))
        yazici.writeheader()
        for kart_ in kartlar:
            yazici.writerow({
                alan: CSV_AYRACI.join(deger) if isinstance(deger, list) else ("" if deger is None else deger)
                for alan, deger in kart_.items()
            })
    return yol


@pytest.fixture()
def yonetici(kullanici_olustur):
    return kullanici_olustur("yonetici", admin=True)


@pytest.fixture()
def gondericiler(client, yonetici):
    def json_gonder(govde):
        yanit = client.post("/api/v1/memes/ai-drafts", json=govde, headers=basliklar(yonetici))
        return yanit.status_code, yanit.json()

    def dosya_gonder(dosyalar):
        yanit = client.post("/api/v1/memes/bulk", files=dosyalar, headers=basliklar(yonetici))
        return yanit.status_code, yanit.json()

    return json_gonder, dosya_gonder


def test_yaml_ve_csv_ayni_karti_uretir(tmp_path):
    kartlar = [kart("sevko-el-uzatma", "memes/sevko-el-uzatma.png", uyari=[], ornek_durumlar=["bir", "iki, virgüllü", "üç"])]
    yamldan = kartlari_oku(yaml_yaz(tmp_path / "kartlar.yaml", kartlar))
    csvden = kartlari_oku(csv_yaz(tmp_path / "kartlar.csv", kartlar))
    assert yamldan == csvden == kartlar


def test_gorseller_kart_dosyasina_ya_da_verilen_klasore_gore_bulunur(tmp_path):
    (tmp_path / "memes").mkdir()
    (tmp_path / "memes" / "a.png").write_bytes(png_olustur(1))
    (tmp_path / "duz").mkdir()
    (tmp_path / "duz" / "b.png").write_bytes(png_olustur(2))
    (tmp_path / "duz" / "kopya.png").write_bytes(png_olustur(2))  # b.png ile aynı baytlar
    dosya = yaml_yaz(tmp_path / "kartlar.yaml", [kart("a", "memes/a.png"), kart("b", "memes/b.png"), kart("yok", "memes/yok.png")])

    kayitlar = kartlari_hazirla([dosya])
    assert [(k.kimlik, k.sorun is None) for k in kayitlar] == [("a", True), ("b", False), ("yok", False)]
    assert kayitlar[0].sha256 == hashlib.sha256(png_olustur(1)).hexdigest()
    assert kayitlar[2].sorun.startswith("görsel bulunamadı")

    # --gorseller verilince yol önce olduğu gibi, sonra yalnızca dosya adıyla aranır.
    ikinci = yaml_yaz(tmp_path / "ikinci.yaml", [kart("b", "memes/b.png"), kart("kopya", "memes/kopya.png")])
    kayitlar = kartlari_hazirla([ikinci], gorsel_klasoru=tmp_path / "duz")
    assert kayitlar[0].sorun is None
    assert kayitlar[1].sorun == "aynı görsel 'b' kartında da var"


def test_kartlar_eslesen_memeye_baglanir_eslesmeyenler_yeni_meme_olur(
    client, session, tmp_path, yonetici, meme_olustur, gondericiler
):
    mevcut = meme_olustur(yonetici)  # png_olustur(1) ile aynı baytlar
    (tmp_path / "memes").mkdir()
    (tmp_path / "memes" / "mevcut.png").write_bytes(png_olustur(1))
    (tmp_path / "memes" / "yeni.png").write_bytes(png_olustur(99))
    dosya = yaml_yaz(tmp_path / "kartlar.yaml", [
        kart("mevcut", "memes/mevcut.png", ornek_durumlar=[f"durum {sira}" for sira in range(7)]),
        kart("yeni", "memes/yeni.png", duygu=["bilinmeyen_duygu"]),
    ])
    kayitlar = kartlari_hazirla([dosya])
    sonuc = aktar(kayitlar, *gondericiler, bekle=lambda _: None, yaz=lambda _: None)

    eslesmeler = {sonuc["sha_kart"][e["sha256"]].kimlik: e for e in sonuc["eklenen"]}
    assert eslesmeler["mevcut"]["meme_id"] == mevcut.id
    assert [(i["alan"], i["kural"]) for i in eslesmeler["mevcut"]["ihlaller"]] == [("ornek_durumlar", "max_adet")]
    assert [(i["alan"], i["kural"]) for i in eslesmeler["yeni"]["ihlaller"]] == [("duygu[0]", "gecersiz_etiket")]
    assert [meme["id"] for meme in sonuc["yeni_memeler"]] == [eslesmeler["yeni"]["meme_id"]] == ["m0002"]
    assert session.get(AiDraft, "m0002").kart["id"] == "yeni"

    satirlar = []
    rapor(kayitlar, sonuc, yaz=satirlar.append)
    metin = "\n".join(satirlar)
    assert "yeni → m0002 (yeni meme), 1 ihlal" in metin
    assert "duygu[0]: Bu etiket listede yok. (gecersiz_etiket)" in metin
    assert "PNG'ye dönüştürülmüşse" in metin

    # Tekrar çalıştırmak taslakları değiştirmez.
    tekrar = aktar(kayitlar, *gondericiler, bekle=lambda _: None, yaz=lambda _: None)
    assert tekrar["eklenen"] == [] and {red["sebep"] for red in tekrar["reddedilen"]} == {"zaten_var"}


def test_yalniz_eslesenler_yeni_meme_olusturmaz(client, session, tmp_path, yonetici, gondericiler):
    (tmp_path / "yeni.png").write_bytes(png_olustur(7))
    dosya = yaml_yaz(tmp_path / "kartlar.yaml", [kart("yeni", "yeni.png")])
    sonuc = aktar(kartlari_hazirla([dosya]), *gondericiler, yalniz_eslesenler=True, bekle=lambda _: None, yaz=lambda _: None)
    assert [k.kimlik for k in sonuc["atlanan"]] == ["yeni"]
    assert session.exec(select(Meme)).all() == []


def test_gecici_hatada_kartlar_tekrar_gonderilir(tmp_path):
    (tmp_path / "a.png").write_bytes(png_olustur(1))
    kayitlar = kartlari_hazirla([yaml_yaz(tmp_path / "kartlar.yaml", [kart("a", "a.png")])])
    yanitlar = iter([(503, {"hata": {"mesaj": "uyuyor"}}), (200, {"eklenen": [], "reddedilen": []})])
    beklemeler = []
    sonuc = aktar(kayitlar, lambda _: next(yanitlar), None, bekle=beklemeler.append, yaz=lambda _: None)
    assert beklemeler == [2] and sonuc["basarisiz"] == []


def test_deneme_modu_yerel_ihlalleri_raporlar(tmp_path, capsys):
    (tmp_path / "memes").mkdir()
    (tmp_path / "memes" / "a.png").write_bytes(png_olustur(1))
    dosya = yaml_yaz(tmp_path / "kartlar.yaml", [kart("a", "memes/a.png", notlar="n" * 537), kart("b", "memes/b.png")])
    assert main(["--deneme", str(dosya)]) == 0
    cikti = capsys.readouterr().out
    assert "2 kart okundu." in cikti
    assert "a → a.png, 1 ihlal" in cikti and "notlar: En fazla 500 karakter olabilir. (max_karakter)" in cikti
    assert "b → atlandı: görsel bulunamadı" in cikti
