"""Etiketleyiciler arası uyum ölçüleri (docs/annotation.md §6).

Her ölçü iki etiketleyicili birimlerle çalışır: `ciftler`, her biri (birinci, ikinci) olan
değer çiftleri listesidir. Ölçü tanımsızsa (veri yok ya da hiç çeşitlilik yok) None döner.
"""

from typing import Callable, Hashable, Optional

DUSUK_UYUM_SINIRI = 0.4


def cohen_kappa(ciftler: list[tuple[Hashable, Hashable]]) -> Optional[float]:
    """Tek seçimli alanlar için Cohen's kappa. Birinci değer birinci etiketleyicinindir."""
    n = len(ciftler)
    if n == 0:
        return None
    kategoriler = {deger for cift in ciftler for deger in cift}
    gozlenen = sum(1 for a, b in ciftler if a == b) / n
    beklenen = sum(
        (sum(1 for a, _ in ciftler if a == k) / n) * (sum(1 for _, b in ciftler if b == k) / n)
        for k in kategoriler
    )
    if beklenen >= 1:
        return None
    return (gozlenen - beklenen) / (1 - beklenen)


def masi_mesafesi(a: frozenset, b: frozenset) -> float:
    """MASI mesafesi (Passonneau 2006): 1 - Jaccard × monotonluk."""
    if a == b:
        return 0.0
    jaccard = len(a & b) / len(a | b)
    if a <= b or b <= a:
        monotonluk = 2 / 3
    elif a & b:
        monotonluk = 1 / 3
    else:
        monotonluk = 0.0
    return 1 - jaccard * monotonluk


def krippendorff_alpha(ciftler: list[tuple], mesafe: Callable[[object, object], float]) -> Optional[float]:
    """Her birimde iki değer, eksik değer yok: alpha = 1 - D_o / D_e."""
    n = len(ciftler)
    if n == 0:
        return None
    gozlenen = sum(mesafe(a, b) for a, b in ciftler) / n
    degerler = [deger for cift in ciftler for deger in cift]
    toplam = len(degerler)
    beklenen = sum(
        mesafe(degerler[i], degerler[j]) for i in range(toplam) for j in range(toplam) if i != j
    ) / (toplam * (toplam - 1))
    if beklenen == 0:
        return None
    return 1 - gozlenen / beklenen


def yuvarla(deger: Optional[float]) -> Optional[float]:
    return None if deger is None else round(deger, 4)
