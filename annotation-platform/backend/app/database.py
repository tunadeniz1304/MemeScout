from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool
import os
from dotenv import load_dotenv

load_dotenv()  # Ortam değişkenlerini .env dosyasından yükler

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://username:password@host:port/database_name"
)


def motor_ayarlari(url: str) -> dict:
    ayarlar = {"echo": True, "pool_pre_ping": True}  # echo=True ile SQL sorguları loglanır, pool_pre_ping kopmuş bağlantıyı yeniler
    if url.startswith("sqlite"):
        # FastAPI istekleri farklı iş parçacıklarında çalıştırır; SQLite bağlantısı bunlar arasında paylaşılır.
        ayarlar["connect_args"] = {"check_same_thread": False}
        if url in ("sqlite://", "sqlite:///:memory:"):
            # Bellek içi veritabanı bağlantıyla birlikte yok olur; tek bağlantıda tutulur.
            ayarlar["poolclass"] = StaticPool
    return ayarlar


engine = create_engine(DATABASE_URL, **motor_ayarlari(DATABASE_URL))

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
