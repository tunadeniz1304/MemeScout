from app.models import User
from app.security import token_olustur


def basliklar(kullanici: User) -> dict:
    return {"Authorization": f"Bearer {token_olustur(kullanici.id)}"}


def gecerli_icerik(**degisiklikler) -> dict:
    """Gönderim kurallarının hepsini geçen bir annotation içeriği."""
    icerik = {
        "tur": "template",
        "ad": "Hayırdır inşallah",
        "kaynak": "Kemal Sunal",
        "vlm_aciklama": "Kaşlarını kaldırmış, şüpheyle bakan bir adam; altta beyaz yazı var.",
        "durum": "Beklenmedik ve şüpheli bir teklif karşısında temkinli şaşkınlık.",
        "ornek_durumlar": [
            "Patron cuma akşamı bir dakika gelir misin yazdı",
            "Hiç konuşmadığın biri naber kanka dedi",
            "Ev sahibi kirayı konuşalım dedi",
        ],
        "uygun_olmayan_durumlar": ["Arkadaşın gerçekten kötü bir haber verdiğinde"],
        "kulturel_bilgi": "Kemal Sunal filmlerindeki şüpheli bakış sahnesine gönderme.",
        "anahtar_kelimeler": ["hayırdır", "şüpheli bakış", "işkillenmek"],
        "duygu": ["suphe", "saskinlik"],
        "niyet": ["tepki_gosterme"],
        "mekanizma": ["ironi"],
        "uyari": [],
        "notlar": None,
    }
    icerik.update(degisiklikler)
    return icerik
