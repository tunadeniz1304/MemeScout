from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401  (tabloların tanınması için gerekli)
from app.database import create_db_and_tables
from app.errors import ApiHatasi, api_hatasi_handler
from app.routes import auth, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(
    title="MemeScout Annotation API",
    version="0.1.0",
    lifespan=lifespan,
)

# The Vite development server and local API use different origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)

app.add_exception_handler(ApiHatasi, api_hatasi_handler)
app.include_router(auth.router)
app.include_router(users.router)


@app.get("/api/v1/health")
def health():
    return {"durum": "calisiyor"}
