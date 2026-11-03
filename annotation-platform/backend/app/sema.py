"""Annotation içerik şeması: alanlar ve gönderim kuralları (docs/annotation.md §3.2).

Kurallar tek yerde tanımlıdır; `GET /schema/annotation` bunları olduğu gibi döner,
backend gönderimde aynı kurallarla doğrular.
"""

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
