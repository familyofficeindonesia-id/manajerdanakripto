"""Pembangkit situs statis: merender seluruh halaman dari basis data ke folder dist/."""
from __future__ import annotations

import math
import shutil
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import Konfigurasi
from .entities import Registri
from .feeds import (TANDA_SINYAL, tulis_indeks_cari, tulis_robots, tulis_rss,
                    tulis_sitemap, tulis_sitemap_berita)
from .models import Artikel
from .store import Penyimpanan
from .utils import (format_tanggal_id, hitung_kata, ke_wib, potong, sekarang_wib,
                    slugify, waktu_relatif_id)


class Pembangun:
    def __init__(self, kfg: Konfigurasi, reg: Registri, simpan: Penyimpanan):
        self.kfg, self.reg, self.simpan = kfg, reg, simpan
        self.keluar = kfg.dir_keluaran
        self.per_halaman = int(kfg.build.get("artikel_per_halaman", 12))
        self.env = self._siapkan_jinja()
        self.artikel: list[Artikel] = []
        self.url_sitemap: list[tuple[str, str, str]] = []

    # ------------------------------------------------------------- jinja ----
    def _siapkan_jinja(self) -> Environment:
        env = Environment(
            loader=FileSystemLoader(str(self.kfg.dir_templat)),
            autoescape=select_autoescape(["html", "xml", "j2"]),
            trim_blocks=True, lstrip_blocks=True)
        env.filters["tanggal"] = format_tanggal_id
        env.filters["relatif"] = waktu_relatif_id
        env.filters["potong"] = potong
        env.filters["slug"] = slugify
        env.globals.update(
            situs=self.kfg.situs,
            base_url=self.kfg.base_url,
            rubrik=self.kfg.rubrik,
            kategori=self.reg.kategori,
            disclaimer=self.kfg.editorial.get("disclaimer", ""),
            tahun=sekarang_wib().year,
            tanggal_hari_ini=format_tanggal_id(sekarang_wib(), dengan_jam=False),
            analytics_id=self.kfg.build.get("google_analytics_id", ""),
            label_rubrik=lambda s: self.kfg.rubrik_by_slug(s)["label"],
            label_kategori=self.reg.label_kategori,
            tanda_sinyal=lambda s: TANDA_SINYAL.get(s, "▬"),
            tokoh=lambda s: self.reg.tokoh.get(s),
            mode_demo=False,
        )
        return env

    # ------------------------------------------------------------ tulis -----
    def _tulis(self, jalur_relatif: str, html: str, prioritas: str = "0.6",
               waktu: str | None = None) -> None:
        """Tulis HTML sebagai index.html di dalam direktori (URL bersih tanpa .html)."""
        if jalur_relatif.endswith(".html"):
            berkas = self.keluar / jalur_relatif.lstrip("/")
            url = "/" + jalur_relatif.lstrip("/")
        else:
            berkas = self.keluar / jalur_relatif.strip("/") / "index.html"
            url = "/" + jalur_relatif.strip("/") + "/" if jalur_relatif.strip("/") else "/"
        berkas.parent.mkdir(parents=True, exist_ok=True)
        berkas.write_text(html, encoding="utf-8")
        if not jalur_relatif.endswith("404.html"):
            self.url_sitemap.append((url, waktu or sekarang_wib().isoformat(), prioritas))

    def _render(self, templat: str, **konteks) -> str:
        return self.env.get_template(templat).render(**konteks)

    # ------------------------------------------------------- data bantu -----
    def _pita(self) -> list[dict]:
        """Chip 'Pita Manajer': tokoh dengan pemberitaan terbaru + sinyal agregat."""
        batas = sekarang_wib() - timedelta(days=14)
        sinyal_per_tokoh: dict[str, Counter] = defaultdict(Counter)
        terakhir: dict[str, str] = {}
        for a in self.artikel:
            dt = ke_wib(a.terbit_pada)
            if not dt or dt < batas:
                continue
            for slug in a.entitas:
                sinyal_per_tokoh[slug][a.sinyal] += 1
                terakhir.setdefault(slug, a.terbit_pada)

        chip = []
        for slug, hitung in sorted(sinyal_per_tokoh.items(),
                                   key=lambda kv: (-sum(kv[1].values()), kv[0]))[:26]:
            t = self.reg.tokoh.get(slug)
            if not t:
                continue
            dominan = hitung.most_common(1)[0][0]
            chip.append({
                "nama_pendek": t.nama.split()[-1].upper(),
                "organisasi": potong(t.organisasi, 22),
                "sinyal": dominan,
                "tanda": TANDA_SINYAL.get(dominan, "▬"),
                "label": {"akumulasi": "AKUM", "distribusi": "DIST"}.get(dominan, "NTRL"),
                "url": t.url,
            })
        return chip

    def _artikel_tokoh(self, slug: str) -> list[Artikel]:
        return [a for a in self.artikel if slug in a.entitas]

    def _artikel_org(self, slug: str) -> list[Artikel]:
        return [a for a in self.artikel if slug in a.organisasi]

    def _sinyal_dominan(self, artikel: list[Artikel]) -> str:
        if not artikel:
            return "netral"
        return Counter(a.sinyal for a in artikel).most_common(1)[0][0]

    # --------------------------------------------------------- paginasi -----
    def _halaman_berpaginasi(self, artikel: list[Artikel], dasar: str, templat: str,
                             halaman_meta: dict, **ekstra) -> None:
        total = max(1, math.ceil(len(artikel) / self.per_halaman))
        for n in range(1, total + 1):
            potongan = artikel[(n - 1) * self.per_halaman: n * self.per_halaman]
            jalur = dasar if n == 1 else f"{dasar.rstrip('/')}/halaman/{n}"
            meta = dict(halaman_meta)
            meta["url"] = "/" + jalur.strip("/") + "/" if jalur.strip("/") else "/"
            if n > 1:
                meta["judul"] = f"{halaman_meta['judul']} — Halaman {n}"
            html = self._render(
                templat, halaman=meta, artikel=potongan,
                total_artikel=len(artikel), halaman_ini=n, total_halaman=total,
                url_halaman=lambda m, d=dasar: ("/" + d.strip("/") + "/") if m == 1
                                               else f"/{d.strip('/')}/halaman/{m}/",
                **ekstra)
            self._tulis(jalur, html, prioritas="0.8" if n == 1 else "0.4")

    # ------------------------------------------------------------ halaman ---
    def _bangun_beranda(self) -> None:
        utama = self.artikel[0] if self.artikel else None
        sorotan = self.artikel[1:1 + int(self.kfg.build.get("jumlah_sorotan", 5))]
        awal = 1 + len(sorotan)
        terbaru = self.artikel[awal: awal + int(self.kfg.build.get("jumlah_terbaru_beranda", 18))]

        # Radar per kategori tokoh
        batas = sekarang_wib() - timedelta(days=7)
        radar = []
        for kunci, info in self.reg.kategori.items():
            slug_tokoh = {t.slug for t in self.reg.daftar_tokoh(kunci)}
            cocok = [a for a in self.artikel
                     if slug_tokoh & set(a.entitas) and (ke_wib(a.terbit_pada) or sekarang_wib()) >= batas]
            hitung = Counter(a.sinyal for a in cocok)
            radar.append({
                "slug": kunci, "label": info["label"], "jumlah": len(cocok),
                "akumulasi": hitung.get("akumulasi", 0), "netral": hitung.get("netral", 0),
                "distribusi": hitung.get("distribusi", 0), "artikel": cocok[:3],
            })
        radar.sort(key=lambda r: -r["jumlah"])

        # Tokoh paling banyak diberitakan
        hitung_tokoh = Counter(s for a in self.artikel for s in a.entitas)
        paling = []
        for slug, n in hitung_tokoh.most_common(9):
            t = self.reg.tokoh.get(slug)
            if t:
                d = t.dict()
                d["jumlah"] = n
                paling.append(d)

        html = self._render(
            "index.html.j2",
            halaman={"judul": self.kfg.situs["nama"], "deskripsi": self.kfg.situs["deskripsi"], "url": "/"},
            utama=utama, sorotan=sorotan, terbaru=terbaru, radar=radar,
            paling_disorot=paling, pita=self._pita())
        self._tulis("/", html, prioritas="1.0")

    def _bangun_artikel(self) -> None:
        pita = self._pita()
        for a in self.artikel:
            terkait = [x for x in self.artikel
                       if x.id != a.id and (set(x.entitas) & set(a.entitas) or x.rubrik == a.rubrik)][:3]
            d = a.dict()
            d["jumlah_kata"] = hitung_kata(a.teks_penuh)
            meta = {
                "judul": a.judul,
                "deskripsi": potong(a.dek or (a.ringkasan[0] if a.ringkasan else ""), 180),
                "url": a.url, "tipe_og": "article", "terbit_pada": a.terbit_pada,
                "rubrik_label": self.kfg.rubrik_by_slug(a.rubrik)["label"],
            }
            self._tulis(a.url, self._render("artikel.html.j2", halaman=meta, a=d,
                                            terkait=terkait, pita=pita),
                        prioritas="0.9", waktu=a.terbit_pada)

    def _bangun_rubrik(self) -> None:
        for r in self.kfg.rubrik:
            artikel = [a for a in self.artikel if a.rubrik == r["slug"]]
            self._halaman_berpaginasi(
                artikel, f"/rubrik/{r['slug']}", "daftar.html.j2",
                {"judul": r["label"], "deskripsi": r["deskripsi"]},
                eyebrow="Rubrik", pita=self._pita())

    def _bangun_tag(self) -> None:
        per_tag: dict[str, list[Artikel]] = defaultdict(list)
        for a in self.artikel:
            for t in a.tag:
                per_tag[t].append(a)
        for tag, artikel in per_tag.items():
            self._halaman_berpaginasi(
                artikel, f"/tag/{tag}", "daftar.html.j2",
                {"judul": f"#{tag}", "deskripsi": f"Seluruh artikel bertanda #{tag}."},
                eyebrow="Tag", pita=[])

    def _bangun_tokoh(self) -> None:
        pita = self._pita()
        jumlah = lambda s: len(self._artikel_tokoh(s))  # noqa: E731

        # direktori utama
        self._tulis("/tokoh", self._render(
            "tokoh_daftar.html.j2",
            halaman={"judul": "Direktori Tokoh",
                     "deskripsi": "Manajer dana, investor institusional, dan analis makro "
                                  "yang keputusan serta pandangannya kami pantau setiap hari.",
                     "url": "/tokoh/"},
            daftar=[t.dict() for t in self.reg.daftar_tokoh()],
            kategori_aktif=None, jumlah_artikel=jumlah, pita=pita), prioritas="0.8")

        # per kategori
        for kunci, info in self.reg.kategori.items():
            self._tulis(f"/tokoh/kategori/{kunci}", self._render(
                "tokoh_daftar.html.j2",
                halaman={"judul": info["label"], "deskripsi": info["deskripsi"],
                         "url": f"/tokoh/kategori/{kunci}/"},
                daftar=[t.dict() for t in self.reg.daftar_tokoh(kunci)],
                kategori_aktif=kunci, jumlah_artikel=jumlah, pita=pita), prioritas="0.6")

        # profil
        for t in self.reg.daftar_tokoh():
            artikel = self._artikel_tokoh(t.slug)
            rekan = [r.dict() for r in self.reg.daftar_tokoh(t.kategori) if r.slug != t.slug][:6]
            sinyal = self._sinyal_dominan(artikel)
            meta = {"judul": f"{t.nama} — {t.organisasi}",
                    "deskripsi": potong(t.bio, 180), "url": t.url, "tipe_og": "profile"}
            self._tulis(t.url, self._render(
                "tokoh.html.j2", halaman=meta, t=t.dict(), artikel=artikel, rekan=rekan,
                sinyal=sinyal,
                label_sinyal={"akumulasi": "Akumulasi", "distribusi": "Distribusi"}.get(sinyal, "Netral"),
                pita=pita), prioritas="0.7")

    def _bangun_perusahaan(self) -> None:
        pita = self._pita()
        jumlah_org = lambda s: len(self._artikel_org(s))  # noqa: E731
        self._tulis("/perusahaan", self._render(
            "perusahaan_daftar.html.j2",
            halaman={"judul": "Direktori Perusahaan",
                     "deskripsi": "Manajer aset, penerbit ETF, dana lindung nilai, dan perusahaan "
                                  "modal ventura yang aktif di pasar aset digital global.",
                     "url": "/perusahaan/"},
            daftar=[o.dict() for o in self.reg.daftar_organisasi()],
            jumlah_artikel_org=jumlah_org, pita=pita), prioritas="0.8")

        for o in self.reg.daftar_organisasi():
            artikel = self._artikel_org(o.slug)
            meta = {"judul": o.nama, "url": o.url,
                    "deskripsi": f"Pemberitaan terbaru mengenai {o.nama} dan para eksekutifnya."}
            self._tulis(o.url, self._render("perusahaan.html.j2", halaman=meta, o=o.dict(),
                                            artikel=artikel, pita=pita), prioritas="0.6")

    def _bangun_statis(self) -> None:
        pita = self._pita()
        # pencarian
        self._tulis("/cari", self._render(
            "cari.html.j2",
            halaman={"judul": "Cari Berita", "url": "/cari/",
                     "deskripsi": "Telusuri arsip berita manajer dana kripto.",
                     "robots": "noindex, follow"}, pita=pita), prioritas="0.3")

        # glosarium
        berkas = self.kfg.akar / "content" / "glosarium.yaml"
        istilah = []
        if berkas.exists():
            data = yaml.safe_load(berkas.read_text(encoding="utf-8")) or {}
            for i in data.get("istilah", []):
                i = dict(i)
                i["slug"] = slugify(i["istilah"])
                istilah.append(i)
        self._tulis("/glosarium", self._render(
            "glosarium.html.j2",
            halaman={"judul": "Glosarium Investasi Aset Digital", "url": "/glosarium/",
                     "deskripsi": "Kamus istilah pengelolaan dana dan aset digital dalam Bahasa Indonesia."},
            istilah=istilah, pita=pita), prioritas="0.6")

        # halaman redaksi
        dir_halaman = self.kfg.akar / "content" / "halaman"
        if dir_halaman.exists():
            for berkas in sorted(dir_halaman.glob("*.yaml")):
                data = yaml.safe_load(berkas.read_text(encoding="utf-8")) or {}
                self._tulis(f"/{data['slug']}", self._render(
                    "statis.html.j2",
                    halaman={"judul": data["judul"], "deskripsi": data.get("deskripsi", ""),
                             "url": f"/{data['slug']}/"},
                    eyebrow=data.get("eyebrow", "Redaksi"), isi=data.get("isi", ""),
                    pita=pita), prioritas="0.4")

        # 404
        self._tulis("404.html", self._render(
            "404.html.j2",
            halaman={"judul": "Halaman tidak ditemukan", "url": "/404.html",
                     "robots": "noindex, nofollow"}, pita=[]))

    def _salin_aset(self) -> None:
        tujuan = self.keluar / "static"
        if tujuan.exists():
            shutil.rmtree(tujuan)
        shutil.copytree(self.kfg.dir_statis, tujuan)

    # ------------------------------------------------------------ bangun ----
    def bangun(self, verbose: bool = True) -> dict:
        self.artikel = self.simpan.artikel(status="terbit")
        self.url_sitemap = []

        if self.keluar.exists():
            shutil.rmtree(self.keluar)
        self.keluar.mkdir(parents=True, exist_ok=True)

        langkah = [
            ("beranda", self._bangun_beranda),
            ("artikel", self._bangun_artikel),
            ("rubrik", self._bangun_rubrik),
            ("tag", self._bangun_tag),
            ("tokoh", self._bangun_tokoh),
            ("perusahaan", self._bangun_perusahaan),
            ("halaman statis", self._bangun_statis),
            ("aset", self._salin_aset),
        ]
        for nama, fungsi in langkah:
            fungsi()
            if verbose:
                print(f"    · {nama}")

        if self.kfg.build.get("aktifkan_rss", True):
            tulis_rss(self.artikel, self.kfg, self.keluar)
        if self.kfg.build.get("aktifkan_sitemap", True):
            tulis_sitemap(self.url_sitemap, self.kfg, self.keluar)
            tulis_sitemap_berita(self.artikel, self.kfg, self.keluar)
            tulis_robots(self.kfg, self.keluar)
        if self.kfg.build.get("aktifkan_pencarian", True):
            tulis_indeks_cari(self.artikel, self.kfg, self.reg, self.keluar)

        ringkas = {"artikel": len(self.artikel), "halaman": len(self.url_sitemap),
                   "keluaran": str(self.keluar)}
        self.simpan.catat("bangun", str(ringkas))
        return ringkas
