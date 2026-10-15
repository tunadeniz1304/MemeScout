from getpass import getpass

from sqlmodel import Session, select

from app.database import create_db_and_tables, engine
from app.models import User
from app.security import sifre_hashle


def main():
    create_db_and_tables()
    kullanici_adi = input("Kullanıcı adı: ").strip()
    gorunen_ad = input("Görünen ad: ").strip()
    takma_ad = input("Takma ad (ör. a1): ").strip()
    sifre = getpass("Şifre (en az 8 karakter, yazarken görünmez): ")

    if len(sifre) < 8:
        print("Şifre en az 8 karakter olmalı.")
        return

    with Session(engine) as session:
        mevcut = session.exec(select(User).where(User.kullanici_adi == kullanici_adi)).first()
        if mevcut:
            print("Bu kullanıcı adı zaten var.")
            return
        session.add(
            User(
                kullanici_adi=kullanici_adi,
                gorunen_ad=gorunen_ad,
                takma_ad=takma_ad,
                sifre_hash=sifre_hashle(sifre),
                admin=True,
            )
        )
        session.commit()

    print(f"Admin oluşturuldu: {kullanici_adi}")


if __name__ == "__main__":
    main()