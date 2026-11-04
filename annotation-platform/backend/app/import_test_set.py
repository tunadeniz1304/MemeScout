"""Test setini işaretler ve hazır test sorgularını yazarları adına API üzerinden ekler (ADR-0012).

Meme'ler yerel görsel dosyalarının sha256'sıyla bulunur; meme id'lerini bilmek gerekmez.

- `--isaretle LISTE`: her satırı bir görsel yolu olan metin dosyası. Bu meme'ler test setine alınır,
  böylece etiketleme atamalarına girmez ve herkes onlara test sorgusu yazabilir.
- `--sorgular JSON`: bir belgede toplanmış sorgular, yazarları adına eklenir:
  {"yazan": "kullanici_adi", "sorgular": [{"gorsel": "final/x.jpg", "mod": "durum", "metin": "..."}]}
  Aynı kişinin aynı meme için aynı metinli sorgusu zaten varsa atlanır; betik tekrar çalıştırılabilir.

Görsel yolları --gorseller klasörüne göredir (ör. --gorseller ../../MEMELER ile "final/x.jpg").

Kullanım (annotation-platform/backend klasöründen):

    python -m app.import_test_set --deneme --gorseller ../../MEMELER --sorgular sorgular.json
    python -m app.import_test_set --api https://memescout-annotation-api.vercel.app/api/v1 --kullanici ADMIN_ADI \\
        --gorseller ../../MEMELER --sorgular sorgular.json

Şifre çalışırken sorulur, ekranda görünmez.
"""

import argparse
import hashlib
import json
import sys
from getpass import getpass
from pathlib import Path
from typing import Callable, Optional

import requests

from app.import_memes import _giris_yap

# (yöntem, API köküne göre yol, json=..., params=...) -> status_code ve json() taşıyan yanıt
Istek = Callable[..., object]


def _sha256(gorseller: Path, yol: str) -> str:
    return hashlib.sha256((gorseller / yol).read_bytes()).hexdigest()


def _mesaj(yanit) -> str:
    try:
        return (yanit.json().get("hata") or {}).get("mesaj", "")
    except ValueError:
        return ""


def eksik_dosyalar(gorseller: Path, yollar: list[str]) -> list[str]:
    return [yol for yol in dict.fromkeys(yollar) if not (gorseller / yol).is_file()]


def meme_haritasi(istek: Istek) -> dict[str, dict]:
    """sha256 -> meme; bütün sayfalar okunur."""
    harita, sayfa = {}, 1
    while True:
        veri = istek("GET", "/memes", params={"sayfa": sayfa, "boyut": 200}).json()
        harita.update({meme["sha256"]: meme for meme in veri["ogeler"]})
        if sayfa * veri["boyut"] >= veri["toplam"]:
            return harita
        sayfa += 1


def isaretle(istek: Istek, gorseller: Path, yollar: list[str], harita: dict[str, dict]) -> dict:
    sonuc = {"isaretlenen": [], "zaten": [], "bulunamayan": [], "basarisiz": []}
    for yol in dict.fromkeys(yollar):
        meme = harita.get(_sha256(gorseller, yol))
        if meme is None:
            sonuc["bulunamayan"].append(yol)
        elif meme.get("test_seti"):
            sonuc["zaten"].append(meme["id"])
        else:
            yanit = istek("PATCH", f"/memes/{meme['id']}", json={"test_seti": True})
            if yanit.status_code == 200:
                sonuc["isaretlenen"].append(meme["id"])
            else:
                sonuc["basarisiz"].append({"gorsel": yol, "durum": yanit.status_code, "mesaj": _mesaj(yanit)})
    return sonuc


def sorgulari_ekle(istek: Istek, gorseller: Path, veri: dict, harita: dict[str, dict]) -> dict:
    kisiler = {kisi["kullanici_adi"]: kisi["id"] for kisi in istek("GET", "/users").json()}
    if veri["yazan"] not in kisiler:
        raise SystemExit(f"'{veri['yazan']}' adında bir kullanıcı yok.")
    yazan_id = kisiler[veri["yazan"]]
    mevcut = {
        (sorgu["metin"], tuple(sorgu["dogru_memeler"]))
        for sorgu in istek("GET", "/test-queries", params={"yazan_id": yazan_id}).json()
    }
    sonuc = {"eklenen": 0, "atlanan": 0, "bulunamayan": [], "basarisiz": []}
    for sorgu in veri["sorgular"]:
        meme = harita.get(_sha256(gorseller, sorgu["gorsel"]))
        if meme is None:
            sonuc["bulunamayan"].append(sorgu["gorsel"])
            continue
        anahtar = (sorgu["metin"], (meme["id"],))
        if anahtar in mevcut:
            sonuc["atlanan"] += 1
            continue
        govde = {"metin": sorgu["metin"], "mod": sorgu.get("mod", "durum"), "dogru_memeler": [meme["id"]], "yazan_id": yazan_id}
        yanit = istek("POST", "/test-queries", json=govde)
        if yanit.status_code == 201:
            sonuc["eklenen"] += 1
            mevcut.add(anahtar)
        else:
            sonuc["basarisiz"].append({"metin": sorgu["metin"], "durum": yanit.status_code, "mesaj": _mesaj(yanit)})
    return sonuc


def _http_istek(api: str, token: str) -> Istek:
    oturum = requests.Session()
    oturum.headers["Authorization"] = f"Bearer {token}"
    return lambda yontem, yol, **ek: oturum.request(yontem, f"{api}{yol}", timeout=60, **ek)


def main(argumanlar: Optional[list[str]] = None) -> int:
    ayrac = argparse.ArgumentParser(description="Test setini işaretler ve hazır test sorgularını ekler.")
    ayrac.add_argument("--api", help="API kök adresi, ör. https://memescout-annotation-api.vercel.app/api/v1")
    ayrac.add_argument("--kullanici", help="admin kullanıcı adı (verilmezse sorulur)")
    ayrac.add_argument("--gorseller", type=Path, required=True, help="görsel yollarının göre olduğu klasör")
    ayrac.add_argument("--isaretle", type=Path, help="test setine alınacak görsellerin listesi (satır başına bir yol)")
    ayrac.add_argument("--sorgular", type=Path, help="yazarı adına eklenecek test sorguları (JSON)")
    ayrac.add_argument("--deneme", action="store_true", help="hiçbir şey göndermeden dosyaları kontrol et")
    secenekler = ayrac.parse_args(argumanlar)
    if not secenekler.isaretle and not secenekler.sorgular:
        ayrac.error("--isaretle ya da --sorgular verilmeli.")

    isaretlenecek = []
    if secenekler.isaretle:
        isaretlenecek = [satir.strip() for satir in secenekler.isaretle.read_text(encoding="utf-8").splitlines() if satir.strip()]
    sorgu_verisi = json.loads(secenekler.sorgular.read_text(encoding="utf-8")) if secenekler.sorgular else None
    yollar = isaretlenecek + [sorgu["gorsel"] for sorgu in (sorgu_verisi or {}).get("sorgular", [])]
    eksikler = eksik_dosyalar(secenekler.gorseller, yollar)
    for yol in eksikler:
        print(f"Görsel bulunamadı: {yol}")
    print(f"{len(dict.fromkeys(isaretlenecek))} görsel test setine alınacak.")
    if sorgu_verisi:
        print(f"{len(sorgu_verisi['sorgular'])} sorgu {len({s['gorsel'] for s in sorgu_verisi['sorgular']})} görsel için "
              f"'{sorgu_verisi['yazan']}' adına eklenecek.")
    if eksikler:
        return 1
    if secenekler.deneme:
        return 0

    api = (secenekler.api or input("API kök adresi: ")).rstrip("/")
    kullanici_adi = secenekler.kullanici or input("Admin kullanıcı adı: ")
    istek = _http_istek(api, _giris_yap(api, kullanici_adi, getpass("Şifre (yazarken görünmez): ")))
    harita = meme_haritasi(istek)
    sorun = False
    if isaretlenecek:
        sonuc = isaretle(istek, secenekler.gorseller, isaretlenecek, harita)
        print(f"Test seti: {len(sonuc['isaretlenen'])} meme alındı, {len(sonuc['zaten'])} meme zaten testteydi.")
        for yol in sonuc["bulunamayan"]:
            print(f"  Platformda yok: {yol}")
        for hata in sonuc["basarisiz"]:
            print(f"  Alınamadı ({hata['durum']}): {hata['gorsel']} {hata['mesaj']}")
        sorun = bool(sonuc["bulunamayan"] or sonuc["basarisiz"])
    if sorgu_verisi:
        sonuc = sorgulari_ekle(istek, secenekler.gorseller, sorgu_verisi, harita)
        print(f"Sorgular: {sonuc['eklenen']} eklendi, {sonuc['atlanan']} zaten vardı.")
        for yol in sonuc["bulunamayan"]:
            print(f"  Platformda yok: {yol}")
        for hata in sonuc["basarisiz"]:
            print(f"  Eklenemedi ({hata['durum']}): {hata['metin']} {hata['mesaj']}")
        sorun = sorun or bool(sonuc["bulunamayan"] or sonuc["basarisiz"])
    return 1 if sorun else 0


if __name__ == "__main__":
    sys.exit(main())
