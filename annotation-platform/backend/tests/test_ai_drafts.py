import json

import pytest
from sqlmodel import select

from app.ai_taslak import karttan_icerik
from app.models import AiDraft, AuditEntry, GoldRecord, Meme
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


def kart(**degisiklikler) -> dict:
    """architecture.md §3 biçiminde, kayıt bilgisi alanlarıyla bir LLM kartı."""
    return {
        "id": "sevko-el-uzatma",
        "gorsel": "memes/sevko-el-uzatma.png",
        **gecerli_icerik(),
        "annotator": ["llm-auto"],
        "reviewer": None,
        "sema_versiyonu": "1.0",
        "etiket_listesi_versiyonu": "1.0",
        "ocr_metin": None,
        "genisletilmis_durumlar": None,
        "gecmis_sorgular": None,
        **degisiklikler,
    }


def ice_aktar(client, kisi, *taslaklar):
    return client.post("/api/v1/memes/ai-drafts", json={"taslaklar": list(taslaklar)}, headers=basliklar(kisi))


def taslak(meme, **ek):
    return {"sha256": meme.sha256, "kaynak": "llm-auto", "kart": kart(), **ek}


def kurallar(hatalar):
    return {(hata["alan"], hata["kural"]) for hata in hatalar}


# ------------------------------------------------------------------ POST /memes/ai-drafts

def test_kart_sha256_ile_memeye_baglanir_ve_ihlaller_raporlanir(client, session, yonetici, meme_olustur):
    meme = meme_olustur(yonetici)
    uzun_kart = kart(
        vlm_aciklama="v" * 350,
        ornek_durumlar=[f"örnek durum {sira}" for sira in range(7)],
        notlar="n" * 537,
        duygu=["umursamazlik", "ustunluk_kibir", "bilinmeyen_duygu"],
    )
    yanit = ice_aktar(client, yonetici, {"sha256": meme.sha256, "kaynak": "llm-auto", "kart": uzun_kart})
    assert yanit.status_code == 200
    sonuc = yanit.json()
    assert sonuc["reddedilen"] == []
    eklenen = sonuc["eklenen"][0]
    assert (eklenen["sha256"], eklenen["meme_id"], eklenen["vlm_taslak_dolduruldu"]) == (meme.sha256, meme.id, True)
    assert kurallar(eklenen["ihlaller"]) == {
        ("vlm_aciklama", "max_karakter"),
        ("ornek_durumlar", "max_adet"),
        ("notlar", "max_karakter"),
        ("duygu[2]", "gecersiz_etiket"),
    }

    kayit = session.get(AiDraft, meme.id)
    assert kayit.kart == uzun_kart  # ham kart değiştirilmeden saklanır
    assert (kayit.kaynak, kayit.yukleyen_id) == ("llm-auto", yonetici.id)
    assert kayit.icerik["ornek_durumlar"] == uzun_kart["ornek_durumlar"]
    session.refresh(meme)
    assert meme.vlm_taslak == "v" * 350

    detay = client.get(f"/api/v1/memes/{meme.id}", headers=basliklar(yonetici)).json()
    assert (detay["ai_taslagi_var"], detay["vlm_taslak"]) == (True, "v" * 350)
    alanlar = {k.alan for k in session.exec(select(AuditEntry).where(AuditEntry.kayit_id == meme.id)).all()}
    assert alanlar == {"ai_taslagi", "vlm_taslak"}


def test_dolu_vlm_taslagi_degismez(client, session, yonetici, meme_olustur):
    meme = meme_olustur(yonetici)
    meme.vlm_taslak = "VLM'in kendi tarifi"
    session.add(meme)
    session.commit()
    eklenen = ice_aktar(client, yonetici, taslak(meme)).json()["eklenen"][0]
    assert eklenen["vlm_taslak_dolduruldu"] is False
    session.refresh(meme)
    assert meme.vlm_taslak == "VLM'in kendi tarifi"


def test_eklenemeyen_kartlar_sebebiyle_reddedilir(
    client, session, yonetici, ali, ayse, meme_olustur, annotation_olustur
):
    atanmis = meme_olustur(yonetici)
    annotation_olustur(atanmis, ali)
    atlanmis = meme_olustur(yonetici)
    annotation_olustur(atlanmis, ali, durum_kodu="atlandi")
    goldlu = meme_olustur(yonetici)
    session.add(GoldRecord(meme_id=goldlu.id, icerik=gecerli_icerik(), sema_versiyonu="1.0", etiket_listesi_versiyonu="v1"))
    session.commit()
    kalibrasyonda = meme_olustur(yonetici)
    annotation_olustur(kalibrasyonda, ayse, kalibrasyon=True)
    cift = meme_olustur(yonetici)
    annotation_olustur(cift, ali, cift_etiket=True)
    baslamis = meme_olustur(yonetici)
    annotation_olustur(baslamis, ali, durum_kodu="devam_ediyor")
    onceden = meme_olustur(yonetici)
    ice_aktar(client, yonetici, taslak(onceden))

    yanit = ice_aktar(
        client, yonetici,
        taslak(atanmis), taslak(atlanmis), taslak(atanmis), {"sha256": "0" * 64, "kart": kart()},
        taslak(goldlu), taslak(kalibrasyonda), taslak(cift), taslak(baslamis), taslak(onceden),
    )
    sonuc = yanit.json()
    assert [e["meme_id"] for e in sonuc["eklenen"]] == [atanmis.id, atlanmis.id]
    assert [(r["meme_id"], r["sebep"]) for r in sonuc["reddedilen"]] == [
        (atanmis.id, "tekrar"),
        (None, "meme_yok"),
        (goldlu.id, "gold_var"),
        (kalibrasyonda.id, "kalibrasyonda"),
        (cift.id, "cift_etiketli"),
        (baslamis.id, "etiketleme_baslamis"),
        (onceden.id, "zaten_var"),
    ]
    assert len(session.exec(select(AiDraft)).all()) == 3


def test_ai_taslagi_admin_ister_ve_istek_dogrulanir(client, yonetici, ali, meme_olustur):
    meme = meme_olustur(yonetici)
    assert ice_aktar(client, ali, taslak(meme)).status_code == 403
    assert ice_aktar(client, yonetici, {"sha256": "kisa", "kart": kart()}).status_code == 422
    assert ice_aktar(client, yonetici, {"sha256": meme.sha256}).status_code == 422
    assert client.post("/api/v1/memes/ai-drafts", json={"taslaklar": []}, headers=basliklar(yonetici)).status_code == 422


def test_kart_icerigi_tur_olarak_duzeltilir():
    icerik = karttan_icerik({"ad": 2023, "ornek_durumlar": "tek durum", "duygu": ["suphe", None, 7], "uyari": []})
    assert (icerik["ad"], icerik["ornek_durumlar"], icerik["duygu"], icerik["uyari"]) == ("2023", ["tek durum"], ["suphe", "7"], [])
    bos = karttan_icerik({})
    assert (bos["uyari"], bos["niyet"], bos["durum"]) == (None, [], None)


# ------------------------------------------------------------------ atama kuralları

def test_ai_taslakli_meme_kalibrasyona_ve_cift_etiketlemeye_alinamaz(client, yonetici, ali, ayse, meme_olustur):
    meme = meme_olustur(yonetici)
    ice_aktar(client, yonetici, taslak(meme))

    def ata(kisi, **ek):
        return client.post("/api/v1/assignments", json={"meme_ids": [meme.id], "annotator_id": kisi.id, **ek}, headers=basliklar(yonetici))

    for ek in ({"kalibrasyon": True}, {"cift_etiket": True}):
        yanit = ata(ali, **ek)
        assert (yanit.status_code, yanit.json()["hata"]["kod"]) == (409, "AI_TASLAKLI_MEME")
        assert yanit.json()["hata"]["detay"] == {"meme_ids": [meme.id]}
    assert ata(ali).status_code == 201
    assert ata(ayse).json()["hata"]["kod"] == "AI_TASLAKLI_MEME"  # ikinci kişi meme'i çift etiketli yapardı


def test_otomatik_dagitim_ai_taslakli_memeleri_cift_etiketlemez(client, yonetici, ali, ayse, meme_olustur):
    memeler = [meme_olustur(yonetici) for _ in range(4)]
    ice_aktar(client, yonetici, *[taslak(meme) for meme in memeler[:2]])
    plan = client.post(
        "/api/v1/assignments/auto",
        json={"annotator_ids": [ali.id, ayse.id], "cift_etiket_orani": 1},
        headers=basliklar(yonetici),
    ).json()
    sayilar = {atama["meme_id"]: len(atama["annotator_ids"]) for atama in plan["atamalar"]}
    assert sayilar == {memeler[0].id: 1, memeler[1].id: 1, memeler[2].id: 2, memeler[3].id: 2}


# ------------------------------------------------------------------ dışa aktarım

def test_ai_taslaklari_disa_aktarilir(client, yonetici, meme_olustur):
    meme = meme_olustur(yonetici)
    ice_aktar(client, yonetici, taslak(meme))
    yanit = client.get("/api/v1/export/ai_drafts.jsonl", headers=basliklar(yonetici))
    assert yanit.status_code == 200
    satir = json.loads(yanit.text.splitlines()[0])
    assert (satir["id"], satir["gorsel"], satir["kaynak"]) == (meme.id, meme.gorsel_yolu, "llm-auto")
    assert satir["kart"] == kart()
    assert satir["icerik"]["ad"] == "Hayırdır inşallah"
    assert satir["olusturma_zamani"].endswith("Z")
    liste = client.get("/api/v1/memes", headers=basliklar(yonetici)).json()
    assert liste["ogeler"][0]["ai_taslagi_var"] is True
    # Kart yüklemek meme oluşturmaz; eşleşmeyen kart yalnızca reddedilir.
    assert liste["toplam"] == 1


def test_meme_modeli_vlm_taslagini_tasir(session, yonetici, meme_olustur):
    meme = meme_olustur(yonetici)
    assert session.exec(select(Meme.vlm_taslak).where(Meme.id == meme.id)).one() is None


# ------------------------------------------------------------------ etiketlemeye başlarken doldurma

def baslat(client, kisi, annotation_id):
    yanit = client.post(f"/api/v1/annotations/{annotation_id}/start", headers=basliklar(kisi))
    assert yanit.status_code == 200
    return yanit.json()


def test_form_ai_taslagiyla_dolu_baslar_ve_duzeltilip_incelemeye_gider(client, yonetici, ali, ayse, meme_olustur, annotation_olustur):
    meme = meme_olustur(yonetici)
    ham = kart(ornek_durumlar=[f"örnek durum {sira}" for sira in range(7)])
    ice_aktar(client, yonetici, {"sha256": meme.sha256, "kaynak": "llm-auto", "kart": ham})
    annotation = annotation_olustur(meme, ali)

    detay = baslat(client, ali, annotation.id)
    assert detay["on_doldurma"] == "ai_taslagi"
    assert detay["icerik"] == karttan_icerik(ham)
    gecmis = client.get(f"/api/v1/annotations/{annotation.id}/versions", headers=basliklar(ali)).json()
    assert [(surum["surum"], surum["icerik"]["ornek_durumlar"][-1]) for surum in gecmis] == [(1, "örnek durum 6")]

    # Taslak kurala uymuyor; annotator düzeltmeden gönderemez.
    gonderim = client.post(f"/api/v1/annotations/{annotation.id}/submit", json={"surum": 1}, headers=basliklar(ali))
    assert gonderim.status_code == 422
    assert ("ornek_durumlar", "max_adet") in kurallar(gonderim.json()["hata"]["alanlar"])

    surum = client.patch(
        f"/api/v1/annotations/{annotation.id}/draft",
        json={"surum": 1, "icerik": {"ornek_durumlar": ham["ornek_durumlar"][:4]}, "tanidiklik": 4},
        headers=basliklar(ali),
    ).json()["surum"]
    sonuc = client.post(f"/api/v1/annotations/{annotation.id}/submit", json={"surum": surum}, headers=basliklar(ali)).json()
    assert sonuc["durum_kodu"] == "gonderildi"  # taslak gold olmaz; ikinci bakışa gider
    kuyruk = client.get("/api/v1/reviews", headers=basliklar(ayse)).json()
    assert [(oge["meme_id"], oge["cift_etiket"]) for oge in kuyruk] == [(meme.id, False)]
    assert client.get(f"/api/v1/memes/{meme.id}/gold", headers=basliklar(ayse)).status_code == 404


def test_vlm_taslagi_yalnizca_gorsel_tarifi_doldurur(client, session, yonetici, ali, ayse, meme_olustur, annotation_olustur):
    meme = meme_olustur(yonetici)
    meme.vlm_taslak = "Şüpheyle bakan bir adam."
    session.add(meme)
    session.commit()
    cift = annotation_olustur(meme, ali, cift_etiket=True)
    kalibrasyon = annotation_olustur(meme, ayse, kalibrasyon=True)

    for kisi, annotation in ((ali, cift), (ayse, kalibrasyon)):
        detay = baslat(client, kisi, annotation.id)
        assert detay["on_doldurma"] == "vlm_taslagi"
        assert detay["icerik"]["vlm_aciklama"] == "Şüpheyle bakan bir adam."
        assert detay["icerik"]["durum"] is None and detay["icerik"]["duygu"] == []


def test_taslak_yoksa_form_bos_baslar_ve_tekrar_baslatmak_doldurmaz(client, session, yonetici, ali, meme_olustur, annotation_olustur):
    meme = meme_olustur(yonetici)
    annotation = annotation_olustur(meme, ali)
    detay = baslat(client, ali, annotation.id)
    assert (detay["on_doldurma"], detay["icerik"]["ad"]) == (None, None)

    meme.vlm_taslak = "Sonradan gelen tarif"
    session.add(meme)
    session.commit()
    assert baslat(client, ali, annotation.id)["icerik"]["vlm_aciklama"] is None
