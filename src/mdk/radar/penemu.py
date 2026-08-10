"""Penemu umpan resmi — mencari URL RSS/Atom sungguhan dari situs perusahaan.

MENGAPA MODUL INI ADA
Menebak URL umpan ("coba saja /feed") menghasilkan daftar yang sebagian besar
mati. Modul ini justru MEMBUKA situs resmi lalu membaca deklarasi umpan yang
tertanam di dalamnya, sehingga URL yang tersimpan adalah URL yang benar-benar
ada.

DUA TAHAP
  1. Baca <link rel="alternate" type="application/rss+xml"> pada halaman muka
     dan halaman berita/blog. Ini cara resmi sebuah situs mengumumkan umpannya.
  2. Bila tahap pertama nihil, uji sejumlah jalur yang lazim dipakai mesin
     situs populer (WordPress, Ghost, Webflow, Hugo, Substack).

Setiap kandidat divalidasi dengan benar-benar menguraikannya: umpan hanya
diterima bila mengembalikan entri yang sah.
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse

import feedparser
import requests

# Jalur yang lazim dipakai berbagai mesin situs.
JALUR_LAZIM = [
    "/feed", "/rss", "/feed.xml", "/rss.xml", "/atom.xml", "/index.xml",
    "/blog/feed", "/blog/rss", "/news/feed", "/insights/feed",
    "/feed/", "/blog/feed.xml", "/research/feed", "/newsroom/rss",
    "/en/feed", "/blog/index.xml",
]

# Halaman yang biasanya memuat deklarasi umpan.
HALAMAN_PERIKSA = ["", "/blog", "/news", "/insights", "/research", "/newsroom", "/media"]

POLA_LINK = re.compile(
    r'<link[^>]+type=["\']application/(?:rss|atom)\+xml["\'][^>]*>', re.I)
POLA_HREF = re.compile(r'href=["\']([^"\']+)["\']', re.I)
POLA_TITLE = re.compile(r'title=["\']([^"\']*)["\']', re.I)

KEPALA = {
    "User-Agent": "ManajerDanaKriptoRadar/1.0 (+https://manajerdanakripto.com/tentang)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _ambil(url: str, timeout: float = 15.0) -> requests.Response | None:
    try:
        r = requests.get(url, headers=KEPALA, timeout=timeout, allow_redirects=True)
        return r if r.status_code == 200 else None
    except requests.RequestException:
        return None


def validasi_umpan(url: str, timeout: float = 15.0) -> dict | None:
    """Uji apakah URL benar-benar umpan yang dapat diurai dan berisi entri."""
    r = _ambil(url, timeout)
    if not r:
        return None
    tipe = (r.headers.get("Content-Type") or "").lower()
    if "html" in tipe and "xml" not in tipe:
        return None
    try:
        parsed = feedparser.parse(r.content)
    except Exception:                                            # noqa: BLE001
        return None
    if not parsed.entries:
        return None
    entri_terbaru = parsed.entries[0]
    return {
        "url": r.url,
        "judul": (getattr(parsed.feed, "title", "") or "").strip() or urlparse(url).netloc,
        "jumlah_entri": len(parsed.entries),
        "contoh_judul": (entri_terbaru.get("title") or "")[:110],
        "terverifikasi": True,
    }


def _kandidat_dari_html(html: str, basis: str) -> list[tuple[str, str]]:
    """Ambil pasangan (url, judul) dari deklarasi <link rel=alternate>."""
    hasil = []
    for tag in POLA_LINK.findall(html or ""):
        href = POLA_HREF.search(tag)
        if not href:
            continue
        judul = POLA_TITLE.search(tag)
        hasil.append((urljoin(basis, href.group(1)),
                      judul.group(1) if judul else ""))
    return hasil


def temukan_untuk_domain(domain: str, maks_umpan: int = 3,
                         timeout: float = 15.0) -> dict:
    """Temukan umpan resmi untuk satu domain.

    Kembalikan {"domain", "umpan": [...], "status", "dicoba"}.
    """
    if not domain:
        return {"domain": "", "umpan": [], "status": "domain-kosong", "dicoba": 0}

    domain = domain.strip().replace("https://", "").replace("http://", "").strip("/")
    basis = f"https://{domain}"
    ditemukan: dict[str, dict] = {}
    dicoba = 0

    # Tahap 1 — baca deklarasi umpan pada halaman-halaman utama.
    kandidat: list[tuple[str, str]] = []
    for jalur in HALAMAN_PERIKSA:
        if len(kandidat) >= maks_umpan * 2:
            break
        dicoba += 1
        r = _ambil(basis + jalur, timeout)
        if not r:
            continue
        kandidat.extend(_kandidat_dari_html(r.text, r.url))

    for url, judul in kandidat:
        if url in ditemukan or len(ditemukan) >= maks_umpan:
            continue
        dicoba += 1
        sah = validasi_umpan(url, timeout)
        if sah:
            sah["judul"] = judul or sah["judul"]
            sah["cara"] = "deklarasi-html"
            ditemukan[url] = sah

    # Tahap 2 — uji jalur lazim hanya bila tahap pertama nihil.
    if not ditemukan:
        for jalur in JALUR_LAZIM:
            if len(ditemukan) >= maks_umpan:
                break
            dicoba += 1
            sah = validasi_umpan(basis + jalur, timeout)
            if sah:
                sah["cara"] = "jalur-lazim"
                ditemukan[sah["url"]] = sah

    status = "ditemukan" if ditemukan else "tidak-ada-umpan"
    return {"domain": domain, "umpan": list(ditemukan.values()),
            "status": status, "dicoba": dicoba}


def temukan_banyak(organisasi: list[dict], maks_serentak: int = 5,
                   maks_umpan: int = 3, verbose: bool = True) -> dict[str, dict]:
    """Jalankan penemuan untuk seluruh organisasi secara paralel."""
    hasil: dict[str, dict] = {}
    punya_domain = [o for o in organisasi if (o.get("situs_web") or "").strip()]
    tanpa_domain = [o["slug"] for o in organisasi if not (o.get("situs_web") or "").strip()]

    if verbose and tanpa_domain:
        print(f"  ! {len(tanpa_domain)} organisasi tanpa domain, dilewati: "
              f"{', '.join(tanpa_domain[:6])}{'…' if len(tanpa_domain) > 6 else ''}")

    with ThreadPoolExecutor(max_workers=maks_serentak) as pool:
        tugas = {pool.submit(temukan_untuk_domain, o["situs_web"], maks_umpan): o
                 for o in punya_domain}
        for i, fut in enumerate(as_completed(tugas), 1):
            org = tugas[fut]
            try:
                r = fut.result()
            except Exception as e:                               # noqa: BLE001
                r = {"domain": org.get("situs_web", ""), "umpan": [],
                     "status": f"galat:{type(e).__name__}", "dicoba": 0}
            hasil[org["slug"]] = r
            if verbose:
                tanda = "✓" if r["umpan"] else ("·" if r["status"] == "tidak-ada-umpan" else "✗")
                jml = f"{len(r['umpan'])} umpan" if r["umpan"] else r["status"]
                print(f"  [{i:>2}/{len(punya_domain)}] {tanda} {org['nama'][:34]:<34} {jml}")

    return hasil
