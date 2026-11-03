from sqlmodel import SQLModel, Session, create_engine
import os
from dotenv import load_dotenv

load_dotenv()  # Ortam değişkenlerini .env dosyasından yükler

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://username:password@host:port/database_name"
)

engine = create_engine(DATABASE_URL, echo=True, pool_pre_ping=True)  # echo=True ile SQL sorguları loglanır, pool_pre_ping kopmuş bağlantıyı yeniler

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
