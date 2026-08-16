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
        self.diblokir = {d.lower() for d in kfg.sumber.get("penerbit_diblokir", [])}
        self.batas_jam = int(kfg.relevansi.get("usia_maksimum_jam", BATAS_JAM_BAWAAN))
        # Penghitung alasan penolakan, untuk ringkasan di akhir jalannya.
        self.tolak_tanpa_tanggal = 0
        self.tolak_basi = 0

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
            if domain_penerbit(tautan) in self.diblokir:
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
                   "tolak_tanpa_tanggal": self.tolak_tanpa_tanggal}
        if verbose:
            print(f"  ✗ Ditolak karena usia: {self.tolak_basi} · "
                  f"tanpa tanggal: {self.tolak_tanpa_tanggal}")
        self.simpan.catat("ingest", str(ringkas))
        return ringkas
