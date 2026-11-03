from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql
from sqlmodel import select

from app.database import engine, rls_ac
from app.models import Annotation, AuditEntry, Meme
from app.sema import bos_icerik
from tests.yardimci import basliklar

BEKLENEN_TABLOLAR = {
    "user",
    "meme",
    "meme_image",
    "annotation",
    "annotation_version",
    "gold_record",
    "comment",
    "label_list_version",
    "test_query",
    "audit_entry",
}


def test_tum_tablolar_olusur():
    assert BEKLENEN_TABLOLAR <= set(inspect(engine).get_table_names())


def test_annotation_varsayilanlari(session, kullanici_olustur):
    yukleyen = kullanici_olustur("yukleyen", admin=True)
    session.add(Meme(id="m0001", gorsel_yolu="memes/m0001.png", sha256="a" * 64, yukleyen_id=yukleyen.id))
    session.flush()
    session.add(Annotation(meme_id="m0001", annotator_id=yukleyen.id))
    session.commit()

    annotation = session.exec(select(Annotation)).one()
    assert annotation.durum_kodu == "atandi"
    assert annotation.surum == 1
    assert annotation.icerik == bos_icerik()
    assert annotation.icerik["uyari"] is None
    assert annotation.icerik["ornek_durumlar"] == []
    assert annotation.alan_guveni == {}


class _SahteSonuc:
    def __init__(self, satirlar):
        self.satirlar = satirlar

    def scalars(self):
        return self

    def all(self):
        return self.satirlar


class _SahtePostgresBaglantisi:
    dialect = postgresql.dialect()

    def __init__(self, rls_kapali):
        self.rls_kapali = rls_kapali
        self.komutlar = []

    def execute(self, komut, parametreler=None):
        self.komutlar.append((str(komut), parametreler))
        return _SahteSonuc(self.rls_kapali)


def test_rls_yalnizca_kapali_tablolarda_acilir():
    baglanti = _SahtePostgresBaglantisi(rls_kapali=["user", "annotation"])
    assert rls_ac(baglanti) == ["user", "annotation"]

    sorgu, parametreler = baglanti.komutlar[0]
    assert "relrowsecurity" in sorgu
    assert BEKLENEN_TABLOLAR <= set(parametreler["tablolar"])
    assert [komut for komut, _ in baglanti.komutlar[1:]] == [
        'ALTER TABLE "user" ENABLE ROW LEVEL SECURITY',
        "ALTER TABLE annotation ENABLE ROW LEVEL SECURITY",
    ]


def test_rls_zaten_aciksa_tabloya_dokunulmaz():
    baglanti = _SahtePostgresBaglantisi(rls_kapali=[])
    assert rls_ac(baglanti) == []
    assert len(baglanti.komutlar) == 1


def test_kullanici_olusturma_denetim_kaydina_yazilir(client, session, kullanici_olustur):
    yonetici = kullanici_olustur("yonetici", admin=True)
    yanit = client.post(
        "/api/v1/users",
        json={"kullanici_adi": "yeniuye", "gorunen_ad": "Yeni", "sifre": "YeniSifre123", "takma_ad": "a9"},
        headers=basliklar(yonetici),
    )
    assert yanit.status_code == 201

    kayit = session.exec(select(AuditEntry).where(AuditEntry.kayit_tipi == "kullanici")).one()
    assert kayit.kullanici_id == yonetici.id
    assert kayit.kayit_id == yanit.json()["id"]
    assert kayit.islem == "olusturma"
    assert kayit.yeni_deger == {"kullanici_adi": "yeniuye", "gorunen_ad": "Yeni", "takma_ad": "a9", "admin": False}
