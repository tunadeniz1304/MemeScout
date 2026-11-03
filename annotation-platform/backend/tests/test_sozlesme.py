from pathlib import Path

import pytest

from app.main import app

yaml = pytest.importorskip("yaml")

SOZLESME = Path(__file__).resolve().parents[2] / "openapi.yaml"
YONTEMLER = ("get", "post", "patch", "put", "delete")
# Sözleşmeye eklenip henüz uygulanmamış işlemler (ADR-0001: önce sözleşme, sonra kod).
HENUZ_UYGULANMAYAN = {("POST", "/memes/ai-drafts")}


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
    assert len(sozlesme) == 45
    assert sozlesme - uygulama == HENUZ_UYGULANMAYAN
    assert uygulama - sozlesme == {("GET", "/health")}
