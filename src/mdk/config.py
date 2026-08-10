"""Pemuat konfigurasi: settings.yaml, sources.yaml, entities.yaml."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

AKAR = Path(__file__).resolve().parents[2]
DIR_KONFIG = AKAR / "config"


def _muat(nama: str) -> dict[str, Any]:
    berkas = DIR_KONFIG / nama
    if not berkas.exists():
        raise FileNotFoundError(f"Berkas konfigurasi tidak ditemukan: {berkas}")
    with berkas.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@dataclass(frozen=True)
class Konfigurasi:
    """Wadah seluruh konfigurasi situs."""
    situs: dict = field(default_factory=dict)
    rubrik: list = field(default_factory=list)
    editorial: dict = field(default_factory=dict)
    relevansi: dict = field(default_factory=dict)
    ai: dict = field(default_factory=dict)
    build: dict = field(default_factory=dict)
    radar: dict = field(default_factory=dict)
    sumber: dict = field(default_factory=dict)
    entitas_mentah: dict = field(default_factory=dict)

    # ---- jalur ----
    @property
    def akar(self) -> Path:
        return AKAR

    @property
    def dir_keluaran(self) -> Path:
        return AKAR / self.build.get("direktori_keluaran", "dist")

    @property
    def dir_data(self) -> Path:
        d = AKAR / "data"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def basis_data(self) -> Path:
        return self.dir_data / "mdk.sqlite3"

    @property
    def dir_templat(self) -> Path:
        return AKAR / "templates"

    @property
    def dir_statis(self) -> Path:
        return AKAR / "static"

    # ---- pintasan ----
    @property
    def base_url(self) -> str:
        return str(self.situs.get("base_url", "")).rstrip("/")

    @property
    def kunci_api(self) -> str:
        return os.environ.get("ANTHROPIC_API_KEY", "")

    def rubrik_by_slug(self, slug: str) -> dict:
        for r in self.rubrik:
            if r["slug"] == slug:
                return r
        return {"slug": slug, "label": slug.replace("-", " ").title(), "deskripsi": ""}

    @property
    def slug_rubrik(self) -> list[str]:
        return [r["slug"] for r in self.rubrik]


@lru_cache(maxsize=1)
def muat_konfigurasi() -> Konfigurasi:
    s = _muat("settings.yaml")
    return Konfigurasi(
        situs=s.get("situs", {}),
        rubrik=s.get("rubrik", []),
        editorial=s.get("editorial", {}),
        relevansi=s.get("relevansi", {}),
        ai=s.get("ai", {}),
        build=s.get("build", {}),
        radar=s.get("radar", {}),
        sumber=_muat("sources.yaml"),
        entitas_mentah=_muat("entities.yaml"),
    )
