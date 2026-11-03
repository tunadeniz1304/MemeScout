import asyncio
import json

from sqlalchemy.exc import IntegrityError, OperationalError
from starlette.requests import Request

from app.errors import alan_yolu, veritabani_hatasi_handler


def test_eksik_alan_sozlesme_bicimindeki_hatayla_doner(client):
    yanit = client.post("/api/v1/auth/login", json={"sifre": "x"})
    assert yanit.status_code == 422
    hata = yanit.json()["hata"]
    assert hata["kod"] == "DOGRULAMA"
    assert {"alan": "kullanici_adi", "kural": "zorunlu", "mesaj": "Bu alan zorunlu."} in hata["alanlar"]


def test_kisa_deger_min_karakter_kuraliyla_doner(client):
    yanit = client.post("/api/v1/auth/register", json={"kullanici_adi": "ab", "sifre": "kisa"})
    assert yanit.status_code == 422
    kurallar = {(alan["alan"], alan["kural"]) for alan in yanit.json()["hata"]["alanlar"]}
    assert kurallar == {("kullanici_adi", "min_karakter"), ("sifre", "min_karakter")}


def test_bozuk_json_govdesi(client):
    yanit = client.post(
        "/api/v1/auth/login",
        content="{bozuk",
        headers={"Content-Type": "application/json"},
    )
    assert yanit.status_code == 422
    assert yanit.json()["hata"]["alanlar"][0]["alan"] == "body"


def test_bilinmeyen_adres_bulunamadi_doner(client):
    yanit = client.get("/api/v1/olmayan-adres")
    assert yanit.status_code == 404
    assert yanit.json()["hata"]["kod"] == "BULUNAMADI"


def test_desteklenmeyen_yontem(client):
    yanit = client.delete("/api/v1/auth/me")
    assert yanit.status_code == 405
    assert yanit.json()["hata"]["kod"] == "YONTEM_DESTEKLENMIYOR"


def test_alan_yolu_liste_elemanlarini_koseli_parantezle_yazar():
    assert alan_yolu(("body", "icerik", "ornek_durumlar", 2)) == "icerik.ornek_durumlar[2]"
    assert alan_yolu(("query", "sayfa")) == "sayfa"
    assert alan_yolu(("body",)) == "body"


def _istek():
    return Request({"type": "http", "method": "GET", "path": "/", "headers": [], "query_string": b""})


def test_veritabanina_ulasilamayinca_503_doner():
    yanit = asyncio.run(veritabani_hatasi_handler(_istek(), OperationalError("SELECT 1", {}, Exception("kapalı"))))
    assert yanit.status_code == 503
    assert json.loads(yanit.body)["hata"]["kod"] == "VERITABANI_ERISILEMEZ"


def test_butunluk_hatasi_cakisma_olarak_doner():
    yanit = asyncio.run(veritabani_hatasi_handler(_istek(), IntegrityError("INSERT", {}, Exception("unique"))))
    assert yanit.status_code == 409
    assert json.loads(yanit.body)["hata"]["kod"] == "CAKISMA"
