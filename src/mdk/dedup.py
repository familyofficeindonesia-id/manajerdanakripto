"""Deduplikasi: URL kanonik (di lapisan basis data) + kemiripan judul."""
from __future__ import annotations

import re

from rapidfuzz import fuzz

_STOPWORD = {
    "the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "is", "are",
    "as", "at", "by", "with", "from", "says", "said", "after", "amid", "over",
    "yang", "dan", "di", "ke", "dari", "untuk", "pada", "kata",
}


def normalkan_judul(judul: str) -> str:
    judul = re.sub(r"[^\w\s]", " ", (judul or "").lower())
    kata = [k for k in judul.split() if k not in _STOPWORD and len(k) > 2]
    return " ".join(sorted(set(kata)))


def kemiripan(a: str, b: str) -> float:
    return fuzz.token_set_ratio(normalkan_judul(a), normalkan_judul(b))


def cari_duplikat(judul: str, kandidat: list[tuple[str, str]],
                  ambang: float = 82.0) -> str | None:
    """Kembalikan id kandidat pertama yang mirip, atau None."""
    for id_, judul_lain in kandidat:
        if kemiripan(judul, judul_lain) >= ambang:
            return id_
    return None


def saring_duplikat(item: list, ambang: float = 82.0) -> list:
    """Buang duplikat internal dalam satu kumpulan item (menyimpan skor tertinggi)."""
    disimpan: list = []
    for it in sorted(item, key=lambda x: -getattr(x, "skor", 0)):
        if not any(kemiripan(it.judul, s.judul) >= ambang for s in disimpan):
            disimpan.append(it)
    return disimpan
