"""Subperintah `mdk radar` — pemantauan sumber berita.

    mdk radar bangun          Bangun config/watchlist.yaml dari registri
    mdk radar temukan         Temukan umpan RSS resmi tiap perusahaan
    mdk radar periksa         Uji setiap URL sumber, nonaktifkan yang mati
    mdk radar daftar          Tampilkan daftar sumber (tabel atau CSV)
    mdk radar pantau          Satu putaran pemantauan
    mdk radar jaga            Pemantauan berkelanjutan (daemon)
    mdk radar status          Ringkasan temuan dan kesehatan sumber
    mdk radar dasbor          Bangkitkan dasbor HTML
    mdk radar teruskan        Dorong temuan ke antrean terjemahan
"""
from __future__ import annotations

import csv
import random
import signal
import sys
import time
from pathlib import Path

import yaml

from ..config import muat_konfigurasi
from ..entities import registri
from ..store import buka
from ..utils import format_tanggal_id, potong, sekarang_wib
from . import penemu as mod_penemu
from .notifikasi import Pengirim
from .pemantau import Pemantau
from .simpan import buka_radar
from .sumber import Sumber, bangun_semua, ringkas

BERKAS_WATCHLIST = "config/watchlist.yaml"
_berhenti = False


def _garis(judul: str) -> None:
    print(f"\n\033[1m{judul}\033[0m\n" + "─" * 70)


def _muat_organisasi(kfg) -> list[dict]:
    berkas = kfg.akar / "config" / "organisasi.yaml"
    if not berkas.exists():
        print("✗ config/organisasi.yaml tidak ditemukan.")
        return []
    return (yaml.safe_load(berkas.read_text(encoding="utf-8")) or {}).get("organisasi", [])


def _jalur_watchlist(kfg) -> Path:
    return kfg.akar / BERKAS_WATCHLIST


def _muat_watchlist(kfg) -> list[Sumber]:
    jalur = _jalur_watchlist(kfg)
    if not jalur.exists():
        return []
    data = yaml.safe_load(jalur.read_text(encoding="utf-8")) or {}
    return [Sumber.dari_dict(d) for d in data.get("sumber", [])]


def _tulis_watchlist(kfg, sumber: list[Sumber], catatan: str = "") -> Path:
    jalur = _jalur_watchlist(kfg)
    isi = {
        "dibangkitkan_pada": sekarang_wib().isoformat(),
        "catatan": catatan or ("Dibangkitkan oleh `mdk radar bangun`. "
                               "Aman disunting manual; jalankan `mdk radar periksa` setelahnya."),
        "ringkasan": ringkas(sumber),
        "sumber": [s.dict() for s in sumber],
    }
    jalur.parent.mkdir(parents=True, exist_ok=True)
    jalur.write_text(yaml.safe_dump(isi, allow_unicode=True, sort_keys=False, width=200),
                     encoding="utf-8")
    return jalur


# ============================================================== perintah ======
def perintah_bangun(args) -> int:
    kfg, reg = muat_konfigurasi(), registri()
    org = _muat_organisasi(kfg)
    _garis("MEMBANGUN DAFTAR SUMBER PEMANTAUAN")

    opsi = dict(getattr(kfg, "radar", {}) or {})
    opsi.setdefault("edisi_indonesia", True)
    opsi.setdefault("bing", True)
    opsi.setdefault("reddit", args.reddit)
    opsi.setdefault("edgar", not args.tanpa_edgar)

    # Pertahankan umpan resmi yang sudah ditemukan pada jalannya sebelumnya.
    lama = {s.id: s for s in _muat_watchlist(kfg)}
    for o in org:
        resmi = [s for s in lama.values()
                 if s.entitas == o["slug"] and s.jenis == "situs_resmi"]
        if resmi:
            o["umpan_resmi"] = [{"url": s.url, "judul": s.label,
                                 "terverifikasi": s.terverifikasi} for s in resmi]

    sumber = bangun_semua(reg, org, opsi)

    # Pertahankan status aktif/nonaktif yang pernah disunting operator.
    for s in sumber:
        if s.id in lama:
            s.aktif = lama[s.id].aktif
            s.terverifikasi = lama[s.id].terverifikasi or s.terverifikasi

    jalur = _tulis_watchlist(kfg, sumber)
    r = ringkas(sumber)

    print(f"  Tokoh dipantau      : {len(reg.tokoh)}")
    print(f"  Organisasi dipantau : {len(org)}")
    print(f"  Total sumber        : {r['total']} ({r['aktif']} aktif)")
    print(f"\n  Rincian per jenis:")
    for jenis, n in r["per_jenis"].items():
        print(f"    {jenis:<18} {n:>4}")
    print(f"\n✓ Ditulis ke {jalur.relative_to(kfg.akar)}")
    print("\n  Langkah berikutnya:")
    print("    1. python -m mdk radar temukan    (cari umpan RSS resmi perusahaan)")
    print("    2. python -m mdk radar periksa    (uji seluruh URL)")
    print("    3. python -m mdk radar pantau     (putaran pemantauan pertama)")
    return 0


def perintah_temukan(args) -> int:
    kfg = muat_konfigurasi()
    org = _muat_organisasi(kfg)
    _garis("MENEMUKAN UMPAN RESMI PERUSAHAAN")
    print("  Membuka situs resmi dan membaca deklarasi umpannya.")
    print("  URL tidak ditebak — hanya yang benar-benar mengembalikan entri yang disimpan.\n")

    hasil = mod_penemu.temukan_banyak(
        org, maks_serentak=args.serentak, maks_umpan=args.maks_umpan)

    # Tulis balik ke organisasi.yaml agar `radar bangun` memakainya.
    ditemukan = 0
    for o in org:
        r = hasil.get(o["slug"])
        if r and r["umpan"]:
            o["umpan_resmi"] = [{"url": u["url"], "judul": u["judul"],
                                 "terverifikasi": True} for u in r["umpan"]]
            o["terverifikasi"] = True
            ditemukan += len(r["umpan"])

    berkas = kfg.akar / "config" / "organisasi.yaml"
    asli = berkas.read_text(encoding="utf-8")
    kepala = asli.split("organisasi:")[0]
    berkas.write_text(
        kepala + yaml.safe_dump({"organisasi": org}, allow_unicode=True,
                                sort_keys=False, width=200),
        encoding="utf-8")

    tanpa = [o["nama"] for o in org if not o.get("umpan_resmi")]
    print(f"\n✓ {ditemukan} umpan resmi ditemukan pada {len(org) - len(tanpa)} organisasi")
    if tanpa:
        print(f"\n  {len(tanpa)} organisasi tanpa umpan resmi (tetap dipantau lewat mesin berita):")
        for n in tanpa[:15]:
            print(f"    · {n}")
        if len(tanpa) > 15:
            print(f"    · … dan {len(tanpa) - 15} lainnya")
    print("\n  Jalankan `python -m mdk radar bangun` untuk memasukkannya ke watchlist.")
    return 0


def perintah_periksa(args) -> int:
    kfg = muat_konfigurasi()
    db = buka_radar(kfg)
    sumber = _muat_watchlist(kfg)
    if not sumber:
        print("✗ watchlist.yaml kosong. Jalankan `mdk radar bangun` lebih dahulu.")
        return 1

    _garis("MENGUJI SELURUH SUMBER")
    target = [s for s in sumber if args.semua or not s.terverifikasi]
    if args.jenis:
        target = [s for s in target if s.jenis == args.jenis]
    print(f"  Menguji {len(target)} dari {len(sumber)} sumber…\n")

    hidup, mati = 0, 0
    for i, s in enumerate(target, 1):
        info = mod_penemu.validasi_umpan(s.url, timeout=args.timeout)
        if info:
            s.terverifikasi, s.aktif, hidup = True, True, hidup + 1
            db.catat_sukses(s.id, s.url, "", "", info["jumlah_entri"], 0)
            tanda, ket = "✓", f"{info['jumlah_entri']:>2} entri · {potong(info['contoh_judul'], 44)}"
        else:
            s.terverifikasi = False
            mati += 1
            if args.nonaktifkan_mati:
                s.aktif = False
            db.catat_gagal(s.id, s.url, "gagal-validasi", batas_nonaktif=1)
            tanda, ket = "✗", "tidak menghasilkan entri yang sah"
        print(f"  [{i:>3}/{len(target)}] {tanda} {s.label[:44]:<44} {ket}")

    _tulis_watchlist(kfg, sumber, "Diperbarui oleh `mdk radar periksa`.")
    print(f"\n✓ {hidup} sumber hidup · {mati} tidak merespons")
    if mati and not args.nonaktifkan_mati:
        print("  Tambahkan --nonaktifkan-mati untuk menonaktifkannya otomatis.")
    return 0


def perintah_daftar(args) -> int:
    kfg = muat_konfigurasi()
    sumber = _muat_watchlist(kfg)
    if not sumber:
        print("✗ watchlist.yaml kosong. Jalankan `mdk radar bangun` lebih dahulu.")
        return 1
    if args.entitas:
        sumber = [s for s in sumber if s.entitas == args.entitas]
    if args.jenis:
        sumber = [s for s in sumber if s.jenis == args.jenis]

    if args.csv:
        jalur = Path(args.csv)
        jalur.parent.mkdir(parents=True, exist_ok=True)
        with jalur.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["ID", "Entitas", "Jenis Entitas", "Jenis Sumber", "Label",
                        "URL", "Prioritas", "Aktif", "Terverifikasi"])
            for s in sumber:
                w.writerow([s.id, s.entitas, s.jenis_entitas, s.jenis, s.label, s.url,
                            s.prioritas, "ya" if s.aktif else "tidak",
                            "ya" if s.terverifikasi else "belum"])
        print(f"✓ {len(sumber)} sumber diekspor ke {jalur}")
        return 0

    _garis(f"DAFTAR SUMBER ({len(sumber)})")
    for s in sumber[: args.batas]:
        tanda = "●" if s.aktif else "○"
        print(f"  {tanda} [{s.jenis:<15}] {s.label[:50]:<50}")
        print(f"      {s.url[:110]}")
    if len(sumber) > args.batas:
        print(f"\n  … dan {len(sumber) - args.batas} lainnya. Pakai --batas atau --csv.")
    return 0


def _satu_putaran(kfg, reg, org, sumber, db, pemantau, pengirim,
                  putaran_ke: int, verbose: bool) -> dict:
    hasil = pemantau.putaran(sumber, putaran_ke=putaran_ke, verbose=verbose)
    baru = hasil.get("klaster_baru", [])
    if baru:
        pengirim.salurkan(baru, verbose=verbose)
    return hasil


def perintah_pantau(args) -> int:
    kfg, reg = muat_konfigurasi(), registri()
    org = _muat_organisasi(kfg)
    sumber = _muat_watchlist(kfg)
    if not sumber:
        print("✗ watchlist.yaml kosong. Jalankan `mdk radar bangun` lebih dahulu.")
        return 1

    db = buka_radar(kfg)
    pemantau = Pemantau(kfg, reg, db, org)
    pengirim = Pengirim(kfg, db, reg, org)

    _garis("PUTARAN PEMANTAUAN")
    for nama, siap, alasan in pengirim.status_kanal():
        print(f"  kanal {nama:<9} {'siap' if siap else 'tidak aktif — ' + alasan}")
    print()

    hasil = _satu_putaran(kfg, reg, org, sumber, db, pemantau, pengirim, 1, not args.senyap)
    print(f"\n✓ {hasil['dijajaki']} sumber dijajaki · {hasil.get('ok', 0)} berubah · "
          f"{hasil.get('tidak_berubah', 0)} tanpa perubahan · {hasil.get('galat', 0)} galat")
    print(f"  {hasil['baru']} item baru dalam {hasil['klaster']} klaster peristiwa")

    if args.teruskan:
        n = pemantau.teruskan_ke_antrean(buka(kfg), batas=args.batas_terusan)
        print(f"  {n} temuan diteruskan ke antrean terjemahan")
    return 0


def perintah_jaga(args) -> int:
    """Pemantauan berkelanjutan dengan interval acak agar pola tidak seragam."""
    global _berhenti
    kfg, reg = muat_konfigurasi(), registri()
    org = _muat_organisasi(kfg)
    sumber = _muat_watchlist(kfg)
    if not sumber:
        print("✗ watchlist.yaml kosong. Jalankan `mdk radar bangun` lebih dahulu.")
        return 1

    db = buka_radar(kfg)
    pemantau = Pemantau(kfg, reg, db, org)
    pengirim = Pengirim(kfg, db, reg, org)

    def tangani(signum, frame):                                   # noqa: ARG001
        global _berhenti
        _berhenti = True
        print("\n▸ Menyelesaikan putaran berjalan lalu berhenti…")

    signal.signal(signal.SIGINT, tangani)
    signal.signal(signal.SIGTERM, tangani)

    _garis("RADAR BERJALAN")
    print(f"  Sumber      : {len([s for s in sumber if s.aktif])} aktif")
    print(f"  Interval    : {args.interval} menit (± {args.jitter} menit)")
    print(f"  Kanal aktif : {', '.join(n for n, siap, _ in pengirim.status_kanal() if siap)}")
    print("  Tekan Ctrl+C untuk berhenti.\n")

    putaran_ke, total_baru = 0, 0
    while not _berhenti:
        putaran_ke += 1
        mulai = time.monotonic()
        print(f"\033[2m[{format_tanggal_id(sekarang_wib())}] putaran #{putaran_ke}\033[0m")
        try:
            hasil = _satu_putaran(kfg, reg, org, sumber, db, pemantau, pengirim,
                                  putaran_ke, not args.senyap)
            total_baru += hasil["baru"]
            print(f"  {hasil['baru']} baru · {hasil['klaster']} klaster · "
                  f"{hasil.get('galat', 0)} galat · {time.monotonic() - mulai:.0f} dtk")
            if args.teruskan:
                pemantau.teruskan_ke_antrean(buka(kfg), batas=args.batas_terusan)
        except Exception as e:                                    # noqa: BLE001
            print(f"  ✗ putaran gagal: {type(e).__name__}: {e}")

        if putaran_ke % 24 == 0:
            dibuang = db.pangkas(hari=int(args.simpan_hari))
            if dibuang:
                print(f"  · pemangkasan arsip: {dibuang} catatan lama dihapus")

        jeda = max(60, (args.interval + random.uniform(-args.jitter, args.jitter)) * 60)
        for _ in range(int(jeda)):
            if _berhenti:
                break
            time.sleep(1)

    print(f"\n▸ Radar berhenti setelah {putaran_ke} putaran, {total_baru} temuan.")
    return 0


def perintah_status(args) -> int:
    kfg = muat_konfigurasi()
    db = buka_radar(kfg)
    reg = registri()
    org = {o["slug"]: o["nama"] for o in _muat_organisasi(kfg)}
    s = db.statistik()
    sumber = _muat_watchlist(kfg)

    _garis("STATUS RADAR")
    print(f"  Sumber terdaftar    : {len(sumber)} ({sum(1 for x in sumber if x.aktif)} aktif)")
    print(f"  Sumber sehat        : {s['sumber_aktif']} · nonaktif otomatis: {s['sumber_nonaktif']}")
    print(f"  Temuan total        : {s['total_temuan']:,}")
    print(f"  Temuan 24 jam       : {s['temuan_24jam']}")
    print(f"  Klaster peristiwa   : {s['klaster']:,}")
    print(f"  Antre terjemahan    : {s['antre_terjemahan']}")

    if s["entitas_teratas"]:
        print("\n  Entitas paling banyak diberitakan (7 hari):")
        for b in s["entitas_teratas"]:
            slug = b["entitas"]
            nama = (reg.tokoh[slug].nama if slug in reg.tokoh else org.get(slug, slug))
            print(f"    {b['c']:>3}  {nama}")

    terbaru = db.temuan_terbaru(jam=24, batas=args.batas)
    if terbaru:
        print(f"\n  {len(terbaru)} temuan terbaru:")
        for t in terbaru[:args.batas]:
            slug = t.get("entitas", "")
            nama = (reg.tokoh[slug].nama if slug in reg.tokoh else org.get(slug, slug))
            print(f"    · [{nama[:22]:<22}] {potong(t.get('judul') or '', 62)}")
    return 0


def perintah_dasbor(args) -> int:
    from .laporan import bangun_dasbor
    kfg = muat_konfigurasi()
    jalur = bangun_dasbor(kfg, buka_radar(kfg), registri(),
                          _muat_organisasi(kfg), _muat_watchlist(kfg), jam=args.jam)
    print(f"✓ Dasbor ditulis ke {jalur}")
    print(f"  Buka: file://{jalur}")
    return 0


def perintah_teruskan(args) -> int:
    kfg, reg = muat_konfigurasi(), registri()
    org = _muat_organisasi(kfg)
    db = buka_radar(kfg)
    pemantau = Pemantau(kfg, reg, db, org)
    n = pemantau.teruskan_ke_antrean(buka(kfg), batas=args.batas)
    _garis("MENERUSKAN KE ANTREAN TERJEMAHAN")
    print(f"✓ {n} temuan diproses")
    print("  Lanjutkan dengan: python -m mdk tulis")
    return 0


# ============================================================== parser ========
def daftarkan(subparser) -> None:
    """Pasang subperintah `radar` pada parser utama."""
    p = subparser.add_parser("radar", help="pemantauan sumber berita tokoh & perusahaan")
    sub = p.add_subparsers(dest="subperintah", required=True)

    b = sub.add_parser("bangun", help="bangun watchlist dari registri entitas")
    b.add_argument("--reddit", action="store_true", help="sertakan sumber Reddit")
    b.add_argument("--tanpa-edgar", action="store_true", help="lewati arsip SEC")
    b.set_defaults(fungsi=perintah_bangun)

    t = sub.add_parser("temukan", help="temukan umpan RSS resmi perusahaan")
    t.add_argument("--serentak", type=int, default=5)
    t.add_argument("--maks-umpan", type=int, default=3)
    t.set_defaults(fungsi=perintah_temukan)

    v = sub.add_parser("periksa", help="uji setiap URL sumber")
    v.add_argument("--semua", action="store_true", help="uji ulang termasuk yang sudah terverifikasi")
    v.add_argument("--jenis", default="", help="batasi pada satu jenis sumber")
    v.add_argument("--timeout", type=float, default=15.0)
    v.add_argument("--nonaktifkan-mati", action="store_true")
    v.set_defaults(fungsi=perintah_periksa)

    d = sub.add_parser("daftar", help="tampilkan atau ekspor daftar sumber")
    d.add_argument("--entitas", default="", help="saring berdasarkan slug entitas")
    d.add_argument("--jenis", default="", help="saring berdasarkan jenis sumber")
    d.add_argument("--batas", type=int, default=40)
    d.add_argument("--csv", default="", help="ekspor ke berkas CSV")
    d.set_defaults(fungsi=perintah_daftar)

    m = sub.add_parser("pantau", help="satu putaran pemantauan")
    m.add_argument("--senyap", action="store_true")
    m.add_argument("--teruskan", action="store_true", help="langsung dorong ke antrean terjemahan")
    m.add_argument("--batas-terusan", type=int, default=60)
    m.set_defaults(fungsi=perintah_pantau)

    j = sub.add_parser("jaga", help="pemantauan berkelanjutan")
    j.add_argument("--interval", type=float, default=20, help="menit antar putaran")
    j.add_argument("--jitter", type=float, default=4, help="variasi acak dalam menit")
    j.add_argument("--senyap", action="store_true")
    j.add_argument("--teruskan", action="store_true")
    j.add_argument("--batas-terusan", type=int, default=60)
    j.add_argument("--simpan-hari", type=int, default=120)
    j.set_defaults(fungsi=perintah_jaga)

    s = sub.add_parser("status", help="ringkasan temuan & kesehatan sumber")
    s.add_argument("--batas", type=int, default=15)
    s.set_defaults(fungsi=perintah_status)

    g = sub.add_parser("dasbor", help="bangkitkan dasbor HTML")
    g.add_argument("--jam", type=int, default=48)
    g.set_defaults(fungsi=perintah_dasbor)

    f = sub.add_parser("teruskan", help="dorong temuan ke antrean terjemahan")
    f.add_argument("--batas", type=int, default=100)
    f.set_defaults(fungsi=perintah_teruskan)


def main(args) -> int:
    return args.fungsi(args)
