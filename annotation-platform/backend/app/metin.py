def tr_kucuk(metin: str) -> str:
    """Türkçe kurallarıyla küçük harfe çevirir (I → ı, İ → i)."""
    return metin.replace("I", "ı").replace("İ", "i").lower()
