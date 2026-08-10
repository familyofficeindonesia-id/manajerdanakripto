"""Lapisan penyimpanan SQLite untuk item mentah dan artikel terbit."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable

from .models import Artikel, ItemMentah
from .utils import sekarang_wib

SKEMA = """
CREATE TABLE IF NOT EXISTS mentah (
    id              TEXT PRIMARY KEY,
    judul           TEXT NOT NULL,
    url             TEXT NOT NULL,
    url_kanonik     TEXT NOT NULL UNIQUE,
    penerbit        TEXT,
    ringkasan_sumber TEXT,
    terbit_pada     TEXT,
    diambil_pada    TEXT,
    bahasa          TEXT,
    bobot_sumber    REAL DEFAULT 1.0,
    entitas         TEXT DEFAULT '[]',
    organisasi      TEXT DEFAULT '[]',
    skor            INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'baru'      -- baru | diproses | dilewati | gagal
);
CREATE INDEX IF NOT EXISTS idx_mentah_status ON mentah(status, skor DESC);
CREATE INDEX IF NOT EXISTS idx_mentah_terbit ON mentah(terbit_pada DESC);

CREATE TABLE IF NOT EXISTS artikel (
    id                TEXT PRIMARY KEY,
    slug              TEXT NOT NULL,
    judul             TEXT NOT NULL,
    dek               TEXT,
    ringkasan         TEXT DEFAULT '[]',
    paragraf          TEXT DEFAULT '[]',
    rubrik            TEXT,
    tag               TEXT DEFAULT '[]',
    entitas           TEXT DEFAULT '[]',
    organisasi        TEXT DEFAULT '[]',
    konteks_indonesia TEXT,
    sinyal            TEXT DEFAULT 'netral',
    kutipan_teks      TEXT,
    kutipan_oleh      TEXT,
    sumber_nama       TEXT,
    sumber_url        TEXT,
    sumber_terbit     TEXT,
    terbit_pada       TEXT,
    penulis           TEXT,
    status            TEXT DEFAULT 'terbit',
    skor              INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_artikel_terbit ON artikel(terbit_pada DESC);
CREATE INDEX IF NOT EXISTS idx_artikel_rubrik ON artikel(rubrik, terbit_pada DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_artikel_slug ON artikel(slug);

CREATE TABLE IF NOT EXISTS jurnal (
    waktu   TEXT,
    tahap   TEXT,
    pesan   TEXT
);
"""

_KOLOM_JSON = ("ringkasan", "paragraf", "tag", "entitas", "organisasi")


class Penyimpanan:
    def __init__(self, jalur: Path):
        self.jalur = Path(jalur)
        self.jalur.parent.mkdir(parents=True, exist_ok=True)
        with self._kon() as kon:
            kon.executescript(SKEMA)

    @contextmanager
    def _kon(self):
        kon = sqlite3.connect(self.jalur)
        kon.row_factory = sqlite3.Row
        try:
            yield kon
            kon.commit()
        finally:
            kon.close()

    # ------------------------------------------------------------- mentah ----
    def simpan_mentah(self, item: ItemMentah) -> bool:
        """Kembalikan True bila item benar-benar baru."""
        with self._kon() as kon:
            kur = kon.execute(
                """INSERT OR IGNORE INTO mentah
                   (id, judul, url, url_kanonik, penerbit, ringkasan_sumber, terbit_pada,
                    diambil_pada, bahasa, bobot_sumber, entitas, organisasi, skor)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (item.id, item.judul, item.url, item.url_kanonik, item.penerbit,
                 item.ringkasan_sumber, item.terbit_pada, item.diambil_pada, item.bahasa,
                 item.bobot_sumber, json.dumps(item.entitas), json.dumps(item.organisasi),
                 item.skor))
            return kur.rowcount > 0

    def sudah_ada(self, url_kanonik: str) -> bool:
        with self._kon() as kon:
            return kon.execute("SELECT 1 FROM mentah WHERE url_kanonik=?",
                               (url_kanonik,)).fetchone() is not None

    def mentah_menunggu(self, batas: int = 40) -> list[sqlite3.Row]:
        with self._kon() as kon:
            return kon.execute(
                "SELECT * FROM mentah WHERE status='baru' ORDER BY skor DESC, terbit_pada DESC LIMIT ?",
                (batas,)).fetchall()

    def tandai_mentah(self, id_: str, status: str) -> None:
        with self._kon() as kon:
            kon.execute("UPDATE mentah SET status=? WHERE id=?", (status, id_))

    def judul_terkini(self, batas: int = 400) -> list[tuple[str, str]]:
        with self._kon() as kon:
            baris = kon.execute(
                "SELECT id, judul FROM mentah ORDER BY diambil_pada DESC LIMIT ?", (batas,)).fetchall()
        return [(b["id"], b["judul"]) for b in baris]

    # ------------------------------------------------------------ artikel ----
    def simpan_artikel(self, a: Artikel) -> None:
        d = a.dict()
        for k in _KOLOM_JSON:
            d[k] = json.dumps(d.get(k, []), ensure_ascii=False)
        kolom = ("id slug judul dek ringkasan paragraf rubrik tag entitas organisasi "
                 "konteks_indonesia sinyal kutipan_teks kutipan_oleh sumber_nama sumber_url "
                 "sumber_terbit terbit_pada penulis status skor").split()
        with self._kon() as kon:
            # Slug harus unik; tambahkan sufiks bila bentrok dengan artikel lain.
            bentrok = kon.execute("SELECT id FROM artikel WHERE slug=? AND id<>?",
                                  (d["slug"], d["id"])).fetchone()
            if bentrok:
                d["slug"] = f"{d['slug']}-{d['id'][:6]}"
            kon.execute(
                f"INSERT OR REPLACE INTO artikel ({','.join(kolom)}) "
                f"VALUES ({','.join('?' * len(kolom))})",
                tuple(d[k] for k in kolom))

    def artikel(self, status: str = "terbit", batas: int | None = None) -> list[Artikel]:
        kueri = "SELECT * FROM artikel WHERE status=? ORDER BY terbit_pada DESC"
        if batas:
            kueri += f" LIMIT {int(batas)}"
        with self._kon() as kon:
            return [Artikel.dari_baris(dict(b)) for b in kon.execute(kueri, (status,)).fetchall()]

    def jumlah_artikel(self) -> int:
        with self._kon() as kon:
            return kon.execute("SELECT COUNT(*) c FROM artikel WHERE status='terbit'").fetchone()["c"]

    def hapus_artikel(self, id_: str) -> None:
        with self._kon() as kon:
            kon.execute("DELETE FROM artikel WHERE id=?", (id_,))

    # ------------------------------------------------------------- jurnal ----
    def catat(self, tahap: str, pesan: str) -> None:
        with self._kon() as kon:
            kon.execute("INSERT INTO jurnal (waktu, tahap, pesan) VALUES (?,?,?)",
                        (sekarang_wib().isoformat(), tahap, pesan))

    def statistik(self) -> dict:
        with self._kon() as kon:
            m = kon.execute("SELECT status, COUNT(*) c FROM mentah GROUP BY status").fetchall()
            a = kon.execute("SELECT status, COUNT(*) c FROM artikel GROUP BY status").fetchall()
        return {"mentah": {b["status"]: b["c"] for b in m},
                "artikel": {b["status"]: b["c"] for b in a}}


def buka(kfg) -> Penyimpanan:
    return Penyimpanan(kfg.basis_data)
