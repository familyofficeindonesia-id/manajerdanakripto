"""
uji_tanggal.py — Uji kelayakan verifikasi tanggal terbit ke halaman penerbit.

Skrip ini TIDAK mengubah apa pun. Ia hanya menjawab tiga pertanyaan:

  1. Dapatkah tautan pengalihan Google News (`news.google.com/rss/articles/CBMi...`)
     diikuti sampai ke alamat penerbit aslinya dari dalam GitHub Actions?
  2. Dapatkah tanggal terbit asli dibaca dari metadata halaman penerbit?
  3. Seberapa jauh tanggal asli itu meleset dari `sumber_terbit` yang tersimpan
     di basis data?

Hasilnya menentukan apakah verifikasi tanggal otomatis layak dibangun.

Pemakaian:
    python src/mdk/uji_tanggal.py --db data/mdk.sqlite3 --jumlah 8
    python src/mdk/uji_tanggal.py --db data/mdk.sqlite3 --penerbit yellow
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    sys.exit("GAGAL: paket `requests` tidak tersedia.")

try:
    from alat_kesegaran import parse_tanggal
except ImportError:
    try:
        from mdk.alat_kesegaran import parse_tanggal
    except ImportError:
        sys.exit("GAGAL: alat_kesegaran.py tidak ditemukan.")

KEPALA = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

BATAS_WAKTU = 20


# ===========================================================================
# Tahap 1 — memecahkan tautan Google News
# ===========================================================================

def _metode_1_pengalihan(url: str) -> tuple[str | None, str]:
    """Ikuti pengalihan HTTP biasa."""
    try:
        r = requests.get(url, headers=KEPALA, timeout=BATAS_WAKTU,
                         allow_redirects=True)
    except requests.RequestException as e:
        return None, f"galat jaringan: {type(e).__name__}"

    akhir = r.url or ""
    if "news.google.com" not in akhir and akhir.startswith("http"):
        return akhir, "berhasil lewat pengalihan HTTP"
    return None, f"berhenti di {akhir[:60]} (status {r.status_code})"


def _metode_2_dari_html(url: str) -> tuple[str | None, str]:
    """Cari alamat penerbit yang tertanam di dalam HTML halaman Google News."""
    try:
        r = requests.get(url, headers=KEPALA, timeout=BATAS_WAKTU,
                         allow_redirects=True)
    except requests.RequestException as e:
        return None, f"galat jaringan: {type(e).__name__}"

    html = r.text or ""
    pola = [
        r'data-n-au="(https?://[^"]+)"',
        r'<c-wiz[^>]*data-p="[^"]*?(https?://[^"&]+)',
        r'<link[^>]+rel="canonical"[^>]+href="(https?://[^"]+)"',
        r'url=(https?://[^"\'&<>]+)',
        r'<a[^>]+href="(https?://(?!news\.google|accounts\.google|policies\.google)[^"]+)"',
    ]
    for p in pola:
        for m in re.finditer(p, html, re.I):
            kandidat = m.group(1)
            if "google.com" in kandidat:
                continue
            return kandidat, "berhasil dari HTML"
    return None, f"tidak ada alamat penerbit di HTML ({len(html)} bita)"


def _metode_3_batchexecute(url: str) -> tuple[str | None, str]:
    """Metode resmi internal Google News (eksperimental, bisa berubah sewaktu-waktu)."""
    try:
        r = requests.get(url, headers=KEPALA, timeout=BATAS_WAKTU)
        html = r.text or ""
    except requests.RequestException as e:
        return None, f"galat jaringan: {type(e).__name__}"

    m_id = re.search(r'data-n-a-id="([^"]+)"', html)
    m_sg = re.search(r'data-n-a-sg="([^"]+)"', html)
    m_ts = re.search(r'data-n-a-ts="([^"]+)"', html)
    if not (m_sg and m_ts):
        return None, "tanda tangan (data-n-a-sg/ts) tidak ditemukan di halaman"

    art_id = url.rstrip("/").rsplit("/", 1)[-1].split("?")[0]
    payload = json.dumps([[[
        "Fbv4je",
        json.dumps(["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1,
                                    "US:en", None, 1, None, None, None, None,
                                    None, 0, 1],
                    "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
                    art_id, int(m_ts.group(1)), m_sg.group(1)]),
        None, "generic"]]])

    try:
        r2 = requests.post(
            "https://news.google.com/_/DotsSplashUi/data/batchexecute",
            headers={**KEPALA,
                     "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
            data={"f.req": payload}, timeout=BATAS_WAKTU)
    except requests.RequestException as e:
        return None, f"galat jaringan pada batchexecute: {type(e).__name__}"

    m = re.search(r'"(https?://(?!news\.google)[^"\\]+)"', r2.text or "")
    if m:
        return m.group(1), "berhasil lewat batchexecute"
    return None, f"batchexecute tidak mengembalikan alamat (status {r2.status_code})"


def pecahkan(url: str) -> tuple[str | None, str]:
    if "news.google.com" not in url:
        return url, "bukan tautan Google News, dipakai langsung"
    for fungsi in (_metode_1_pengalihan, _metode_2_dari_html, _metode_3_batchexecute):
        hasil, catatan = fungsi(url)
        if hasil:
            return hasil, catatan
        terakhir = catatan
    return None, terakhir


# ===========================================================================
# Tahap 2 — membaca tanggal terbit dari halaman penerbit
# ===========================================================================

POLA_TANGGAL = [
    (r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)',
     "meta article:published_time"),
    (r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']article:published_time',
     "meta article:published_time (urutan terbalik)"),
    (r'<meta[^>]+itemprop=["\']datePublished["\'][^>]+content=["\']([^"\']+)',
     "meta datePublished"),
    (r'"datePublished"\s*:\s*"([^"]+)"', "JSON-LD datePublished"),
    (r'<time[^>]+datetime=["\']([^"\']+)', "tag <time datetime>"),
]


def baca_tanggal(url: str) -> tuple[datetime | None, str]:
    try:
        r = requests.get(url, headers=KEPALA, timeout=BATAS_WAKTU,
                         allow_redirects=True)
    except requests.RequestException as e:
        return None, f"galat jaringan: {type(e).__name__}"

    if r.status_code != 200:
        return None, f"status {r.status_code}"

    html = r.text or ""
    for pola, nama in POLA_TANGGAL:
        m = re.search(pola, html, re.I)
        if m:
            tanggal = parse_tanggal(m.group(1))
            if tanggal:
                return tanggal, nama
    return None, "tidak ada metadata tanggal yang dikenali"


# ===========================================================================
# Pelaksana
# ===========================================================================

def ambil_contoh(db: str, jumlah: int, penerbit: str | None) -> list[dict]:
    kon = sqlite3.connect(db)
    kon.row_factory = sqlite3.Row
    try:
        syarat, arg = "", []
        if penerbit:
            syarat = "WHERE LOWER(sumber_nama) LIKE ?"
            arg = [f"%{penerbit.lower()}%"]
        baris = kon.execute(
            f"""SELECT judul, sumber_nama, sumber_url, sumber_terbit, terbit_pada
                FROM artikel {syarat}
                ORDER BY terbit_pada DESC LIMIT ?""", arg + [jumlah]).fetchall()
        return [dict(b) for b in baris]
    finally:
        kon.close()


def main() -> int:
    p = argparse.ArgumentParser(description="Uji verifikasi tanggal ke penerbit.")
    p.add_argument("--db", default="data/mdk.sqlite3")
    p.add_argument("--jumlah", type=int, default=8)
    p.add_argument("--penerbit", help="Saring contoh berdasarkan nama penerbit.")
    a = p.parse_args()

    contoh = ambil_contoh(a.db, a.jumlah, a.penerbit)
    if not contoh:
        print("Tidak ada artikel yang cocok untuk diuji.")
        return 0

    print(f"Menguji {len(contoh)} artikel.\n" + "=" * 72)

    pecah_ok = tanggal_ok = meleset = 0
    selisih_terbesar = 0.0

    for i, c in enumerate(contoh, 1):
        print(f"\n[{i}/{len(contoh)}] {c['judul'][:64]}")
        print(f"  Penerbit   : {c['sumber_nama']}")
        print(f"  Tersimpan  : {c['sumber_terbit']}")

        asli, catatan = pecahkan(c["sumber_url"] or "")
        print(f"  Pemecahan  : {catatan}")
        if not asli:
            continue
        pecah_ok += 1
        print(f"  Alamat asli: {asli[:88]}")

        tanggal, cara = baca_tanggal(asli)
        if not tanggal:
            print(f"  Tanggal    : GAGAL — {cara}")
            continue
        tanggal_ok += 1
        print(f"  Tanggal    : {tanggal.isoformat()} (dari {cara})")

        tersimpan = parse_tanggal(c["sumber_terbit"])
        if not tersimpan:
            continue
        jam = abs((tersimpan - tanggal).total_seconds() / 3600.0)
        selisih_terbesar = max(selisih_terbesar, jam)
        if jam > 48:
            meleset += 1
            print(f"  >>> MELESET {jam:.0f} jam ({jam / 24:.1f} hari) <<<")
        else:
            print(f"  Selisih    : {jam:.1f} jam — wajar")

    print("\n" + "=" * 72)
    print("RINGKASAN")
    print(f"  Tautan berhasil dipecahkan : {pecah_ok}/{len(contoh)}")
    print(f"  Tanggal berhasil dibaca    : {tanggal_ok}/{len(contoh)}")
    print(f"  Meleset lebih dari 48 jam  : {meleset}")
    print(f"  Selisih terbesar           : {selisih_terbesar:.0f} jam "
          f"({selisih_terbesar / 24:.1f} hari)")

    print("\nKESIMPULAN")
    if pecah_ok == 0:
        print("  Tautan Google News TIDAK dapat dipecahkan dari lingkungan ini.")
        print("  Verifikasi tanggal otomatis belum dapat dibangun dengan cara ini.")
    elif tanggal_ok < pecah_ok / 2:
        print("  Tautan dapat dipecahkan, tetapi tanggal jarang terbaca.")
        print("  Verifikasi hanya akan menutup sebagian kasus.")
    else:
        print("  Verifikasi tanggal otomatis LAYAK dibangun.")
        print(f"  Perkiraan biaya: 2 permintaan HTTP per artikel "
              f"(~{2 * 25} permintaan untuk 25 artikel per jalan).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
