"""Textos que ven las personas."""


def plural(n: int, uno: str, varios: str) -> str:
    """La cantidad con la palabra que le toca: singular con 1, plural con cualquier otra."""
    return f"{n} {uno if n == 1 else varios}"
