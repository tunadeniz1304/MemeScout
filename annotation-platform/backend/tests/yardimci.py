from app.models import User
from app.security import token_olustur


def basliklar(kullanici: User) -> dict:
    return {"Authorization": f"Bearer {token_olustur(kullanici.id)}"}
