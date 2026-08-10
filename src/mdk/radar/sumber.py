"""Pembangun URL sumber pemantauan.

Modul ini menjawab satu pertanyaan: dari mana saja berita tentang seorang tokoh
atau sebuah perusahaan dapat ditangkap secara otomatis?

TUJUH JENIS SUMBER
  1. google_news_en  — Google News RSS, kueri frasa persis, edisi Inggris
  2. google_news_id  — Google News RSS, edisi Indonesia (menangkap liputan lokal)
  3. bing_news       — Bing News RSS, indeks berbeda dari Google
  4. situs_resmi     — umpan RSS/Atom situs resmi (ditemukan otomatis)
  5. youtube         — umpan kanal YouTube (wawancara & podcast)
  6. sec_edgar       — pengajuan SEC (13F-HR, 8-K, S-1) untuk entitas AS
  7. reddit          — pencarian Reddit, penanda dini pembicaraan pasar

Semua URL dibangun dari pola yang terdokumentasi publik. Tidak ada URL yang
ditebak, kecuali `situs_resmi` yang justru ditemukan lewat penelusuran nyata
oleh modul `penemu.py`, bukan dikarang.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import quote_plus

# --------------------------------------------------------------------- pola --
POLA = {
    "google_news_en": "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en",
    "google_news_id": "https://news.google.com/rss/search?q={q}&hl=id&gl=ID&ceid=ID:id",
    "bing_news":      "https://www.bing.com/news/search?q={q}&format=RSS",
    "reddit":         "https://www.reddit.com/search.rss?q={q}&sort=new&t=week",
    "youtube":        "https://www.youtube.com/feeds/videos.xml?channel_id={id}",
    "sec_edgar":      ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
                       "&company={q}&type={arsip}&dateb=&owner=include&count=20&output=atom"),
    "nitter":         "https://{instance}/{handle}/rss",
}

# Kata pembatas untuk entitas bernama generik ("Strategy", "Galaxy", "Gemini").
# Tanpa ini, kueri "Strategy" mengembalikan ribuan artikel tak relevan.
PEMBATAS = "(bitcoin OR crypto OR cryptocurrency OR ETF OR fund OR digital asset)"

# Pembatas ringan untuk nama unik: mempertajam tanpa membuang liputan sah.
PEMBATAS_RINGAN = "(crypto OR bitcoin OR fund OR ETF OR investment OR market)"

# Prioritas menentukan frekuensi jajak pendapat (lihat pemantau.py).
PRIORITAS_BAWAAN = {
    "google_news_en": 1,   # tercepat, cakupan terluas
    "situs_resmi": 1,      # sumber primer, paling tepercaya
    "sec_edgar": 1,        # pengungkapan resmi, nilai berita tinggi
    "google_news_id": 2,
    "bing_news": 2,
    "youtube": 3,
    "reddit": 3,
    "nitter": 3,
}

# Bobot kepercayaan sumber; dipakai saat memilih tautan utama sebuah klaster.
BOBOT_SUMBER = {
    "situs_resmi": 1.30,
    "sec_edgar": 1.40,
    "google_news_en": 1.00,
    "google_news_id": 0.95,
    "bing_news": 0.90,
    "youtube": 0.70,
    "reddit": 0.45,
    "nitter": 0.55,
}


@dataclass
class Sumber:
    """Satu umpan yang dipantau."""
    id: str                       # <entitas>::<jenis>::<n>
    entitas: str                  # slug tokoh atau organisasi
    jenis_entitas: str            # tokoh | organisasi
    jenis: str                    # google_news_en | bing_news | ...
    url: str
    label: str
    prioritas: int = 2
    bobot: float = 1.0
    aktif: bool = True
    terverifikasi: bool = False
    catatan: str = ""

    def dict(self) -> dict:
        return {
            "id": self.id, "entitas": self.entitas, "jenis_entitas": self.jenis_entitas,
            "jenis": self.jenis, "url": self.url, "label": self.label,
            "prioritas": self.prioritas, "bobot": self.bobot, "aktif": self.aktif,
            "terverifikasi": self.terverifikasi, "catatan": self.catatan,
        }

    @classmethod
    def dari_dict(cls, d: dict) -> "Sumber":
        sah = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in sah})


# ----------------------------------------------------------------- kueri -----
def bangun_kueri(nama: str, generik: bool, alias: list[str] | None = None,
                 ketat: bool = False) -> str:
    """Susun kueri pencarian berita untuk satu entitas.

    - Nama selalu dibungkus tanda kutip agar dicari sebagai frasa persis.
    - Nama generik WAJIB memakai pembatas topik.
    - `ketat=True` menambahkan pembatas meski nama tidak generik; berguna untuk
      tokoh yang namanya juga umum dipakai orang lain.
    """
    inti = f'"{nama}"'
    if alias:
        varian = " OR ".join(f'"{a}"' for a in alias[:3] if a and a != nama)
        if varian:
            inti = f"({inti} OR {varian})"
    if generik:
        return f"{inti} {PEMBATAS}"
    if ketat:
        return f"{inti} {PEMBATAS_RINGAN}"
    return inti


def bersihkan_nama_edgar(nama: str) -> str:
    """Siapkan nama badan hukum untuk kotak pencarian EDGAR.

    EDGAR mencocokkan awalan nama secara harfiah, sehingga catatan tambahan
    dalam tanda kurung ("(sebelumnya MicroStrategy)") justru membuat pencarian
    gagal. Fungsi ini membuang keterangan tersebut dan menyisakan nama inti.
    """
    nama = re.sub(r"\s*\([^)]*\)", "", nama or "")          # buang keterangan kurung
    nama = re.sub(r"\s*/\s*.*$", "", nama)                    # buang alternatif setelah "/"
    nama = re.sub(r"[.,]", " ", nama)
    return re.sub(r"\s+", " ", nama).strip()


def _url(pola: str, **kw) -> str:
    """Isi placeholder pada pola URL. Nama parameter sengaja `pola`,
    bukan `jenis`, agar tidak bertabrakan dengan kata kunci pemanggil."""
    return POLA[pola].format(**kw)


# --------------------------------------------------- pembangun per entitas ---
def sumber_tokoh(tokoh, opsi: dict | None = None) -> list[Sumber]:
    """Bangun seluruh sumber pemantauan untuk satu tokoh."""
    opsi = opsi or {}
    slug, nama = tokoh.slug, tokoh.nama
    hasil: list[Sumber] = []

    def tambah(jenis: str, url: str, label: str, **kw) -> None:
        hasil.append(Sumber(
            id=f"{slug}::{jenis}::{len([s for s in hasil if s.jenis == jenis]) + 1}",
            entitas=slug, jenis_entitas="tokoh", jenis=jenis, url=url, label=label,
            prioritas=PRIORITAS_BAWAAN.get(jenis, 2), bobot=BOBOT_SUMBER.get(jenis, 1.0),
            **kw))

    # 1 & 2. Google News — frasa persis, lalu versi dipertajam topik.
    kueri_polos = bangun_kueri(nama, generik=False)
    kueri_tajam = bangun_kueri(nama, generik=False, ketat=True)
    tambah("google_news_en", _url("google_news_en", q=quote_plus(kueri_polos)),
           f"Google News (EN) — {nama}", terverifikasi=True)
    tambah("google_news_en", _url("google_news_en", q=quote_plus(kueri_tajam)),
           f"Google News (EN, terfokus) — {nama}", terverifikasi=True)

    # 3. Edisi Indonesia — menangkap saduran media lokal lebih dahulu.
    if opsi.get("edisi_indonesia", True):
        tambah("google_news_id", _url("google_news_id", q=quote_plus(kueri_polos)),
               f"Google News (ID) — {nama}", terverifikasi=True)

    # 4. Bing — indeks berbeda, kerap memuat sumber yang tidak terjaring Google.
    if opsi.get("bing", True):
        tambah("bing_news", _url("bing_news", q=quote_plus(kueri_tajam)),
               f"Bing News — {nama}", terverifikasi=True)

    # 5. Reddit — sinyal dini, kualitas beragam, bobot rendah.
    if opsi.get("reddit", False):
        tambah("reddit", _url("reddit", q=quote_plus(f'"{nama}"')),
               f"Reddit — {nama}", terverifikasi=True)

    # 6. Kanal YouTube — hanya bila ID kanal sudah diisi manual.
    kanal = (opsi.get("kanal_youtube") or {}).get(slug, "")
    if kanal:
        tambah("youtube", _url("youtube", id=kanal), f"YouTube — {nama}",
               terverifikasi=False, catatan="ID kanal diisi manual; verifikasi dengan `radar periksa`")

    # 7. X/Twitter lewat Nitter — nonaktif secara bawaan karena instans sering mati.
    if opsi.get("nitter") and tokoh.x:
        tambah("nitter", _url("nitter", instance=opsi["nitter"], handle=tokoh.x),
               f"X/@{tokoh.x} — {nama}", aktif=False,
               catatan="Instans Nitter tidak stabil; aktifkan setelah diuji")

    return hasil


def sumber_organisasi(org: dict, opsi: dict | None = None) -> list[Sumber]:
    """Bangun seluruh sumber pemantauan untuk satu organisasi."""
    opsi = opsi or {}
    slug, nama = org["slug"], org["nama"]
    generik = bool(org.get("generik", False))
    alias = list(org.get("alias", []) or [])
    hasil: list[Sumber] = []

    def tambah(jenis: str, url: str, label: str, **kw) -> None:
        hasil.append(Sumber(
            id=f"{slug}::{jenis}::{len([s for s in hasil if s.jenis == jenis]) + 1}",
            entitas=slug, jenis_entitas="organisasi", jenis=jenis, url=url, label=label,
            prioritas=PRIORITAS_BAWAAN.get(jenis, 2), bobot=BOBOT_SUMBER.get(jenis, 1.0),
            **kw))

    kueri = bangun_kueri(nama, generik=generik, alias=alias)
    tambah("google_news_en", _url("google_news_en", q=quote_plus(kueri)),
           f"Google News (EN) — {nama}", terverifikasi=True)

    if opsi.get("edisi_indonesia", True):
        tambah("google_news_id", _url("google_news_id", q=quote_plus(kueri)),
               f"Google News (ID) — {nama}", terverifikasi=True)

    if opsi.get("bing", True):
        tambah("bing_news", _url("bing_news", q=quote_plus(kueri)),
               f"Bing News — {nama}", terverifikasi=True)

    # Umpan resmi: URL diisi oleh `radar temukan`, bukan ditebak di sini.
    for umpan in org.get("umpan_resmi", []) or []:
        tambah("situs_resmi", umpan["url"], f"Situs resmi — {umpan.get('judul', nama)}",
               terverifikasi=bool(umpan.get("terverifikasi", False)))

    # Pengajuan SEC — pengungkapan posisi 13F dan aksi korporasi 8-K.
    if org.get("edgar") and opsi.get("edgar", True):
        nama_edgar = bersihkan_nama_edgar(org.get("nama_resmi") or nama)
        for jenis_arsip, keterangan in (("13F-HR", "posisi triwulanan"),
                                        ("8-K", "aksi korporasi")):
            if jenis_arsip == "8-K" and not org.get("ticker"):
                continue          # 8-K hanya relevan untuk emiten terbuka
            tambah("sec_edgar",
                   _url("sec_edgar", q=quote_plus(nama_edgar), arsip=jenis_arsip),
                   f"SEC EDGAR {jenis_arsip} ({keterangan}) — {nama}",
                   terverifikasi=False,
                   catatan="Pencarian berdasarkan nama; ganti ke CIK bila hasilnya meleset")

    return hasil


# ------------------------------------------------------------- agregasi ------
def bangun_semua(registri, organisasi: list[dict], opsi: dict | None = None) -> list[Sumber]:
    """Bangun daftar sumber lengkap untuk seluruh tokoh dan organisasi."""
    semua: list[Sumber] = []
    for t in registri.daftar_tokoh():
        semua.extend(sumber_tokoh(t, opsi))
    for o in organisasi:
        semua.extend(sumber_organisasi(o, opsi))
    return semua


def ringkas(sumber: list[Sumber]) -> dict:
    """Statistik ringkas untuk ditampilkan di CLI."""
    per_jenis: dict[str, int] = {}
    for s in sumber:
        per_jenis[s.jenis] = per_jenis.get(s.jenis, 0) + 1
    return {
        "total": len(sumber),
        "aktif": sum(1 for s in sumber if s.aktif),
        "terverifikasi": sum(1 for s in sumber if s.terverifikasi),
        "per_jenis": dict(sorted(per_jenis.items(), key=lambda kv: -kv[1])),
        "entitas": len({s.entitas for s in sumber}),
    }
