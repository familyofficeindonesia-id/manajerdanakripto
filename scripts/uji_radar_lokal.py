"""Uji ujung-ke-ujung radar dengan server RSS tiruan.

Menguji rantai penuh tanpa menyentuh internet:
    jajak → saring → deduplikasi → pengelompokan → notifikasi → antrean terjemahan

Skenario yang diperiksa:
  1. Item baru terdeteksi dan tercatat
  2. Putaran kedua atas umpan yang sama TIDAK menghasilkan duplikat
  3. Satu peristiwa yang diliput lima media menjadi SATU klaster
  4. Permintaan bersyarat (ETag) menghasilkan 304 dan menghemat unduhan
  5. Sumber yang mati dinonaktifkan otomatis setelah gagal beruntun
  6. Temuan berskor tinggi diteruskan ke tabel `mentah`

Jalankan:  python scripts/uji_radar_lokal.py
"""
from __future__ import annotations

import http.server
import socketserver
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR / "src"))

from mdk.config import muat_konfigurasi          # noqa: E402
from mdk.entities import registri                # noqa: E402
from mdk.radar.notifikasi import Pengirim        # noqa: E402
from mdk.radar.pemantau import Pemantau          # noqa: E402
from mdk.radar.simpan import PenyimpananRadar    # noqa: E402
from mdk.radar.sumber import Sumber              # noqa: E402
from mdk.store import Penyimpanan                # noqa: E402

PORT = 8931
HITUNG_PERMINTAAN = {"total": 0, "304": 0}


def _rfc(jam_lalu: int = 1) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=jam_lalu)).strftime(
        "%a, %d %b %Y %H:%M:%S +0000")


def _umpan(butir: list[tuple[str, str, str]]) -> str:
    """butir: (judul, url, penerbit)"""
    item = "".join(f"""
    <item>
      <title>{j}</title>
      <link>{u}</link>
      <source url="https://{p}">{p}</source>
      <pubDate>{_rfc(2)}</pubDate>
      <description>Laporan mengenai pergerakan dana institusional aset digital.</description>
    </item>""" for j, u, p in butir)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Umpan Uji</title><link>http://localhost</link>
<description>Umpan tiruan untuk pengujian radar</description>{item}
</channel></rss>"""


# Peristiwa yang sama, diberitakan lima media dengan judul berbeda-beda.
SATU_PERISTIWA = [
    ("BlackRock bitcoin ETF sees record weekly inflows", "https://a.test/1", "reuters.com"),
    ("Record weekly inflows for BlackRock's bitcoin ETF", "https://b.test/2", "coindesk.com"),
    ("BlackRock ETF records weekly bitcoin inflow record", "https://c.test/3", "theblock.co"),
    ("Weekly inflows hit record at BlackRock bitcoin ETF", "https://d.test/4", "decrypt.co"),
    ("BlackRock's bitcoin ETF posts record inflows this week", "https://e.test/5", "blockworks.co"),
]
PERISTIWA_LAIN = [
    ("Cathie Wood ARK Invest trims Coinbase position", "https://f.test/6", "cnbc.com"),
    ("Michael Saylor Strategy discloses new bitcoin purchase", "https://g.test/7", "bloomberg.com"),
]

UMPAN = {
    "/klaster.xml": _umpan(SATU_PERISTIWA),
    "/beragam.xml": _umpan(PERISTIWA_LAIN),
    "/kosong.xml": _umpan([]),
}


class Penangan(http.server.BaseHTTPRequestHandler):
    def do_GET(self):                                             # noqa: N802
        HITUNG_PERMINTAAN["total"] += 1

        if self.path == "/mati.xml":                              # selalu gagal
            self.send_response(503)
            self.end_headers()
            return

        isi = UMPAN.get(self.path)
        if isi is None:
            self.send_response(404)
            self.end_headers()
            return

        etag = f'"{abs(hash(self.path)) % 10**8}"'
        if self.headers.get("If-None-Match") == etag:              # permintaan bersyarat
            HITUNG_PERMINTAAN["304"] += 1
            self.send_response(304)
            self.send_header("ETag", etag)
            self.end_headers()
            return

        data = isi.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/rss+xml; charset=utf-8")
        self.send_header("ETag", etag)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):                                     # senyapkan log
        pass


def _sumber_uji() -> list[Sumber]:
    b = f"http://127.0.0.1:{PORT}"
    return [
        Sumber(id="blackrock::uji::1", entitas="blackrock", jenis_entitas="organisasi",
               jenis="google_news_en", url=f"{b}/klaster.xml",
               label="Uji — klaster satu peristiwa", prioritas=1, bobot=1.0,
               terverifikasi=True),
        Sumber(id="ark-invest::uji::1", entitas="ark-invest", jenis_entitas="organisasi",
               jenis="google_news_en", url=f"{b}/beragam.xml",
               label="Uji — dua peristiwa berbeda", prioritas=1, bobot=1.0,
               terverifikasi=True),
        Sumber(id="rusak::uji::1", entitas="strategy", jenis_entitas="organisasi",
               jenis="bing_news", url=f"{b}/mati.xml",
               label="Uji — sumber mati", prioritas=1, bobot=1.0),
    ]


def _cetak(nomor: str, judul: str, lulus: bool, rincian: str = "") -> bool:
    tanda = "\033[32m✓ LULUS\033[0m" if lulus else "\033[31m✗ GAGAL\033[0m"
    print(f"  {nomor}. {judul:<52} {tanda}")
    if rincian:
        print(f"       {rincian}")
    return lulus


def main() -> int:
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("127.0.0.1", PORT), Penangan)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(0.4)

    kfg, reg = muat_konfigurasi(), registri()
    db_uji = kfg.dir_data / "uji_radar.sqlite3"
    db_uji.unlink(missing_ok=True)

    db = PenyimpananRadar(db_uji)
    simpan_utama = Penyimpanan(db_uji)
    org = [{"slug": "blackrock", "nama": "BlackRock"},
           {"slug": "ark-invest", "nama": "ARK Invest"},
           {"slug": "strategy", "nama": "Strategy"}]

    # Longgarkan ambang agar umpan tiruan lolos saringan.
    kfg.radar.update(skor_minimum=10, skor_minimum_notifikasi=10,
                     skor_minimum_terjemah=10, batas_nonaktif=2,
                     jeda_per_domain_detik=0.0)

    pemantau = Pemantau(kfg, reg, db, org)
    sumber = _sumber_uji()
    lulus_semua = True

    print("\n\033[1mUJI UJUNG-KE-UJUNG RADAR\033[0m")
    print("─" * 74)

    # -- 1. Putaran pertama --------------------------------------------------
    p1 = pemantau.putaran(sumber, putaran_ke=1, verbose=False)
    lulus_semua &= _cetak("1", "Item baru terdeteksi pada putaran pertama",
                          p1["baru"] == 7,
                          f"{p1['baru']} item baru dari {p1['dijajaki']} sumber (diharapkan 7)")

    # -- 2. Pengelompokan ----------------------------------------------------
    jml_klaster = p1["klaster"]
    lulus_semua &= _cetak("2", "Lima liputan satu peristiwa menjadi satu klaster",
                          jml_klaster == 3,
                          f"{jml_klaster} klaster terbentuk dari 7 item (diharapkan 3)")

    besar = max(p1["klaster_baru"], key=lambda k: k["jumlah_sumber"])
    lulus_semua &= _cetak("3", "Klaster terbesar mencatat lima media berbeda",
                          besar["jumlah_sumber"] == 5,
                          f"\"{besar['judul_utama'][:56]}\" · {besar['jumlah_sumber']} media")

    # -- 4. Anti-duplikat ----------------------------------------------------
    p2 = pemantau.putaran(sumber, putaran_ke=2, verbose=False)
    lulus_semua &= _cetak("4", "Putaran kedua tidak menghasilkan duplikat",
                          p2["baru"] == 0, f"{p2['baru']} item baru (diharapkan 0)")

    # -- 5. Permintaan bersyarat --------------------------------------------
    lulus_semua &= _cetak("5", "Permintaan bersyarat menghemat unduhan",
                          HITUNG_PERMINTAAN["304"] > 0,
                          f"{HITUNG_PERMINTAAN['304']} balasan 304 dari "
                          f"{HITUNG_PERMINTAAN['total']} permintaan")

    # -- 6. Nonaktif otomatis ------------------------------------------------
    kondisi = db.kondisi("rusak::uji::1")
    lulus_semua &= _cetak("6", "Sumber mati dinonaktifkan otomatis",
                          bool(kondisi) and kondisi["aktif"] == 0,
                          f"gagal beruntun: {kondisi['gagal_beruntun'] if kondisi else '-'}x, "
                          f"status: {'nonaktif' if kondisi and not kondisi['aktif'] else 'masih aktif'}")

    # -- 7. Notifikasi -------------------------------------------------------
    kfg.radar["kanal"] = ["berkas", "rss"]
    pengirim = Pengirim(kfg, db, reg, org)
    hasil_kirim = pengirim.salurkan(p1["klaster_baru"], verbose=False)
    berkas_jsonl = kfg.dir_data / "radar" / "temuan.jsonl"
    lulus_semua &= _cetak("7", "Notifikasi tertulis ke berkas arsip",
                          berkas_jsonl.exists() and berkas_jsonl.stat().st_size > 0,
                          f"berkas: {', '.join(f'{k}={v}' for k, v in hasil_kirim.items())}")

    # -- 8. Cegah kirim ganda ------------------------------------------------
    ulang = pengirim.salurkan(p1["klaster_baru"], verbose=False)
    lulus_semua &= _cetak("8", "Klaster yang sama tidak dikirim dua kali",
                          all("dilewati" in v for k, v in ulang.items() if k != "rss"),
                          str(ulang))

    # -- 9. Teruskan ke antrean terjemahan -----------------------------------
    n = pemantau.teruskan_ke_antrean(simpan_utama, batas=50)
    antre = simpan_utama.mentah_menunggu(50)
    lulus_semua &= _cetak("9", "Temuan diteruskan ke antrean terjemahan",
                          n > 0 and len(antre) > 0,
                          f"{n} diproses, {len(antre)} menunggu di tabel `mentah`")

    # -- 10. Idempotensi terusan --------------------------------------------
    n2 = pemantau.teruskan_ke_antrean(simpan_utama, batas=50)
    lulus_semua &= _cetak("10", "Terusan tidak mengantre ulang item yang sama",
                          n2 == 0, f"{n2} diproses pada panggilan kedua (diharapkan 0)")

    srv.shutdown()
    db_uji.unlink(missing_ok=True)

    print("─" * 74)
    if lulus_semua:
        print("\033[32m\033[1m  SELURUH UJI LULUS\033[0m — rantai radar berfungsi utuh.\n")
        return 0
    print("\033[31m\033[1m  ADA UJI YANG GAGAL\033[0m\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
