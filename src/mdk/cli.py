"""Antarmuka baris perintah ManajerDanaKripto.

Contoh pemakaian:
    python -m mdk ambil                 # ambil umpan berita saja
    python -m mdk tulis --batas 20      # tulis ulang antrean menjadi artikel
    python -m mdk bangun                # bangun situs statis ke dist/
    python -m mdk jalankan              # ambil → tulis → bangun
    python -m mdk sajikan --port 8000   # pratinjau lokal
    python -m mdk status                # ringkasan basis data
    python -m mdk periksa               # uji kesehatan konfigurasi
"""
from __future__ import annotations

import argparse
import http.server
import functools
import socketserver
import sys
from pathlib import Path

from .config import muat_konfigurasi
from .entities import registri
from .store import buka


def _garis(judul: str) -> None:
    print(f"\n\033[1m{judul}\033[0m\n" + "─" * 62)


def perintah_ambil(args) -> int:
    from .pipeline import tahap_ambil
    _garis("MENGAMBIL UMPAN BERITA")
    hasil = tahap_ambil(sertakan_entitas=not args.hanya_umum)
    print(f"\n✓ {hasil['umpan']} umpan · {hasil['terbaca']} item terbaca · "
          f"{hasil['disimpan']} baru disimpan · {hasil['dibuang']} tidak relevan")
    return 0


def perintah_tulis(args) -> int:
    from .pipeline import tahap_tulis
    _garis("MENULIS ULANG BERITA")
    hasil = tahap_tulis(batas=args.batas)
    print(f"\n✓ {hasil['ditulis']} artikel ditulis · {hasil['gagal']} gagal · "
          f"{hasil['dilewati']} duplikat dilewati")
    return 0 if hasil["ditulis"] or not hasil["gagal"] else 1


def perintah_bangun(args) -> int:
    from .pipeline import tahap_bangun
    _garis("MEMBANGUN SITUS STATIS")
    hasil = tahap_bangun()
    print(f"\n✓ {hasil['halaman']} halaman dari {hasil['artikel']} artikel → {hasil['keluaran']}/")
    return 0


def perintah_jalankan(args) -> int:
    from .pipeline import jalankan_penuh
    _garis("PIPELINE PENUH")
    hasil = jalankan_penuh(batas=args.batas, sertakan_entitas=not args.hanya_umum)
    print(f"\n✓ Selesai — {hasil['ambil']['disimpan']} berita baru, "
          f"{hasil['tulis']['ditulis']} artikel, {hasil['bangun']['halaman']} halaman")
    return 0


def perintah_sajikan(args) -> int:
    kfg = muat_konfigurasi()
    akar = kfg.dir_keluaran
    if not akar.exists():
        print(f"✗ Folder {akar}/ belum ada. Jalankan `python -m mdk bangun` lebih dahulu.")
        return 1

    class Penangan(http.server.SimpleHTTPRequestHandler):
        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def log_message(self, fmt, *a):
            if args.verbose:
                super().log_message(fmt, *a)

    penangan = functools.partial(Penangan, directory=str(akar))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", args.port), penangan) as srv:
        print(f"▸ Pratinjau berjalan di http://localhost:{args.port}  (Ctrl+C untuk berhenti)")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\n▸ Server dihentikan.")
    return 0


def perintah_status(args) -> int:
    kfg = muat_konfigurasi()
    simpan, reg = buka(kfg), registri()
    s = simpan.statistik()
    _garis("STATUS BASIS DATA")
    print(f"Basis data     : {kfg.basis_data}")
    print(f"Tokoh dipantau : {len(reg.tokoh)} · Organisasi: {len(reg.organisasi)}")
    print(f"Item mentah    : {sum(s['mentah'].values())} {dict(s['mentah'])}")
    print(f"Artikel        : {sum(s['artikel'].values())} {dict(s['artikel'])}")
    print(f"Keluaran situs : {kfg.dir_keluaran} "
          f"({'ada' if kfg.dir_keluaran.exists() else 'belum dibangun'})")
    return 0


def perintah_periksa(args) -> int:
    """Uji kesehatan: konfigurasi, templat, kunci API, dan integritas entitas."""
    _garis("PEMERIKSAAN KESEHATAN")
    kfg, reg = muat_konfigurasi(), registri()
    masalah: list[str] = []

    print(f"✓ Konfigurasi termuat — {len(kfg.rubrik)} rubrik, {len(reg.tokoh)} tokoh")

    wajib = ["base.html.j2", "index.html.j2", "artikel.html.j2", "daftar.html.j2",
             "tokoh.html.j2", "tokoh_daftar.html.j2", "perusahaan.html.j2",
             "perusahaan_daftar.html.j2", "cari.html.j2", "glosarium.html.j2",
             "statis.html.j2", "404.html.j2"]
    hilang = [t for t in wajib if not (kfg.dir_templat / t).exists()]
    print("✓ Seluruh templat tersedia" if not hilang else f"✗ Templat hilang: {hilang}")
    masalah += [f"templat hilang: {t}" for t in hilang]

    ganda = [s for s, t in reg.tokoh.items() if len(t.alias) != len(set(a.lower() for a in t.alias))]
    if ganda:
        masalah.append(f"alias ganda pada: {ganda}")
    belum = [t.slug for t in reg.tokoh.values() if not t.terverifikasi]
    print(f"✓ Registri entitas konsisten — {len(belum)} profil menunggu verifikasi redaksi")

    kunci = kfg.kunci_api
    contoh = (not kunci) or len(kunci) < 30 or "xxxx" in kunci.lower()
    print("! ANTHROPIC_API_KEY masih berisi nilai contoh — tahap `tulis` tidak akan berjalan"
          if contoh and kunci else
          ("! ANTHROPIC_API_KEY belum disetel — tahap `tulis` tidak akan berjalan"
           if contoh else "✓ ANTHROPIC_API_KEY terpasang"))

    if masalah:
        print("\n✗ Ditemukan masalah:")
        for m in masalah:
            print(f"  - {m}")
        return 1
    print("\n✓ Semua pemeriksaan lolos.")
    return 0


def perintah_demo(args) -> int:
    """Isi basis data dengan artikel contoh lalu bangun situs pratinjau."""
    akar = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(akar / "scripts"))
    import seed_demo                                    # noqa: PLC0415
    return seed_demo.main(bangun=True)


def buat_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mdk", description="Mesin berita ManajerDanaKripto.com",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = p.add_subparsers(dest="perintah", required=True)

    a = sub.add_parser("ambil", help="ambil umpan berita ke antrean")
    a.add_argument("--hanya-umum", action="store_true", help="lewati kueri per tokoh")
    a.set_defaults(fungsi=perintah_ambil)

    t = sub.add_parser("tulis", help="tulis ulang antrean menjadi artikel Indonesia")
    t.add_argument("--batas", type=int, default=None, help="jumlah maksimum artikel")
    t.set_defaults(fungsi=perintah_tulis)

    b = sub.add_parser("bangun", help="bangun situs statis ke dist/")
    b.set_defaults(fungsi=perintah_bangun)

    j = sub.add_parser("jalankan", help="ambil + tulis + bangun")
    j.add_argument("--batas", type=int, default=None)
    j.add_argument("--hanya-umum", action="store_true")
    j.set_defaults(fungsi=perintah_jalankan)

    s = sub.add_parser("sajikan", help="pratinjau situs di peramban lokal")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--verbose", action="store_true")
    s.set_defaults(fungsi=perintah_sajikan)

    sub.add_parser("status", help="ringkasan basis data").set_defaults(fungsi=perintah_status)
    sub.add_parser("periksa", help="uji kesehatan konfigurasi").set_defaults(fungsi=perintah_periksa)
    sub.add_parser("demo", help="isi data contoh lalu bangun pratinjau").set_defaults(fungsi=perintah_demo)

    # Subperintah radar (pemantauan sumber berita) didaftarkan oleh modulnya sendiri.
    from .radar import cli as radar_cli                          # noqa: PLC0415
    radar_cli.daftarkan(sub)
    return p


def main(argv: list[str] | None = None) -> int:
    args = buat_parser().parse_args(argv)
    try:
        return args.fungsi(args)
    except KeyboardInterrupt:
        print("\n▸ Dibatalkan pengguna.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
