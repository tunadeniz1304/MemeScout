from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy import event, text
from sqlalchemy.pool import StaticPool
import os
from dotenv import load_dotenv

load_dotenv()  # Ortam değişkenlerini .env dosyasından yükler


def veritabani_adresi() -> str:
    if os.getenv("VERCEL_ENV") == "preview":
        # Vercel önizleme sürümleri canlı veritabanına dokunmasın: tablo oluşturma ya da deneme verisi
        # canlıya gitmesin diye DATABASE_URL tanımlı olsa da boş, bellek içi SQLite ile açılırlar.
        print("Önizleme sürümü: DATABASE_URL yerine bellek içi SQLite kullanılıyor.", flush=True)
        return "sqlite://"
    return os.getenv(
        "DATABASE_URL",
        "postgresql://username:password@host:port/database_name"
    )


DATABASE_URL = veritabani_adresi()


def motor_ayarlari(url: str) -> dict:
    # SQL_ECHO=1 ile SQL sorguları loglanır. Varsayılan kapalı: parametrelerle birlikte şifre hash'leri,
    # annotation metinleri ve görsel baytları da loglara düşerdi. pool_pre_ping kopmuş bağlantıyı yeniler.
    ayarlar = {"echo": os.getenv("SQL_ECHO") == "1", "pool_pre_ping": True}
    if url.startswith("sqlite"):
        # FastAPI istekleri farklı iş parçacıklarında çalıştırır; SQLite bağlantısı bunlar arasında paylaşılır.
        ayarlar["connect_args"] = {"check_same_thread": False}
        if url in ("sqlite://", "sqlite:///:memory:"):
            # Bellek içi veritabanı bağlantıyla birlikte yok olur; tek bağlantıda tutulur.
            ayarlar["poolclass"] = StaticPool
    return ayarlar


engine = create_engine(DATABASE_URL, **motor_ayarlari(DATABASE_URL))

if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def _sqlite_yabanci_anahtarlar(dbapi_baglantisi, _):
        # SQLite yabancı anahtarları varsayılan olarak denetlemez; PostgreSQL gibi davransın.
        dbapi_baglantisi.execute("PRAGMA foreign_keys=ON")

# Tablolar oluşturulurken kullanılan PostgreSQL danışma kilidinin anahtarı (rastgele seçilmiş sabit).
TABLO_KILIDI = 4290001


def rls_ac(baglanti) -> list[str]:
    """public şemadaki uygulama tablolarında satır düzeyi güvenliği açar.

    Backend tablo sahibi rolüyle bağlandığı için RLS onu etkilemez; Supabase'in
    herkese açık API'si ise politika olmadan bu tablolara erişemez. Zaten açık
    olan tablolara dokunulmaz, bu yüzden her açılışta tekrar çalışabilir.
    """
    tablolar = [tablo.name for tablo in SQLModel.metadata.sorted_tables]
    kapali = baglanti.execute(
        text(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = current_schema() AND c.relkind = 'r' "
            "AND NOT c.relrowsecurity AND c.relname = ANY(:tablolar)"
        ),
        {"tablolar": tablolar},
    ).scalars().all()
    hazirlayici = baglanti.dialect.identifier_preparer
    for tablo in kapali:
        baglanti.execute(text(f"ALTER TABLE {hazirlayici.quote(tablo)} ENABLE ROW LEVEL SECURITY"))
    return list(kapali)


def create_db_and_tables():
    from app import models  # noqa: F401  (tabloların metadata'ya kaydı için)
    from app.etiketler import etiket_listesi_tohumla

    with engine.begin() as baglanti:
        postgres = baglanti.dialect.name == "postgresql"
        if postgres:
            # Aynı anda açılan iki sunucu örneği tabloları birlikte oluşturmaya çalışmasın.
            baglanti.execute(text("SELECT pg_advisory_xact_lock(:anahtar)"), {"anahtar": TABLO_KILIDI})
        SQLModel.metadata.create_all(baglanti)
        if postgres:
            rls_ac(baglanti)
        etiket_listesi_tohumla(baglanti)

def get_session():
    with Session(engine) as session:
        yield session
