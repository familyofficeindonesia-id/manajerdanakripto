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
"""
from __future__ import annotations

from .alat_kesegaran import alasan_tolak, masih_segar
from .build import Pembangun
from .config import muat_konfigurasi
from .dedup import cari_duplikat
from .entities import registri
from .ingest import Pengambil
from .rewrite import Penulis
from .store import buka

# Batas umur berita yang boleh ditulis menjadi artikel, dihitung dari tanggal
# terbit sumber. Sengaja lebih longgar dari batas pengambilan (24 jam) supaya
# berita yang masuk tepat sebelum jadwal tidak hangus sebelum sempat ditulis.
BATAS_JAM_TULIS = 36

# Berapa banyak antrean yang diperiksa kesegarannya dalam satu jalan.
# Angka besar agar sisa antrean lama ikut terkuras, bukan hanya bagian atasnya.
PERIKSA_ANTREAN_MAKS = 2000

# Berapa banyak judul artikel terbit yang dijadikan pembanding duplikat.
# Semakin besar, semakin jauh ke belakang pengulangan dapat dikenali.
RIWAYAT_JUDUL_MAKS = 400

# Porsi minimum artikel berbahasa Indonesia dalam satu jalan penulisan.
# 0,60 berarti 60% jatah diberikan lebih dulu kepada sumber lokal; sisa jatah
# yang tidak terpakai (karena stok lokal kurang) dialihkan ke sumber asing,
# sehingga tidak ada slot yang terbuang.
PORSI_LOKAL = 0.60

# Seberapa dalam antrean digali untuk mencari stok lokal. Sumber lokal biasanya
# berskor lebih rendah daripada media global, jadi pengambilan harus lebih
# dalam daripada sekadar bagian atas antrean.
GALI_ANTREAN = 500

# Kegagalan yang bersifat sementara. Item dengan alasan ini dikembalikan ke
# status 'baru' agar dicoba lagi pada jalan berikutnya, bukan dibuang sebagai
# 'gagal'. Batas alaminya adalah saringan usia: bila berita keburu basi
# sebelum berhasil ditulis, ia akan terkuras sendiri dari antrean.
GALAT_SEMENTARA = (
    "503", "502", "504", "429",
    "unavailable", "overloaded", "resource_exhausted",
    "quota", "rate limit", "ratelimit",
    "timeout", "timed out", "connection",
)


def tahap_ambil(sertakan_entitas: bool = True, verbose: bool = True) -> dict:
    kfg, reg = muat_konfigurasi(), registri()
    simpan = buka(kfg)
    if verbose:
        print("▸ Tahap 1/3 — Mengambil umpan berita")
    return Pengambil(kfg, reg, simpan).jalankan(sertakan_entitas, verbose)


def _sementara(alasan: str) -> bool:
    """True bila kegagalan bersifat sementara dan layak dicoba ulang."""
    teks = (alasan or "").lower()
    return any(tanda in teks for tanda in GALAT_SEMENTARA)


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

    antre = simpan.mentah_menunggu(GALI_ANTREAN)

    # Riwayat judul yang SUDAH terbit, dipakai sebagai pembanding duplikat.
    # Tanpa ini, satu peristiwa yang sama bisa ditulis berulang kali pada
    # hari-hari berbeda — persis yang terjadi ketika Google News menyajikan
    # ulang artikel lama dengan URL baru setiap beberapa hari.
    riwayat = [(a.id, a.judul)
               for a in simpan.artikel("terbit", RIWAYAT_JUDUL_MAKS)]
    if verbose and riwayat:
        print(f"  Pembanding duplikat: {len(riwayat)} judul yang sudah terbit")

    # Jatah lokal dihitung lebih dulu, lalu diisi dari antrean berbahasa
    # Indonesia. Sisanya diisi sumber asing. Urutan skor tetap dihormati di
    # dalam masing-masing kelompok.
    jatah_lokal = int(batas * PORSI_LOKAL)
    lokal = [b for b in antre if (b["bahasa"] or "en").lower().startswith("id")]
    asing = [b for b in antre if not (b["bahasa"] or "en").lower().startswith("id")]

    if verbose:
        print(f"  Stok antrean: {len(lokal)} lokal · {len(asing)} asing "
              f"(jatah lokal {jatah_lokal} dari {batas})")
        if len(lokal) < jatah_lokal:
            print(f"  ! Stok lokal kurang dari jatah — {jatah_lokal - len(lokal)} "
                  f"slot dialihkan ke sumber asing")

    # Lokal didahulukan, lalu asing. Pemotongan jumlah dilakukan saat pemilihan
    # supaya item lokal yang tersaring duplikat dapat digantikan item lokal lain.
    urutan = lokal + asing
    kuota_lokal_terpakai = 0

    # Buang duplikat lintas sumber sebelum memanggil model (hemat biaya API).
    terpilih, judul_dipakai = [], list(riwayat)
    ulangan = 0
    for baris in urutan:
        adalah_lokal = (baris["bahasa"] or "en").lower().startswith("id")

        # Jangan biarkan sumber asing memakan jatah sebelum stok lokal habis
        # diperiksa; urutan `lokal + asing` sudah menjamin ini, jadi di sini
        # cukup dicatat untuk laporan.
        if adalah_lokal:
            kuota_lokal_terpakai += 0   # dihitung setelah lolos saringan

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
        if adalah_lokal:
            kuota_lokal_terpakai += 1
        if len(terpilih) >= batas:
            break

    if verbose:
        if ulangan > 10:
            print(f"  ... dan {ulangan - 10} pengulangan lainnya")
        print(f"▸ Tahap 2/3 — Menulis ulang {len(terpilih)} berita "
              f"({kuota_lokal_terpakai} lokal, "
              f"{len(terpilih) - kuota_lokal_terpakai} asing · "
              f"{ulangan} pengulangan)")
    if not terpilih:
        return {"ditulis": 0, "gagal": 0, "dicoba_lagi": 0, "lokal": 0,
                "dilewati": len(antre), "basi": basi}

    artikel, gagal = Penulis(kfg, reg).tulis_banyak(terpilih, verbose)
    for a in artikel:
        simpan.simpan_artikel(a)
        simpan.tandai_mentah(a.id, "diproses")
    dicoba_lagi = 0
    for id_, alasan in gagal:
        if _sementara(alasan):
            # Kembalikan ke antrean, jangan dibuang. Kegagalan seperti 503 atau
            # kuota habis bukan salah beritanya.
            simpan.tandai_mentah(id_, "baru")
            dicoba_lagi += 1
            simpan.catat("tulis", f"{id_}: DICOBA LAGI — {alasan[:120]}")
        else:
            simpan.tandai_mentah(id_, "gagal")
            simpan.catat("tulis", f"{id_}: {alasan}")

    if verbose and dicoba_lagi:
        print(f"  ↻ {dicoba_lagi} berita dikembalikan ke antrean "
              f"(kegagalan sementara, akan dicoba lagi)")

    ringkas = {"ditulis": len(artikel), "gagal": len(gagal) - dicoba_lagi,
               "dicoba_lagi": dicoba_lagi, "lokal": kuota_lokal_terpakai,
               "dilewati": len(antre) - len(terpilih), "basi": basi}
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
