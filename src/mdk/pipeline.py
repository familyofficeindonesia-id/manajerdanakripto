"""Orkestrasi pipeline: ambil → saring → tulis ulang → simpan → bangun situs.

CATATAN PERUBAHAN — gerbang kesegaran berita
--------------------------------------------
Sebelumnya, item pada tabel `mentah` yang berstatus 'baru' tidak pernah
kedaluwarsa. Item berskor tinggi bisa mengendap berhari-hari di antrean, lalu
ditulis menjadi artikel dan tayang dengan tanggal hari ini — sehingga berita
lama tampil seolah baru.

Sekarang, sebelum satu pun panggilan API dilakukan, seluruh antrean disaring
berdasarkan `terbit_pada` (tanggal terbit ASLI dari sumber). Item yang lewat
batas umur ditandai 'dilewati' dan tidak akan diproses lagi.

CATATAN PERUBAHAN — kolam kandidat pada jalan bertumpuk
-------------------------------------------------------
Alur penerbitan kini berjalan tiap jam dengan batas kecil (3 artikel) alih-alih
tiga kali sehari dengan batas besar (25). Pola lama mengambil `batas * 2` baris
dari antrean sebagai kandidat — memadai untuk batas 25 (50 kandidat), tetapi
melumpuhkan batas 3: hanya 6 baris yang diperiksa, dan bila 4 di antaranya
ternyata pengulangan, jalan itu cuma menghasilkan 2 artikel meski antrean masih
memuat ratusan berita layak.

Kolam kandidat sekarang dipisahkan dari batas penulisan. Penyaringan duplikat
tidak memanggil API sama sekali, jadi memperbesar kolam tidak menambah biaya —
hanya beberapa milidetik pembacaan SQLite.
"""
from __future__ import annotations

from .alat_kesegaran import alasan_tolak, masih_segar
from .build import Pembangun
from .config import muat_konfigurasi
from .dedup import cari_duplikat
from .entities import registri
from .ingest import Pengambil
from .rewrite import Penulis, kegagalan_sementara
from .store import buka

# Batas umur berita yang boleh ditulis menjadi artikel, dihitung dari tanggal
# terbit sumber. Sengaja lebih longgar dari batas pengambilan supaya berita yang
# masuk tepat sebelum jadwal tidak hangus sebelum sempat ditulis.
#
# Dinaikkan dari 36 ke 48 jam. Log 28 Agustus menunjukkan ambang 36 jam membuang
# justru bahan terbaik di antrean — pengumuman penutupan dana $1,5 miliar
# Franklin Templeton, perubahan lisensi indeks ARK 21Shares, pernyataan Michael
# Saylor dan Bitwise — semuanya gugur pada 36,0 sampai 37,7 jam, yaitu selisih
# menit dari ambang.
#
# Kelonggaran ini TIDAK melanggar prinsip integritas tanggal. Tanggal yang
# ditampilkan tetap tanggal terbit asli dari sumber, dan berita berumur dua hari
# tetap ditandai demikian di situs. Yang dijaga adalah kejujuran tanggal, bukan
# kemudaan berita.
BATAS_JAM_TULIS = 48

# Berapa banyak antrean yang diperiksa kesegarannya dalam satu jalan.
# Angka besar agar sisa antrean lama ikut terkuras, bukan hanya bagian atasnya.
PERIKSA_ANTREAN_MAKS = 2000

# Berapa banyak baris antrean yang dipertimbangkan sebagai kandidat penulisan.
# HARUS jauh lebih besar dari `batas`, karena sebagian besar kandidat gugur
# sebagai pengulangan sebelum sempat terpilih. Lihat catatan di docstring.
KANDIDAT_MINIMUM = 80
KANDIDAT_PER_ARTIKEL = 12

# Berapa banyak judul artikel terbit yang dijadikan pembanding duplikat.
# Semakin besar, semakin jauh ke belakang pengulangan dapat dikenali.
RIWAYAT_JUDUL_MAKS = 400


def tahap_ambil(sertakan_entitas: bool = True, verbose: bool = True) -> dict:
    kfg, reg = muat_konfigurasi(), registri()
    simpan = buka(kfg)
    if verbose:
        print("▸ Tahap 1/3 — Mengambil umpan berita")
    return Pengambil(kfg, reg, simpan).jalankan(sertakan_entitas, verbose)


def _kuras_antrean_basi(simpan, verbose: bool = True) -> int:
    """Tandai 'dilewati' semua item antrean yang tanggal sumbernya sudah lewat.

    Dijalankan sebelum pemilihan artikel supaya berita basi tidak pernah
    sampai ke tahap penulisan, dan tidak menyumbat antrean di jalan berikutnya.
    """
    antre = simpan.mentah_menunggu(PERIKSA_ANTREAN_MAKS)
    dibuang = 0
    for baris in antre:
        alasan = alasan_tolak(baris["terbit_pada"], BATAS_JAM_TULIS)
        if alasan is None:
            continue
        simpan.tandai_mentah(baris["id"], "dilewati")
        dibuang += 1
        if verbose and dibuang <= 15:
            print(f"  [BASI] {baris['judul'][:70]} — {alasan}")
    if verbose:
        if dibuang > 15:
            print(f"  ... dan {dibuang - 15} item basi lainnya")
        if dibuang:
            print(f"  ✗ {dibuang} item basi dikeluarkan dari antrean "
                  f"(batas {BATAS_JAM_TULIS} jam dari tanggal terbit sumber)")
            simpan.catat("tulis", f"antrean basi dibuang: {dibuang}")
    return dibuang


def tahap_tulis(batas: int | None = None, verbose: bool = True) -> dict:
    kfg, reg = muat_konfigurasi(), registri()
    simpan = buka(kfg)
    batas = batas or int(kfg.ai.get("batas_artikel_per_jalankan", 40))

    # Gerbang kesegaran — dijalankan lebih dahulu, sebelum biaya API keluar.
    basi = _kuras_antrean_basi(simpan, verbose)

    # Kolam kandidat: cukup besar agar pengulangan yang gugur tidak memakan
    # jatah penulisan. Tidak ada panggilan API di tahap ini.
    kandidat = max(KANDIDAT_MINIMUM, batas * KANDIDAT_PER_ARTIKEL)
    antre = simpan.mentah_menunggu(kandidat)
    if verbose:
        print(f"  Kolam kandidat: {len(antre)} item antrean "
              f"(target tulis {batas})")

    # Riwayat judul yang SUDAH terbit, dipakai sebagai pembanding duplikat.
    # Tanpa ini, satu peristiwa yang sama bisa ditulis berulang kali pada
    # hari-hari berbeda — persis yang terjadi ketika Google News menyajikan
    # ulang artikel lama dengan URL baru setiap beberapa hari.
    riwayat = [(a.id, a.judul)
               for a in simpan.artikel("terbit", RIWAYAT_JUDUL_MAKS)]
    if verbose and riwayat:
        print(f"  Pembanding duplikat: {len(riwayat)} judul yang sudah terbit")

    # Buang duplikat lintas sumber sebelum memanggil model (hemat biaya API).
    terpilih, judul_dipakai = [], list(riwayat)
    ulangan = 0
    diperiksa = 0
    for baris in antre:
        diperiksa += 1
        # Pengaman kedua: kalau ada item lolos di antara kurasan dan pemilihan.
        if not masih_segar(baris["terbit_pada"], BATAS_JAM_TULIS):
            simpan.tandai_mentah(baris["id"], "dilewati")
            basi += 1
            continue
        if cari_duplikat(baris["judul"], judul_dipakai):
            simpan.tandai_mentah(baris["id"], "dilewati")
            ulangan += 1
            if verbose and ulangan <= 10:
                print(f"  [ULANG] {baris['judul'][:70]}")
            continue
        judul_dipakai.append((baris["id"], baris["judul"]))
        terpilih.append(baris)
        if len(terpilih) >= batas:
            break

    # Item yang tidak sempat diperiksa TETAP berstatus 'baru' dan akan menjadi
    # kandidat pada jalan berikutnya. Inilah yang membuat pola "tiap jam,
    # sedikit-sedikit" bekerja: antrean menetes, bukan dibuang.
    tersisa = len(antre) - diperiksa

    if verbose:
        if ulangan > 10:
            print(f"  ... dan {ulangan - 10} pengulangan lainnya")
        print(f"▸ Tahap 2/3 — Menulis ulang {len(terpilih)} berita "
              f"({ulangan} pengulangan dibuang, "
              f"{tersisa} tersisa di antrean untuk jalan berikutnya)")
    if not terpilih:
        return {"ditulis": 0, "gagal": 0, "dilewati": ulangan,
                "tersisa": tersisa, "basi": basi}

    artikel, gagal = Penulis(kfg, reg).tulis_banyak(terpilih, verbose)
    for a in artikel:
        simpan.simpan_artikel(a)
        simpan.tandai_mentah(a.id, "diproses")
    # Kegagalan sementara dikembalikan ke antrean, bukan dikubur.
    #
    # `rewrite.py` sudah membedakan server sibuk dari kuota habis dan bahkan
    # mencetak janji "semuanya kembali ke antrean untuk jalan berikutnya" —
    # tetapi janji itu tidak pernah ditepati selama seluruh kegagalan ditandai
    # 'gagal' di sini tanpa memeriksa sebabnya. Jalan 28 Agustus kehilangan lima
    # berita layak dengan cara ini: empat karena server Gemini sedang padat, satu
    # karena kuota harian habis. Tidak satu pun disebabkan oleh beritanya.
    #
    # Item yang dikembalikan tidak akan berputar selamanya: gerbang kesegaran di
    # awal jalan berikutnya tetap menguras yang sudah lewat 48 jam.
    dikubur = dikembalikan = 0
    for id_, alasan in gagal:
        if kegagalan_sementara(alasan):
            simpan.tandai_mentah(id_, "baru")
            dikembalikan += 1
        else:
            simpan.tandai_mentah(id_, "gagal")
            dikubur += 1
        simpan.catat("tulis", f"{id_}: {alasan}")

    if verbose and dikembalikan:
        print(f"  ↩ {dikembalikan} berita dikembalikan ke antrean "
              f"(kegagalan sementara di sisi layanan, bukan isi beritanya)")

    ringkas = {"ditulis": len(artikel), "gagal": dikubur,
               "dikembalikan": dikembalikan,
               "dilewati": ulangan, "tersisa": tersisa, "basi": basi}
    simpan.catat("tulis", str(ringkas))
    return ringkas


def tahap_bangun(verbose: bool = True) -> dict:
    kfg = muat_konfigurasi()
    if verbose:
        print("▸ Tahap 3/3 — Membangun situs statis")
    return Pembangun(kfg, registri(), buka(kfg)).bangun(verbose)


def jalankan_penuh(batas: int | None = None, sertakan_entitas: bool = True,
                   verbose: bool = True) -> dict:
    hasil = {"ambil": tahap_ambil(sertakan_entitas, verbose),
             "tulis": tahap_tulis(batas, verbose)}
    hasil["bangun"] = tahap_bangun(verbose)
    return hasil
