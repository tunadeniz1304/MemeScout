"""LLM kartlarını API üzerinden meme'lere taslak olarak bağlar (ADR-0010).

Kartlar architecture.md §3 biçimindedir. YAML dosyası kart listesidir; CSV dosyası aynı
sütunları taşır ve liste alanlarında öğeler " | " ile ayrılır. Her kartın `gorsel` yolu kart
dosyasının klasörüne (ya da --gorseller ile verilen klasöre) göre çözülür ve görselin sha256'sıyla
meme bulunur. Eşleşen meme yoksa görsel yeni meme olarak yüklenir (--yalniz-eslesenler ile
atlanır). Taslak gold olmaz: atanan annotator formu taslakla dolu bulur, düzeltir ve gönderir.

Kullanım (annotation-platform/backend klasöründen):

    python -m app.import_ai_drafts --deneme memescout_gold.yaml
    python -m app.import_ai_drafts --api https://memescout-annotation-api.vercel.app/api/v1 --kullanici ADMIN_ADI memescout_gold.yaml

Şifre çalışırken sorulur, ekranda görünmez.
"""

import argparse
import csv
import hashlib
import json
import sys
import time
from dataclasses import dataclass
from getpass import getpass
from pathlib import Path
from typing import Callable, Optional

import requests
import yaml

from app.ai_taslak import karttan_icerik
from app.etiketler import tohum_alanlari
from app.import_memes import (
    DENEME_SAYISI,
    TEKRAR_DENENECEK_DURUMLAR,
    Gorsel,
    _giris_yap,
    _http_gonderici,
    parcalara_bol,
    yukle,
)
from app.models import simdi
from app.sema import ALAN_KURALLARI, LISTE_TIPLERI, icerik_dogrula

CSV_AYRACI = " | "
# Kayıt bilgisi olup CSV'de liste olarak yazılan sütunlar.
KAYIT_LISTE_ALANLARI = ("annotator", "genisletilmis_durumlar", "gecmis_sorgular")
ICERIK_LISTE_ALANLARI = tuple(alan for alan, kural in ALAN_KURALLARI.items() if kural["tip"] in LISTE_TIPLERI)
AZAMI_KART_ADEDI = 200

JsonGonderici = Callable[[dict], tuple[Optional[int], dict]]


@dataclass
class Kart:
    kimlik: str
    kart: dict
    gorsel_yolu: Optional[Path] = None
    veri: Optional[bytes] = None
    sha256: Optional[str] = None
    sorun: Optional[str] = None


def _json_uyumlu(deger):
    # YAML tarih gibi JSON'da karşılığı olmayan değerler üretebilir; metne çevrilir.
    return json.loads(json.dumps(deger, ensure_ascii=False, default=str))


def _csv_satiri(satir: dict) -> dict:
    kart = {}
    for alan, deger in satir.items():
        if alan is None:
            continue
        deger = (deger or "").strip()
        if alan in ICERIK_LISTE_ALANLARI:
            # CSV'de boş hücre ile "bilinçli uyarı yok" ayırt edilemez; boş liste olarak okunur.
            kart[alan] = [parca.strip() for parca in deger.split(CSV_AYRACI.strip()) if parca.strip()] if deger else []
        elif alan in KAYIT_LISTE_ALANLARI:
            kart[alan] = [parca.strip() for parca in deger.split(CSV_AYRACI.strip()) if parca.strip()] if deger else None
        else:
            kart[alan] = None if deger in ("", "null") else deger
    return kart


def kartlari_oku(yol: Path) -> list[dict]:
    if yol.suffix.lower() == ".csv":
        with yol.open(encoding="utf-8-sig", newline="") as dosya:
            return [_csv_satiri(satir) for satir in csv.DictReader(dosya)]
    veri = yaml.safe_load(yol.read_text(encoding="utf-8"))
    kartlar = veri if isinstance(veri, list) else [veri]
    if not all(isinstance(kart, dict) for kart in kartlar):
        raise SystemExit(f"{yol}: kart listesi bekleniyordu.")
    return [_json_uyumlu(kart) for kart in kartlar]


def _gorseli_bul(gorsel: str, taban: Path) -> Optional[Path]:
    for aday in (taban / gorsel, taban / Path(gorsel).name):
        if aday.is_file():
            return aday
    return None


def kartlari_hazirla(dosyalar: list[Path], gorsel_klasoru: Optional[Path] = None) -> list[Kart]:
    """Kartları okur, görsellerini bulur ve sha256'larını hesaplar. Sorunlu kartlar `sorun` taşır."""
    kayitlar: list[Kart] = []
    ilk_gorulen: dict[str, str] = {}
    for dosya in dosyalar:
        taban = gorsel_klasoru or dosya.parent
        for sira, kart in enumerate(kartlari_oku(dosya), start=1):
            kayit = Kart(kimlik=str(kart.get("id") or f"{dosya.name}#{sira}"), kart=kart)
            kayitlar.append(kayit)
            gorsel = kart.get("gorsel")
            if not gorsel:
                kayit.sorun = "kartta gorsel alanı yok"
                continue
            kayit.gorsel_yolu = _gorseli_bul(str(gorsel), taban)
            if kayit.gorsel_yolu is None:
                kayit.sorun = f"görsel bulunamadı: {taban / gorsel}"
                continue
            kayit.veri = kayit.gorsel_yolu.read_bytes()
            kayit.sha256 = hashlib.sha256(kayit.veri).hexdigest()
            if kayit.sha256 in ilk_gorulen:
                kayit.sorun = f"aynı görsel '{ilk_gorulen[kayit.sha256]}' kartında da var"
                continue
            ilk_gorulen[kayit.sha256] = kayit.kimlik
    return kayitlar


def kaynak_adi(kart: dict) -> str:
    annotator = kart.get("annotator")
    if isinstance(annotator, list) and annotator:
        return ",".join(str(ad) for ad in annotator)[:100]
    return str(annotator)[:100] if annotator else "llm"


def yerel_ihlaller(kart: dict) -> list[dict]:
    """Sunucuya sormadan, ilk etiket listesine (v1) göre kural ihlalleri."""
    return icerik_dogrula(karttan_icerik(kart), tohum_alanlari(simdi()))


def _tekrar_dene(islem: Callable[[], tuple[Optional[int], dict]], bekle, yaz, etiket: str) -> tuple[Optional[int], dict]:
    for deneme in range(DENEME_SAYISI):
        try:
            durum, govde = islem()
        except requests.RequestException as hata:
            durum, govde = None, {"hata": {"mesaj": str(hata)}}
        if (durum is not None and durum not in TEKRAR_DENENECEK_DURUMLAR) or deneme == DENEME_SAYISI - 1:
            return durum, govde
        bekleme = 2 ** (deneme + 1)
        yaz(f"  {etiket}: {durum or 'bağlantı hatası'}, {bekleme} sn sonra tekrar denenecek")
        bekle(bekleme)
    return durum, govde


def _taslaklari_gonder(kayitlar: list[Kart], gonder_json: JsonGonderici, bekle, yaz) -> tuple[list, list, list]:
    eklenen, reddedilen, basarisiz = [], [], []
    for bas in range(0, len(kayitlar), AZAMI_KART_ADEDI):
        parca = kayitlar[bas : bas + AZAMI_KART_ADEDI]
        govde = {"taslaklar": [{"sha256": k.sha256, "kaynak": kaynak_adi(k.kart), "kart": k.kart} for k in parca]}
        durum, yanit = _tekrar_dene(lambda: gonder_json(govde), bekle, yaz, "kartlar")
        if durum != 200:
            mesaj = (yanit.get("hata") or {}).get("mesaj", "") if isinstance(yanit, dict) else ""
            basarisiz.extend({"kart": k, "durum": durum, "mesaj": mesaj} for k in parca)
            continue
        eklenen.extend(yanit["eklenen"])
        reddedilen.extend(yanit["reddedilen"])
    return eklenen, reddedilen, basarisiz


def aktar(
    kayitlar: list[Kart],
    gonder_json: JsonGonderici,
    gonder_dosya,
    yalniz_eslesenler: bool = False,
    bekle: Callable[[float], None] = time.sleep,
    yaz=print,
) -> dict:
    """Kartları gönderir; eşleşen meme'i olmayanların görsellerini yükleyip bir kez daha gönderir."""
    hazir = [kayit for kayit in kayitlar if kayit.sorun is None]
    sha_kart = {kayit.sha256: kayit for kayit in hazir}
    eklenen, reddedilen, basarisiz = _taslaklari_gonder(hazir, gonder_json, bekle, yaz)

    eksikler = [sha_kart[red["sha256"]] for red in reddedilen if red["sebep"] == "meme_yok"]
    reddedilen = [red for red in reddedilen if red["sebep"] != "meme_yok"]
    atlanan, yeni_memeler = [], []
    if eksikler and yalniz_eslesenler:
        atlanan = eksikler
    elif eksikler:
        gorseller = [Gorsel(kayit.gorsel_yolu.name, kayit.veri, kayit.sha256) for kayit in eksikler]
        yukleme = yukle(parcalara_bol(gorseller), gonder_dosya, bekle=bekle, yaz=lambda _: None)
        yeni_memeler = yukleme["yuklenen"]
        for red in yukleme["reddedilen"] + yukleme["basarisiz"]:
            if red.get("sebep") != "kopya":
                yaz(f"Görsel yüklenemedi: {red['dosya_adi']} ({red.get('sebep') or red.get('durum')})")
        # Yüklenemeyen görselin kartı ikinci gönderimde de meme_yok döner ve raporda görünür.
        ikinci_eklenen, ikinci_reddedilen, ikinci_basarisiz = _taslaklari_gonder(eksikler, gonder_json, bekle, yaz)
        eklenen += ikinci_eklenen
        reddedilen += ikinci_reddedilen
        basarisiz += ikinci_basarisiz
    return {
        "eklenen": eklenen,
        "reddedilen": reddedilen,
        "basarisiz": basarisiz,
        "atlanan": atlanan,
        "yeni_memeler": yeni_memeler,
        "sha_kart": sha_kart,
    }


def _ihlal_satirlari(ihlaller: list[dict]) -> list[str]:
    return [f"      - {ihlal['alan']}: {ihlal['mesaj']} ({ihlal['kural']})" for ihlal in ihlaller]


def rapor(kayitlar: list[Kart], sonuc: Optional[dict], yaz=print) -> None:
    yaz(f"{len(kayitlar)} kart okundu.")
    for kayit in kayitlar:
        if kayit.sorun:
            yaz(f"  {kayit.kimlik} → atlandı: {kayit.sorun}")
    if sonuc is None:
        # Deneme: sunucuya sorulmadan, ilk etiket listesine göre kontrol.
        for kayit in kayitlar:
            if kayit.sorun is None:
                ihlaller = yerel_ihlaller(kayit.kart)
                yaz(f"  {kayit.kimlik} → {kayit.gorsel_yolu.name}, {len(ihlaller)} ihlal")
                for satir in _ihlal_satirlari(ihlaller):
                    yaz(satir)
        return

    sha_kart = sonuc["sha_kart"]
    yeni = {meme["sha256"]: meme["id"] for meme in sonuc["yeni_memeler"]}
    for eklenen in sonuc["eklenen"]:
        kayit = sha_kart[eklenen["sha256"]]
        not_ = " (yeni meme)" if eklenen["sha256"] in yeni else ""
        yaz(f"  {kayit.kimlik} → {eklenen['meme_id']}{not_}, {len(eklenen['ihlaller'])} ihlal")
        for satir in _ihlal_satirlari(eklenen["ihlaller"]):
            yaz(satir)
    for red in sonuc["reddedilen"]:
        yaz(f"  {sha_kart[red['sha256']].kimlik} → reddedildi ({red['sebep']}): {red['mesaj']}")
    for kayit in sonuc["atlanan"]:
        yaz(f"  {kayit.kimlik} → eşleşen meme yok, atlandı")
    for hata in sonuc["basarisiz"]:
        yaz(f"  {hata['kart'].kimlik} → gönderilemedi ({hata['durum']}): {hata['mesaj']}")
    yaz(
        f"\nÖzet: {len(sonuc['eklenen'])} taslak eklendi, {len(yeni)} yeni meme oluştu, "
        f"{len(sonuc['reddedilen'])} kart reddedildi, {sum(1 for k in kayitlar if k.sorun)} kart atlandı."
    )
    if yeni:
        yaz(
            "Not: Kartın görseli zip'teki dosyanın birebir kopyası değilse (ör. PNG'ye dönüştürülmüşse) "
            "sha256'sı tutmaz ve ayrı bir meme olarak yüklenir. Yeni meme'lerin kopya olmadığını kontrol edin."
        )


def _json_gonderici(api: str, token: str) -> JsonGonderici:
    oturum = requests.Session()
    oturum.headers["Authorization"] = f"Bearer {token}"

    def gonder(govde: dict) -> tuple[Optional[int], dict]:
        yanit = oturum.post(f"{api}/memes/ai-drafts", json=govde, timeout=120)
        try:
            return yanit.status_code, yanit.json()
        except ValueError:
            return yanit.status_code, {"hata": {"mesaj": yanit.text[:200]}}

    return gonder


def main(argumanlar: Optional[list[str]] = None) -> int:
    ayristirici = argparse.ArgumentParser(description="LLM kartlarını meme'lere taslak olarak bağlar.")
    ayristirici.add_argument("dosyalar", nargs="+", type=Path, help="YAML ya da CSV kart dosyaları")
    ayristirici.add_argument("--api", help="API kök adresi, ör. https://memescout-annotation-api.vercel.app/api/v1")
    ayristirici.add_argument("--kullanici", help="admin kullanıcı adı (verilmezse sorulur)")
    ayristirici.add_argument("--gorseller", type=Path, help="görsellerin bulunduğu klasör (varsayılan: kart dosyasının klasörü)")
    ayristirici.add_argument("--yalniz-eslesenler", action="store_true", help="eşleşen meme'i olmayan kartlar için yeni meme oluşturma")
    ayristirici.add_argument("--deneme", action="store_true", help="hiçbir şey göndermeden kartları ve görselleri kontrol et")
    secenekler = ayristirici.parse_args(argumanlar)

    eksikler = [str(dosya) for dosya in secenekler.dosyalar if not dosya.is_file()]
    if eksikler:
        raise SystemExit(f"Bulunamadı: {', '.join(eksikler)}")
    kayitlar = kartlari_hazirla(secenekler.dosyalar, secenekler.gorseller)
    if secenekler.deneme:
        rapor(kayitlar, None)
        return 0
    if not secenekler.api:
        raise SystemExit("--api adresi gerekli (ya da yalnızca kontrol için --deneme kullan).")

    api = secenekler.api.rstrip("/")
    kullanici_adi = secenekler.kullanici or input("Admin kullanıcı adı: ").strip()
    token = _giris_yap(api, kullanici_adi, getpass("Şifre (yazarken görünmez): "))
    sonuc = aktar(kayitlar, _json_gonderici(api, token), _http_gonderici(api, token), secenekler.yalniz_eslesenler)
    rapor(kayitlar, sonuc)
    return 1 if sonuc["basarisiz"] else 0


if __name__ == "__main__":
    sys.exit(main())
