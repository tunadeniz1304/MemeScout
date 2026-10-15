from fastapi import Request
from fastapi.responses import JSONResponse


class ApiHatasi(Exception):
    def __init__(self, status_kodu: int, kod: str, mesaj: str, detay: dict | None = None):
        self.status_kodu = status_kodu
        self.kod = kod
        self.mesaj = mesaj
        self.detay = detay


async def api_hatasi_handler(request: Request, exc: ApiHatasi):
    hata = {"kod": exc.kod, "mesaj": exc.mesaj}
    if exc.detay:
        hata["detay"] = exc.detay
    return JSONResponse(status_code=exc.status_kodu, content={"hata": hata})