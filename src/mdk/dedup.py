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


# ---------------------------------------------------------------------------
# DUA AMBANG, BUKAN SATU. Diukur pada judul nyata dari jalan #122
# (4 September 2026), bukan diperkirakan.
#
# Perbandingan LINTAS BAHASA (judul Indonesia yang sudah terbit lawan judul
# Inggris kandidat) kehilangan hampir seluruh kosakata pada penerjemahan. Nama
# diri bertahan, selebihnya berubah total, sehingga peristiwa yang sama persis
# hanya mencetak 65-69. Ambangnya harus tetap tinggi: menurunkannya mulai
# membuang berita sah, karena artikel yang memang berbeda juga jatuh di 58-68.
#
# Perbandingan SEBAHASA jauh lebih tajam. Pada jalan #122:
#
#   Indonesia lawan Indonesia
#     "Proyeksikan Ethereum Tembus 10.000" vs "Proyeksikan Bitcoin US$1 Juta
#      pada 2030 dan Soroti Ethereum"                          79,5  DUPLIKAT
#     "Prediksi Bitcoin Capai US$1 Juta"  vs judul di atas      73,9  DUPLIKAT
#     "Pertahankan Posisi Beli Bitcoin"   vs judul di atas      63,0  beda
#     pasangan non-Hayes tertinggi                              51,7  beda
#
#   Inggris lawan Inggris (judul sumber)
#     "Forecasts Ethereum to Reach $10,000" vs
#     "Predicts Ethereum Price to Hit $10K"                     75,3  DUPLIKAT
#     "Forecasts Ethereum..." vs "Says Ignore Warsh..."         62,5  beda
#
# Duplikat mendarat di 73-80, yang benar-benar beda mentok di 63. Ambang 72
# duduk di celah itu.
#
# PERINGATAN: celah 63-74 diukur dari 10 pasang judul saja. Margin sembilan
# poin itu tipis. Bila kelak ada berita sah yang terbuang sebagai [KEMBAR],
# angka inilah yang pertama harus ditinjau — dan tinjau dengan mengukur, bukan
# dengan menerka.
# ---------------------------------------------------------------------------
AMBANG_LINTAS_BAHASA = 82.0
AMBANG_SEBAHASA = 72.0


def cari_duplikat(judul: str, kandidat: list[tuple[str, str]],
                  ambang: float = AMBANG_LINTAS_BAHASA) -> str | None:
    """Kembalikan id kandidat pertama yang mirip, atau None."""
    for id_, judul_lain in kandidat:
        if kemiripan(judul, judul_lain) >= ambang:
            return id_
    return None


def saring_duplikat(item: list, ambang: float = AMBANG_LINTAS_BAHASA) -> list:
    """Buang duplikat internal dalam satu kumpulan item (menyimpan skor tertinggi)."""
    disimpan: list = []
    for it in sorted(item, key=lambda x: -getattr(x, "skor", 0)):
        if not any(kemiripan(it.judul, s.judul) >= ambang for s in disimpan):
            disimpan.append(it)
    return disimpan
