from pathlib import Path

import pytest

from app.main import app

yaml = pytest.importorskip("yaml")

SOZLESME = Path(__file__).resolve().parents[2] / "openapi.yaml"
YONTEMLER = ("get", "post", "patch", "put", "delete")

# Sözleşmeye eklenmiş ama henüz uygulanmamış işlemler; uygulayan commit listeyi boşaltır.
HENUZ_UYGULANMAYAN = {
    ("GET", "/memes/{meme_id}/exclusion-vote"),
    ("PUT", "/memes/{meme_id}/exclusion-vote"),
    ("DELETE", "/memes/{meme_id}/exclusion-vote"),
    ("GET", "/exclusion-pool"),
    ("POST", "/exclusion-pool/{meme_id}/decision"),
}


def islemler(yollar: dict, onek: str = "") -> set[tuple[str, str]]:
    return {
        (yontem.upper(), yol[len(onek):])
        for yol, tanim in yollar.items()
        if yol.startswith(onek)
        for yontem in tanim
        if yontem in YONTEMLER
    }


def test_sozlesmedeki_her_islem_uygulanmis():
    sozlesme = islemler(yaml.safe_load(SOZLESME.read_text(encoding="utf-8"))["paths"])
    uygulama = islemler(app.openapi()["paths"], onek="/api/v1")
    assert len(sozlesme) == 50
    assert sozlesme - uygulama == HENUZ_UYGULANMAYAN
    assert uygulama - sozlesme == {("GET", "/health")}
