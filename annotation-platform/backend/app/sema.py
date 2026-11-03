"""Annotation içerik şeması: alanlar ve gönderim kuralları (docs/annotation.md §3.2).

Kurallar tek yerde tanımlıdır; `GET /schema/annotation` bunları olduğu gibi döner,
backend gönderimde aynı kurallarla doğrular.
"""

from app.metin import tr_kucuk

SEMA_VERSIYONU = "1.0"

ETIKET_ALANLARI = ("duygu", "niyet", "mekanizma", "uyari")

# Sıra, formdaki alan sırasıdır.
ALAN_KURALLARI: dict[str, dict] = {
    "tur": {
        "zorunlu": True,
        "tip": "enum",
        "degerler": ["template", "hazir_meme"],
        "aciklama": "Üzerine farklı metinler yazılan şablon mu, olduğu gibi paylaşılan hazır meme mi",
    },
    "ad": {"zorunlu": True, "tip": "metin", "max_karakter": 60, "aciklama": "Meme'in bilinen adı"},
    "kaynak": {"zorunlu": False, "tip": "metin", "max_karakter": 100, "aciklama": "Eser, karakter, sahne"},
    "vlm_aciklama": {
        "zorunlu": True,
        "tip": "metin",
        "min_karakter": 20,
        "max_karakter": 250,
        "aciklama": "Yalnızca görselde görünenler: kişi, yüz ifadesi, nesne, sahne, yazı. Yorum yok.",
    },
    "durum": {
        "zorunlu": True,
        "tip": "metin",
        "min_karakter": 20,
        "max_karakter": 200,
        "aciklama": "Somut varlık değil, soyut iskelet",
    },
    "ornek_durumlar": {
        "zorunlu": True,
        "tip": "metin_listesi",
        "min_adet": 3,
        "max_adet": 5,
        "tekrarsiz": True,
        "max_karakter": 150,
        "aciklama": "Kullanıcının gerçekte yazacağı dille: kısa, gündelik, gerekiyorsa argolu",
    },
    "uygun_olmayan_durumlar": {
        "zorunlu": True,
        "tip": "metin_listesi",
        "min_adet": 1,
        "max_adet": 2,
        "tekrarsiz": True,
        "max_karakter": 150,
        "aciklama": "Bu meme'in kullanılmayacağı durumlar",
    },
    "kulturel_bilgi": {
        "zorunlu": True,
        "tip": "metin",
        "max_karakter": 500,
        "aciklama": "Gereken arka plan ve neden komik olduğu",
    },
    "anahtar_kelimeler": {
        "zorunlu": True,
        "tip": "metin_listesi",
        "min_adet": 3,
        "max_adet": 8,
        "tekrarsiz": True,
        "max_karakter": 40,
        "aciklama": "Düz Türkçe, Türkçe karakterle: bilinen ad, replik, karakter, görünen nesne. Hashtag ve bitişik yazım yok.",
    },
    "duygu": {
        "zorunlu": True,
        "tip": "etiket_listesi",
        "etiket_alani": "duygu",
        "min_adet": 1,
        "max_adet": 3,
        "tekrarsiz": True,
    },
    "niyet": {
        "zorunlu": True,
        "tip": "etiket_listesi",
        "etiket_alani": "niyet",
        "min_adet": 1,
        "max_adet": 3,
        "tekrarsiz": True,
    },
    "mekanizma": {
        "zorunlu": True,
        "tip": "etiket_listesi",
        "etiket_alani": "mekanizma",
        "min_adet": 1,
        "max_adet": 3,
        "tekrarsiz": True,
    },
    "uyari": {
        "zorunlu": True,
        "tip": "etiket_listesi",
        "etiket_alani": "uyari",
        "min_adet": 0,
        "tekrarsiz": True,
        "aciklama": "Boş liste = bilinçli 'uyarı yok' onayı",
    },
    "notlar": {"zorunlu": False, "tip": "metin", "max_karakter": 500, "aciklama": "Serbest not"},
}

LISTE_TIPLERI = ("metin_listesi", "etiket_listesi")


def bos_icerik() -> dict:
    # uyari null başlar: "henüz cevaplanmadı" ile "uyarı yok" ([]) ayrı tutulur (ADR-0004).
    return {
        alan: [] if kural["tip"] in LISTE_TIPLERI and alan != "uyari" else None
        for alan, kural in ALAN_KURALLARI.items()
    }


# --- Gönderim doğrulaması -------------------------------------------------------------
# Hata yolları içerik alan adıdır (liste elemanları için `ornek_durumlar[2]`); frontend
# hatayı ilgili inputun altında bu yolla gösterir.

def _hata(alan: str, kural: str, mesaj: str) -> dict:
    return {"alan": alan, "kural": kural, "mesaj": mesaj}


def _bos_mu(deger) -> bool:
    return deger is None or (isinstance(deger, str) and not deger.strip())


def _metin_dogrula(alan: str, kural: dict, deger) -> list[dict]:
    if _bos_mu(deger):
        return [_hata(alan, "zorunlu", "Bu alan zorunlu.")] if kural["zorunlu"] else []
    if not isinstance(deger, str):
        return [_hata(alan, "gecersiz_deger", "Metin olmalı.")]
    if kural["tip"] == "enum":
        if deger not in kural["degerler"]:
            return [_hata(alan, "gecersiz_etiket", f"Geçerli değerler: {', '.join(kural['degerler'])}.")]
        return []
    uzunluk = len(deger.strip())
    hatalar = []
    if "min_karakter" in kural and uzunluk < kural["min_karakter"]:
        hatalar.append(_hata(alan, "min_karakter", f"En az {kural['min_karakter']} karakter olmalı."))
    if "max_karakter" in kural and uzunluk > kural["max_karakter"]:
        hatalar.append(_hata(alan, "max_karakter", f"En fazla {kural['max_karakter']} karakter olabilir."))
    return hatalar


def _liste_dogrula(alan: str, kural: dict, deger, etiket_durumlari: dict) -> list[dict]:
    if deger is None:
        if not kural["zorunlu"]:
            return []
        if alan == "uyari":
            return [_hata(alan, "zorunlu", "Bir uyarı seç ya da bilinçli olarak 'uyarı yok' seçeneğini onayla.")]
        return [_hata(alan, "zorunlu", "Bu alan zorunlu.")]
    if not isinstance(deger, list):
        return [_hata(alan, "gecersiz_deger", "Liste olmalı.")]
    if not deger and not kural["zorunlu"]:
        return []

    hatalar = []
    if "min_adet" in kural and len(deger) < kural["min_adet"]:
        hatalar.append(_hata(alan, "min_adet", f"En az {kural['min_adet']} öğe olmalı."))
    if "max_adet" in kural and len(deger) > kural["max_adet"]:
        hatalar.append(_hata(alan, "max_adet", f"En fazla {kural['max_adet']} öğe olabilir."))

    gorulenler = set()
    for sira, oge in enumerate(deger):
        yol = f"{alan}[{sira}]"
        if not isinstance(oge, str):
            hatalar.append(_hata(yol, "gecersiz_deger", "Metin olmalı."))
            continue
        if kural["tip"] == "metin_listesi":
            metin = oge.strip()
            if not metin:
                hatalar.append(_hata(yol, "zorunlu", "Boş öğe olamaz."))
                continue
            if "max_karakter" in kural and len(metin) > kural["max_karakter"]:
                hatalar.append(_hata(yol, "max_karakter", f"En fazla {kural['max_karakter']} karakter olabilir."))
            anahtar = tr_kucuk(metin)
        else:
            durumlar = etiket_durumlari.get(kural["etiket_alani"], {})
            if oge not in durumlar:
                hatalar.append(_hata(yol, "gecersiz_etiket", "Bu etiket listede yok."))
            elif not durumlar[oge]:
                hatalar.append(_hata(yol, "pasif_etiket", "Bu etiket pasifleştirildi; başka bir etiket seç."))
            anahtar = oge
        if kural.get("tekrarsiz") and anahtar in gorulenler:
            hatalar.append(_hata(yol, "tekrar", "Bu öğe listede tekrar ediyor."))
        gorulenler.add(anahtar)
    return hatalar


def icerik_dogrula(icerik: dict, etiket_alanlari: dict) -> list[dict]:
    """İçeriği gönderim kurallarına göre doğrular; hata yoksa boş liste döner.

    `etiket_alanlari`, güncel etiket listesinin `alanlar` sözlüğüdür; pasif etiketler
    `pasif_etiket`, listede olmayanlar `gecersiz_etiket` hatası verir.
    """
    etiket_durumlari = {
        alan: {oge["etiket"]: oge["aktif"] for oge in etiketler} for alan, etiketler in etiket_alanlari.items()
    }
    hatalar = []
    for alan, kural in ALAN_KURALLARI.items():
        deger = icerik.get(alan)
        if kural["tip"] in LISTE_TIPLERI:
            hatalar.extend(_liste_dogrula(alan, kural, deger, etiket_durumlari))
        else:
            hatalar.extend(_metin_dogrula(alan, kural, deger))
    return hatalar
