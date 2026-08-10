"""Registri tokoh/organisasi dan mesin penandaan entitas pada teks berita."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

from .config import Konfigurasi, muat_konfigurasi
from .models import Tokoh
from .utils import slugify


@dataclass
class Organisasi:
    slug: str
    nama: str
    negara: str = ""
    tokoh: list[str] = field(default_factory=list)   # slug tokoh

    @property
    def url(self) -> str:
        return f"/perusahaan/{self.slug}/"

    def dict(self) -> dict:
        return {"slug": self.slug, "nama": self.nama, "negara": self.negara,
                "tokoh": self.tokoh, "url": self.url}


class Registri:
    """Akses terpusat ke daftar tokoh, organisasi, dan kategori."""

    def __init__(self, kfg: Konfigurasi | None = None):
        self.kfg = kfg or muat_konfigurasi()
        mentah = self.kfg.entitas_mentah
        self.kategori: dict[str, dict] = mentah.get("kategori", {})
        self.tokoh: dict[str, Tokoh] = {}
        self.organisasi: dict[str, Organisasi] = {}

        for baris in mentah.get("tokoh", []):
            t = Tokoh(
                slug=baris["slug"], nama=baris["nama"], organisasi=baris["organisasi"],
                org_slug=baris.get("org_slug") or slugify(baris["organisasi"]),
                jabatan=baris.get("jabatan", ""), kategori=baris.get("kategori", "manajer-aset"),
                negara=baris.get("negara", ""), x=baris.get("x", "") or "",
                alias=list(baris.get("alias", []) or []), bio=baris.get("bio", ""),
                terverifikasi=bool(baris.get("terverifikasi", False)),
            )
            if not t.alias or t.nama not in t.alias:
                t.alias.insert(0, t.nama)
            self.tokoh[t.slug] = t
            org = self.organisasi.setdefault(
                t.org_slug, Organisasi(slug=t.org_slug, nama=t.organisasi, negara=t.negara))
            org.tokoh.append(t.slug)

        self._pola = self._bangun_pola()

    # ------------------------------------------------------------------ pola --
    def _bangun_pola(self) -> list[tuple[re.Pattern, str, bool]]:
        """(pola, slug_tokoh, apakah_nama_lengkap) diurutkan dari alias terpanjang."""
        pola: list[tuple[re.Pattern, str, bool]] = []
        for t in self.tokoh.values():
            for i, alias in enumerate(t.alias):
                alias = alias.strip()
                if len(alias) < 4:      # terlalu pendek -> rawan positif palsu
                    continue
                pola.append((
                    re.compile(r"(?<!\w)" + re.escape(alias).replace(r"\ ", r"\s+") + r"(?!\w)",
                               re.IGNORECASE),
                    t.slug, i == 0,
                ))
        pola.sort(key=lambda p: len(p[0].pattern), reverse=True)
        return pola

    # --------------------------------------------------------------- kueri ---
    def daftar_tokoh(self, kategori: str | None = None) -> list[Tokoh]:
        hasil = list(self.tokoh.values())
        if kategori:
            hasil = [t for t in hasil if t.kategori == kategori]
        return sorted(hasil, key=lambda t: t.nama)

    def daftar_organisasi(self) -> list[Organisasi]:
        return sorted(self.organisasi.values(), key=lambda o: o.nama)

    def label_kategori(self, kunci: str) -> str:
        return self.kategori.get(kunci, {}).get("label", kunci.replace("-", " ").title())

    def alias_kueri(self, maks_per_tokoh: int = 2, hemat: bool = False) -> list[tuple[str, str]]:
        """Pasangan (slug_tokoh, alias) untuk membangun kueri Google News."""
        keluar: list[tuple[str, str]] = []
        for t in self.tokoh.values():
            batas = 1 if hemat else maks_per_tokoh
            for alias in t.alias[:batas]:
                keluar.append((t.slug, alias))
        return keluar

    # ------------------------------------------------------------- penandaan --
    def tandai(self, judul: str, ringkasan: str = "") -> dict:
        """Deteksi tokoh & organisasi. Mengembalikan skor relevansi mentah."""
        rel = self.kfg.relevansi
        teks_judul, teks_ringkas = judul or "", ringkasan or ""
        tokoh_cocok: dict[str, int] = {}

        for pola, slug, nama_lengkap in self._pola:
            di_judul = bool(pola.search(teks_judul))
            di_ringkas = bool(pola.search(teks_ringkas))
            if not (di_judul or di_ringkas):
                continue
            nilai = 0
            if di_judul:
                nilai += int(rel.get("bobot_entitas_di_judul", 45))
            if di_ringkas:
                nilai += int(rel.get("bobot_entitas_di_ringkasan", 25))
            if not nama_lengkap:                     # alias organisasi/julukan
                nilai = int(nilai * 0.7) + int(rel.get("bobot_organisasi", 15))
            tokoh_cocok[slug] = max(tokoh_cocok.get(slug, 0), nilai)

        org = sorted({self.tokoh[s].org_slug for s in tokoh_cocok})
        return {
            "entitas": sorted(tokoh_cocok, key=lambda s: -tokoh_cocok[s]),
            "organisasi": org,
            "skor_entitas": sum(sorted(tokoh_cocok.values(), reverse=True)[:3]),
        }

    def skor_tema(self, teks: str) -> int:
        kunci = self.kfg.sumber.get("kata_kunci_tema", [])
        bobot = int(self.kfg.relevansi.get("bobot_kata_kunci_tema", 10))
        rendah = (teks or "").lower()
        cocok = sum(1 for k in kunci if k.lower() in rendah)
        return min(cocok, 4) * bobot

    def ditolak(self, teks: str) -> bool:
        rendah = (teks or "").lower()
        return any(k.lower() in rendah for k in self.kfg.sumber.get("kata_kunci_tolak", []))


@lru_cache(maxsize=1)
def registri() -> Registri:
    return Registri()
