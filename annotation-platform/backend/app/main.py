

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app import models  # noqa: F401
from app.database import create_db_and_tables
from app.errors import ApiHatasi, api_hatasi_handler
from app.routes import auth, users

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
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        frontend_url,
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
