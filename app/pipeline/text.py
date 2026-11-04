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


def split_track(item: str) -> tuple[str, str]:
    """Split a Skiley track line "Title - Artist" on the LAST " - ".

    Titles can contain " - " (e.g. "Quinn the Eskimo (The Mighty Quinn) - Live, December 30, 1985 - Grateful Dead").
    Returns (title, artist); artist is "" if there is no separator.
    """
    if " - " not in item:
        return item.strip(), ""
    title, artist = item.rsplit(" - ", 1)
    return title.strip(), artist.strip()
