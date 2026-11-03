import pytest

from app.olcum import cohen_kappa, krippendorff_alpha, masi_mesafesi

A, B, C = "a", "b", "c"


def kume(*etiketler):
    return frozenset(etiketler)


def test_cohen_kappa_elle_hesaplanan_ornek():
    # p_o = 3/4, p_e = 0.5 × 0.25 + 0.5 × 0.75 = 0.5 → kappa = 0.5
    assert cohen_kappa([(A, A), (A, B), (B, B), (B, B)]) == pytest.approx(0.5)


def test_cohen_kappa_tam_uyum_ve_tanimsiz_durumlar():
    assert cohen_kappa([(A, A), (B, B)]) == pytest.approx(1.0)
    assert cohen_kappa([(A, A), (A, A)]) is None  # tek kategori: beklenen uyum 1, kappa tanımsız
    assert cohen_kappa([]) is None


@pytest.mark.parametrize(
    "birinci, ikinci, beklenen",
    [
        (kume(A), kume(A), 0.0),
        (kume(), kume(), 0.0),
        (kume(A), kume(A, B), 1 - (1 / 2) * (2 / 3)),
        (kume(A, B), kume(B, C), 1 - (1 / 3) * (1 / 3)),
        (kume(A), kume(B), 1.0),
        (kume(), kume(A), 1.0),
    ],
)
def test_masi_mesafesi(birinci, ikinci, beklenen):
    assert masi_mesafesi(birinci, ikinci) == pytest.approx(beklenen)
    assert masi_mesafesi(ikinci, birinci) == pytest.approx(beklenen)


def test_krippendorff_alpha_elle_hesaplanan_ornek():
    # D_o = (0 + 2/3 + 1) / 3 = 5/9; altı değerin sıralı çiftlerinde D_e = 64/90 → alpha = 1 - (5/9)/(64/90) = 0.21875
    ciftler = [(kume(A), kume(A)), (kume(A, B), kume(A)), (kume(C), kume(B))]
    assert krippendorff_alpha(ciftler, masi_mesafesi) == pytest.approx(0.21875)


def test_krippendorff_alpha_uc_durumlar():
    assert krippendorff_alpha([(kume(A), kume(A)), (kume(B), kume(B))], masi_mesafesi) == pytest.approx(1.0)
    assert krippendorff_alpha([(kume(A), kume(B)), (kume(B), kume(A))], masi_mesafesi) == pytest.approx(-0.5)
    assert krippendorff_alpha([(kume(A), kume(A)), (kume(A), kume(A))], masi_mesafesi) is None
    assert krippendorff_alpha([], masi_mesafesi) is None
