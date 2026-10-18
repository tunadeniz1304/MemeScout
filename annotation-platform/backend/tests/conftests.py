import pytest
from sqlmodel import SQLModel, create_engine, Session
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_session

# Bellek içi SQLite motoru oluşturulur
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DATABASE_URL, echo=False)


@pytest.fixture(scope="session", autouse=True)
def create_test_database():
    SQLModel.metadata.create_all(engine)
    yield
    


@pytest.fixture()
def session():
    with Session(engine) as session:
        yield session

@pytest.fixture()
def client(session):
   
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
