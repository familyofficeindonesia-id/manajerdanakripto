# ManajerDanaKripto.com

Portal berita berbahasa Indonesia yang memantau keputusan, pernyataan, dan posisi
**64 manajer dana serta investor institusional aset kripto global**, lalu
menyajikannya kembali dalam Bahasa Indonesia formal disertai **Konteks Indonesia**
pada setiap artikel.

Sistem ini terdiri atas dua bagian yang berjalan dalam satu perintah:

1. **Pipeline berita** — mengambil umpan RSS, menyaring relevansi, membuang
   duplikat, lalu menulis ulang setiap berita menjadi artikel orisinal Bahasa
   Indonesia menggunakan Anthropic Messages API.
2. **Pembangkit situs statis** — merender basis data artikel menjadi situs HTML
   siap unggah, lengkap dengan RSS, sitemap berita, indeks pencarian, dan data
   terstruktur `schema.org`.

Keluarannya berupa berkas statis murni, sehingga dapat dihosting gratis di
GitHub Pages, Cloudflare Pages, Netlify, atau server Nginx mana pun.

---

## Daftar Isi

- [Mulai cepat](#mulai-cepat)
- [Radar: pemantauan sumber berita](#radar-pemantauan-sumber-berita)
- [Arsitektur](#arsitektur)
- [Struktur berkas](#struktur-berkas)
- [Perintah](#perintah)
- [Konfigurasi](#konfigurasi)
- [Fitur situs](#fitur-situs)
- [Kepatuhan hak cipta](#kepatuhan-hak-cipta)
- [Penerbitan otomatis](#penerbitan-otomatis)
- [Penyesuaian umum](#penyesuaian-umum)
- [Daftar periksa sebelum produksi](#daftar-periksa-sebelum-produksi)
- [Biaya operasional](#biaya-operasional)

---

## Mulai cepat

Persyaratan: Python 3.11 atau lebih baru.

> **Baru pertama kali menyiapkan?** Ikuti [`RUNBOOK.md`](RUNBOOK.md) — panduan
> bernomor 1 sampai 20, dari pemasangan hingga otomatisasi. Nomor 1–9 dapat
> dijalankan sekaligus dengan `./mulai.sh`.

```bash
# 1. Pasang dependensi
pip install -r requirements.txt

# 2. Lihat situs dengan artikel contoh (tanpa perlu kunci API)
python scripts/seed_demo.py --bangun
python -m mdk sajikan          # buka http://localhost:8000

# 3. Siapkan kunci API untuk berita sungguhan
cp .env.example .env           # lalu isi ANTHROPIC_API_KEY
export ANTHROPIC_API_KEY="sk-ant-..."

# 4. Jalankan pipeline penuh
python -m mdk jalankan
```

> Perintah `python -m mdk` memerlukan `PYTHONPATH=src`. Bila memakai `make`,
> variabel tersebut sudah disetel otomatis — cukup jalankan `make demo`,
> `make jalankan`, atau `make sajikan`.

---

## Radar: pemantauan sumber berita

Radar adalah lapisan yang menjawab pertanyaan "dari mana berita tentang mereka
datang, dan bagaimana saya tahu begitu ada yang baru". Ia memantau **489 sumber**
untuk **64 tokoh dan 63 organisasi**, mendeteksi berita baru, mengelompokkan
liputan atas peristiwa yang sama, mengirim notifikasi, lalu mendorong hasilnya
ke pipeline penerjemahan.

### Mulai cepat

```bash
python -m mdk radar bangun      # bangun daftar 489 sumber dari registri entitas
python -m mdk radar temukan     # temukan umpan RSS resmi tiap perusahaan
python -m mdk radar periksa     # uji setiap URL, nonaktifkan yang mati
python -m mdk radar pantau      # putaran pertama — lihat apa yang tertangkap
python -m mdk radar jaga --interval 20 --teruskan    # jalankan terus-menerus
```

### Tujuh jenis sumber

| Jenis | Cakupan | Catatan |
|---|---|---|
| `google_news_en` | Ribuan media global | Dua kueri per entitas: frasa persis dan versi dipertajam topik |
| `google_news_id` | Media Indonesia | Menangkap saduran lokal, kerap lebih dahulu terbit daripada terjemahan kita |
| `bing_news` | Indeks berbeda dari Google | Sering memuat sumber yang tidak terjaring Google |
| `situs_resmi` | Blog, riset, dan ruang berita perusahaan | **Ditemukan otomatis**, bukan ditebak — lihat di bawah |
| `sec_edgar` | Pengajuan 13F-HR dan 8-K | Pengungkapan posisi resmi, nilai berita tertinggi |
| `youtube` | Kanal wawancara dan podcast | Aktif setelah ID kanal diisi di `settings.yaml` |
| `reddit` | Pembicaraan pasar | Nonaktif secara bawaan; nyalakan dengan `radar bangun --reddit` |

### Umpan resmi ditemukan, bukan ditebak

Menebak URL umpan menghasilkan daftar yang sebagian besar mati. Perintah
`radar temukan` justru membuka situs resmi tiap perusahaan, membaca deklarasi
`<link rel="alternate" type="application/rss+xml">` di dalamnya, lalu
memvalidasi setiap kandidat dengan benar-benar menguraikannya. Hanya URL yang
mengembalikan entri sah yang disimpan, dan hasilnya ditulis balik ke
`config/organisasi.yaml`.

Bila sebuah situs tidak mengumumkan umpannya, sistem menguji enam belas jalur
lazim (WordPress, Ghost, Webflow, Hugo, Substack). Perusahaan yang tetap tidak
punya umpan resmi tidak hilang dari pemantauan — mereka tetap terpantau lewat
mesin berita.

### Pengelompokan peristiwa

Satu peristiwa yang diliput sepuluh media akan menghasilkan sepuluh notifikasi
bila tidak ditangani. Radar mengelompokkan laporan berdasarkan kemiripan judul
(ambang 80 dari 100), memilih satu tautan utama berdasarkan bobot kepercayaan
sumber, lalu mengirim **satu** notifikasi bertuliskan "juga diberitakan 9 media
lain". Klaster juga dibandingkan dengan 72 jam terakhir, sehingga liputan susulan
atas peristiwa lama tidak memicu peringatan baru.

### Kanal notifikasi

Aktifkan lewat `radar.kanal` di `config/settings.yaml`. Kredensial dibaca dari
`.env`, tidak pernah dari berkas konfigurasi.

| Kanal | Kegunaan | Variabel lingkungan |
|---|---|---|
| `konsol` | Keluaran terminal | — |
| `berkas` | Arsip JSONL + CSV siap buka di Excel | — |
| `rss` | Umpan pribadi untuk Feedly/Inoreader | — |
| `telegram` | Peringatan langsung ke ponsel | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |
| `webhook` | Slack, Discord, n8n, Zapier, Make | `RADAR_WEBHOOK_URL`, `RADAR_WEBHOOK_GAYA` |
| `surel` | Ringkasan HTML berkala | `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `RADAR_EMAIL_KE` |
| `whatsapp` | WhatsApp Business API | `WHATSAPP_API_URL`, `WHATSAPP_TOKEN`, `WHATSAPP_TUJUAN` |

### Tiga ambang skor

Skor menggabungkan kekuatan penyebutan entitas, kesesuaian tema, dan bobot
kepercayaan sumber. Tiga ambang di `settings.yaml` mengatur alurnya:

```
skor_minimum: 35            → item dicatat ke arsip radar
skor_minimum_notifikasi: 45 → klaster dikirim ke kanal notifikasi
skor_minimum_terjemah: 55   → temuan didorong ke antrean penerjemahan
```

Naikkan `skor_minimum_terjemah` bila biaya API terlalu tinggi; turunkan bila
terlalu banyak berita relevan yang terlewat.

### Efisiensi penjajakan

- **Permintaan bersyarat.** ETag dan `Last-Modified` disimpan per sumber. Umpan
  tanpa perubahan menjawab 304 tanpa mengirim isi.
- **Prioritas jajak.** Sumber primer dijajaki tiap putaran; sumber sekunder
  setiap dua putaran; sumber tersier setiap tiga putaran.
- **Batas laju per domain.** Jeda minimum antar permintaan ke domain yang sama,
  dengan urutan sumber diacak agar beban tersebar.
- **Nonaktif otomatis.** Sumber yang gagal enam kali beruntun dinonaktifkan dan
  dilaporkan di dasbor. Hidupkan kembali dengan `radar periksa --semua`.
- **Pemangkasan arsip.** Catatan lebih tua dari 120 hari dibuang otomatis.

### Menjalankan terus-menerus

Tiga pilihan, dari yang paling andal:

1. **systemd** (disarankan untuk server sendiri) —
   `deploy/mdk-radar.service`. Pasang, `systemctl enable --now mdk-radar`,
   pantau dengan `journalctl -u mdk-radar -f`.
2. **cron** — `deploy/crontab.contoh` memuat jadwal lengkap: pemantauan tiap
   20 menit, penerjemahan tiga kali sehari, pembangunan situs tiap jam.
3. **GitHub Actions** — `.github/workflows/radar.yml` berjalan tiap 30 menit.
   Paling mudah disiapkan, tetapi penjadwalannya dapat tertunda saat beban tinggi.

### Alur lengkap hingga tayang

```
radar jaga  →  temuan baru  →  notifikasi Telegram  →  antrean `mentah`
                                                              │
                                              mdk tulis  ◂────┘
                                                   │
                                          artikel Bahasa Indonesia
                                                   │
                                            mdk bangun → dist/
```

Dengan `--teruskan`, temuan berskor tinggi langsung masuk antrean, sehingga
Anda cukup menjalankan `mdk tulis` lalu `mdk bangun` untuk menayangkannya.

### Memantau kesehatan sistem

```bash
python -m mdk radar status              # ringkasan di terminal
python -m mdk radar dasbor              # dasbor HTML di data/radar/dasbor.html
python -m mdk radar daftar --csv sumber.csv    # ekspor seluruh sumber
python -m mdk radar daftar --entitas michael-saylor
```

### Pengujian

`python scripts/uji_radar_lokal.py` menjalankan sepuluh uji ujung-ke-ujung
terhadap server RSS tiruan lokal — tanpa menyentuh internet dan tanpa biaya API.
Yang diperiksa: deteksi item baru, pencegahan duplikat lintas putaran,
pengelompokan lima liputan menjadi satu klaster, penghematan lewat permintaan
bersyarat, penonaktifan sumber mati, penulisan notifikasi, pencegahan kirim
ganda, dan penerusan idempoten ke antrean terjemahan.


---

## Arsitektur

```
                    config/sources.yaml        config/entities.yaml
                            │                          │
                            ▼                          ▼
   ┌──────────────────────────────────────────────────────────────┐
   │  1. AMBIL          ingest.py                                 │
   │     · Umpan RSS umum (CoinDesk, The Block, Kontan, dll)      │
   │     · Kueri Google News per tokoh (dibangkitkan otomatis)     │
   │     · Skor relevansi = entitas + tema × bobot sumber          │
   └──────────────────────────────────────────────────────────────┘
                            │  metadata saja, bukan isi artikel
                            ▼
   ┌──────────────────────────────────────────────────────────────┐
   │  2. SARING         dedup.py + entities.py                     │
   │     · URL kanonik (buang parameter pelacakan)                 │
   │     · Kemiripan judul (rapidfuzz, ambang 82)                  │
   │     · Penandaan tokoh & organisasi                            │
   └──────────────────────────────────────────────────────────────┘
                            │
                            ▼
   ┌──────────────────────────────────────────────────────────────┐
   │  3. TULIS          rewrite.py → Anthropic Messages API        │
   │     · Artikel ORISINAL Bahasa Indonesia (bukan terjemahan)    │
   │     · Judul, dek, 3 poin kilat, 4-6 paragraf                  │
   │     · Rubrik, tag, sinyal posisi, Konteks Indonesia           │
   │     · Pagar hak cipta dipaksakan di sisi kode                 │
   └──────────────────────────────────────────────────────────────┘
                            │
                            ▼
              data/mdk.sqlite3  (mentah + artikel + jurnal)
                            │
                            ▼
   ┌──────────────────────────────────────────────────────────────┐
   │  4. BANGUN         build.py + feeds.py → dist/                │
   │     Beranda · Artikel · Rubrik · Tag · Profil tokoh ·         │
   │     Profil perusahaan · Pencarian · Glosarium · Halaman       │
   │     redaksi · RSS · sitemap.xml · sitemap-berita.xml ·        │
   │     robots.txt · indeks-cari.json                             │
   └──────────────────────────────────────────────────────────────┘
```

---

## Struktur berkas

```
manajerdanakripto/
├── config/
│   ├── settings.yaml           identitas situs, rubrik, editorial, radar
│   ├── sources.yaml            umpan RSS + template kueri per tokoh
│   ├── entities.yaml           64 tokoh, organisasi, alias, bio  ← inti sistem
│   ├── organisasi.yaml         63 perusahaan sebagai entitas pantau mandiri
│   └── watchlist.yaml          489 sumber (dibangkitkan, aman disunting)
├── content/
│   ├── glosarium.yaml          26 istilah investasi berbahasa Indonesia
│   └── halaman/                tentang, disclaimer, pedoman, kontak
├── src/mdk/
│   ├── config.py               pemuat konfigurasi
│   ├── models.py               Tokoh, ItemMentah, Artikel
│   ├── utils.py                slug, kanonikalisasi URL, format tanggal & rupiah
│   ├── store.py                lapisan SQLite
│   ├── entities.py             registri + mesin penandaan entitas
│   ├── ingest.py               pengambilan umpan RSS
│   ├── dedup.py                deduplikasi kemiripan judul
│   ├── rewrite.py              penulisan ulang berbasis Claude + pagar hak cipta
│   ├── pipeline.py             orkestrasi tiga tahap
│   ├── build.py                pembangkit situs statis
│   ├── feeds.py                RSS, sitemap, robots, indeks pencarian
│   ├── cli.py                  antarmuka baris perintah
│   └── radar/                  lapisan pemantauan sumber berita
│       ├── sumber.py           pembangun URL tujuh jenis sumber
│       ├── penemu.py           penemuan umpan RSS resmi otomatis
│       ├── pemantau.py         mesin jajak + pengelompokan peristiwa
│       ├── notifikasi.py       tujuh kanal pengiriman
│       ├── laporan.py          dasbor HTML
│       ├── simpan.py           tabel terlihat, kesehatan, klaster, notifikasi
│       └── cli.py              subperintah `mdk radar`
├── templates/                  12 templat Jinja2
├── static/                     CSS, JavaScript, logo, gambar Open Graph
├── scripts/
│   ├── seed_demo.py            artikel contoh untuk pratinjau
│   ├── buat_og.py              pembangkit gambar Open Graph
│   └── uji_radar_lokal.py      uji ujung-ke-ujung radar (server tiruan)
├── deploy/
│   ├── mdk-radar.service       unit systemd untuk radar berkelanjutan
│   └── crontab.contoh          jadwal cron lengkap
├── .github/workflows/
│   ├── terbit.yml              penerbitan terjadwal ke GitHub Pages
│   └── radar.yml               pemantauan tiap 30 menit
├── Makefile
└── requirements.txt
```

---

## Perintah

| Perintah | Keterangan |
|---|---|
| `python -m mdk periksa` | Uji kesehatan konfigurasi, templat, dan kunci API |
| `python -m mdk ambil` | Ambil umpan berita ke antrean (tanpa biaya API) |
| `python -m mdk tulis --batas 20` | Tulis ulang antrean menjadi artikel Bahasa Indonesia |
| `python -m mdk bangun` | Bangun situs statis ke `dist/` |
| `python -m mdk jalankan` | Pipeline penuh: ambil → tulis → bangun |
| `python -m mdk sajikan --port 8000` | Pratinjau lokal |
| `python -m mdk status` | Ringkasan isi basis data |
| `python -m mdk demo` | Muat artikel contoh lalu bangun pratinjau |
| `python -m mdk radar bangun` | Bangun daftar 489 sumber pemantauan |
| `python -m mdk radar temukan` | Temukan umpan RSS resmi tiap perusahaan |
| `python -m mdk radar periksa` | Uji setiap URL sumber, nonaktifkan yang mati |
| `python -m mdk radar pantau --teruskan` | Satu putaran pemantauan + dorong ke antrean |
| `python -m mdk radar jaga --interval 20` | Pemantauan berkelanjutan |
| `python -m mdk radar status` / `dasbor` | Ringkasan dan dasbor HTML |

Padanan `make`: `make periksa`, `make ambil`, `make tulis`, `make bangun`,
`make jalankan`, `make sajikan`, `make demo`, `make og`, `make bersih`,
`make radar-bangun`, `make radar-temukan`, `make radar-periksa`,
`make radar-pantau`, `make radar-jaga`, `make radar-dasbor`, `make radar-uji`.

---

## Konfigurasi

### `config/entities.yaml` — inti sistem

Setiap tokoh menghasilkan tiga hal sekaligus: kueri berita, aturan penandaan
artikel, dan halaman profil. Menambah tokoh baru cukup menambah satu blok:

```yaml
- slug: nama-tokoh
  nama: Nama Tokoh
  organisasi: Nama Perusahaan
  org_slug: nama-perusahaan
  jabatan: Direktur Utama
  kategori: manajer-aset        # treasury | manajer-aset | hedge-fund | ventura | makro | bursa
  negara: Amerika Serikat
  x: handle_tanpa_at
  alias: ["Nama Tokoh", "Nama Perusahaan"]   # hindari kata generik
  bio: "Ringkasan satu kalimat."
  terverifikasi: false
```

> **Penting.** Seluruh entri saat ini bernilai `terverifikasi: false`. Jabatan
> eksekutif berubah cukup sering, dan sebagian bio disusun dari pengetahuan umum
> yang perlu diperiksa ulang. Lakukan verifikasi manual terhadap jabatan,
> afiliasi, dan handle X sebelum menayangkan situs ke publik.

### `config/settings.yaml`

Mengatur identitas situs, delapan rubrik, ambang relevansi, model AI, dan
kebijakan editorial (batas kutipan, panjang artikel, teks sanggahan).

### `config/sources.yaml`

Berisi 13 umpan RSS umum — termasuk Kontan, Bisnis Indonesia, dan CNBC Indonesia
untuk konteks lokal — serta template kueri Google News yang secara otomatis
dibangkitkan untuk setiap alias tokoh. Dengan 64 tokoh × 2 alias × 2 template,
sistem memantau sekitar **270 sumber** per jalannya pipeline.

Bila kuota permintaan menjadi kendala, setel `mode_hemat: true` untuk membatasi
kueri pada nama lengkap saja.

---

## Fitur situs

**Untuk pembaca**

- Beranda dengan berita utama, rail sorotan, kisi terbaru, dan **Radar Manajer**
  (rekap sinyal per kategori tokoh dalam tujuh hari terakhir)
- **Pita Manajer** — papan berjalan di bawah masthead tempat "ticker"-nya adalah
  manusia, bukan koin. Setiap keping menampilkan nama, organisasi, dan sinyal
  posisi hasil pembacaan redaksi, sekaligus menjadi jalan pintas ke halaman profil
- **Konteks Indonesia** pada setiap artikel — modul bergaris kuningan yang
  menjelaskan relevansi berita bagi investor domestik
- Direktori 64 tokoh dan 58 organisasi, dapat disaring per kategori
- Pencarian sisi klien tanpa server, dengan penyaring rubrik
- Glosarium 26 istilah investasi dalam Bahasa Indonesia
- Berbagi ke WhatsApp, Telegram, X, dan LinkedIn — dua yang pertama diutamakan
  karena dominan di Indonesia
- Papan harga BTC dan kurs USD/IDR pada masthead
- Mode terang dan gelap, mengikuti preferensi sistem
- Responsif hingga lebar 320 piksel, fokus papan ketik terlihat, animasi berhenti
  saat pengguna mengaktifkan pengurangan gerak

**Untuk mesin pencari**

- Data terstruktur `NewsArticle`, `BreadcrumbList`, `ProfilePage`, `Organization`,
  `DefinedTermSet`, dan `NewsMediaOrganization`
- `sitemap-berita.xml` sesuai spesifikasi Google News (jendela dua hari)
- URL bersih tanpa akhiran `.html`, kanonik, Open Graph, dan kartu X
- RSS 2.0 berisi ringkasan, bukan isi penuh

---

## Kepatuhan hak cipta

Ini bagian yang paling menentukan keberlangsungan sebuah portal agregasi.
Sistem memaksakan aturan berikut **di sisi kode**, bukan sekadar melalui
instruksi kepada model:

| Aturan | Penerapan |
|---|---|
| Tidak ada penerbitan ulang | Model diminta menulis laporan baru, bukan menerjemahkan |
| Kutipan maksimum 14 kata | `_terapkan_pagar_kutipan()` membuang kutipan yang melebihi batas |
| Satu kutipan per artikel | Tanda kutip panjang di dalam paragraf diturunkan menjadi parafrase |
| Panjang artikel dibatasi | `_terapkan_pagar_panjang()` memangkas pada 480 kata |
| Atribusi wajib | Blok sumber dengan tautan `rel="nofollow"` dirender pada setiap artikel |
| Hanya metadata disimpan | Basis data tidak pernah memuat teks penuh artikel sumber |
| Larangan nasihat investasi | Dinyatakan dalam prompt sistem dan diulang pada sanggahan setiap artikel |

Ambang tersebut dapat diperketat melalui blok `editorial` pada
`config/settings.yaml`. Menaikkannya tidak disarankan.

---

## Penerbitan otomatis

Berkas `.github/workflows/terbit.yml` menjalankan pipeline tiga kali sehari
(06.00, 12.00, dan 18.00 WIB) lalu menerbitkan hasilnya ke GitHub Pages.

Langkah penyiapan:

1. Unggah repositori ke GitHub.
2. Buka **Settings → Secrets and variables → Actions**, tambahkan secret
   `ANTHROPIC_API_KEY`.
3. Buka **Settings → Pages**, setel *Source* menjadi **GitHub Actions**.
4. Perbarui `base_url` pada `config/settings.yaml` sesuai domain Anda.
5. Jalankan alur kerja secara manual melalui tab **Actions** untuk uji pertama.

Basis data artikel disimpan antarjalannya menggunakan cache Actions, sehingga
arsip artikel terus bertambah tanpa memerlukan basis data eksternal.

Alternatif hosting: unggah isi folder `dist/` ke Cloudflare Pages, Netlify,
Vercel, atau server Nginx. Tidak diperlukan runtime apa pun di sisi server.

---

## Penyesuaian umum

**Mengganti warna dan tipografi.** Seluruh token berada pada blok `:root`
di `static/css/style.css`. Palet saat ini: tinta navy `#0E1626`, kertas dingin
`#EEF1F6`, hijau rupiah `#0B6E4F`, dan kuningan `#B98A22` yang khusus dipakai
untuk modul Konteks Indonesia dan rubrik syariah.

**Menambah rubrik.** Tambahkan entri pada `rubrik` di `config/settings.yaml`.
Navigasi, halaman rubrik, penyaring pencarian, dan pilihan klasifikasi model
akan menyesuaikan otomatis.

**Menyambungkan buletin.** Ubah `url_buletin` pada
`templates/partials/buletin.html.j2` menjadi endpoint Mailchimp, Brevo, atau
Substack Anda. Selama nilainya `#`, formulir menampilkan status "Segera hadir".

**Menambahkan analitik.** Isi `google_analytics_id` pada `config/settings.yaml`.

**Mengganti gambar Open Graph.** Ubah `scripts/buat_og.py` lalu jalankan
`make og`.

---

## Daftar periksa sebelum produksi

- [ ] Verifikasi jabatan dan afiliasi seluruh 64 tokoh, lalu setel
      `terverifikasi: true`
- [ ] Perbarui `base_url`, alamat surel redaksi, dan handle media sosial pada
      `config/settings.yaml`
- [ ] Tinjau teks sanggahan bersama penasihat hukum, khususnya terkait ketentuan
      promosi produk keuangan di Indonesia
- [ ] Uji `python -m mdk tulis --batas 3` dan baca ketiga hasilnya secara manual
      sebelum menaikkan batas
- [ ] Siapkan alur tinjauan redaksi: pertimbangkan menyetel `status` awal artikel
      menjadi `draf` dan menayangkannya setelah diperiksa manusia
- [ ] Daftarkan situs ke Google Search Console dan ajukan `sitemap-berita.xml`
- [ ] Siapkan kanal penerimaan hak jawab sesuai halaman `/pedoman/`
- [ ] Pastikan pemakaian umpan RSS mematuhi ketentuan layanan masing-masing
      penerbit
- [ ] Jalankan `mdk radar temukan` lalu `mdk radar periksa --nonaktifkan-mati`,
      dan periksa domain perusahaan yang gagal
- [ ] Uji satu kanal notifikasi (Telegram paling cepat disiapkan) sebelum
      menjalankan `radar jaga`
- [ ] Amati `radar status` selama beberapa hari, lalu setel ulang tiga ambang
      skor sesuai volume yang nyaman

---

## Biaya operasional

| Komponen | Perkiraan biaya |
|---|---|
| Hosting (GitHub Pages / Cloudflare Pages) | Gratis |
| Pengambilan umpan RSS | Gratis |
| Anthropic API | ± 25 artikel per hari pada model Sonnet, sekitar 3.000 token per artikel |
| Domain | Sesuai penyedia |

Biaya API merupakan satu-satunya komponen yang berskala dengan volume. Kendalikan
melalui `batas_artikel_per_jalankan` pada `config/settings.yaml` atau argumen
`--batas` pada perintah `tulis`.

---

## Lisensi dan atribusi

Kode dalam repositori ini bebas Anda gunakan dan modifikasi. Artikel yang
dihasilkan merupakan tulisan orisinal redaksi Anda. Hak atas materi sumber tetap
berada pada penerbit masing-masing, dan setiap artikel menautkannya secara
terbuka.
