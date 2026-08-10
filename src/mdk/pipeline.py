"""Orkestrasi pipeline: ambil → saring → tulis ulang → simpan → bangun situs."""
from __future__ import annotations

from .build import Pembangun
from .config import muat_konfigurasi
from .dedup import cari_duplikat
from .entities import registri
from .ingest import Pengambil
from .rewrite import Penulis
from .store import buka


def tahap_ambil(sertakan_entitas: bool = True, verbose: bool = True) -> dict:
    kfg, reg = muat_konfigurasi(), registri()
    simpan = buka(kfg)
    if verbose:
        print("▸ Tahap 1/3 — Mengambil umpan berita")
    return Pengambil(kfg, reg, simpan).jalankan(sertakan_entitas, verbose)


def tahap_tulis(batas: int | None = None, verbose: bool = True) -> dict:
    kfg, reg = muat_konfigurasi(), registri()
    simpan = buka(kfg)
    batas = batas or int(kfg.ai.get("batas_artikel_per_jalankan", 40))
    antre = simpan.mentah_menunggu(batas * 2)

    # Buang duplikat lintas sumber sebelum memanggil model (hemat biaya API).
    terpilih, judul_dipakai = [], []
    for baris in antre:
        if cari_duplikat(baris["judul"], judul_dipakai):
            simpan.tandai_mentah(baris["id"], "dilewati")
            continue
        judul_dipakai.append((baris["id"], baris["judul"]))
        terpilih.append(baris)
        if len(terpilih) >= batas:
            break

    if verbose:
        print(f"▸ Tahap 2/3 — Menulis ulang {len(terpilih)} berita "
              f"({len(antre) - len(terpilih)} duplikat dilewati)")
    if not terpilih:
        return {"ditulis": 0, "gagal": 0, "dilewati": len(antre)}

    artikel, gagal = Penulis(kfg, reg).tulis_banyak(terpilih, verbose)
    for a in artikel:
        simpan.simpan_artikel(a)
        simpan.tandai_mentah(a.id, "diproses")
    for id_, alasan in gagal:
        simpan.tandai_mentah(id_, "gagal")
        simpan.catat("tulis", f"{id_}: {alasan}")

    ringkas = {"ditulis": len(artikel), "gagal": len(gagal),
               "dilewati": len(antre) - len(terpilih)}
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
