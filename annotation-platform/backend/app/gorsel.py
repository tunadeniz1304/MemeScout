"""Yüklenen dosyanın görsel türünü uzantıya değil ilk baytlarına bakarak belirler."""

from typing import Optional

UZANTILAR = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}
GORSEL_UZANTILARI = {"jpg", "jpeg", "png", "webp", "gif"}

# BulkUploadResult.reddedilen[].sebep değerleri
DESTEKLENMEYEN_TUR = "desteklenmeyen_tur"
BOZUK_DOSYA = "bozuk_dosya"
KOPYA = "kopya"


def _tur(veri: bytes) -> Optional[str]:
    if veri.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if veri.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if veri[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if len(veri) >= 12 and veri[:4] == b"RIFF" and veri[8:12] == b"WEBP":
        return "image/webp"
    return None


def _butun_mu(tur: str, veri: bytes) -> bool:
    # Yarım inmiş dosyaları yakalamak için biçimin bitiş işaretine bakılır.
    if tur == "image/jpeg":
        return veri.rfind(b"\xff\xd9") > 2
    if tur == "image/png":
        return b"IEND" in veri[-32:]
    if tur == "image/gif":
        return veri.rstrip(b"\x00").endswith(b";")
    return int.from_bytes(veri[4:8], "little") + 8 <= len(veri)  # webp: RIFF boyutu


def _gorsel_gibi_mi(dosya_adi: Optional[str], icerik_tipi: Optional[str]) -> bool:
    uzanti = (dosya_adi or "").rsplit(".", 1)[-1].lower() if "." in (dosya_adi or "") else ""
    return uzanti in GORSEL_UZANTILARI or (icerik_tipi or "").startswith("image/")


def incele(dosya_adi: Optional[str], icerik_tipi: Optional[str], veri: bytes) -> tuple[Optional[str], Optional[str]]:
    """(MIME türü, None) ya da (None, red sebebi) döner."""
    tur = _tur(veri)
    if tur is None:
        return None, BOZUK_DOSYA if _gorsel_gibi_mi(dosya_adi, icerik_tipi) else DESTEKLENMEYEN_TUR
    if not _butun_mu(tur, veri):
        return None, BOZUK_DOSYA
    return tur, None
