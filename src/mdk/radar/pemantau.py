"""Mesin pemantauan — menjajaki seluruh sumber dan mendeteksi berita baru.

ALUR SATU PUTARAN
  1. Muat daftar sumber aktif + kondisi kesehatannya
  2. Jajaki secara paralel dengan permintaan bersyarat (ETag / If-Modified-Since)
  3. Saring: usia, daftar tolak, relevansi entitas
  4. Buang yang pernah dilihat (sidik URL kanonik)
  5. Kelompokkan laporan atas peristiwa yang sama menjadi satu klaster
  6. Teruskan klaster ke antrean terjemahan + kanal notifikasi

EFISIENSI
  · Permintaan bersyarat: sumber tanpa perubahan menjawab 304 tanpa isi.
  · Prioritas jajak: sumber primer setiap putaran, sumber sekunder lebih jarang.
  · Batas serentak per domain agar tidak dianggap penyalahgunaan.
  · Nonaktif otomatis setelah kegagalan beruntun; dapat dihidupkan kembali.
"""
from __future__ import annotations

import random
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import feedparser
import requests

from ..dedup import kemiripan
from ..models import ItemMentah
from ..utils import (bersihkan_html, domain_penerbit, kanonikalisasi_url, potong,
                     sekarang_wib, sidik_jari)
from .simpan import PenyimpananRadar
from .sumber import Sumber


@dataclass
class Temuan:
    """Satu item berita baru yang lolos seluruh saringan."""
    sidik: str
    url: str
    url_kanonik: str
    judul: str
    penerbit: str
    ringkasan: str
    terbit_pada: str
    entitas: str
    jenis_entitas: str
    nama_entitas: str
    sumber_id: str
    jenis_sumber: str
    skor: float = 0.0
    entitas_terdeteksi: list[str] = field(default_factory=list)
    organisasi_terdeteksi: list[str] = field(default_factory=list)


class PembatasDomain:
    """Menahan laju permintaan per domain agar sopan terhadap penyedia umpan."""

    def __init__(self, jeda_detik: float = 1.0):
        self.jeda = jeda_detik
        self._terakhir: dict[str, float] = {}
        self._kunci = threading.Lock()

    def tunggu(self, url: str) -> None:
        host = urlparse(url).netloc.lower()
        with self._kunci:
            sisa = self.jeda - (time.monotonic() - self._terakhir.get(host, 0.0))
            if sisa > 0:
                time.sleep(sisa)
            self._terakhir[host] = time.monotonic()


class Pemantau:
    def __init__(self, kfg, reg, simpan_radar: PenyimpananRadar, organisasi: list[dict]):
        self.kfg = kfg
        self.reg = reg
        self.db = simpan_radar
        self.org_by_slug = {o["slug"]: o for o in organisasi}
        self.opsi = kfg.radar if hasattr(kfg, "radar") else {}
        self.pembatas = PembatasDomain(float(self.opsi.get("jeda_per_domain_detik", 1.0)))
        self.sesi = requests.Session()
        self.sesi.headers["User-Agent"] = self.opsi.get(
            "user_agent", "ManajerDanaKriptoRadar/1.0 (+https://manajerdanakripto.com/tentang)")

    # ---------------------------------------------------------- penjajakan --
    def _jajaki(self, s: Sumber, kondisi: dict | None) -> tuple[Sumber, str, list, dict]:
        """Ambil satu umpan. Kembalikan (sumber, status, entri, header_baru)."""
        kepala = {}
        if kondisi:
            if kondisi.get("etag"):
                kepala["If-None-Match"] = kondisi["etag"]
            if kondisi.get("modifikasi"):
                kepala["If-Modified-Since"] = kondisi["modifikasi"]

        self.pembatas.tunggu(s.url)
        try:
            r = self.sesi.get(s.url, headers=kepala,
                              timeout=float(self.opsi.get("timeout_detik", 25)))
        except requests.RequestException as e:
            return s, f"galat:{type(e).__name__}", [], {}

        if r.status_code == 304:
            return s, "tidak-berubah", [], {}
        if r.status_code == 429:
            return s, "galat:dibatasi-laju", [], {}
        if r.status_code != 200:
            return s, f"galat:http-{r.status_code}", [], {}

        try:
            parsed = feedparser.parse(r.content)
        except Exception as e:                                   # noqa: BLE001
            return s, f"galat:urai-{type(e).__name__}", [], {}

        if getattr(parsed, "bozo", 0) and not parsed.entries:
            return s, "galat:umpan-tidak-sah", [], {}

        header = {"etag": r.headers.get("ETag", ""),
                  "modifikasi": r.headers.get("Last-Modified", "")}
        return s, "ok", parsed.entries, header

    # ------------------------------------------------------------ saringan --
    def _waktu_entri(self, entri) -> str:
        for kunci in ("published_parsed", "updated_parsed"):
            nilai = entri.get(kunci)
            if nilai:
                try:
                    return datetime(*nilai[:6], tzinfo=timezone.utc).isoformat()
                except (TypeError, ValueError):
                    continue
        return sekarang_wib().isoformat()

    def _judul_bersih(self, judul: str) -> str:
        judul = bersihkan_html(judul)
        # Google News dan Bing menambahkan " - Nama Media" di ujung judul.
        if " - " in judul and len(judul.rsplit(" - ", 1)[-1]) < 45:
            judul = judul.rsplit(" - ", 1)[0]
        return judul.strip()

    def _nama_entitas(self, s: Sumber) -> str:
        if s.jenis_entitas == "tokoh":
            t = self.reg.tokoh.get(s.entitas)
            return t.nama if t else s.entitas
        o = self.org_by_slug.get(s.entitas)
        return o["nama"] if o else s.entitas

    def _olah_entri(self, s: Sumber, entri) -> Temuan | None:
        tautan = entri.get("link", "")
        if not tautan:
            return None
        kanonik = kanonikalisasi_url(tautan)
        if not kanonik:
            return None

        judul = self._judul_bersih(entri.get("title", ""))
        if not judul:
            return None
        ringkas = potong(bersihkan_html(
            entri.get("summary", "") or entri.get("description", "")), 420)

        if self.reg.ditolak(f"{judul} {ringkas}"):
            return None

        terbit = self._waktu_entri(entri)
        batas = sekarang_wib() - timedelta(hours=int(self.opsi.get("usia_maksimum_jam", 72)))
        try:
            if datetime.fromisoformat(terbit) < batas:
                return None
        except ValueError:
            pass

        sumber_entri = entri.get("source") or {}
        penerbit = (sumber_entri.get("title") if isinstance(sumber_entri, dict) else None) \
            or domain_penerbit(tautan) or s.label

        # Skor relevansi: entitas terdeteksi + kesesuaian dengan entitas pemicu.
        tanda = self.reg.tandai(judul, ringkas)
        skor = tanda["skor_entitas"] + self.reg.skor_tema(f"{judul} {ringkas}")
        if s.entitas in tanda["entitas"] or s.entitas in tanda["organisasi"]:
            skor += 20                      # entitas pemicu benar-benar disebut
        if self._nama_entitas(s).lower() in judul.lower():
            skor += 15                      # disebut langsung pada judul
        skor *= s.bobot

        # Sumber resmi dan arsip SEC selalu relevan meski penanda entitas meleset.
        if s.jenis in ("situs_resmi", "sec_edgar"):
            skor = max(skor, 60)
        elif skor < float(self.opsi.get("skor_minimum", 35)):
            return None

        return Temuan(
            sidik=sidik_jari(kanonik), url=tautan, url_kanonik=kanonik, judul=judul,
            penerbit=penerbit, ringkasan=ringkas, terbit_pada=terbit,
            entitas=s.entitas, jenis_entitas=s.jenis_entitas,
            nama_entitas=self._nama_entitas(s), sumber_id=s.id, jenis_sumber=s.jenis,
            skor=round(skor, 1),
            entitas_terdeteksi=tanda["entitas"] or ([s.entitas] if s.jenis_entitas == "tokoh" else []),
            organisasi_terdeteksi=tanda["organisasi"] or ([s.entitas] if s.jenis_entitas == "organisasi" else []))

    # ------------------------------------------------------- pengelompokan --
    def _kelompokkan(self, temuan: list[Temuan]) -> list[dict]:
        """Gabungkan laporan atas peristiwa yang sama menjadi satu klaster.

        Tanpa langkah ini, satu peristiwa yang diliput sepuluh media akan
        menghasilkan sepuluh notifikasi terpisah.
        """
        ambang = float(self.opsi.get("ambang_klaster", 80))
        lama = self.db.judul_klaster_terkini(jam=72)
        klaster: list[dict] = []

        for t in sorted(temuan, key=lambda x: -x.skor):
            # Sudah dilaporkan pada putaran sebelumnya?
            cocok_lama = next((kid for kid, judul in lama
                               if kemiripan(t.judul, judul) >= ambang), None)
            if cocok_lama:
                t_klaster = cocok_lama
                for k in klaster:
                    if k["id"] == t_klaster:
                        k["anggota"].append(t)
                        break
                else:
                    klaster.append({"id": t_klaster, "anggota": [t], "lanjutan": True})
                continue

            # Cocok dengan klaster yang sedang dibentuk pada putaran ini?
            for k in klaster:
                if kemiripan(t.judul, k["anggota"][0].judul) >= ambang:
                    k["anggota"].append(t)
                    break
            else:
                klaster.append({"id": f"k-{t.sidik[:12]}", "anggota": [t], "lanjutan": False})

        # Susun ringkasan tiap klaster.
        hasil = []
        for k in klaster:
            anggota = sorted(k["anggota"], key=lambda x: -x.skor)
            utama = anggota[0]
            entitas = sorted({e for a in anggota for e in
                              (a.entitas_terdeteksi + a.organisasi_terdeteksi + [a.entitas])})
            hasil.append({
                "id": k["id"], "lanjutan": k["lanjutan"],
                "judul_utama": utama.judul, "url_utama": utama.url,
                "penerbit": utama.penerbit, "entitas": entitas,
                "jumlah_sumber": len({a.penerbit for a in anggota}),
                "skor": round(sum(a.skor for a in anggota[:3]), 1),
                "anggota": anggota,
                "dibuat_pada": sekarang_wib().isoformat(),
            })
        hasil.sort(key=lambda k: -k["skor"])
        return hasil

    # ---------------------------------------------------------- satu putaran --
    def putaran(self, sumber: list[Sumber], putaran_ke: int = 1,
                verbose: bool = True) -> dict:
        kondisi_semua = self.db.semua_kondisi()

        # Sumber prioritas 1 dijajaki tiap putaran, prioritas 2 tiap 2 putaran, dst.
        antre = [s for s in sumber
                 if s.aktif
                 and (kondisi_semua.get(s.id, {}).get("aktif", 1) == 1)
                 and putaran_ke % max(1, s.prioritas) == 0]
        if not antre:
            return {"dijajaki": 0, "baru": 0, "klaster": 0}

        random.shuffle(antre)               # sebar beban antar domain
        maks_pekerja = int(self.opsi.get("maks_serentak", 8))
        temuan: list[Temuan] = []
        hitung = {"ok": 0, "tidak-berubah": 0, "galat": 0}

        with ThreadPoolExecutor(max_workers=maks_pekerja) as pool:
            tugas = {pool.submit(self._jajaki, s, kondisi_semua.get(s.id)): s for s in antre}
            for i, fut in enumerate(as_completed(tugas), 1):
                s, status, entri, header = fut.result()

                if status.startswith("galat"):
                    hitung["galat"] += 1
                    n = self.db.catat_gagal(s.id, s.url, status,
                                            int(self.opsi.get("batas_nonaktif", 6)))
                    if verbose and n >= int(self.opsi.get("batas_nonaktif", 6)):
                        print(f"    ! dinonaktifkan setelah {n}x gagal: {s.label[:52]}")
                    continue

                if status == "tidak-berubah":
                    hitung["tidak-berubah"] += 1
                    self.db.catat_sukses(s.id, s.url, kondisi_semua.get(s.id, {}).get("etag", ""),
                                         kondisi_semua.get(s.id, {}).get("modifikasi", ""), 0, 0)
                    continue

                hitung["ok"] += 1
                maks = int(self.opsi.get("maks_item_per_umpan", 30))
                calon = [self._olah_entri(s, e) for e in entri[:maks]]
                calon = [c for c in calon if c]

                # Buang yang sudah pernah dilihat pada putaran sebelumnya.
                dikenal = self.db.sidik_dikenal([c.sidik for c in calon])
                baru = [c for c in calon if c.sidik not in dikenal]
                temuan.extend(baru)
                self.db.catat_sukses(s.id, s.url, header.get("etag", ""),
                                     header.get("modifikasi", ""), len(entri), len(baru))

                if verbose and baru:
                    print(f"    + {len(baru):>2} baru · {s.label[:56]}")

        # Buang duplikat dalam satu putaran (URL sama dari beberapa sumber).
        unik: dict[str, Temuan] = {}
        for t in temuan:
            ada = unik.get(t.sidik)
            if not ada or t.skor > ada.skor:
                unik[t.sidik] = t
        temuan = list(unik.values())

        klaster = self._kelompokkan(temuan) if temuan else []

        # Simpan hasil.
        for k in klaster:
            for a in k["anggota"]:
                self.db.catat_terlihat({
                    "sidik": a.sidik, "url": a.url, "judul": a.judul,
                    "penerbit": a.penerbit, "entitas": a.entitas,
                    "jenis_entitas": a.jenis_entitas, "sumber_id": a.sumber_id,
                    "jenis_sumber": a.jenis_sumber, "terbit_pada": a.terbit_pada,
                    "klaster": k["id"], "skor": a.skor})
            self.db.simpan_klaster(k)

        return {"dijajaki": len(antre), "ok": hitung["ok"],
                "tidak_berubah": hitung["tidak-berubah"], "galat": hitung["galat"],
                "baru": len(temuan), "klaster": len(klaster),
                "klaster_baru": [k for k in klaster if not k["lanjutan"]]}

    # --------------------------------------------- teruskan ke penerjemah ---
    def teruskan_ke_antrean(self, simpan_utama, batas: int = 60) -> int:
        """Masukkan temuan ke tabel `mentah` agar siap ditulis ulang `mdk tulis`."""
        antre = self.db.belum_diteruskan(batas)
        diteruskan: list[str] = []

        for t in antre:
            if float(t.get("skor") or 0) < float(self.opsi.get("skor_minimum_terjemah", 55)):
                diteruskan.append(t["sidik"])       # ditandai agar tidak diproses ulang
                continue
            tanda = self.reg.tandai(t["judul"] or "", "")
            item = ItemMentah(
                judul=t["judul"] or "", url=t["url"],
                url_kanonik=kanonikalisasi_url(t["url"]),
                penerbit=t["penerbit"] or "", ringkasan_sumber="",
                terbit_pada=t["terbit_pada"] or "",
                diambil_pada=sekarang_wib().isoformat(), bahasa="en",
                bobot_sumber=1.0,
                entitas=tanda["entitas"] or ([t["entitas"]] if t["jenis_entitas"] == "tokoh" else []),
                organisasi=tanda["organisasi"] or ([t["entitas"]] if t["jenis_entitas"] == "organisasi" else []),
                skor=int(float(t.get("skor") or 0)))
            simpan_utama.simpan_mentah(item)
            diteruskan.append(t["sidik"])

        self.db.tandai_diteruskan(diteruskan)
        return len(diteruskan)
