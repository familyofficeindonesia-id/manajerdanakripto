"""Pengambilan umpan RSS: umpan umum + kueri Google News per tokoh.

Hanya metadata yang disimpan (judul, tautan, ringkasan pendek, waktu, penerbit).
Teks penuh artikel sumber tidak pernah disalin ke basis data maupun ke situs.

CATATAN PERUBAHAN — penyaringan usia berita
-------------------------------------------
Sebelumnya ada tiga celah yang membuat berita lama lolos:

  1. Entri tanpa tanggal diberi cap waktu SEKARANG, sehingga otomatis
     dianggap berita baru.
  2. Batas usia bawaan 96 jam (empat hari), terlalu longgar untuk portal
     berita harian.
  3. Tanggal yang gagal diurai dilewatkan begitu saja (`except: pass`),
     sehingga entri bermasalah tetap masuk.

Sekarang aturannya tegas: entri yang tanggal terbitnya tidak dapat dibaca
DITOLAK, bukan ditebak. Batas bawaan 24 jam dan dapat diatur lewat
`relevansi.usia_maksimum_jam` pada berkas konfigurasi.
"""
from __future__ import annotations

import time
from urllib.parse import quote_plus

import feedparser

from .alat_kesegaran import parse_tanggal, umur_jam
from .config import Konfigurasi
from .entities import Registri
from .models import ItemMentah
from .store import Penyimpanan
from .utils import (bersihkan_html, domain_penerbit, kanonikalisasi_url, potong,
                    sekarang_wib)

# Batas usia bawaan bila tidak disetel di konfigurasi.
BATAS_JAM_BAWAAN = 24

# Batas ATAS yang tidak boleh dilampaui, berapa pun isi konfigurasi.
# Portal berita harian tidak seharusnya menayangkan berita berumur berhari-hari.
# Ubah angka di sini bila suatu saat batasnya memang perlu dilonggarkan —
# nilai pada konfigurasi sengaja tidak diberi wewenang melewatinya.
BATAS_JAM_MAKS = 24

# Penerbit yang diblokir permanen, di luar daftar pada berkas konfigurasi.
# Yellow.com menerbitkan ulang artikel lama dengan tanggal baru, dan tanggal
# palsu itu diteruskan Google News apa adanya — sehingga artikel Februari dapat
# tampil sebagai berita hari ini. Karena tanggal dari sumbernya sendiri tidak
# dapat dipercaya, tidak ada penyaringan tanggal yang mampu menahannya.
# Tambahkan penerbit lain ke daftar ini bila ditemukan pola serupa.
PENERBIT_DIBLOKIR_TETAP = {
    "yellow.com",
}

# Toleransi tanggal "masa depan". Beda zona waktu di server sumber sering
# membuat tanggal terlihat 1-2 jam ke depan; lebih dari ini dianggap rusak.
TOLERANSI_DEPAN_JAM = 3


def _penerbit_entri(entri, cadangan: str) -> str:
    sumber = entri.get("source") or {}
    if isinstance(sumber, dict) and sumber.get("title"):
        return str(sumber["title"])
    return domain_penerbit(entri.get("link", "")) or cadangan


def _judul_bersih(judul: str) -> str:
    """Google News menambahkan ' - Nama Media' di akhir judul; buang bagian itu."""
    judul = bersihkan_html(judul)
    if " - " in judul and len(judul.rsplit(" - ", 1)[-1]) < 40:
        judul = judul.rsplit(" - ", 1)[0]
    return judul.strip()


class Pengambil:
    def __init__(self, kfg: Konfigurasi, reg: Registri, simpan: Penyimpanan):
        self.kfg, self.reg, self.simpan = kfg, reg, simpan
        self.opsi = kfg.sumber.get("pengaturan_pengambilan", {})
        self.diblokir = {d.lower().strip() for d in
                         kfg.sumber.get("penerbit_diblokir", []) if d}
        self.diblokir |= {d.lower().strip() for d in PENERBIT_DIBLOKIR_TETAP}
        diminta = int(kfg.relevansi.get("usia_maksimum_jam", BATAS_JAM_BAWAAN))
        self.batas_jam = min(diminta, BATAS_JAM_MAKS)
        self.batas_dipangkas = diminta if diminta > BATAS_JAM_MAKS else 0
        # Penghitung alasan penolakan, untuk ringkasan di akhir jalannya.
        self.tolak_tanpa_tanggal = 0
        self.tolak_basi = 0
        self.tolak_penerbit = 0

    # ------------------------------------------------------------- daftar ----
    def daftar_umpan(self, sertakan_entitas: bool = True) -> list[dict]:
        umpan = [dict(u) for u in self.kfg.sumber.get("umpan_umum", [])]
        blok = self.kfg.sumber.get("kueri_entitas", {})
        if sertakan_entitas and blok.get("aktif", True):
            pasangan = self.reg.alias_kueri(
                maks_per_tokoh=int(blok.get("maks_alias_per_tokoh", 2)),
                hemat=bool(blok.get("mode_hemat", False)))
            for slug, alias in pasangan:
                for t in blok.get("template", []):
                    umpan.append({
                        "nama": f"{t['nama']}: {alias}",
                        "url": t["url"].replace("{q}", quote_plus(alias)),
                        "bahasa": "en", "bobot": float(t.get("bobot", 1.0)),
                        "petunjuk_tokoh": slug,
                    })
        return umpan

    # ----------------------------------------------------------- blokir ------
    def _diblokir(self, tautan: str, penerbit: str) -> bool:
        """Periksa daftar penerbit diblokir terhadap domain DAN nama penerbit.

        Untuk item yang datang lewat Google News, domain tautan selalu
        `news.google.com`, sehingga pemeriksaan domain saja tidak pernah
        mengenali penerbit aslinya. Nama penerbit diambil dari `entri.source`
        dan itulah yang memuat nama media sebenarnya.
        """
        if not self.diblokir:
            return False

        domain = (domain_penerbit(tautan) or "").lower()
        nama = (penerbit or "").lower().strip()
        # Bentuk tanpa akhiran domain, agar "Yellow.com" cocok dengan "yellow".
        nama_inti = nama.rsplit(".", 1)[0] if "." in nama else nama

        for blok in self.diblokir:
            blok_inti = blok.rsplit(".", 1)[0] if "." in blok else blok
            if not blok_inti:
                continue
            if domain and (blok == domain or domain.endswith("." + blok)):
                return True
            if nama and (blok == nama or blok_inti == nama_inti):
                return True
        return False

    # ---------------------------------------------------------- kesegaran ----
    def _lolos_usia(self, entri, judul: str) -> str | None:
        """Kembalikan tanggal terbit ISO bila entri cukup segar, selain itu None.

        Entri tanpa tanggal yang terbaca DITOLAK. Menebak tanggal dengan waktu
        sekarang adalah persis penyebab berita lama tampil sebagai berita baru.
        """
        tanggal = parse_tanggal(entri)
        if tanggal is None:
            self.tolak_tanpa_tanggal += 1
            return None

        jam = umur_jam(tanggal)
        if jam < -TOLERANSI_DEPAN_JAM:
            self.tolak_basi += 1
            return None
        if jam > self.batas_jam:
            self.tolak_basi += 1
            return None
        return tanggal.isoformat()

    # ------------------------------------------------------------ ambil 1 ----
    def ambil_umpan(self, umpan: dict) -> list[ItemMentah]:
        maks = int(self.opsi.get("maks_item_per_umpan", 40))
        hasil: list[ItemMentah] = []

        try:
            parsed = feedparser.parse(
                umpan["url"], agent=self.opsi.get("user_agent", "ManajerDanaKripto/1.0"))
        except Exception as e:                                   # noqa: BLE001
            self.simpan.catat("ingest", f"GAGAL {umpan['nama']}: {e}")
            return hasil

        for entri in parsed.entries[:maks]:
            tautan = entri.get("link", "")
            if not tautan:
                continue
            kanonik = kanonikalisasi_url(tautan)
            penerbit = _penerbit_entri(entri, umpan["nama"])
            if self._diblokir(tautan, penerbit):
                self.tolak_penerbit += 1
                continue
            if self.simpan.sudah_ada(kanonik):
                continue

            judul = _judul_bersih(entri.get("title", ""))

            # Gerbang kesegaran — dijalankan sebelum pekerjaan lain.
            terbit = self._lolos_usia(entri, judul)
            if terbit is None:
                continue

            ringkas = potong(bersihkan_html(entri.get("summary", "") or
                                            entri.get("description", "")), 400)
            if not judul or self.reg.ditolak(f"{judul} {ringkas}"):
                continue

            tanda = self.reg.tandai(judul, ringkas)
            skor = tanda["skor_entitas"] + self.reg.skor_tema(f"{judul} {ringkas}")
            skor = int(skor * float(umpan.get("bobot", 1.0)))

            hasil.append(ItemMentah(
                judul=judul, url=tautan, url_kanonik=kanonik, penerbit=penerbit,
                ringkasan_sumber=ringkas, terbit_pada=terbit,
                diambil_pada=sekarang_wib().isoformat(), bahasa=umpan.get("bahasa", "en"),
                bobot_sumber=float(umpan.get("bobot", 1.0)), entitas=tanda["entitas"],
                organisasi=tanda["organisasi"], skor=skor))
        return hasil

    # ---------------------------------------------------------- jalankan -----
    def jalankan(self, sertakan_entitas: bool = True, verbose: bool = True) -> dict:
        umpan = self.daftar_umpan(sertakan_entitas)
        ambang = int(self.kfg.relevansi.get("skor_minimum", 40))
        jeda = float(self.opsi.get("jeda_antar_umpan_detik", 1.2))
        total, disimpan, dibuang = 0, 0, 0

        if verbose:
            print(f"  Batas usia berita: {self.batas_jam} jam "
                  f"(entri tanpa tanggal ditolak)")
            print(f"  Penerbit diblokir: {len(self.diblokir)} "
                  f"({', '.join(sorted(self.diblokir)[:6])})")
            if self.batas_dipangkas:
                print(f"  ! Konfigurasi meminta {self.batas_dipangkas} jam, "
                      f"dipangkas ke {BATAS_JAM_MAKS} jam oleh BATAS_JAM_MAKS "
                      f"di ingest.py")

        for i, u in enumerate(umpan, 1):
            item = self.ambil_umpan(u)
            total += len(item)
            for it in item:
                if it.skor < ambang or not it.entitas:
                    dibuang += 1
                    continue
                if self.simpan.simpan_mentah(it):
                    disimpan += 1
            if verbose:
                print(f"  [{i:>3}/{len(umpan)}] {u['nama'][:58]:<58} "
                      f"{len(item):>3} item")
            time.sleep(jeda)

        ringkas = {"umpan": len(umpan), "terbaca": total, "disimpan": disimpan,
                   "dibuang": dibuang, "tolak_basi": self.tolak_basi,
                   "tolak_tanpa_tanggal": self.tolak_tanpa_tanggal,
                   "tolak_penerbit": self.tolak_penerbit}
        if verbose:
            print(f"  ✗ Ditolak — usia: {self.tolak_basi} · "
                  f"tanpa tanggal: {self.tolak_tanpa_tanggal} · "
                  f"penerbit diblokir: {self.tolak_penerbit}")
        self.simpan.catat("ingest", str(ringkas))
        return ringkas
