from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import models  # noqa: F401  (tabloların tanınması için gerekli)
from app.database import create_db_and_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(
    title="MemeScout Annotation API",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/api/v1/health")
def health():
    return {"durum": "calisiyor"}