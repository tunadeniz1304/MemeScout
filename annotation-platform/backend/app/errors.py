
import logging
from typing import Optional

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("uvicorn.error")

class ApiHatasi(Exception):
    def __init__(
        self,
        status_kodu: int,
        kod: str,
        mesaj: str,
        detay: Optional[dict] = None,
        alanlar: Optional[list[dict]] = None,
    ):
        self.status_kodu = status_kodu
        self.kod = kod
        self.mesaj = mesaj
        self.detay = detay
        self.alanlar = alanlar


def hata_yaniti(status_kodu: int, kod: str, mesaj: str, detay=None, alanlar=None, headers=None):
    hata = {"kod": kod, "mesaj": mesaj}
    if alanlar:
        hata["alanlar"] = alanlar
    if detay:
        hata["detay"] = detay
    return JSONResponse(status_code=status_kodu, content={"hata": hata}, headers=headers)


async def api_hatasi_handler(request: Request, exc: ApiHatasi):
    return hata_yaniti(exc.status_kodu, exc.kod, exc.mesaj, exc.detay, exc.alanlar)


# --- FastAPI'nin istek doğrulama hataları sözleşmedeki FieldError biçimine çevrilir ---

_KONUMLAR = {"body", "query", "path", "header", "cookie"}


def alan_yolu(loc) -> str:
    parcalar = list(loc)
    if parcalar and parcalar[0] in _KONUMLAR:
        parcalar = parcalar[1:]
    yol = ""
    for parca in parcalar:
        if isinstance(parca, int):
            yol += f"[{parca}]"
        else:
            yol += f".{parca}" if yol else str(parca)
    return yol or "body"


def _alan_hatasi(hata: dict) -> dict:
    tip = hata.get("type", "")
    ctx = hata.get("ctx") or {}
    alan = alan_yolu(hata.get("loc", ()))
    if tip == "missing":
        return {"alan": alan, "kural": "zorunlu", "mesaj": "Bu alan zorunlu."}
    if tip == "string_too_short":
        return {"alan": alan, "kural": "min_karakter", "mesaj": f"En az {ctx.get('min_length')} karakter olmalı."}
    if tip == "string_too_long":
        return {"alan": alan, "kural": "max_karakter", "mesaj": f"En fazla {ctx.get('max_length')} karakter olabilir."}
    if tip == "too_short":
        return {"alan": alan, "kural": "min_adet", "mesaj": f"En az {ctx.get('min_length')} öğe olmalı."}
    if tip == "too_long":
        return {"alan": alan, "kural": "max_adet", "mesaj": f"En fazla {ctx.get('max_length')} öğe olabilir."}
    if tip in ("greater_than_equal", "greater_than"):
        sinir = ctx.get("ge", ctx.get("gt"))
        return {"alan": alan, "kural": "aralik", "mesaj": f"{sinir} veya daha büyük olmalı."}
    if tip in ("less_than_equal", "less_than"):
        sinir = ctx.get("le", ctx.get("lt"))
        return {"alan": alan, "kural": "aralik", "mesaj": f"{sinir} veya daha küçük olmalı."}
    if tip in ("literal_error", "enum"):
        return {"alan": alan, "kural": "gecersiz_deger", "mesaj": f"Geçerli değerler: {ctx.get('expected', '')}."}
    if tip == "json_invalid":
        return {"alan": "body", "kural": "gecersiz_deger", "mesaj": "İstek gövdesi geçerli bir JSON değil."}
    return {"alan": alan, "kural": "gecersiz_deger", "mesaj": "Geçersiz değer."}


async def dogrulama_hatasi_handler(request: Request, exc: RequestValidationError):
    alanlar = [_alan_hatasi(hata) for hata in exc.errors()]
    return hata_yaniti(422, "DOGRULAMA", "İstekteki bazı alanlar eksik veya hatalı.", alanlar=alanlar)


_HTTP_KODLARI = {
    401: ("YETKISIZ", "Giriş yapmanız gerekiyor."),
    403: ("YASAK", "Bu işlem için yetkiniz yok."),
    404: ("BULUNAMADI", "İstenen kaynak bulunamadı."),
    405: ("YONTEM_DESTEKLENMIYOR", "Bu adres bu HTTP yöntemini desteklemiyor."),
}


async def http_hatasi_handler(request: Request, exc: StarletteHTTPException):
    kod, mesaj = _HTTP_KODLARI.get(exc.status_code, ("HATA", "İstek işlenemedi."))
    return hata_yaniti(exc.status_code, kod, mesaj, headers=getattr(exc, "headers", None))


async def veritabani_hatasi_handler(request: Request, exc: SQLAlchemyError):
    # Bu hatalar CORS katmanının içinde yakalanır; böylece tarayıcı yanıtı okuyabilir.
    logger.error("Veritabanı hatası: %s %s", request.method, request.url.path, exc_info=exc)
    if isinstance(exc, OperationalError):
        return hata_yaniti(503, "VERITABANI_ERISILEMEZ", "Veritabanına şu an ulaşılamıyor. Biraz sonra tekrar deneyin.")
    if isinstance(exc, IntegrityError):
        return hata_yaniti(409, "CAKISMA", "Kayıt aynı anda başka bir işlemle değişti. Tekrar deneyin.")
    return hata_yaniti(500, "SUNUCU_HATASI", "Beklenmeyen bir hata oluştu.")


async def beklenmeyen_hata_handler(request: Request, exc: Exception):
    return hata_yaniti(500, "SUNUCU_HATASI", "Beklenmeyen bir hata oluştu.")
