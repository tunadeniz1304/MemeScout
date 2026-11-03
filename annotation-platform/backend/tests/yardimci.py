import struct
import zlib

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


def png_olustur(tohum: int = 0) -> bytes:
    """Tohuma göre rengi değişen 1x1 geçerli PNG; her tohum farklı sha256 verir."""

    def parca(tip: bytes, veri: bytes) -> bytes:
        return struct.pack(">I", len(veri)) + tip + veri + struct.pack(">I", zlib.crc32(tip + veri) & 0xFFFFFFFF)

    renk = bytes([tohum % 256, (tohum // 256) % 256, (tohum // 65536) % 256])
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + parca(b"IHDR", ihdr)
        + parca(b"IDAT", zlib.compress(b"\x00" + renk))
        + parca(b"IEND", b"")
    )
