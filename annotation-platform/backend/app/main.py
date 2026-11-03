from contextlib import asynccontextmanager
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import models  # noqa: F401
from app.database import create_db_and_tables
from app.errors import (
    ApiHatasi,
    api_hatasi_handler,
    beklenmeyen_hata_handler,
    dogrulama_hatasi_handler,
    http_hatasi_handler,
    veritabani_hatasi_handler,
)
from app.routes import annotations, assignments, auth, comments, memes, queries, reviews, schema, users

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(
    title="MemeScout Annotation API",
    version="0.1.0",
    lifespan=lifespan,
)

# Sonunda "/" varsa origin eşleşmez, bu yüzden temizliyoruz.
frontend_url = os.getenv("FRONTEND_URL", "https://seng-429.vercel.app").strip().rstrip("/")

# Router'lardan ÖNCE eklenmeli.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        frontend_url,
    ],
    # Ana domain, git-branch ve deploy'a özel tüm Vercel adreslerine izin verir
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Geçici debug: hangi Origin'in geldiğini Render loglarında görmek için ---
# Sorun çözülünce silebilirsiniz. CORS middleware'inden SONRA eklendiği için
# en dış katmanda çalışır ve preflight istekleri de görünür.
@app.middleware("http")
async def log_origin(request, call_next):
    print(
        "ORIGIN:", request.headers.get("origin"),
        "| METHOD:", request.method,
        "| PATH:", request.url.path,
        "| REQ-HEADERS:", request.headers.get("access-control-request-headers"),
        flush=True,
    )
    return await call_next(request)

app.add_exception_handler(ApiHatasi, api_hatasi_handler)
app.add_exception_handler(RequestValidationError, dogrulama_hatasi_handler)
app.add_exception_handler(StarletteHTTPException, http_hatasi_handler)
app.add_exception_handler(SQLAlchemyError, veritabani_hatasi_handler)
app.add_exception_handler(Exception, beklenmeyen_hata_handler)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(schema.router)
app.include_router(memes.router)
app.include_router(assignments.router)
app.include_router(annotations.router)
app.include_router(comments.router)
app.include_router(reviews.router)
app.include_router(queries.router)


@app.get("/")
def root():
    return {"durum": "calisiyor", "docs": "/docs"}


@app.get("/api/v1/health")
def health():
    return {"durum": "calisiyor"}