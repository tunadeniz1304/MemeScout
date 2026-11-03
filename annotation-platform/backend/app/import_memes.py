"""Mevcut meme'leri API üzerinden toplu yükler.

Kaynak olarak zip dosyaları (ör. WhatsApp sohbet dışa aktarımı) ve görsel dosyaları ya da
bunları içeren klasörler verilir. Aynı görsel birden fazla kez geçiyorsa sha256 ile ayıklanır;
sunucu zaten yüklenmiş olanları da kopya olarak reddeder, bu yüzden betik tekrar
çalıştırılabilir. Barındırma ortamı istek gövdesini sınırladığı için (Vercel'de 4.5 MB)
görseller parça parça gönderilir.

Kullanım (annotation-platform/backend klasöründen):

    python -m app.import_memes --api https://memescout-annotation-api.vercel.app/api/v1 --kullanici ADMIN_ADI KLASOR
    python -m app.import_memes --deneme KLASOR   # yalnızca sayar, hiçbir şey yüklemez

Şifre çalışırken sorulur, ekranda görünmez.
"""

import argparse
import hashlib
import mimetypes
import sys
import time
import zipfile
from dataclasses import dataclass
from getpass import getpass
from pathlib import Path
from typing import Callable, Iterable, Optional

import requests

GORSEL_UZANTILARI = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
# Vercel'in 4.5 MB istek sınırının altında kalmak için; çok parçalı gövdenin ek baytlarına pay bırakılır.
AZAMI_PARCA_BAYTI = 3_500_000
AZAMI_PARCA_ADEDI = 60
TEKRAR_DENENECEK_DURUMLAR = {409, 502, 503, 504}
DENEME_SAYISI = 5


@dataclass
class Gorsel:
    ad: str
    veri: bytes
    sha256: str


def _gorsel_mi(ad: str) -> bool:
    yol = Path(ad)
    # macOS arşivlerindeki "__MACOSX/._x.jpg" kayıtları görsel değildir.
    if "__MACOSX" in yol.parts or yol.name.startswith("._"):
        return False
    return yol.suffix.lower() in GORSEL_UZANTILARI


def _kaynaktaki_gorseller(kaynak: Path) -> Iterable[tuple[str, bytes]]:
    if kaynak.is_dir():
        for alt in sorted(kaynak.iterdir()):
            yield from _kaynaktaki_gorseller(alt)
    elif kaynak.suffix.lower() == ".zip":
        with zipfile.ZipFile(kaynak) as arsiv:
            for kayit in sorted(arsiv.infolist(), key=lambda kayit: kayit.filename):
                if not kayit.is_dir() and _gorsel_mi(kayit.filename):
                    yield f"{kaynak.stem}/{Path(kayit.filename).name}", arsiv.read(kayit)
    elif _gorsel_mi(kaynak.name):
        yield kaynak.name, kaynak.read_bytes()


def gorselleri_topla(kaynaklar: list[Path]) -> tuple[list[Gorsel], list[tuple[str, str]]]:
    """Görselleri sırayla toplar. İkinci kez görülen görseller (ad, ilk görüldüğü ad) olarak ayrılır."""
    gorseller: list[Gorsel] = []
    ilk_gorulen: dict[str, str] = {}
    tekrarlar: list[tuple[str, str]] = []
    for kaynak in kaynaklar:
        for ad, veri in _kaynaktaki_gorseller(kaynak):
            sha256 = hashlib.sha256(veri).hexdigest()
            if sha256 in ilk_gorulen:
                tekrarlar.append((ad, ilk_gorulen[sha256]))
                continue
            ilk_gorulen[sha256] = ad
            gorseller.append(Gorsel(ad, veri, sha256))
    return gorseller, tekrarlar


def parcalara_bol(
    gorseller: list[Gorsel],
    azami_bayt: int = AZAMI_PARCA_BAYTI,
    azami_adet: int = AZAMI_PARCA_ADEDI,
) -> list[list[Gorsel]]:
    parcalar: list[list[Gorsel]] = []
    parca: list[Gorsel] = []
    boyut = 0
    for gorsel in gorseller:
        if parca and (boyut + len(gorsel.veri) > azami_bayt or len(parca) >= azami_adet):
            parcalar.append(parca)
            parca, boyut = [], 0
        parca.append(gorsel)
        boyut += len(gorsel.veri)
    if parca:
        parcalar.append(parca)
    return parcalar


def _cok_parcali(parca: list[Gorsel]) -> list[tuple]:
    return [
        ("dosyalar", (gorsel.ad, gorsel.veri, mimetypes.guess_type(gorsel.ad)[0] or "application/octet-stream"))
        for gorsel in parca
    ]


Gonderici = Callable[[list[tuple]], tuple[int, dict]]


def yukle(parcalar: list[list[Gorsel]], gonder: Gonderici, bekle: Callable[[float], None] = time.sleep, yaz=print) -> dict:
    """Parçaları sırayla gönderir; geçici hatalarda bekleyip tekrar dener.

    `gonder`, çok parçalı dosya listesini alıp (HTTP durum kodu, JSON gövdesi) döner.
    """
    ozet = {"yuklenen": [], "reddedilen": [], "basarisiz": []}
    for sira, parca in enumerate(parcalar, start=1):
        for deneme in range(DENEME_SAYISI):
            try:
                durum, govde = gonder(_cok_parcali(parca))
            except requests.RequestException as hata:
                durum, govde = None, {"hata": {"mesaj": str(hata)}}
            gecici = durum is None or durum in TEKRAR_DENENECEK_DURUMLAR
            if not gecici or deneme == DENEME_SAYISI - 1:
                break
            # Ücretsiz Supabase uzun süre boşta kalınca uykuya geçer; uyanması birkaç saniye sürer.
            bekleme = 2 ** (deneme + 1)
            yaz(f"  parça {sira}: {durum or 'bağlantı hatası'}, {bekleme} sn sonra tekrar denenecek")
            bekle(bekleme)
        if durum != 200:
            mesaj = (govde.get("hata") or {}).get("mesaj", "") if isinstance(govde, dict) else ""
            ozet["basarisiz"].extend({"dosya_adi": gorsel.ad, "durum": durum, "mesaj": mesaj} for gorsel in parca)
            yaz(f"Parça {sira}/{len(parcalar)} yüklenemedi ({durum}): {mesaj}")
            continue
        ozet["yuklenen"].extend(govde["yuklenen"])
        ozet["reddedilen"].extend(govde["reddedilen"])
        yaz(f"Parça {sira}/{len(parcalar)}: {len(govde['yuklenen'])} yüklendi, {len(govde['reddedilen'])} reddedildi")
    return ozet


def _giris_yap(api: str, kullanici_adi: str, sifre: str) -> str:
    yanit = requests.post(f"{api}/auth/login", json={"kullanici_adi": kullanici_adi, "sifre": sifre}, timeout=30)
    if yanit.status_code != 200:
        mesaj = yanit.json().get("hata", {}).get("mesaj", yanit.text) if yanit.headers.get("content-type", "").startswith("application/json") else yanit.text
        raise SystemExit(f"Giriş yapılamadı ({yanit.status_code}): {mesaj}")
    kullanici = yanit.json()["kullanici"]
    if not kullanici["admin"]:
        raise SystemExit(f"'{kullanici['kullanici_adi']}' admin değil; toplu yükleme admin yetkisi ister.")
    return yanit.json()["erisim_token"]


def _http_gonderici(api: str, token: str) -> Gonderici:
    oturum = requests.Session()
    oturum.headers["Authorization"] = f"Bearer {token}"

    def gonder(dosyalar: list[tuple]) -> tuple[int, dict]:
        yanit = oturum.post(f"{api}/memes/bulk", files=dosyalar, timeout=120)
        try:
            return yanit.status_code, yanit.json()
        except ValueError:
            return yanit.status_code, {"hata": {"mesaj": yanit.text[:200]}}

    return gonder


def main(argumanlar: Optional[list[str]] = None) -> int:
    ayristirici = argparse.ArgumentParser(description="Meme görsellerini API üzerinden toplu yükler.")
    ayristirici.add_argument("kaynaklar", nargs="+", type=Path, help="zip dosyaları, görseller ya da bunları içeren klasörler")
    ayristirici.add_argument("--api", help="API kök adresi, ör. https://memescout-annotation-api.vercel.app/api/v1")
    ayristirici.add_argument("--kullanici", help="admin kullanıcı adı (verilmezse sorulur)")
    ayristirici.add_argument("--deneme", action="store_true", help="hiçbir şey yüklemeden yalnızca say")
    secenekler = ayristirici.parse_args(argumanlar)

    eksikler = [str(kaynak) for kaynak in secenekler.kaynaklar if not kaynak.exists()]
    if eksikler:
        raise SystemExit(f"Bulunamadı: {', '.join(eksikler)}")
    gorseller, tekrarlar = gorselleri_topla(secenekler.kaynaklar)
    parcalar = parcalara_bol(gorseller)
    toplam_bayt = sum(len(gorsel.veri) for gorsel in gorseller)
    print(
        f"{len(gorseller) + len(tekrarlar)} görsel bulundu, {len(tekrarlar)} tanesi kaynaklarda tekrar ediyor. "
        f"{len(gorseller)} farklı görsel ({toplam_bayt / 1_000_000:.1f} MB) {len(parcalar)} parçada gönderilecek."
    )
    if secenekler.deneme:
        return 0
    if not secenekler.api:
        raise SystemExit("--api adresi gerekli (ya da yalnızca saymak için --deneme kullan).")

    api = secenekler.api.rstrip("/")
    kullanici_adi = secenekler.kullanici or input("Admin kullanıcı adı: ").strip()
    token = _giris_yap(api, kullanici_adi, getpass("Şifre (yazarken görünmez): "))
    ozet = yukle(parcalar, _http_gonderici(api, token))

    kopyalar = [red for red in ozet["reddedilen"] if red["sebep"] == "kopya"]
    digerleri = [red for red in ozet["reddedilen"] if red["sebep"] != "kopya"]
    print(f"\nYüklenen: {len(ozet['yuklenen'])}")
    print(f"Zaten yüklü (kopya): {len(kopyalar)}")
    for red in digerleri:
        print(f"Reddedildi: {red['dosya_adi']} ({red['sebep']})")
    for hata in ozet["basarisiz"]:
        print(f"Gönderilemedi: {hata['dosya_adi']} ({hata['durum']})")
    if ozet["yuklenen"]:
        print(f"Meme kimlikleri: {ozet['yuklenen'][0]['id']} – {ozet['yuklenen'][-1]['id']}")
    return 1 if ozet["basarisiz"] else 0


if __name__ == "__main__":
    sys.exit(main())
