"""
uji_umpan.py — Periksa apakah setiap umpan di config/sources.yaml benar-benar hidup.

Untuk tiap umpan dilaporkan: status HTTP, jumlah entri, umur entri terbaru, dan
apakah tanggal terbitnya terbaca. Umpan yang mati atau tanpa tanggal sebaiknya
dibuang dari konfigurasi.

Skrip ini TIDAK mengubah apa pun.

Pemakaian:
    python src/mdk/uji_umpan.py
    python src/mdk/uji_umpan.py --config config/sources.yaml
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

try:
    import feedparser
    import yaml
except ImportError as e:
    sys.exit(f"GAGAL: paket tidak tersedia ({e.name}).")

try:
    from alat_kesegaran import parse_tanggal, umur_jam
except ImportError:
    try:
        from mdk.alat_kesegaran import parse_tanggal, umur_jam
    except ImportError:
        sys.exit("GAGAL: alat_kesegaran.py tidak ditemukan.")

AGEN = "ManajerDanaKripto/1.0 (+https://manajerdanakripto.com/tentang)"


def periksa(nama: str, url: str) -> dict:
    hasil = {"nama": nama, "url": url, "entri": 0, "status": "?",
             "umur_terbaru": None, "bertanggal": 0, "ok": False}
    try:
        f = feedparser.parse(url, agent=AGEN)
    except Exception as e:                                       # noqa: BLE001
        hasil["status"] = f"galat: {type(e).__name__}"
        return hasil

    hasil["status"] = str(getattr(f, "status", "?"))
    entri = getattr(f, "entries", []) or []
    hasil["entri"] = len(entri)

    if not entri:
        if getattr(f, "bozo", 0):
            hasil["status"] += " (tidak dapat diurai)"
        return hasil

    umur_min = None
    for e in entri[:20]:
        t = parse_tanggal(e)
        if t is None:
            continue
        hasil["bertanggal"] += 1
        j = umur_jam(t)
        if umur_min is None or j < umur_min:
            umur_min = j

    hasil["umur_terbaru"] = umur_min
    # Sehat bila ada entri, mayoritas bertanggal, dan yang terbaru masih segar.
    hasil["ok"] = bool(
        entri and hasil["bertanggal"] >= max(1, len(entri[:20]) // 2)
        and umur_min is not None and umur_min < 24 * 7)
    return hasil


def main() -> int:
    p = argparse.ArgumentParser(description="Periksa kesehatan umpan RSS.")
    p.add_argument("--config", default="config/sources.yaml")
    a = p.parse_args()

    with open(a.config, encoding="utf-8") as fh:
        kfg = yaml.safe_load(fh)

    umpan = kfg.get("umpan_umum", [])
    print(f"Memeriksa {len(umpan)} umpan dari {a.config}\n" + "=" * 78)
    print(f"{'':2} {'Nama':<26} {'Entri':>6} {'Terbaru':>10} {'Tgl':>5}  Status")
    print("-" * 78)

    sehat, sakit = [], []
    for u in umpan:
        r = periksa(u.get("nama", "?"), u.get("url", ""))
        tanda = "OK" if r["ok"] else "!!"
        umur = (f"{r['umur_terbaru']:.0f} jam" if r["umur_terbaru"] is not None
                else "-")
        print(f"{tanda:2} {r['nama'][:26]:<26} {r['entri']:>6} {umur:>10} "
              f"{r['bertanggal']:>5}  {r['status']}")
        (sehat if r["ok"] else sakit).append(r)

    print("-" * 78)
    print(f"Sehat: {len(sehat)} · Bermasalah: {len(sakit)}")

    if sakit:
        print("\nUMPAN BERMASALAH — sebaiknya dibuang dari config/sources.yaml:")
        for r in sakit:
            sebab = ("tidak ada entri" if not r["entri"]
                     else "entri tanpa tanggal" if not r["bertanggal"]
                     else "entri terbaru sudah sangat lama")
            print(f"  - {r['nama']}: {sebab} (status {r['status']})")
            print(f"    {r['url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
