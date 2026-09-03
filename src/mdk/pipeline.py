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

import json

from .alat_kesegaran import alasan_tolak, masih_segar
from .build import Pembangun
from .config import muat_konfigurasi
from .dedup import AMBANG_LINTAS_BAHASA, AMBANG_SEBAHASA, cari_duplikat
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

# Berapa artikel paling banyak boleh terbit tentang SATU tokoh dalam satu jalan.
#
# Jalan #122 (4 September 2026) menerbitkan enam artikel; empat di antaranya
# tentang Arthur Hayes, berjajar di Sorotan Hari Ini. Dedup tidak salah — tiga
# dari empat itu memang peristiwa berbeda (proyeksi Ethereum 10.000, target
# Ether 2026, prediksi Bitcoin US$1 juta). Yang tidak ada adalah pagar
# KOMPOSISI: satu tokoh yang sedang ramai diberitakan menghasilkan banyak item
# berskor tinggi sekaligus, karena namanya ada di judul, dan mereka menduduki
# puncak antrean bersama-sama.
#
# Nilai 0 mematikan pagar ini sepenuhnya.
MAKS_ARTIKEL_PER_TOKOH = 2


def _tokoh_utama(baris) -> str:
    """Slug tokoh berskor tertinggi pada satu baris antrean.

    Kolom `mentah.entitas` berisi JSON daftar slug yang SUDAH diurutkan menurun
    berdasarkan skor oleh `Registri.tandai()`, jadi elemen pertama adalah subjek
    utama berita. Tidak perlu memindai ulang nama tokoh terhadap judul.

    Mengembalikan "" bila tidak ada entitas terdeteksi — berita semacam itu
    tidak dikenai pagar komposisi.
    """
    try:
        mentah = baris["entitas"]
    except (KeyError, IndexError, TypeError):
        return ""
    if isinstance(mentah, str):
        try:
            daftar = json.loads(mentah or "[]")
        except (json.JSONDecodeError, TypeError):
            return ""
    else:
        daftar = list(mentah or [])
    return str(daftar[0]) if daftar else ""


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
    #
    # Dua pembanding, dua ambang. Versi sebelumnya menumpuk keduanya dalam satu
    # daftar dengan satu ambang, sehingga ambang tinggi yang WAJIB dipakai untuk
    # perbandingan lintas bahasa ikut melemahkan perbandingan sesama judul
    # Inggris — padahal justru di situ duplikatnya paling mudah dikenali.
    #
    #   riwayat_terbit  : judul Indonesia yang sudah tayang. Lintas bahasa
    #                     terhadap kandidat, jadi ambang 82.
    #   judul_terpilih  : judul Inggris kandidat yang sudah dipilih pada jalan
    #                     ini. Sebahasa, jadi ambang 72.
    #
    # Pada jalan #122, dua judul sumber Arthur Hayes tentang peristiwa yang sama
    # mencetak 75,3 satu sama lain — lolos ambang 82, tertangkap ambang 72, dan
    # tertangkapnya SEBELUM panggilan API keluar.
    terpilih = []
    riwayat_terbit = list(riwayat)
    judul_terpilih: list[tuple[str, str]] = []
    hitung_tokoh: dict[str, int] = {}
    maks_tokoh = int(kfg.editorial.get("maks_artikel_per_tokoh",
                                       MAKS_ARTIKEL_PER_TOKOH))
    ulangan = 0
    ditunda = 0
    diperiksa = 0
    for baris in antre:
        diperiksa += 1
        # Pengaman kedua: kalau ada item lolos di antara kurasan dan pemilihan.
        if not masih_segar(baris["terbit_pada"], BATAS_JAM_TULIS):
            simpan.tandai_mentah(baris["id"], "dilewati")
            basi += 1
            continue
        kembar = (cari_duplikat(baris["judul"], riwayat_terbit,
                                AMBANG_LINTAS_BAHASA)
                  or cari_duplikat(baris["judul"], judul_terpilih,
                                   AMBANG_SEBAHASA))
        if kembar:
            simpan.tandai_mentah(baris["id"], "dilewati")
            ulangan += 1
            if verbose and ulangan <= 10:
                print(f"  [ULANG] {baris['judul'][:70]}")
            continue
        # Pagar komposisi. PENTING: item yang tertahan di sini TIDAK ditandai
        # 'dilewati'. Beritanya sah dan bukan pengulangan — ia hanya tidak muat
        # pada jalan ini. Statusnya dibiarkan 'baru' supaya kembali menjadi
        # kandidat di jalan berikutnya, ketika penghitung sudah nol lagi.
        #
        # Karena perulangan tetap menyisir seluruh kolam 120 kandidat, jatah
        # tulis yang tersisa terisi oleh tokoh lain — itulah gunanya pagar ini:
        # bukan menerbitkan lebih sedikit, melainkan menerbitkan lebih beragam.
        tokoh = _tokoh_utama(baris)
        if tokoh and maks_tokoh > 0 and hitung_tokoh.get(tokoh, 0) >= maks_tokoh:
            ditunda += 1
            if verbose and ditunda <= 8:
                print(f"  [TUNDA] {baris['judul'][:60]} — "
                      f"kuota tokoh '{tokoh}' ({maks_tokoh}) sudah penuh")
            continue

        judul_terpilih.append((baris["id"], baris["judul"]))
        if tokoh:
            hitung_tokoh[tokoh] = hitung_tokoh.get(tokoh, 0) + 1
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
        if ditunda > 8:
            print(f"  ... dan {ditunda - 8} penundaan tokoh lainnya")
        if ditunda:
            print(f"  ⏸ {ditunda} berita ditunda ke jalan berikutnya "
                  f"(kuota {maks_tokoh} artikel per tokoh; TIDAK dibuang)")
        print(f"▸ Tahap 2/3 — Menulis ulang {len(terpilih)} berita "
              f"({ulangan} pengulangan dibuang, {ditunda} ditunda, "
              f"{tersisa} tersisa di antrean untuk jalan berikutnya)")
    if not terpilih:
        return {"ditulis": 0, "gagal": 0, "dilewati": ulangan,
                "ditunda": ditunda, "tersisa": tersisa, "basi": basi}

    artikel, gagal = Penulis(kfg, reg).tulis_banyak(terpilih, verbose)

    # ------------------------------------------------------------------
    # Pemeriksaan duplikat KEDUA — sesama Bahasa Indonesia.
    #
    # Penyaringan di atas membandingkan judul MENTAH dari RSS (berbahasa
    # Inggris) dengan judul artikel yang SUDAH TERBIT (berbahasa Indonesia).
    # Perbandingan lintas bahasa itu praktis tidak pernah mencapai ambang:
    # nama diri seperti Ethereum atau Bitcoin memang bertahan melewati
    # penerjemahan, tetapi selebihnya berubah total, sehingga skornya
    # mentok di kisaran 65-69 untuk peristiwa yang sama persis.
    #
    # Akibatnya dua penerbit yang memberitakan peristiwa sama dengan judul
    # Inggris berbeda lolos berdua, lalu terbit sebagai dua artikel
    # Indonesia yang nyaris kembar — misalnya "Tom Lee Soroti Peran
    # Ethereum sebagai Lapisan Verifikasi AI" dan "Tom Lee Soroti Potensi
    # Ethereum sebagai Lapisan Verifikasi AI" pada 19 Agustus 2026, yang
    # mencetak kemiripan 94,7 begitu dibandingkan sesama Bahasa Indonesia.
    #
    # Menurunkan ambang bukan jalan keluar: pasangan lintas bahasa yang
    # benar-benar duplikat berada di 65-69, sementara artikel Indonesia
    # yang memang berbeda juga jatuh di kisaran 58-68. Tidak ada satu angka
    # yang memisahkan keduanya. Karena itu pemeriksaan diulang di sini,
    # ketika kedua sisi perbandingan sudah sama-sama Bahasa Indonesia.
    #
    # Biaya panggilan API untuk artikel duplikat memang sudah terlanjur
    # keluar. Yang diselamatkan adalah slot penerbitannya — untuk situs
    # yang terbit 1-3 artikel per hari, satu duplikat berarti sepertiga
    # keluaran hari itu terbuang.
    #
    # Judul yang lolos ikut ditambahkan ke pembanding, sehingga dua artikel
    # kembar yang ditulis dalam SATU jalan yang sama juga tersaring.
    # ------------------------------------------------------------------
    judul_terbit = list(riwayat)
    disimpan = []
    ulangan_pasca = 0
    for a in artikel:
        # AMBANG_SEBAHASA, bukan 82: kedua sisi perbandingan di sini sudah
        # sama-sama Bahasa Indonesia. Pada jalan #122 pasangan duplikat mencetak
        # 73,9 dan 79,5 — keduanya lolos ambang lama dan terbit berdampingan
        # di beranda.
        if cari_duplikat(a.judul, judul_terbit, AMBANG_SEBAHASA):
            # 'dilewati', bukan 'baru': artikelnya sudah ditulis dan memang
            # duplikat, jadi menulis ulang di jalan berikutnya hanya akan
            # membakar kuota untuk hasil yang sama.
            simpan.tandai_mentah(a.id, "dilewati")
            ulangan_pasca += 1
            if verbose:
                print(f"  [KEMBAR] {a.judul[:70]}")
            continue
        judul_terbit.append((a.id, a.judul))
        simpan.simpan_artikel(a)
        simpan.tandai_mentah(a.id, "diproses")
        disimpan.append(a)

    if verbose and ulangan_pasca:
        print(f"  \u2717 {ulangan_pasca} artikel kembar tidak diterbitkan "
              f"(judul Indonesia terlalu mirip dengan yang sudah tayang)")
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

    ringkas = {"ditulis": len(disimpan), "gagal": dikubur,
               "dikembalikan": dikembalikan,
               "dilewati": ulangan, "kembar": ulangan_pasca,
               "ditunda": ditunda, "tersisa": tersisa, "basi": basi}
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
