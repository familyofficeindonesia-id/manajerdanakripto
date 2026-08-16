"""
alat_kesegaran.py — Penyaring kesegaran berita untuk ManajerDanaKripto.

Tujuan: mencegah berita lama (mis. artikel Februari) tayang dengan stempel
tanggal build hari ini. Aturan dasarnya sederhana dan sengaja ketat:

    Artikel TANPA tanggal terbit yang bisa dibaca = DITOLAK.

Itu penyebab paling umum berita basi lolos ke situs: parser gagal membaca
tanggal, lalu kode menganggapnya "berita baru".

Cara pakai di skrip pengumpul berita:

    from alat_kesegaran import parse_tanggal, masih_segar, BATAS_JAM_AMBIL

    tanggal = parse_tanggal(entry)
    if not masih_segar(tanggal, BATAS_JAM_AMBIL):
        print(f"[LEWATI] {entry.get('title')} — terbit {tanggal}")
        continue

Cara pakai di build.py (pagar pengaman sebelum render):

    from alat_kesegaran import masih_segar, parse_tanggal, BATAS_JAM_TAYANG

    if not masih_segar(parse_tanggal(row["tanggal_sumber"]), BATAS_JAM_TAYANG):
        continue
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

# --------------------------------------------------------------------------
# Pengaturan
# --------------------------------------------------------------------------

# Batas saat MENGAMBIL berita dari sumber. Hanya berita <= 24 jam yang diambil.
BATAS_JAM_AMBIL = 24

# Batas saat MENAYANGKAN dari database. Sengaja lebih longgar dari batas ambil,
# supaya artikel yang sah tidak hilang kalau build tertunda beberapa jam.
BATAS_JAM_TAYANG = 48

# Toleransi tanggal "masa depan". Beda zona waktu di server sumber sering
# bikin tanggal terlihat 1-2 jam ke depan. Lebih dari ini = data rusak.
TOLERANSI_DEPAN_JAM = 3

# Kunci yang biasa dipakai feed/scraper untuk menyimpan tanggal terbit.
_KUNCI_TANGGAL = (
    "published_parsed",
    "updated_parsed",
    "published",
    "updated",
    "pubDate",
    "pubdate",
    "date",
    "datePublished",
    "dc:date",
    "created",
    "tanggal_sumber",
    "tanggal_terbit",
    "tanggal",
)

# Format tanggal tambahan yang dicoba kalau ISO dan RFC-2822 gagal.
_FORMAT_CADANGAN = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%b %d, %Y %H:%M",
    "%b %d, %Y",
    "%d %b %Y",
    "%B %d, %Y",
    "%d %B %Y",
)


# --------------------------------------------------------------------------
# Fungsi bantu
# --------------------------------------------------------------------------

def _ke_utc(dt: datetime) -> datetime:
    """Samakan semua datetime ke UTC. Yang polos dianggap sudah UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _dari_teks(teks: str) -> datetime | None:
    teks = teks.strip()
    if not teks:
        return None

    # 1. ISO 8601 — bentuk paling umum di API modern.
    coba = teks.replace("Z", "+00:00")
    try:
        return _ke_utc(datetime.fromisoformat(coba))
    except ValueError:
        pass

    # 2. RFC 2822 — bentuk standar di RSS (pubDate).
    try:
        return _ke_utc(parsedate_to_datetime(teks))
    except (TypeError, ValueError):
        pass

    # 3. Format bebas lain.
    for fmt in _FORMAT_CADANGAN:
        try:
            return _ke_utc(datetime.strptime(teks, fmt))
        except ValueError:
            continue

    return None


# --------------------------------------------------------------------------
# API utama
# --------------------------------------------------------------------------

def parse_tanggal(sumber) -> datetime | None:
    """
    Baca tanggal terbit dari berbagai bentuk masukan dan kembalikan datetime UTC.

    Menerima: datetime, struct_time, epoch (int/float), string, dict, atau
    objek entry feedparser. Kembali None kalau tidak ada tanggal yang terbaca.
    None berarti TOLAK — jangan pernah diganti dengan waktu sekarang.
    """
    if sumber is None:
        return None

    if isinstance(sumber, datetime):
        return _ke_utc(sumber)

    if isinstance(sumber, time.struct_time):
        return datetime.fromtimestamp(time.mktime(sumber), tz=timezone.utc)

    if isinstance(sumber, bool):
        return None

    if isinstance(sumber, (int, float)):
        # Epoch detik. Nilai kecil pasti bukan tanggal yang masuk akal.
        if sumber < 946_684_800:  # sebelum 1 Jan 2000
            return None
        try:
            return datetime.fromtimestamp(sumber, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None

    if isinstance(sumber, str):
        return _dari_teks(sumber)

    # dict atau objek entry: telusuri kunci-kunci tanggal yang umum.
    for kunci in _KUNCI_TANGGAL:
        nilai = None
        if isinstance(sumber, dict):
            nilai = sumber.get(kunci)
        else:
            nilai = getattr(sumber, kunci, None)

        if nilai is None:
            continue

        hasil = parse_tanggal(nilai)
        if hasil is not None:
            return hasil

    return None


def umur_jam(tanggal: datetime | None) -> float | None:
    """Umur artikel dalam jam. None kalau tanggal tidak terbaca."""
    if tanggal is None:
        return None
    selisih = datetime.now(timezone.utc) - _ke_utc(tanggal)
    return selisih.total_seconds() / 3600.0


def masih_segar(
    tanggal,
    batas_jam: int = BATAS_JAM_AMBIL,
    toleransi_depan_jam: int = TOLERANSI_DEPAN_JAM,
) -> bool:
    """
    True kalau artikel layak tayang. Menerima datetime, string, atau entry.

    Ditolak kalau:
      - tanggal tidak terbaca (None)
      - lebih tua dari batas_jam
      - bertanggal terlalu jauh ke masa depan (tanda data rusak)
    """
    tanggal = parse_tanggal(tanggal)
    if tanggal is None:
        return False

    jam = umur_jam(tanggal)
    if jam is None:
        return False
    if jam < -abs(toleransi_depan_jam):
        return False
    return jam <= batas_jam


def alasan_tolak(tanggal, batas_jam: int = BATAS_JAM_AMBIL) -> str | None:
    """Keterangan singkat kenapa ditolak, untuk log. None kalau lolos."""
    asli = tanggal
    tanggal = parse_tanggal(tanggal)
    if tanggal is None:
        return f"tanggal tidak terbaca ({asli!r})"

    jam = umur_jam(tanggal)
    if jam < -abs(TOLERANSI_DEPAN_JAM):
        return f"tanggal di masa depan ({tanggal.isoformat()})"
    if jam > batas_jam:
        return f"terlalu lama: {jam:.1f} jam (batas {batas_jam})"
    return None


def saring_entri(entri, batas_jam: int = BATAS_JAM_AMBIL, ambil_judul=None):
    """
    Saring daftar entri sekaligus. Kembalikan (lolos, ditolak).

    `ditolak` berisi tuple (entri, alasan) supaya bisa dicetak ke log build.
    """
    lolos, ditolak = [], []
    for e in entri:
        alasan = alasan_tolak(e, batas_jam)
        if alasan is None:
            lolos.append(e)
        else:
            ditolak.append((e, alasan))

    if ambil_judul is None:
        def ambil_judul(x):
            if isinstance(x, dict):
                return x.get("title") or x.get("judul") or "(tanpa judul)"
            return getattr(x, "title", "(tanpa judul)")

    print(f"[SARING] {len(lolos)} lolos, {len(ditolak)} ditolak "
          f"(batas {batas_jam} jam)")
    for e, alasan in ditolak:
        print(f"  [TOLAK] {ambil_judul(e)} — {alasan}")

    return lolos, ditolak


# --------------------------------------------------------------------------
# Uji cepat: jalankan `python alat_kesegaran.py` untuk memastikan modul waras.
# --------------------------------------------------------------------------

if __name__ == "__main__":
    sekarang = datetime.now(timezone.utc)
    contoh = [
        {"title": "Berita 2 jam lalu", "published": (sekarang - timedelta(hours=2)).isoformat()},
        {"title": "Berita 30 jam lalu", "published": (sekarang - timedelta(hours=30)).isoformat()},
        {"title": "Artikel Februari (kasus yellow.com)", "pubDate": "Tue, 03 Feb 2026 19:09:00 +0000"},
        {"title": "Tanpa tanggal", "published": ""},
        {"title": "Tanggal aneh", "published": "kemarin sore"},
        {"title": "Format RSS normal", "pubDate": (sekarang - timedelta(hours=5)).strftime("%a, %d %b %Y %H:%M:%S +0000")},
    ]
    saring_entri(contoh)
