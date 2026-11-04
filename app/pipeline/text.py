"""Shared text helpers for matching names across lists and sources."""
import re
import unicodedata

_CURLY = {"’": "'", "‘": "'", "“": '"', "”": '"'}


def norm(s: str) -> str:
    """Comparison key for list items (spec R4): NFKC, straight quotes, collapsed whitespace, casefold.

    Output text always keeps the original; this is only for comparing.
    """
    s = unicodedata.normalize("NFKC", s or "")
    for a, b in _CURLY.items():
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip().casefold()


_DASHES = "‐‑‒–—−"


def artist_key(name: str) -> str:
    """Cache key for an artist: norm() plus '&' -> 'and', unicode dashes -> '-', leading 'the ' dropped.

    So "The Front Bottoms" / "Front Bottoms" and "Hootie & The Blowfish" / "Hootie and the Blowfish" share a key.
    """
    s = norm(name)
    for d in _DASHES:
        s = s.replace(d, "-")
    s = s.replace("&", " and ")
    s = re.sub(r"\s+", " ", s).strip()
    return re.sub(r"^the ", "", s)


def split_track(item: str) -> tuple[str, str]:
    """Split a Skiley track line "Title - Artist" on the LAST " - ".

    Titles can contain " - " (e.g. "Quinn the Eskimo (The Mighty Quinn) - Live, December 30, 1985 - Grateful Dead").
    Returns (title, artist); artist is "" if there is no separator.
    """
    if " - " not in item:
        return item.strip(), ""
    title, artist = item.rsplit(" - ", 1)
    return title.strip(), artist.strip()
