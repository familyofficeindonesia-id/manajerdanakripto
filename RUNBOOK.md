# RUNBOOK — Urutan Menyiapkan dan Menjalankan ManajerDanaKripto.com

Panduan berurutan dari nol hingga situs tayang dan radar berjalan otomatis.
Ikuti nomor dari 1 sampai 20. Nomor 1–14 wajib; 15–20 untuk operasional harian.

**Jalan pintas.** Nomor 1–9 dapat dijalankan sekaligus dengan satu perintah:

```bash
./mulai.sh
```

Selebihnya tetap perlu dijalankan manual karena memerlukan keputusan Anda.

---

## Ringkasan seluruh berkas

| # | Berkas | Tindakan | Wajib |
|---|---|---|---|
| 1 | — | Pasang Python 3.11+ | Ya |
| 2 | `manajerdanakripto-source.zip` | Ekstrak | Ya |
| 3 | `requirements.txt` | `pip install -r` | Ya |
| 4 | `.env.example` → `.env` | Salin dan isi | Ya |
| 5 | `config/settings.yaml` | Sunting identitas situs | Ya |
| 6 | `config/entities.yaml` | Verifikasi 64 tokoh | Ya |
| 7 | `config/organisasi.yaml` | Verifikasi 63 domain | Ya |
| 8 | `mulai.sh` | Jalankan persiapan | Disarankan |
| 9 | `scripts/uji_radar_lokal.py` | Uji sistem | Disarankan |
| 10 | `scripts/seed_demo.py` | Bangun pratinjau contoh | Disarankan |
| 11 | `python -m mdk radar bangun` | Bangun 489 sumber | Ya |
| 12 | `python -m mdk radar temukan` | Temukan umpan resmi | Ya |
| 13 | `python -m mdk radar periksa` | Uji seluruh URL | Ya |
| 14 | `python -m mdk radar pantau` | Putaran pemantauan pertama | Ya |
| 15 | `python -m mdk tulis --batas 3` | Uji penulisan artikel | Ya |
| 16 | `python -m mdk bangun` | Bangun situs produksi | Ya |
| 17 | `dist/` | Unggah ke hosting | Ya |
| 18 | `deploy/mdk-radar.service` **atau** `deploy/crontab.contoh` **atau** `.github/workflows/` | Otomatisasi | Ya |
| 19 | `scripts/buat_og.py` | Ganti gambar Open Graph | Opsional |
| 20 | `scripts/bangun_pratinjau.py` | Berkas pratinjau untuk dibagikan | Opsional |

---

# BAGIAN A — PEMASANGAN

## 1. Pasang Python 3.11 atau lebih baru

```bash
python3 --version          # harus 3.11 ke atas
```

Ubuntu/Debian:
```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip
```

macOS:
```bash
brew install python@3.12
```

Windows: unduh dari python.org, centang **Add Python to PATH** saat memasang.

---

## 2. Ekstrak proyek

```bash
unzip manajerdanakripto-source.zip
cd manajerdanakripto
ls        # harus terlihat: config/ src/ templates/ static/ scripts/ deploy/
```

---

## 3. `requirements.txt` — pasang dependensi

```bash
python3 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Tujuh paket akan terpasang: feedparser, Jinja2, PyYAML, python-dateutil,
rapidfuzz, requests, Pillow.

> Setiap membuka terminal baru, jalankan lagi `source .venv/bin/activate`.

---

# BAGIAN B — KONFIGURASI

## 4. `.env` — kunci API dan kredensial notifikasi

```bash
cp .env.example .env
nano .env
```

**Wajib diisi:**
```
ANTHROPIC_API_KEY=sk-ant-...        # dari console.anthropic.com/settings/keys
```

**Disarankan** (agar Anda menerima peringatan berita baru di ponsel):
```
TELEGRAM_BOT_TOKEN=...              # buat bot lewat @BotFather
TELEGRAM_CHAT_ID=...                # dari api.telegram.org/bot<TOKEN>/getUpdates
```

Kanal lain (webhook, surel, WhatsApp) opsional — lihat komentar di dalam berkas.

> Berkas `.env` sudah tercantum di `.gitignore`. Jangan pernah mengomitnya.

---

## 5. `config/settings.yaml` — identitas situs

Sunting empat hal berikut:

```yaml
situs:
  base_url: "https://manajerdanakripto.com"     # domain Anda yang sebenarnya
  email_redaksi: "redaksi@manajerdanakripto.com"
  media_sosial:
    x: "manajerdanakripto"
    telegram: "manajerdanakripto"
build:
  google_analytics_id: ""                        # isi bila memakai GA4
```

Setelah radar berjalan beberapa hari, kembali ke berkas ini untuk menyetel tiga
ambang skor pada blok `radar` sesuai volume berita yang nyaman bagi Anda.

---

## 6. `config/entities.yaml` — verifikasi 64 tokoh

**Ini langkah paling penting sebelum tayang ke publik.**

Seluruh entri saat ini bernilai `terverifikasi: false`. Jabatan eksekutif
berubah cukup sering, dan sebagian biografi disusun dari pengetahuan umum yang
perlu diperiksa ulang. Periksa tiga kolom untuk setiap tokoh:

```yaml
- slug: michael-saylor
  jabatan: Ketua Eksekutif        # ← periksa jabatan terkini
  organisasi: Strategy            # ← periksa afiliasi terkini
  x: saylor                       # ← periksa handle X
  bio: "..."                      # ← periksa isi biografi
  terverifikasi: false            # ← ubah menjadi true setelah diperiksa
```

Setelah diverifikasi, catatan "menunggu verifikasi redaksi" akan hilang dari
halaman profil.

---

## 7. `config/organisasi.yaml` — verifikasi 63 domain perusahaan

Kolom `situs_web` berisi dugaan terbaik dan perlu dikonfirmasi. Langkah 12
akan menguji setiap domain secara otomatis dan melaporkan mana yang gagal;
perbaiki yang gagal secara manual lalu jalankan ulang.

Perhatikan juga kolom `generik`. Bernilai `true` untuk nama yang terlalu umum
(Strategy, Galaxy, Gemini, Placeholder, Maelstrom) sehingga kueri pencariannya
selalu diberi pembatas topik. Tambahkan `generik: true` bila Anda menemukan
organisasi lain yang mengembalikan hasil melenceng.

---

# BAGIAN C — PERSIAPAN OTOMATIS

## 8. `mulai.sh` — persiapan sekali jalan

```bash
chmod +x mulai.sh
./mulai.sh
```

Skrip ini mengulang langkah 1–7 secara otomatis dan menambahkan langkah 9–11.
Aman dijalankan berulang kali; berkas `.env` yang sudah ada tidak akan ditimpa.

Pilihan tambahan:
```bash
./mulai.sh --tanpa-venv     # pakai Python sistem
./mulai.sh --tanpa-demo     # lewati pemuatan artikel contoh
```

**Bila Anda menjalankan `mulai.sh`, lanjutkan langsung ke langkah 12.**

---

## 9. `scripts/uji_radar_lokal.py` — uji sistem

```bash
export PYTHONPATH=src
python scripts/uji_radar_lokal.py
```

Sepuluh uji ujung-ke-ujung terhadap server RSS tiruan lokal. Tidak menyentuh
internet dan tidak menghabiskan kuota API. Seluruhnya harus lulus sebelum
lanjut.

---

## 10. `scripts/seed_demo.py` — lihat tampilan situs

```bash
python scripts/seed_demo.py --bangun
python -m mdk sajikan
```

Buka `http://localhost:8000`. Isi halaman adalah artikel contoh bertanda
"MODE DEMO" — bukan berita nyata. Hapus dengan `python scripts/seed_demo.py --bersihkan`
setelah berita sungguhan masuk.

---

# BAGIAN D — MENYALAKAN RADAR

## 11. Bangun daftar sumber

```bash
python -m mdk radar bangun
```

Menghasilkan `config/watchlist.yaml` berisi **489 sumber** untuk 64 tokoh dan
63 organisasi.

---

## 12. Temukan umpan RSS resmi perusahaan

```bash
python -m mdk radar temukan
```

Membuka situs resmi tiap perusahaan, membaca deklarasi umpannya, lalu
memvalidasi setiap kandidat. Hasilnya ditulis balik ke `config/organisasi.yaml`.
Perusahaan tanpa umpan resmi tetap terpantau lewat mesin berita.

Setelah selesai, jalankan ulang `python -m mdk radar bangun` agar umpan yang
baru ditemukan masuk ke watchlist.

---

## 13. Uji seluruh URL sumber

```bash
python -m mdk radar periksa --nonaktifkan-mati
```

Menguji setiap URL dan menonaktifkan yang tidak merespons. Jalankan ulang
sebulan sekali; sudah dijadwalkan dalam contoh crontab.

---

## 14. Putaran pemantauan pertama

```bash
python -m mdk radar pantau
```

Lihat berita apa yang tertangkap. Bila terlalu banyak berita tidak relevan,
naikkan `radar.skor_minimum` di `config/settings.yaml`. Bila terlalu sedikit,
turunkan.

---

# BAGIAN E — MENERBITKAN

## 15. Uji penulisan artikel (mulai kecil)

```bash
python -m mdk radar teruskan          # dorong temuan ke antrean
python -m mdk tulis --batas 3         # tulis tiga artikel saja
```

**Baca ketiga hasilnya secara manual** sebelum menaikkan batas. Periksa:
akurasi fakta, kewajaran Bahasa Indonesia, relevansi blok Konteks Indonesia,
dan ketepatan atribusi sumber.

Bila hasilnya memuaskan, naikkan bertahap: `--batas 10`, lalu `--batas 25`.

---

## 16. Bangun situs produksi

```bash
python scripts/seed_demo.py --bersihkan     # hapus artikel contoh
python -m mdk bangun
python -m mdk sajikan                       # tinjau di localhost:8000
```

---

## 17. Unggah folder `dist/`

Situs berupa berkas statis murni. Tidak memerlukan runtime apa pun di sisi
peladen.

**Pilihan A — GitHub Pages** (gratis, otomatis):
1. Unggah repositori ke GitHub
2. **Settings → Secrets and variables → Actions** → tambahkan `ANTHROPIC_API_KEY`
3. **Settings → Pages** → *Source* = **GitHub Actions**
4. Alur kerja `.github/workflows/terbit.yml` akan menerbitkan otomatis

**Pilihan B — Cloudflare Pages / Netlify / Vercel:**
Hubungkan repositori, setel folder keluaran ke `dist`.

**Pilihan C — Peladen sendiri (Nginx):**
```bash
rsync -avz dist/ pengguna@peladen:/var/www/manajerdanakripto/
```

---

## 18. Otomatisasi — pilih SATU

**Pilihan A — systemd** (paling andal, untuk peladen sendiri):
```bash
sudo cp deploy/mdk-radar.service /etc/systemd/system/
sudo nano /etc/systemd/system/mdk-radar.service    # sesuaikan User & jalur
sudo systemctl daemon-reload
sudo systemctl enable --now mdk-radar
journalctl -u mdk-radar -f                          # pantau log
```

**Pilihan B — cron:**
```bash
sudo timedatectl set-timezone Asia/Jakarta
crontab -e          # tempelkan isi deploy/crontab.contoh, sesuaikan jalur
```

**Pilihan C — GitHub Actions** (paling mudah, penjadwalan kurang rapat):
Sudah tersedia di `.github/workflows/radar.yml` dan `terbit.yml`. Tambahkan
secret `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, dan `TELEGRAM_CHAT_ID`.

---

# BAGIAN F — OPSIONAL

## 19. `scripts/buat_og.py` — gambar pratinjau media sosial

```bash
python scripts/buat_og.py
```

Jalankan ulang setelah mengubah identitas visual.

---

## 20. `scripts/bangun_pratinjau.py` — berkas pratinjau untuk dibagikan

```bash
python scripts/bangun_pratinjau.py
```

Menggabungkan seluruh situs menjadi satu berkas HTML mandiri sekitar 680 KB.
Cocok dilampirkan ke surel atau WhatsApp saat presentasi ke calon mitra, tanpa
perlu menyalakan peladen.

---

# Operasional harian setelah semuanya berjalan

| Perintah | Kapan |
|---|---|
| `make radar-pantau` | Otomatis tiap 20 menit |
| `make tulis` | Otomatis tiga kali sehari |
| `make bangun` | Otomatis tiap jam |
| `make radar-dasbor` | Kapan pun ingin melihat kondisi sistem |
| `make radar-periksa` | Sebulan sekali |
| `python -m mdk radar status` | Pemeriksaan cepat di terminal |

---

# Bila terjadi masalah

| Gejala | Penyebab umum | Tindakan |
|---|---|---|
| `ModuleNotFoundError: mdk` | `PYTHONPATH` belum disetel | `export PYTHONPATH=src`, atau pakai `make` |
| `ANTHROPIC_API_KEY belum disetel` | `.env` belum dimuat | `set -a && . ./.env && set +a` |
| `radar pantau` tidak menemukan apa pun | Ambang terlalu tinggi | Turunkan `radar.skor_minimum` |
| Banyak berita tidak relevan | Ambang terlalu rendah | Naikkan `radar.skor_minimum`, tambahkan `generik: true` |
| Banyak sumber mati | Umpan berubah | `python -m mdk radar periksa --semua` |
| Artikel gagal ditulis | Metadata terlalu tipis | Normal; periksa `python -m mdk status` |
| Biaya API terlalu tinggi | Terlalu banyak artikel | Turunkan `--batas`, naikkan `skor_minimum_terjemah` |

---

# Daftar periksa sebelum tayang ke publik

- [ ] Seluruh 64 tokoh diverifikasi, `terverifikasi: true`
- [ ] Domain perusahaan yang gagal pada langkah 12 sudah diperbaiki
- [ ] `base_url` dan alamat surel redaksi sudah benar
- [ ] Teks sanggahan sudah ditinjau penasihat hukum
- [ ] Minimal sepuluh artikel dibaca manual dan dinilai layak
- [ ] Satu kanal notifikasi sudah diuji
- [ ] Situs terdaftar di Google Search Console, `sitemap-berita.xml` diajukan
- [ ] Kanal penerimaan hak jawab sesuai halaman `/pedoman/` sudah siap
- [ ] Artikel contoh sudah dihapus (`seed_demo.py --bersihkan`)
