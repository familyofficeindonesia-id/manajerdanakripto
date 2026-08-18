"""
cari_umpan.py — Temukan alamat RSS resmi sebuah situs, alih-alih menebaknya.

Membaca deklarasi <link rel="alternate" type="application/rss+xml"> pada halaman
situs, lalu memvalidasi tiap kandidat dengan benar-benar menguraikannya. Hanya
alamat yang mengembalikan entri sah yang dilaporkan.

Menggunakan kembali src/mdk/radar/penemu.py, dengan User-Agent peramban agar
situs yang menolak perayap (403) tetap dapat dibaca.

Skrip ini TIDAK mengubah apa pun.

Pemakaian:
    python src/mdk/cari_umpan.py blockworks.co dlnews.com
    python src/mdk/cari_umpan.py --bermasalah
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

# Domain yang gagal pada uji umpan terakhir.
DOMAIN_BERMASALAH = [
    "blockworks.co",
    "dlnews.com",
    "kontan.co.id",
    "bisnis.com",
    "cnbcindonesia.com",
]

UA_PERAMBAN = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")


def muat_penemu():
    """Muat penemu.py langsung dari berkas, tanpa melewati paket induk."""
    jalur = Path(__file__).resolve().parent / "radar" / "penemu.py"
    if not jalur.exists():
        sys.exit(f"GAGAL: {jalur} tidak ditemukan.")
    spec = importlib.util.spec_from_file_location("penemu_mandiri", jalur)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def main() -> int:
    p = argparse.ArgumentParser(description="Temukan alamat RSS resmi situs.")
    p.add_argument("domain", nargs="*", help="Domain yang dicari umpannya.")
    p.add_argument("--bermasalah", action="store_true",
                   help="Pakai daftar domain yang gagal pada uji terakhir.")
    p.add_argument("--maks", type=int, default=3,
                   help="Maksimum umpan per domain (bawaan 3).")
    a = p.parse_args()

    domain = a.domain or (DOMAIN_BERMASALAH if a.bermasalah else [])
    if not domain:
        p.error("sebutkan domain, atau pakai --bermasalah")

    penemu = muat_penemu()
    # Ganti User-Agent bawaan modul dengan peramban.
    penemu.KEPALA = {**penemu.KEPALA, "User-Agent": UA_PERAMBAN}

    print(f"Mencari umpan resmi untuk {len(domain)} domain.")
    print(f"User-Agent: {UA_PERAMBAN[:60]}...\n" + "=" * 76)

    ketemu_total = 0
    for d in domain:
        print(f"\n{d}")
        try:
            hasil = penemu.temukan_untuk_domain(d, maks_umpan=a.maks)
        except Exception as e:                                    # noqa: BLE001
            print(f"  GAGAL: {type(e).__name__}: {e}")
            continue

        if not hasil["umpan"]:
            print(f"  Tidak ditemukan umpan ({hasil['status']}, "
                  f"{hasil['dicoba']} alamat dicoba)")
            continue

        for u in hasil["umpan"]:
            ketemu_total += 1
            print(f"  DITEMUKAN ({u.get('cara', '?')})")
            print(f"    url    : {u['url']}")
            print(f"    judul  : {u['judul'][:60]}")
            print(f"    entri  : {u['jumlah_entri']}")
            print(f"    contoh : {u['contoh_judul'][:60]}")

    print("\n" + "=" * 76)
    print(f"Total umpan ditemukan: {ketemu_total}")
    if ketemu_total:
        print("\nSalin alamat di atas ke config/sources.yaml, lalu jalankan")
        print("kembali \"Uji Umpan Berita\" untuk memastikan kesegarannya.")
    else:
        print("\nTidak ada yang ditemukan. Situs-situs ini kemungkinan tidak")
        print("lagi menyediakan RSS publik, atau memblokir akses otomatis.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
