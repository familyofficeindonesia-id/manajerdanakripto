"""
bersihkan_berita_lama.py — Hapus berita basi dari database ManajerDanaKripto.

Dirancang untuk dijalankan lewat GitHub Actions (tanpa terminal). Skrip ini
mendeteksi sendiri file database, nama tabel, dan kolom tanggalnya, jadi tidak
perlu diberi tahu skemanya.

MODE AMAN adalah bawaan: tanpa argumen, skrip hanya MELAPORKAN apa yang akan
dihapus tanpa menghapus apa pun. Baca laporannya dulu, baru jalankan dengan
--hapus.

Contoh:
    python bersihkan_berita_lama.py                    # laporan saja
    python bersihkan_berita_lama.py --hapus            # hapus > 48 jam
    python bersihkan_berita_lama.py --hapus --jam 24   # hapus > 24 jam
    python bersihkan_berita_lama.py --hapus --tanpa-tanggal
    python bersihkan_berita_lama.py --db data/berita.db --hapus
"""

from __future__ import annotations

import argparse
import glob
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone

try:
    from alat_kesegaran import parse_tanggal, umur_jam
except ImportError:
    sys.exit(
        "GAGAL: file alat_kesegaran.py tidak ditemukan.\n"
        "Letakkan kedua file ini di folder yang sama (akar repositori)."
    )

# Kolom yang mungkin menyimpan tanggal terbit, diurut dari yang paling dipercaya.
KANDIDAT_KOLOM_TANGGAL = (
    # Tanggal terbit ASLI dari sumber — paling dipercaya.
    "sumber_terbit", "tanggal_sumber", "sumber_tanggal", "terbit_sumber",
    "published_at", "published", "pubdate", "pub_date", "date_published",
    "tanggal_terbit",
    # Tanggal internal. Hati-hati: kalau ini diisi waktu build, penyaringan
    # berdasarkan kolom ini TIDAK akan menangkap berita basi.
    "terbit_pada", "tanggal", "waktu_terbit", "diambil_pada", "waktu_ambil",
    "created_at", "date", "waktu",
)

# Kolom yang isinya kemungkinan waktu proses, bukan waktu terbit sumber.
KOLOM_MERAGUKAN = {"terbit_pada", "diambil_pada", "waktu_ambil",
                   "created_at", "dilihat_pada"}

# Kolom yang berisi waktu tayang KAMI (bukan tanggal sumber).
KANDIDAT_KOLOM_KAMI = ("terbit_pada", "diambil_pada", "waktu_ambil", "created_at")

# Tabel pembukuan radar. JANGAN dihapus isinya: `terlihat` adalah catatan
# anti-duplikat — kalau dikosongkan, berita lama justru akan diambil ulang
# karena sistem lupa pernah melihatnya.
TABEL_DILINDUNGI = {
    "terlihat", "kesehatan", "klaster", "notifikasi",
    "sumber", "meta", "migrasi",
}

# Kolom yang mungkin berisi judul, untuk keperluan laporan saja.
KANDIDAT_KOLOM_JUDUL = ("judul", "title", "headline", "nama", "slug")


def cari_database(diberikan: str | None) -> list[str]:
    if diberikan:
        if not os.path.exists(diberikan):
            sys.exit(f"GAGAL: database '{diberikan}' tidak ada.")
        return [diberikan]

    pola = ("*.db", "*.sqlite", "*.sqlite3", "*.db3")
    ditemukan = []
    for akar, folder, _ in os.walk("."):
        # Lewati folder yang tidak relevan.
        folder[:] = [f for f in folder if f not in
                     {".git", "node_modules", "__pycache__", ".venv", "venv"}]
        for p in pola:
            ditemukan.extend(glob.glob(os.path.join(akar, p)))
    return sorted(set(ditemukan))


def kolom_tabel(kon: sqlite3.Connection, tabel: str) -> list[str]:
    return [r[1] for r in kon.execute(f'PRAGMA table_info("{tabel}")')]


def pilih_kolom(kolom: list[str], kandidat) -> str | None:
    kecil = {k.lower(): k for k in kolom}
    for c in kandidat:
        if c in kecil:
            return kecil[c]
    return None


def proses_tabel(kon, tabel, batas_jam, hapus, hapus_tanpa_tanggal,
                 tabel_diminta=None):
    if tabel_diminta and tabel.lower() not in tabel_diminta:
        return 0

    if not tabel_diminta and tabel.lower() in TABEL_DILINDUNGI:
        print(f"  Tabel '{tabel}': tabel pembukuan radar — DILINDUNGI, dilewati.")
        print(f"    (pakai --tabel {tabel} kalau memang sengaja ingin diproses)")
        return 0

    kolom = kolom_tabel(kon, tabel)
    kol_tgl = pilih_kolom(kolom, KANDIDAT_KOLOM_TANGGAL)
    kol_judul = pilih_kolom(kolom, KANDIDAT_KOLOM_JUDUL)

    if not kol_tgl:
        print(f"  Tabel '{tabel}': tidak ada kolom tanggal — dilewati.")
        return 0

    print(f"  Tabel '{tabel}' (kolom tanggal: {kol_tgl})")
    print(f"    Semua kolom: {', '.join(kolom)}")
    if kol_tgl.lower() in KOLOM_MERAGUKAN:
        print(f"    PERINGATAN: '{kol_tgl}' mungkin berisi waktu proses/build,")
        print(f"    bukan tanggal terbit asli dari sumber. Kalau artikel lama")
        print(f"    tetap terhitung 'segar' di bawah, itu penyebabnya.")

    pilih_judul = f', "{kol_judul}"' if kol_judul else ""
    baris = list(kon.execute(f'SELECT rowid, "{kol_tgl}"{pilih_judul} FROM "{tabel}"'))

    basi, tanpa_tanggal, segar = [], [], 0
    for r in baris:
        rowid, nilai = r[0], r[1]
        judul = r[2] if kol_judul and len(r) > 2 else "(tanpa judul)"
        tanggal = parse_tanggal(nilai)
        if tanggal is None:
            tanpa_tanggal.append((rowid, judul, nilai))
            continue
        jam = umur_jam(tanggal)
        if jam > batas_jam:
            basi.append((rowid, judul, tanggal, jam))
        else:
            segar += 1

    print(f"    Total {len(baris)} baris — {segar} segar, "
          f"{len(basi)} basi, {len(tanpa_tanggal)} tanpa tanggal")

    for rowid, judul, tanggal, jam in basi[:20]:
        hari = jam / 24
        print(f"    [BASI] {str(judul)[:70]} — {tanggal.date()} ({hari:.1f} hari)")
    if len(basi) > 20:
        print(f"    ... dan {len(basi) - 20} lainnya")

    for rowid, judul, nilai in tanpa_tanggal[:10]:
        print(f"    [KOSONG] {str(judul)[:70]} — nilai: {nilai!r}")
    if len(tanpa_tanggal) > 10:
        print(f"    ... dan {len(tanpa_tanggal) - 10} lainnya")

    target = [b[0] for b in basi]
    if hapus_tanpa_tanggal:
        target += [t[0] for t in tanpa_tanggal]

    if not target:
        return 0

    if not hapus:
        print(f"    -> {len(target)} baris AKAN dihapus (mode laporan, "
              f"belum ada yang dihapus)")
        return 0

    kon.executemany(f'DELETE FROM "{tabel}" WHERE rowid = ?',
                    [(t,) for t in target])
    print(f"    -> {len(target)} baris DIHAPUS")
    return len(target)


def proses_selisih(kon, tabel, batas_jam, hapus, tabel_diminta=None):
    """Hapus baris yang jarak waktu tayang kami dengan tanggal sumbernya
    melebihi `batas_jam`.

    Menangkap artikel yang mengendap lama di antrean lalu tayang seolah baru.
    TIDAK menangkap kasus di mana tanggal dari sumber itu sendiri keliru —
    untuk itu kedua kolom sama-sama salah, sehingga selisihnya tetap kecil.
    """
    if tabel_diminta and tabel.lower() not in tabel_diminta:
        return 0
    if not tabel_diminta and tabel.lower() in TABEL_DILINDUNGI:
        return 0

    kolom = kolom_tabel(kon, tabel)
    kol_sumber = pilih_kolom(kolom, KANDIDAT_KOLOM_TANGGAL[:10])
    kol_kami = pilih_kolom(kolom, KANDIDAT_KOLOM_KAMI)
    kol_judul = pilih_kolom(kolom, KANDIDAT_KOLOM_JUDUL)

    if not kol_sumber or not kol_kami or kol_sumber == kol_kami:
        print(f"  Tabel '{tabel}': tidak punya dua kolom tanggal yang bisa "
              f"dibandingkan — dilewati.")
        return 0

    print(f"  Tabel '{tabel}': membandingkan '{kol_kami}' terhadap '{kol_sumber}'")

    pilih_judul = f', "{kol_judul}"' if kol_judul else ""
    baris = list(kon.execute(
        f'SELECT rowid, "{kol_kami}", "{kol_sumber}"{pilih_judul} FROM "{tabel}"'))

    kena, tak_terbaca = [], 0
    for r in baris:
        rowid, nilai_kami, nilai_sumber = r[0], r[1], r[2]
        judul = r[3] if kol_judul and len(r) > 3 else "(tanpa judul)"
        t_kami = parse_tanggal(nilai_kami)
        t_sumber = parse_tanggal(nilai_sumber)
        if t_kami is None or t_sumber is None:
            tak_terbaca += 1
            continue
        selisih = (t_kami - t_sumber).total_seconds() / 3600.0
        if selisih > batas_jam:
            kena.append((rowid, judul, selisih))

    print(f"    Total {len(baris)} baris — {len(kena)} melewati batas "
          f"{batas_jam} jam, {tak_terbaca} tidak dapat dibandingkan")

    for rowid, judul, selisih in kena[:25]:
        print(f"    [SELISIH] {str(judul)[:64]} — {selisih:.1f} jam "
              f"({selisih / 24:.1f} hari)")
    if len(kena) > 25:
        print(f"    ... dan {len(kena) - 25} lainnya")

    if not kena:
        return 0
    if not hapus:
        print(f"    -> {len(kena)} baris AKAN dihapus (mode laporan)")
        return 0

    kon.executemany(f'DELETE FROM "{tabel}" WHERE rowid = ?',
                    [(k[0],) for k in kena])
    print(f"    -> {len(kena)} baris DIHAPUS")
    return len(kena)


def proses_cocok(kon, tabel, teks, hapus, tabel_diminta=None, batas_jam=0):
    """Hapus baris yang salah satu kolom teksnya memuat `teks`.

    Bila `batas_jam` > 0, hanya baris yang JUGA lebih tua dari batas itu yang
    dihapus — berguna agar berita segar dari penerbit yang sama tidak ikut
    terbuang. Bila `batas_jam` = 0, seluruh baris yang cocok dihapus.
    """
    if tabel_diminta and tabel.lower() not in tabel_diminta:
        return 0
    if not tabel_diminta and tabel.lower() in TABEL_DILINDUNGI:
        return 0

    kolom = kolom_tabel(kon, tabel)
    kol_judul = pilih_kolom(kolom, KANDIDAT_KOLOM_JUDUL)
    kol_tgl = pilih_kolom(kolom, KANDIDAT_KOLOM_TANGGAL)
    cari = teks.lower()

    baris = list(kon.execute(f'SELECT rowid, * FROM "{tabel}"'))
    if not baris:
        return 0
    nama_kol = [d[0] for d in kon.execute(
        f'SELECT rowid, * FROM "{tabel}" LIMIT 1').description]

    kena = []
    for r in baris:
        for k, v in zip(nama_kol, r):
            if isinstance(v, str) and cari in v.lower():
                judul = "(tanpa judul)"
                if kol_judul and kol_judul in nama_kol:
                    judul = str(r[nama_kol.index(kol_judul)])
                tanggal = None
                if kol_tgl and kol_tgl in nama_kol:
                    tanggal = parse_tanggal(r[nama_kol.index(kol_tgl)])
                kena.append((r[0], judul, k, tanggal))
                break

    if not kena:
        return 0

    print(f"  Tabel '{tabel}': {len(kena)} baris memuat {teks!r}")
    if kol_tgl:
        print(f"    Tanggal diambil dari kolom '{kol_tgl}'")

    # Saring lagi berdasarkan umur bila diminta.
    if batas_jam > 0:
        tersaring, aman = [], 0
        for rowid, judul, k, tanggal in kena:
            if tanggal is None:
                tersaring.append((rowid, judul, k, tanggal))
                continue
            if umur_jam(tanggal) > batas_jam:
                tersaring.append((rowid, judul, k, tanggal))
            else:
                aman += 1
        print(f"    Penyaringan umur {batas_jam} jam aktif — "
              f"{len(tersaring)} kena, {aman} dipertahankan karena masih segar")
        kena = tersaring
        if not kena:
            return 0

    for rowid, judul, k, tanggal in kena[:30]:
        cap = tanggal.strftime("%Y-%m-%d %H:%M") if tanggal else "tanpa tanggal"
        umur = f"{umur_jam(tanggal) / 24:>5.1f} hari" if tanggal else "        ?"
        print(f"    [COCOK] {cap} · {umur} · {judul[:56]}")
    if len(kena) > 30:
        print(f"    ... dan {len(kena) - 30} lainnya")

    if not hapus:
        print(f"    -> {len(kena)} baris AKAN dihapus (mode laporan)")
        return 0

    kon.executemany(f'DELETE FROM "{tabel}" WHERE rowid = ?',
                    [(k[0],) for k in kena])
    print(f"    -> {len(kena)} baris DIHAPUS")
    return len(kena)


def main():
    p = argparse.ArgumentParser(description="Hapus berita basi dari database.")
    p.add_argument("--db", help="Path database. Kosongkan untuk deteksi otomatis.")
    p.add_argument("--jam", type=int, default=48,
                   help="Batas umur dalam jam (bawaan: 48).")
    p.add_argument("--hapus", action="store_true",
                   help="Benar-benar hapus. Tanpa ini hanya melapor.")
    p.add_argument("--tanpa-tanggal", action="store_true", dest="tanpa_tanggal",
                   help="Ikut hapus baris yang tanggalnya kosong/tidak terbaca.")
    p.add_argument("--tanpa-cadangan", action="store_true",
                   help="Lewati pembuatan file cadangan .bak.")
    p.add_argument("--tabel",
                   help="Batasi ke tabel tertentu (pisahkan dengan koma). "
                        "Ini juga membuka tabel yang dilindungi.")
    p.add_argument("--pakai-umur", action="store_true", dest="pakai_umur",
                   help="Untuk --cocok: hanya hapus yang JUGA lebih tua dari --jam.")
    p.add_argument("--selisih", type=int, metavar="JAM",
                   help="Hapus baris yang waktu tayang kami berjarak lebih dari "
                        "JAM dari tanggal sumbernya.")
    p.add_argument("--cocok",
                   help="Hapus baris yang memuat teks ini (mis. nama penerbit). "
                        "Mengabaikan penyaringan tanggal.")
    p.add_argument("--skema", action="store_true",
                   help="Hanya tampilkan struktur tabel lalu berhenti.")
    a = p.parse_args()

    if a.skema:
        for db in cari_database(a.db):
            print(f"Database: {db}")
            kon = sqlite3.connect(db)
            for (nama, sql) in kon.execute(
                    "SELECT name, sql FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%'"):
                jml = kon.execute(f'SELECT COUNT(*) FROM "{nama}"').fetchone()[0]
                print(f"\n--- Tabel '{nama}' ({jml} baris) ---\n{sql}")
                contoh = kon.execute(f'SELECT * FROM "{nama}" LIMIT 2').fetchall()
                nama_kol = [d[0] for d in kon.execute(
                    f'SELECT * FROM "{nama}" LIMIT 1').description]
                for baris in contoh:
                    print("  contoh baris:")
                    for k, v in zip(nama_kol, baris):
                        print(f"    {k} = {str(v)[:90]!r}")
            kon.close()
        return

    sekarang = datetime.now(timezone.utc)
    print(f"Waktu sekarang (UTC): {sekarang.isoformat()}")
    if a.cocok:
        if a.pakai_umur:
            print(f"Pencocokan teks: {a.cocok!r} DAN lebih tua dari {a.jam} jam")
        else:
            print(f"Pencocokan teks: {a.cocok!r} (semua, tanpa lihat tanggal)")
    elif a.selisih:
        print(f"Batas selisih tayang vs tanggal sumber: {a.selisih} jam")
    else:
        print(f"Batas umur: {a.jam} jam")
    print(f"Mode: {'HAPUS' if a.hapus else 'LAPORAN SAJA'}\n")

    daftar_db = cari_database(a.db)
    if not daftar_db:
        sys.exit("GAGAL: tidak ada file database ditemukan.")

    total = 0
    for db in daftar_db:
        print(f"Database: {db}")

        if a.hapus and not a.tanpa_cadangan:
            cadangan = db + ".bak"
            shutil.copy2(db, cadangan)
            print(f"  Cadangan dibuat: {cadangan}")

        kon = sqlite3.connect(db)
        try:
            tabel = [r[0] for r in kon.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'")]
            if not tabel:
                print("  (tidak ada tabel)")
                continue
            diminta = ({t.strip().lower() for t in a.tabel.split(",")}
                       if a.tabel else None)
            for t in tabel:
                if a.cocok:
                    total += proses_cocok(kon, t, a.cocok, a.hapus, diminta,
                                          a.jam if a.pakai_umur else 0)
                elif a.selisih:
                    total += proses_selisih(kon, t, a.selisih, a.hapus, diminta)
                else:
                    total += proses_tabel(kon, t, a.jam, a.hapus,
                                          a.tanpa_tanggal, diminta)
            if a.hapus:
                kon.commit()
                kon.execute("VACUUM")
        finally:
            kon.close()
        print()

    if a.hapus:
        print(f"SELESAI: {total} baris dihapus. "
              f"Jalankan ulang build agar situs ikut diperbarui.")
    else:
        print("SELESAI (laporan saja). Tidak ada data yang diubah.\n"
              "Jalankan lagi dengan --hapus kalau laporan di atas sudah sesuai.")


if __name__ == "__main__":
    main()
