"""Model data inti: ItemMentah, Tokoh, dan Artikel."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from .utils import sidik_jari, slugify, waktu_baca


@dataclass
class Tokoh:
    """Satu manajer dana / investor pada registri entitas."""
    slug: str
    nama: str
    organisasi: str
    org_slug: str
    jabatan: str = ""
    kategori: str = "manajer-aset"
    negara: str = ""
    x: str = ""
    alias: list[str] = field(default_factory=list)
    bio: str = ""
    terverifikasi: bool = False

    @property
    def inisial(self) -> str:
        bagian = [b for b in self.nama.split() if b]
        return (bagian[0][0] + (bagian[-1][0] if len(bagian) > 1 else "")).upper()

    @property
    def url(self) -> str:
        return f"/tokoh/{self.slug}/"

    @property
    def url_organisasi(self) -> str:
        return f"/perusahaan/{self.org_slug}/"

    def dict(self) -> dict:
        d = asdict(self)
        d.update(inisial=self.inisial, url=self.url, url_organisasi=self.url_organisasi)
        return d


@dataclass
class ItemMentah:
    """Satu entri umpan RSS sebelum diproses. Tidak pernah dipublikasikan."""
    judul: str
    url: str
    url_kanonik: str
    penerbit: str
    ringkasan_sumber: str = ""
    terbit_pada: str = ""          # ISO 8601
    diambil_pada: str = ""
    bahasa: str = "en"
    bobot_sumber: float = 1.0
    entitas: list[str] = field(default_factory=list)
    organisasi: list[str] = field(default_factory=list)
    skor: int = 0

    @property
    def id(self) -> str:
        return sidik_jari(self.url_kanonik)


@dataclass
class Artikel:
    """Artikel siap tayang — seluruhnya tulisan orisinal berbahasa Indonesia."""
    id: str
    slug: str
    judul: str
    dek: str = ""                              # subjudul satu kalimat
    ringkasan: list[str] = field(default_factory=list)   # 3 poin kilat
    paragraf: list[str] = field(default_factory=list)    # isi artikel
    rubrik: str = "berita-utama"
    tag: list[str] = field(default_factory=list)
    entitas: list[str] = field(default_factory=list)     # slug tokoh
    organisasi: list[str] = field(default_factory=list)  # slug organisasi
    konteks_indonesia: str = ""
    sinyal: str = "netral"                     # akumulasi | netral | distribusi
    kutipan_teks: str = ""
    kutipan_oleh: str = ""
    sumber_nama: str = ""
    sumber_url: str = ""
    sumber_terbit: str = ""                    # ISO 8601, waktu terbit sumber
    terbit_pada: str = ""                      # ISO 8601, waktu tayang kami
    penulis: str = "Redaksi ManajerDanaKripto"
    status: str = "terbit"                     # draf | terbit | arsip
    skor: int = 0

    # ---- turunan ----
    @property
    def teks_penuh(self) -> str:
        return " ".join([self.dek] + self.ringkasan + self.paragraf)

    @property
    def menit_baca(self) -> int:
        return waktu_baca(self.teks_penuh)

    @property
    def url(self) -> str:
        tahun, bulan = (self.terbit_pada[:4] or "2026"), (self.terbit_pada[5:7] or "01")
        return f"/berita/{tahun}/{bulan}/{self.slug}/"

    @property
    def label_sinyal(self) -> str:
        return {"akumulasi": "Akumulasi", "distribusi": "Distribusi"}.get(self.sinyal, "Netral")

    def dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.update(url=self.url, menit_baca=self.menit_baca, label_sinyal=self.label_sinyal)
        return d

    # ---- serialisasi ----
    @classmethod
    def dari_baris(cls, baris: dict) -> "Artikel":
        data = dict(baris)
        for k in ("ringkasan", "paragraf", "tag", "entitas", "organisasi"):
            nilai = data.get(k)
            data[k] = json.loads(nilai) if isinstance(nilai, str) else (nilai or [])
        sah = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in sah})

    @classmethod
    def baru(cls, judul: str, **kw) -> "Artikel":
        slug = slugify(judul)
        return cls(id=sidik_jari(kw.get("sumber_url", ""), judul), slug=slug, judul=judul, **kw)
