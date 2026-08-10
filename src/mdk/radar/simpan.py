"""Penyimpanan radar — tabel tambahan pada basis data yang sama.

Empat tabel:
  terlihat      : catatan URL yang pernah dilihat. Inti anti-duplikat.
  kesehatan     : kondisi tiap sumber (ETag, kegagalan beruntun, hasil terakhir).
  klaster       : pengelompokan beberapa laporan atas satu peristiwa yang sama.
  notifikasi    : jurnal pengiriman, mencegah kirim ganda saat proses diulang.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

from ..utils import sekarang_wib, sidik_jari

SKEMA = """
CREATE TABLE IF NOT EXISTS terlihat (
    sidik         TEXT PRIMARY KEY,      -- hash URL kanonik
    url           TEXT NOT NULL,
    judul         TEXT,
    penerbit      TEXT,
    entitas       TEXT,                  -- slug entitas pemicu
    jenis_entitas TEXT,
    sumber_id     TEXT,
    jenis_sumber  TEXT,
    terbit_pada   TEXT,
    dilihat_pada  TEXT,
    klaster       TEXT,                  -- id klaster peristiwa
    skor          REAL DEFAULT 0,
    diteruskan    INTEGER DEFAULT 0      -- 1 = sudah masuk antrean terjemahan
);
CREATE INDEX IF NOT EXISTS idx_terlihat_waktu   ON terlihat(dilihat_pada DESC);
CREATE INDEX IF NOT EXISTS idx_terlihat_entitas ON terlihat(entitas, dilihat_pada DESC);
CREATE INDEX IF NOT EXISTS idx_terlihat_klaster ON terlihat(klaster);

CREATE TABLE IF NOT EXISTS kesehatan (
    sumber_id       TEXT PRIMARY KEY,
    url             TEXT,
    etag            TEXT,
    modifikasi      TEXT,                -- header Last-Modified
    terakhir_jajak  TEXT,
    terakhir_sukses TEXT,
    gagal_beruntun  INTEGER DEFAULT 0,
    total_item      INTEGER DEFAULT 0,
    total_temuan    INTEGER DEFAULT 0,   -- item baru yang lolos saringan
    galat_terakhir  TEXT,
    aktif           INTEGER DEFAULT 1,
    terverifikasi   INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS klaster (
    id            TEXT PRIMARY KEY,
    judul_utama   TEXT,
    url_utama     TEXT,
    penerbit      TEXT,
    entitas       TEXT DEFAULT '[]',
    jumlah_sumber INTEGER DEFAULT 1,
    skor          REAL DEFAULT 0,
    dibuat_pada   TEXT,
    diperbarui    TEXT,
    dinotifikasi  INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_klaster_waktu ON klaster(dibuat_pada DESC);

CREATE TABLE IF NOT EXISTS notifikasi (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    klaster  TEXT,
    kanal    TEXT,
    status   TEXT,
    pesan    TEXT,
    waktu    TEXT
);
CREATE INDEX IF NOT EXISTS idx_notif_klaster ON notifikasi(klaster, kanal);
"""


class PenyimpananRadar:
    def __init__(self, jalur: Path):
        self.jalur = Path(jalur)
        self.jalur.parent.mkdir(parents=True, exist_ok=True)
        with self._kon() as kon:
            kon.executescript(SKEMA)

    @contextmanager
    def _kon(self):
        kon = sqlite3.connect(self.jalur, timeout=30)
        kon.row_factory = sqlite3.Row
        try:
            kon.execute("PRAGMA journal_mode=WAL")
            yield kon
            kon.commit()
        finally:
            kon.close()

    # ------------------------------------------------------------ terlihat --
    def pernah_dilihat(self, url_kanonik: str) -> bool:
        with self._kon() as kon:
            return kon.execute("SELECT 1 FROM terlihat WHERE sidik=?",
                               (sidik_jari(url_kanonik),)).fetchone() is not None

    def sidik_dikenal(self, sidik_list: list[str]) -> set[str]:
        """Periksa banyak sidik sekaligus — jauh lebih cepat daripada satu per satu."""
        if not sidik_list:
            return set()
        with self._kon() as kon:
            hasil = set()
            for i in range(0, len(sidik_list), 400):        # hindari batas SQLite
                bagian = sidik_list[i:i + 400]
                tanya = ",".join("?" * len(bagian))
                hasil |= {b["sidik"] for b in kon.execute(
                    f"SELECT sidik FROM terlihat WHERE sidik IN ({tanya})", bagian).fetchall()}
            return hasil

    def catat_terlihat(self, temuan: dict) -> bool:
        """Simpan satu temuan. Kembalikan True bila benar-benar baru."""
        with self._kon() as kon:
            kur = kon.execute(
                """INSERT OR IGNORE INTO terlihat
                   (sidik, url, judul, penerbit, entitas, jenis_entitas, sumber_id,
                    jenis_sumber, terbit_pada, dilihat_pada, klaster, skor, diteruskan)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0)""",
                (temuan["sidik"], temuan["url"], temuan.get("judul", ""),
                 temuan.get("penerbit", ""), temuan.get("entitas", ""),
                 temuan.get("jenis_entitas", ""), temuan.get("sumber_id", ""),
                 temuan.get("jenis_sumber", ""), temuan.get("terbit_pada", ""),
                 sekarang_wib().isoformat(), temuan.get("klaster", ""),
                 float(temuan.get("skor", 0))))
            return kur.rowcount > 0

    def temuan_terbaru(self, jam: int = 24, batas: int = 200) -> list[dict]:
        batas_waktu = (sekarang_wib() - timedelta(hours=jam)).isoformat()
        with self._kon() as kon:
            return [dict(b) for b in kon.execute(
                "SELECT * FROM terlihat WHERE dilihat_pada >= ? "
                "ORDER BY skor DESC, dilihat_pada DESC LIMIT ?",
                (batas_waktu, batas)).fetchall()]

    def belum_diteruskan(self, batas: int = 100) -> list[dict]:
        with self._kon() as kon:
            return [dict(b) for b in kon.execute(
                "SELECT * FROM terlihat WHERE diteruskan=0 ORDER BY skor DESC LIMIT ?",
                (batas,)).fetchall()]

    def tandai_diteruskan(self, sidik_list: list[str]) -> None:
        if not sidik_list:
            return
        with self._kon() as kon:
            kon.executemany("UPDATE terlihat SET diteruskan=1 WHERE sidik=?",
                            [(s,) for s in sidik_list])

    def pangkas(self, hari: int = 120) -> int:
        """Buang catatan lama agar basis data tidak tumbuh tanpa batas."""
        batas = (sekarang_wib() - timedelta(days=hari)).isoformat()
        with self._kon() as kon:
            kur = kon.execute("DELETE FROM terlihat WHERE dilihat_pada < ?", (batas,))
            kon.execute("DELETE FROM klaster WHERE dibuat_pada < ?", (batas,))
            return kur.rowcount

    # ----------------------------------------------------------- kesehatan --
    def kondisi(self, sumber_id: str) -> dict | None:
        with self._kon() as kon:
            b = kon.execute("SELECT * FROM kesehatan WHERE sumber_id=?", (sumber_id,)).fetchone()
            return dict(b) if b else None

    def semua_kondisi(self) -> dict[str, dict]:
        with self._kon() as kon:
            return {b["sumber_id"]: dict(b)
                    for b in kon.execute("SELECT * FROM kesehatan").fetchall()}

    def catat_sukses(self, sumber_id: str, url: str, etag: str, modifikasi: str,
                     jumlah_item: int, jumlah_temuan: int) -> None:
        waktu = sekarang_wib().isoformat()
        with self._kon() as kon:
            kon.execute(
                """INSERT INTO kesehatan
                     (sumber_id, url, etag, modifikasi, terakhir_jajak, terakhir_sukses,
                      gagal_beruntun, total_item, total_temuan, galat_terakhir, aktif, terverifikasi)
                   VALUES (?,?,?,?,?,?,0,?,?,'',1,1)
                   ON CONFLICT(sumber_id) DO UPDATE SET
                     etag=excluded.etag, modifikasi=excluded.modifikasi,
                     terakhir_jajak=excluded.terakhir_jajak,
                     terakhir_sukses=excluded.terakhir_sukses,
                     gagal_beruntun=0, galat_terakhir='', aktif=1, terverifikasi=1,
                     total_item=kesehatan.total_item + excluded.total_item,
                     total_temuan=kesehatan.total_temuan + excluded.total_temuan""",
                (sumber_id, url, etag or "", modifikasi or "", waktu, waktu,
                 jumlah_item, jumlah_temuan))

    def catat_gagal(self, sumber_id: str, url: str, galat: str,
                    batas_nonaktif: int = 6) -> int:
        """Naikkan penghitung kegagalan; nonaktifkan otomatis bila melewati batas."""
        waktu = sekarang_wib().isoformat()
        with self._kon() as kon:
            kon.execute(
                """INSERT INTO kesehatan (sumber_id, url, terakhir_jajak, gagal_beruntun,
                                          galat_terakhir, aktif, terverifikasi)
                   VALUES (?,?,?,1,?,1,0)
                   ON CONFLICT(sumber_id) DO UPDATE SET
                     terakhir_jajak=excluded.terakhir_jajak,
                     gagal_beruntun=kesehatan.gagal_beruntun + 1,
                     galat_terakhir=excluded.galat_terakhir""",
                (sumber_id, url, waktu, galat[:250]))
            n = kon.execute("SELECT gagal_beruntun FROM kesehatan WHERE sumber_id=?",
                            (sumber_id,)).fetchone()["gagal_beruntun"]
            if n >= batas_nonaktif:
                kon.execute("UPDATE kesehatan SET aktif=0 WHERE sumber_id=?", (sumber_id,))
            return n

    def aktifkan_ulang(self, sumber_id: str | None = None) -> int:
        with self._kon() as kon:
            if sumber_id:
                kur = kon.execute(
                    "UPDATE kesehatan SET aktif=1, gagal_beruntun=0 WHERE sumber_id=?",
                    (sumber_id,))
            else:
                kur = kon.execute("UPDATE kesehatan SET aktif=1, gagal_beruntun=0 WHERE aktif=0")
            return kur.rowcount

    # ------------------------------------------------------------- klaster --
    def simpan_klaster(self, k: dict) -> None:
        with self._kon() as kon:
            kon.execute(
                """INSERT INTO klaster
                     (id, judul_utama, url_utama, penerbit, entitas, jumlah_sumber,
                      skor, dibuat_pada, diperbarui, dinotifikasi)
                   VALUES (?,?,?,?,?,?,?,?,?,0)
                   ON CONFLICT(id) DO UPDATE SET
                     jumlah_sumber=excluded.jumlah_sumber, skor=excluded.skor,
                     entitas=excluded.entitas, diperbarui=excluded.diperbarui""",
                (k["id"], k["judul_utama"], k["url_utama"], k.get("penerbit", ""),
                 json.dumps(k.get("entitas", []), ensure_ascii=False),
                 int(k.get("jumlah_sumber", 1)), float(k.get("skor", 0)),
                 k.get("dibuat_pada") or sekarang_wib().isoformat(),
                 sekarang_wib().isoformat()))

    def klaster_belum_dinotifikasi(self, batas: int = 50) -> list[dict]:
        with self._kon() as kon:
            baris = kon.execute(
                "SELECT * FROM klaster WHERE dinotifikasi=0 ORDER BY skor DESC LIMIT ?",
                (batas,)).fetchall()
        keluar = []
        for b in baris:
            d = dict(b)
            d["entitas"] = json.loads(d.get("entitas") or "[]")
            keluar.append(d)
        return keluar

    def tandai_dinotifikasi(self, id_list: list[str]) -> None:
        if not id_list:
            return
        with self._kon() as kon:
            kon.executemany("UPDATE klaster SET dinotifikasi=1 WHERE id=?",
                            [(i,) for i in id_list])

    def judul_klaster_terkini(self, jam: int = 72, batas: int = 500) -> list[tuple[str, str]]:
        batas_waktu = (sekarang_wib() - timedelta(hours=jam)).isoformat()
        with self._kon() as kon:
            return [(b["id"], b["judul_utama"]) for b in kon.execute(
                "SELECT id, judul_utama FROM klaster WHERE dibuat_pada >= ? "
                "ORDER BY dibuat_pada DESC LIMIT ?", (batas_waktu, batas)).fetchall()]

    # ---------------------------------------------------------- notifikasi --
    def catat_notifikasi(self, klaster_id: str, kanal: str, status: str, pesan: str = "") -> None:
        with self._kon() as kon:
            kon.execute(
                "INSERT INTO notifikasi (klaster, kanal, status, pesan, waktu) VALUES (?,?,?,?,?)",
                (klaster_id, kanal, status, pesan[:250], sekarang_wib().isoformat()))

    def sudah_dikirim(self, klaster_id: str, kanal: str) -> bool:
        with self._kon() as kon:
            return kon.execute(
                "SELECT 1 FROM notifikasi WHERE klaster=? AND kanal=? AND status='terkirim'",
                (klaster_id, kanal)).fetchone() is not None

    # ------------------------------------------------------------ statistik --
    def statistik(self) -> dict:
        with self._kon() as kon:
            t = kon.execute("SELECT COUNT(*) c FROM terlihat").fetchone()["c"]
            hari = kon.execute(
                "SELECT COUNT(*) c FROM terlihat WHERE dilihat_pada >= ?",
                ((sekarang_wib() - timedelta(hours=24)).isoformat(),)).fetchone()["c"]
            k = kon.execute("SELECT COUNT(*) c FROM klaster").fetchone()["c"]
            aktif = kon.execute("SELECT COUNT(*) c FROM kesehatan WHERE aktif=1").fetchone()["c"]
            mati = kon.execute("SELECT COUNT(*) c FROM kesehatan WHERE aktif=0").fetchone()["c"]
            antre = kon.execute("SELECT COUNT(*) c FROM terlihat WHERE diteruskan=0").fetchone()["c"]
            teratas = [dict(b) for b in kon.execute(
                "SELECT entitas, COUNT(*) c FROM terlihat WHERE dilihat_pada >= ? "
                "GROUP BY entitas ORDER BY c DESC LIMIT 8",
                ((sekarang_wib() - timedelta(days=7)).isoformat(),)).fetchall()]
        return {"total_temuan": t, "temuan_24jam": hari, "klaster": k,
                "sumber_aktif": aktif, "sumber_nonaktif": mati,
                "antre_terjemahan": antre, "entitas_teratas": teratas}


def buka_radar(kfg) -> PenyimpananRadar:
    return PenyimpananRadar(kfg.basis_data)
