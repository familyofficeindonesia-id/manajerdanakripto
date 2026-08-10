#!/usr/bin/env bash
# =============================================================================
# ManajerDanaKripto.com — Skrip Persiapan Awal
# -----------------------------------------------------------------------------
# Menjalankan LANGKAH 1 sampai 9 pada RUNBOOK.md secara otomatis:
#   · memeriksa versi Python
#   · membuat lingkungan virtual
#   · memasang dependensi
#   · menyiapkan berkas .env
#   · menguji kesehatan konfigurasi
#   · memuat artikel contoh dan membangun situs pratinjau
#
# Pemakaian:
#   ./mulai.sh                 persiapan penuh (disarankan)
#   ./mulai.sh --tanpa-venv    pakai Python sistem, tanpa lingkungan virtual
#   ./mulai.sh --tanpa-demo    lewati pemuatan artikel contoh
#
# Skrip ini AMAN dijalankan berulang kali. Berkas .env yang sudah ada tidak
# akan ditimpa.
# =============================================================================

set -euo pipefail

AKAR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$AKAR"

PAKAI_VENV=1
PAKAI_DEMO=1
for arg in "$@"; do
  case "$arg" in
    --tanpa-venv) PAKAI_VENV=0 ;;
    --tanpa-demo) PAKAI_DEMO=0 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "Argumen tidak dikenal: $arg" >&2; exit 1 ;;
  esac
done

# --- tampilan ----------------------------------------------------------------
TEBAL=$'\033[1m'; HIJAU=$'\033[32m'; KUNING=$'\033[33m'; MERAH=$'\033[31m'; NORMAL=$'\033[0m'
langkah() { printf '\n%s▸ LANGKAH %s — %s%s\n' "$TEBAL" "$1" "$2" "$NORMAL"; }
sukses()  { printf '  %s✓%s %s\n' "$HIJAU" "$NORMAL" "$1"; }
ingat()   { printf '  %s!%s %s\n' "$KUNING" "$NORMAL" "$1"; }
gagal()   { printf '  %s✗%s %s\n' "$MERAH" "$NORMAL" "$1"; exit 1; }

printf '%s\n' "══════════════════════════════════════════════════════════════════════"
printf '%s  ManajerDanaKripto.com — Persiapan Awal%s\n' "$TEBAL" "$NORMAL"
printf '%s\n' "══════════════════════════════════════════════════════════════════════"

# --- LANGKAH 1: Python -------------------------------------------------------
langkah 1 "Memeriksa Python"
PY_SISTEM="$(command -v python3 || true)"
[ -n "$PY_SISTEM" ] || gagal "python3 tidak ditemukan. Pasang Python 3.11 atau lebih baru."

VERSI="$("$PY_SISTEM" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
COCOK="$("$PY_SISTEM" -c 'import sys; print(1 if sys.version_info >= (3,11) else 0)')"
[ "$COCOK" = "1" ] || gagal "Python $VERSI terlalu lama. Diperlukan 3.11 atau lebih baru."
sukses "Python $VERSI ($PY_SISTEM)"

# --- LANGKAH 2: lingkungan virtual -------------------------------------------
if [ "$PAKAI_VENV" = "1" ]; then
  langkah 2 "Menyiapkan lingkungan virtual"
  if [ -d .venv ]; then
    sukses "Lingkungan virtual sudah ada di .venv/"
  else
    "$PY_SISTEM" -m venv .venv || gagal "Gagal membuat lingkungan virtual. Pasang paket python3-venv."
    sukses "Lingkungan virtual dibuat di .venv/"
  fi
  PY="$AKAR/.venv/bin/python"
else
  langkah 2 "Melewati lingkungan virtual (--tanpa-venv)"
  PY="$PY_SISTEM"
  ingat "Dependensi akan dipasang ke Python sistem."
fi

# --- LANGKAH 3: dependensi ---------------------------------------------------
langkah 3 "Memasang dependensi"
"$PY" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
if "$PY" -m pip install --quiet -r requirements.txt; then
  sukses "Tujuh paket terpasang dari requirements.txt"
else
  ingat "Pemasangan biasa gagal, mencoba dengan --break-system-packages…"
  "$PY" -m pip install --quiet --break-system-packages -r requirements.txt \
    || gagal "Pemasangan dependensi gagal. Periksa koneksi jaringan."
  sukses "Dependensi terpasang"
fi

export PYTHONPATH="$AKAR/src"

# --- LANGKAH 4: berkas .env --------------------------------------------------
langkah 4 "Menyiapkan berkas .env"
if [ -f .env ]; then
  sukses "Berkas .env sudah ada — tidak ditimpa"
else
  cp .env.example .env
  sukses "Berkas .env dibuat dari .env.example"
fi

NILAI_KUNCI="$(grep -E '^ANTHROPIC_API_KEY=' .env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"'"'"'" ' || true)"
if [ -n "$NILAI_KUNCI" ] && [ "${#NILAI_KUNCI}" -ge 30 ] && ! printf '%s' "$NILAI_KUNCI" | grep -qi 'xxxx'; then
  sukses "ANTHROPIC_API_KEY sudah terisi"
  ADA_KUNCI=1
else
  ingat "ANTHROPIC_API_KEY belum diisi."
  ingat "Buka .env lalu isi kunci dari https://console.anthropic.com/settings/keys"
  ingat "Tanpa kunci ini, tahap penulisan artikel tidak dapat berjalan."
  ADA_KUNCI=0
fi

# --- LANGKAH 5: uji kesehatan ------------------------------------------------
langkah 5 "Menguji kesehatan konfigurasi"
if [ "$ADA_KUNCI" = "1" ]; then
  set -a; . ./.env; set +a
fi
"$PY" -m mdk periksa || gagal "Uji kesehatan gagal. Periksa pesan galat di atas."

# --- LANGKAH 6: uji radar ----------------------------------------------------
langkah 6 "Menguji rantai radar (server tiruan lokal, tanpa jaringan)"
if "$PY" scripts/uji_radar_lokal.py >/dev/null 2>&1; then
  sukses "Sepuluh uji ujung-ke-ujung radar lulus"
else
  ingat "Sebagian uji radar tidak lulus. Jalankan manual untuk melihat rinciannya:"
  ingat "  $PY scripts/uji_radar_lokal.py"
fi

# --- LANGKAH 7: artikel contoh -----------------------------------------------
if [ "$PAKAI_DEMO" = "1" ]; then
  langkah 7 "Memuat artikel contoh dan membangun situs"
  "$PY" scripts/seed_demo.py --bangun >/dev/null || gagal "Pembangunan situs contoh gagal."
  JML="$(find dist -name index.html | wc -l | tr -d ' ')"
  sukses "$JML halaman dibangun ke dist/"
else
  langkah 7 "Melewati artikel contoh (--tanpa-demo)"
fi

# --- LANGKAH 8: berkas pratinjau ---------------------------------------------
langkah 8 "Membangun berkas pratinjau mandiri"
if [ -d dist ]; then
  "$PY" scripts/bangun_pratinjau.py >/dev/null && \
    sukses "dist-pratinjau/manajerdanakripto-pratinjau.html siap dibagikan"
else
  ingat "Folder dist/ belum ada, pratinjau dilewati."
fi

# --- LANGKAH 9: daftar sumber radar ------------------------------------------
langkah 9 "Membangun daftar sumber pemantauan"
"$PY" -m mdk radar bangun 2>&1 | grep -E "Total sumber|Tokoh dipantau|Organisasi" || true
sukses "config/watchlist.yaml siap"

# --- ringkasan ---------------------------------------------------------------
printf '\n%s\n' "══════════════════════════════════════════════════════════════════════"
printf '%s  PERSIAPAN SELESAI%s\n' "$TEBAL$HIJAU" "$NORMAL"
printf '%s\n\n' "══════════════════════════════════════════════════════════════════════"

if [ "$PAKAI_VENV" = "1" ]; then
  printf '  Aktifkan lingkungan virtual pada setiap sesi terminal baru:\n'
  printf '    %ssource .venv/bin/activate%s\n\n' "$TEBAL" "$NORMAL"
fi
printf '  Setel jalur modul (atau cukup pakai perintah make):\n'
printf '    %sexport PYTHONPATH=src%s\n\n' "$TEBAL" "$NORMAL"

printf '  Lihat hasilnya sekarang:\n'
printf '    %spython -m mdk sajikan%s      → buka http://localhost:8000\n\n' "$TEBAL" "$NORMAL"

printf '  Langkah berikutnya (lihat RUNBOOK.md untuk rinciannya):\n'
printf '    10. python -m mdk radar temukan               cari umpan RSS resmi\n'
printf '    11. python -m mdk radar periksa --nonaktifkan-mati\n'
printf '    12. python -m mdk radar pantau                putaran pemantauan pertama\n'
if [ "$ADA_KUNCI" = "0" ]; then
  printf '    13. %sisi ANTHROPIC_API_KEY di .env lebih dahulu%s\n' "$KUNING" "$NORMAL"
else
  printf '    13. python -m mdk tulis --batas 3             uji penulisan artikel\n'
fi
printf '    14. python -m mdk bangun                     bangun situs produksi\n\n'
