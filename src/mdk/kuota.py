"""
Pemutus arus (circuit breaker) untuk kuota harian Gemini.

Tujuan: begitu satu jalan menabrak 429 "kuota harian habis", jalan-jalan
berikutnya tidak perlu membakar request lagi hanya untuk menemukan tembok
yang sama. Penanda disimpan di basis data SQLite yang sudah ada, sehingga
ikut terbawa cache dan backup branch `cadangan-basis-data`.

Pemakaian dari kode Python:

    from mdk import kuota

    boleh, alasan = kuota.boleh_menulis()
    if not boleh:
        print(f"Melewati tahap tulis: {alasan}")
        return

    # ... saat menerima 429 kuota harian:
    kuota.catat_habis("429 pada artikel X")

Pemakaian sebagai gerbang di GitHub Actions:

    python -m mdk.kuota periksa

Akan mencetak `boleh=true` atau `boleh=false` ke stdout, dan menulis
`boleh=<nilai>` ke $GITHUB_OUTPUT bila tersedia. Selalu keluar dengan kode 0
supaya tidak menggagalkan job.
"""

from __future__ import annotations

import os
import sys
import glob
import sqlite3
from datetime import datetime, timedelta, timezone

# Jam reset kuota dalam UTC. Tengah malam waktu Pasifik = 07:00 UTC saat PDT,
# 08:00 UTC saat PST. Angka ini BELUM diverifikasi terhadap log Anda — lihat
# catatan di bawah tentang cara memastikannya.
JAM_RESET_UTC = int(os.environ.get("JAM_RESET_KUOTA_UTC", "7"))

# Kandidat lokasi basis data, dicoba berurutan bila MDK_BASIS_DATA tidak diisi.
POLA_BASIS_DATA = [
    "data/*.sqlite3",
    "data/*.db",
    "*.sqlite3",
    "*.db",
    "basis_data/*.sqlite3",
    "basis_data/*.db",
]

NAMA_TABEL = "status_kuota"


def temukan_basis_data() -> str | None:
    """Cari berkas basis data. Env MDK_BASIS_DATA selalu menang."""
    dari_env = os.environ.get("MDK_BASIS_DATA", "").strip()
    if dari_env:
        return dari_env if os.path.exists(dari_env) else None

    for pola in POLA_BASIS_DATA:
        cocok = sorted(glob.glob(pola))
        if cocok:
            return cocok[0]
    return None


def _sambung(jalur: str) -> sqlite3.Connection:
    conn = sqlite3.connect(jalur, timeout=30)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {NAMA_TABEL} (
            kunci   TEXT PRIMARY KEY,
            waktu   TEXT NOT NULL,
            catatan TEXT
        )
        """
    )
    conn.commit()
    return conn


def _reset_berikutnya(sesudah: datetime) -> datetime:
    """Batas reset kuota pertama yang jatuh setelah waktu `sesudah`."""
    batas = sesudah.replace(
        hour=JAM_RESET_UTC, minute=0, second=0, microsecond=0
    )
    if batas <= sesudah:
        batas += timedelta(days=1)
    return batas


def catat_habis(catatan: str = "") -> bool:
    """Tandai bahwa kuota harian sudah habis. Kembalikan True bila tersimpan."""
    jalur = temukan_basis_data()
    if not jalur:
        print("  ! Penanda kuota tidak tersimpan: basis data tidak ditemukan")
        return False

    sekarang = datetime.now(timezone.utc)
    try:
        conn = _sambung(jalur)
        conn.execute(
            f"INSERT OR REPLACE INTO {NAMA_TABEL} (kunci, waktu, catatan) "
            "VALUES ('kuota_habis', ?, ?)",
            (sekarang.isoformat(), catatan[:500]),
        )
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f"  ! Penanda kuota gagal disimpan: {e}")
        return False

    pulih = _reset_berikutnya(sekarang)
    print(
        f"  # Penanda kuota dipasang. Tahap tulis ditunda sampai "
        f"{pulih.isoformat()} (UTC)."
    )
    return True


def boleh_menulis() -> tuple[bool, str]:
    """
    Periksa apakah tahap tulis boleh dijalankan.

    Kembalikan (True, alasan) bila boleh, (False, alasan) bila harus ditunda.
    Selalu memilih untuk MENGIZINKAN bila status tidak bisa dibaca — lebih baik
    membuang beberapa request daripada diam-diam berhenti menerbitkan.
    """
    jalur = temukan_basis_data()
    if not jalur:
        return True, "basis data tidak ditemukan, penanda dilewati"

    try:
        conn = _sambung(jalur)
        baris = conn.execute(
            f"SELECT waktu, catatan FROM {NAMA_TABEL} WHERE kunci = 'kuota_habis'"
        ).fetchone()
    except sqlite3.Error as e:
        return True, f"penanda tidak terbaca ({e}), dilanjutkan"

    if not baris:
        conn.close()
        return True, "tidak ada penanda kuota"

    try:
        dipasang = datetime.fromisoformat(baris[0])
    except (ValueError, TypeError):
        conn.close()
        return True, "waktu penanda tidak terbaca, dilanjutkan"

    if dipasang.tzinfo is None:
        dipasang = dipasang.replace(tzinfo=timezone.utc)

    sekarang = datetime.now(timezone.utc)
    pulih = _reset_berikutnya(dipasang)

    if sekarang >= pulih:
        # Jendela reset sudah lewat: bersihkan penanda dan izinkan.
        try:
            conn.execute(
                f"DELETE FROM {NAMA_TABEL} WHERE kunci = 'kuota_habis'"
            )
            conn.commit()
        except sqlite3.Error:
            pass
        conn.close()
        return True, f"kuota sudah reset pada {pulih.isoformat()}"

    conn.close()
    sisa = pulih - sekarang
    jam = int(sisa.total_seconds() // 3600)
    menit = int((sisa.total_seconds() % 3600) // 60)
    return False, (
        f"kuota habis sejak {dipasang.isoformat()}; "
        f"perkiraan pulih dalam {jam}j {menit}m"
    )


def hapus_penanda() -> bool:
    """Bersihkan penanda secara manual (untuk override dari workflow_dispatch)."""
    jalur = temukan_basis_data()
    if not jalur:
        return False
    try:
        conn = _sambung(jalur)
        conn.execute(f"DELETE FROM {NAMA_TABEL} WHERE kunci = 'kuota_habis'")
        conn.commit()
        conn.close()
        print("  # Penanda kuota dihapus.")
        return True
    except sqlite3.Error as e:
        print(f"  ! Gagal menghapus penanda: {e}")
        return False


def _tulis_output(nilai: bool) -> None:
    berkas = os.environ.get("GITHUB_OUTPUT")
    if not berkas:
        return
    try:
        with open(berkas, "a", encoding="utf-8") as f:
            f.write(f"boleh={'true' if nilai else 'false'}\n")
    except OSError:
        pass


def main(argv: list[str]) -> int:
    perintah = argv[1] if len(argv) > 1 else "periksa"

    if perintah == "hapus":
        hapus_penanda()
        return 0

    if perintah == "tandai":
        catat_habis("ditandai manual")
        return 0

    boleh, alasan = boleh_menulis()
    print(f"boleh={'true' if boleh else 'false'} · {alasan}")
    _tulis_output(boleh)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
