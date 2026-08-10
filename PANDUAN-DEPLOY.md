# Panduan Tayang — ManajerDanaKripto.com lewat GitHub Pages

Panduan ini membawa Anda dari nol sampai `https://manajerdanakripto.com` hidup,
ber-HTTPS, dan memperbarui dirinya sendiri tiga kali sehari.

Seluruh langkah wajib bisa dikerjakan **dari peramban saja**. Terminal hanya
diperlukan bila Anda memilih jalur unggah lewat Git (Tahap 2, opsi B).

**Perkiraan waktu**

| Tahap | Isi | Waktu |
|---|---|---|
| 0 | Kumpulkan tiga bahan | 30–60 menit |
| 1 | Buat repositori GitHub | 10 menit |
| 2 | Unggah kode | 15 menit |
| 3 | Nyalakan Pages, uji tayang | 15 menit |
| 4 | Sambungkan domain + HTTPS | 20 menit + tunggu DNS |
| 5 | Nyalakan mesin berita | 30 menit |
| 6 | Verifikasi redaksi sebelum publik | 4–8 jam |

Tahap 0–4 bisa selesai dalam satu sore. Tahap 6 adalah pekerjaan editorial dan
tidak boleh dilewati sebelum situs dipromosikan ke publik.

---

## TAHAP 0 — Tiga bahan yang harus ada lebih dulu

### 0.1 Akun GitHub

Daftar di <https://github.com/signup>. Gratis. Catat **username** Anda —
nanti dipakai sebagai bagian dari alamat DNS (`username.github.io`).

Nyalakan autentikasi dua faktor saat diminta. GitHub mewajibkannya, dan repositori
ini akan menyimpan kunci API berbayar.

### 0.2 Domain `manajerdanakripto.com`

Beli di registrar mana pun. Yang penting: registrar itu memberi Anda akses
**DNS management** untuk membuat record A, AAAA, CNAME, dan TXT.

Pilihan yang lazim dipakai dari Indonesia:

| Registrar | Catatan |
|---|---|
| Cloudflare Registrar | Harga sesuai biaya pokok, DNS-nya paling lengkap. Perlu memindahkan nameserver ke Cloudflare. |
| Namecheap | Antarmuka DNS sederhana, dokumentasi GitHub Pages banyak memakainya sebagai contoh. |
| Niagahoster / Rumahweb / IDwebhost | Lokal, bisa bayar transfer bank/QRIS, dukungan Bahasa Indonesia. |
| GoDaddy | Tersedia luas, tetapi harga perpanjangan tahun kedua sering melonjak. |

Perhatikan biaya **perpanjangan**, bukan hanya harga tahun pertama. Aktifkan
juga *domain privacy* bila gratis, dan **matikan** layanan parkir/redirect bawaan
registrar — layanan itu memasang record A sendiri yang akan bentrok pada Tahap 4.

> Bila `manajerdanakripto.com` ternyata sudah diambil orang, alternatif terdekat
> yang menjaga merek: `manajerdanakripto.id`, `manajerdanakripto.co.id`, atau
> `manajerdanakripto.net`. Bila Anda mengubah domain, ubah juga `situs.domain`
> dan `situs.base_url` di `config/settings.yaml`, plus baris `echo` di kedua
> berkas alur kerja `.github/workflows/`.

### 0.3 Kunci API Anthropic

Ini yang menulis artikel. Tanpa kunci ini, situs tetap tayang tetapi kosong.

1. Buka <https://console.anthropic.com>, daftar.
2. **Billing** → isi saldo. Mulai dari USD 10–20 untuk sebulan pertama.
3. **Settings → API Keys** → *Create Key*. Beri nama `manajerdanakripto-produksi`.
4. Salin kunci `sk-ant-...` ke tempat aman. **Kunci hanya ditampilkan sekali.**
5. Pasang **usage limit** bulanan di halaman Billing agar tidak ada kejutan biaya.

Perkiraan biaya operasional: 25 artikel per putaran × 3 putaran per hari.
Pantau di halaman *Usage* selama minggu pertama, lalu setel `--batas` di
`.github/workflows/terbit.yml` sesuai anggaran Anda.

### 0.4 (Disarankan) Bot Telegram untuk peringatan

Agar Anda menerima notifikasi di ponsel tiap kali radar menangkap berita penting.

1. Di Telegram, cari **@BotFather** → `/newbot` → ikuti instruksi.
2. Salin token yang diberikan (`123456:ABC-DEF...`).
3. Kirim satu pesan apa pun ke bot Anda.
4. Buka `https://api.telegram.org/bot<TOKEN>/getUpdates` di peramban.
5. Salin angka pada `"chat":{"id":...}` — itu **chat ID** Anda.

---

## TAHAP 1 — Buat repositori

1. Buka <https://github.com/new>.
2. **Repository name**: `manajerdanakripto`
3. **Description**: `Portal berita manajer dana kripto berbahasa Indonesia`
4. Pilih **Public**.

   > Wajib Public bila Anda memakai GitHub Free. GitHub Pages dengan domain
   > kustom hanya tersedia di repositori privat bagi pelanggan Pro/Team.
   > Kunci API Anda tetap aman karena disimpan sebagai *encrypted secret*,
   > bukan di dalam kode.

5. **Jangan** centang *Add a README file*, *Add .gitignore*, atau *Choose a license*.
   Repositori harus kosong agar unggahan pertama tidak bentrok.
6. **Create repository**.

Halaman berikutnya menampilkan layar "Quick setup". Biarkan terbuka.

---

## TAHAP 2 — Unggah kode

Pakai **opsi A** bila Anda tidak terbiasa dengan terminal. Pakai **opsi B** bila
Anda ingin cara yang lebih rapi dan mudah diulang.

### Opsi A — Unggah lewat peramban

1. Ekstrak `manajerdanakripto-repo.zip` di komputer Anda. Anda akan mendapat
   folder `manajerdanakripto-repo` berisi `src/`, `config/`, `templates/`, dan
   seterusnya.
2. Di halaman repositori GitHub, klik **uploading an existing file**.
3. Buka folder hasil ekstrak, **pilih semua isinya** (Ctrl+A / Cmd+A) — pilih
   *isi* folder, bukan folder induknya — lalu seret ke area unggah.
4. Tunggu sampai semua berkas terdaftar. Isi kolom commit dengan
   `Unggahan awal kode ManajerDanaKripto`, lalu **Commit changes**.

**Periksa ini setelah unggah selesai.** Peramban kadang melewatkan folder
tersembunyi. Buka repositori Anda dan pastikan ada folder **`.github`**.

Bila `.github` tidak ada, buat manual:

1. **Add file → Create new file**.
2. Pada kolom nama, ketik persis: `.github/workflows/terbit.yml`
   (GitHub otomatis membuat foldernya saat Anda mengetik `/`).
3. Tempel isi berkas `terbit.yml` dari folder hasil ekstrak. **Commit**.
4. Ulangi untuk `.github/workflows/radar.yml` dan
   `.github/workflows/uji-tayang.yml`.

Periksa juga keberadaan `.gitignore` dan `.env.example`. Bila `.gitignore`
hilang, buat dengan cara yang sama — berkas itu yang mencegah kunci rahasia
ikut terunggah bila kelak Anda bekerja secara lokal.

### Opsi B — Unggah lewat Git

Perlu Git terpasang (<https://git-scm.com/downloads>) atau GitHub Desktop
(<https://desktop.github.com>).

```bash
cd manajerdanakripto-repo
git init
git add -A
git commit -m "Unggahan awal kode ManajerDanaKripto"
git branch -M main
git remote add origin https://github.com/USERNAME/manajerdanakripto.git
git push -u origin main
```

Ganti `USERNAME` dengan username GitHub Anda. Saat diminta kata sandi, masukkan
**personal access token**, bukan kata sandi akun — buat di
**Settings → Developer settings → Personal access tokens → Fine-grained tokens**
dengan izin *Contents: Read and write* pada repositori ini.

### Verifikasi Tahap 2

Halaman utama repositori harus menampilkan:

```
.github/    config/     content/    data/       deploy/
scripts/    src/        static/     templates/
.env.example    .gitignore    Makefile    PANDUAN-DEPLOY.md
README.md       RUNBOOK.md    mulai.sh    requirements.txt
```

---

## TAHAP 3 — Nyalakan GitHub Pages dan lakukan uji tayang

Kita nyalakan situs lebih dulu dengan **data contoh**. Tujuannya memisahkan
masalah: bila ada yang salah di tahap ini, penyebabnya pasti Pages atau DNS —
bukan kunci API atau mesin berita.

### 3.1 Setel sumber penerbitan

1. Repositori → **Settings** (tab paling kanan).
2. Menu kiri → **Pages**.
3. Pada **Build and deployment → Source**, pilih **GitHub Actions**.

   Jangan pilih *Deploy from a branch*. Situs ini dibangun oleh alur kerja,
   bukan disajikan langsung dari isi repositori.

Tidak ada tombol *Save* di bagian ini; pilihan langsung tersimpan.

### 3.2 Jalankan uji tayang

1. Tab **Actions**. Bila muncul layar persetujuan, klik
   **I understand my workflows, go ahead and enable them**.
2. Daftar kiri → **Uji tayang (mode demo, tanpa kunci API)**.
3. Tombol **Run workflow** di kanan → **Run workflow**.
4. Tunggu 2–4 menit. Muat ulang halaman sampai muncul centang hijau.

### 3.3 Buka hasilnya

Kembali ke **Settings → Pages**. Di bagian atas kini ada alamat:

```
https://USERNAME.github.io/manajerdanakripto/
```

Buka. Anda akan melihat situs lengkap dengan spanduk kuning
**"MODE DEMO — isi halaman ini adalah data contoh, bukan berita nyata."**
Itu benar dan memang diharapkan. Klik-klik beberapa halaman: rubrik, profil
tokoh, halaman perusahaan, pencarian.

**Bila tahap ini gagal**, jangan lanjut ke Tahap 4. Lihat bagian
*Pemecahan masalah* di bawah.

---

## TAHAP 4 — Sambungkan domain dan HTTPS

Urutannya penting: **daftarkan domain di GitHub lebih dulu, baru atur DNS.**
Terbalik urutannya membuka celah pengambilalihan domain oleh pihak lain.

### 4.1 (Disarankan) Verifikasi kepemilikan domain

1. Klik foto profil Anda (pojok kanan atas) → **Settings** (setelan *akun*,
   bukan setelan repositori).
2. Menu kiri → **Pages** → **Add a domain**.
3. Masukkan `manajerdanakripto.com` → **Add domain**.
4. GitHub menampilkan sebuah record TXT, misalnya:

   ```
   Nama  : _github-pages-challenge-USERNAME
   Nilai : a1b2c3d4e5f6...
   ```

5. Tambahkan record TXT itu di panel DNS registrar Anda.
6. Tunggu beberapa menit, kembali ke GitHub, klik **Verify**.

Langkah ini mengunci domain ke akun Anda sehingga tidak bisa diklaim orang lain
di repositori mana pun.

### 4.2 Daftarkan domain di repositori

1. Repositori → **Settings → Pages**.
2. **Custom domain** → ketik `manajerdanakripto.com` → **Save**.
3. GitHub akan menampilkan peringatan bahwa DNS belum benar. Itu wajar —
   kita atur DNS pada langkah berikutnya.

### 4.3 Atur DNS di registrar

Masuk ke panel DNS domain Anda. **Hapus dulu** semua record A, AAAA, dan CNAME
bawaan untuk `@` dan `www` (biasanya mengarah ke halaman parkir registrar).
Lalu tambahkan:

**Empat record A** — untuk `manajerdanakripto.com`

| Type | Name/Host | Value | TTL |
|---|---|---|---|
| A | `@` | `185.199.108.153` | otomatis |
| A | `@` | `185.199.109.153` | otomatis |
| A | `@` | `185.199.110.153` | otomatis |
| A | `@` | `185.199.111.153` | otomatis |

**Empat record AAAA** — dukungan IPv6

| Type | Name/Host | Value |
|---|---|---|
| AAAA | `@` | `2606:50c0:8000::153` |
| AAAA | `@` | `2606:50c0:8001::153` |
| AAAA | `@` | `2606:50c0:8002::153` |
| AAAA | `@` | `2606:50c0:8003::153` |

**Satu record CNAME** — agar `www.manajerdanakripto.com` ikut hidup

| Type | Name/Host | Value |
|---|---|---|
| CNAME | `www` | `USERNAME.github.io` |

Ganti `USERNAME` dengan username GitHub Anda. Sebagian registrar meminta titik
di akhir (`username.github.io.`) — ikuti format yang ditampilkan panelnya.

**Catatan Cloudflare.** Bila DNS Anda di Cloudflare, setel semua record di atas
ke mode **DNS only** (ikon awan abu-abu), bukan *Proxied* (oranye). Proxy
Cloudflare menghalangi GitHub menerbitkan sertifikat HTTPS. Setelah HTTPS aktif
di GitHub, Anda boleh menyalakan proxy bila mau.

### 4.4 Tunggu propagasi

Umumnya 10–30 menit; batas resminya 24 jam. Periksa dari terminal:

```bash
dig manajerdanakripto.com +noall +answer -t A
dig www.manajerdanakripto.com +noall +answer -t CNAME
```

Atau lewat peramban di <https://dnschecker.org>.

### 4.5 Nyalakan HTTPS

1. Kembali ke **Settings → Pages**.
2. Tunggu sampai muncul tanda centang hijau: *DNS check successful*.
3. Centang **Enforce HTTPS**.

Kotak centang itu kadang masih kelabu selama 15–60 menit sementara GitHub
menerbitkan sertifikat Let's Encrypt. Bila belum bisa dicentang setelah sejam,
hapus isi *Custom domain*, simpan, tulis ulang, simpan lagi — itu memicu GitHub
mengajukan sertifikat baru.

### Verifikasi Tahap 4

Keempat alamat ini harus membuka situs yang sama, dengan gembok di bilah alamat:

- `http://manajerdanakripto.com`
- `https://manajerdanakripto.com`
- `http://www.manajerdanakripto.com`
- `https://www.manajerdanakripto.com`

Situs masih menampilkan spanduk MODE DEMO. Itu benar. Kita ganti sekarang.

---

## TAHAP 5 — Nyalakan mesin berita

### 5.1 Simpan kunci rahasia

Repositori → **Settings → Secrets and variables → Actions** → tab **Secrets** →
**New repository secret**. Tambahkan satu per satu:

| Name | Secret | Wajib |
|---|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-...` | Ya |
| `TELEGRAM_BOT_TOKEN` | token dari @BotFather | Tidak |
| `TELEGRAM_CHAT_ID` | chat ID Anda | Tidak |

Nama harus persis, huruf besar semua. Setelah disimpan, nilainya tidak bisa
dilihat lagi oleh siapa pun termasuk Anda — hanya bisa diganti.

### 5.2 Periksa identitas situs

Buka `config/settings.yaml` lewat peramban, klik ikon pensil. Pastikan:

```yaml
situs:
  base_url: "https://manajerdanakripto.com"
  email_redaksi: "redaksi@manajerdanakripto.com"
  media_sosial:
    x: "manajerdanakripto"
    telegram: "manajerdanakripto"
```

Berkas ini sudah terisi benar untuk domain `manajerdanakripto.com`. Ubah hanya
bila Anda memakai domain lain, atau bila alamat surel redaksi Anda berbeda.

> Alamat `redaksi@manajerdanakripto.com` harus benar-benar bisa menerima surel.
> Itu kanal hak jawab yang dijanjikan di halaman `/pedoman/`. Sebagian besar
> registrar menjual email forwarding murah; Zoho Mail dan Cloudflare Email
> Routing menyediakan versi gratis.

### 5.3 Bangun daftar sumber

Alur radar akan membuat `config/watchlist.yaml` sendiri saat pertama berjalan.

1. **Actions → Radar — pantau sumber berita → Run workflow**.
2. Tunggu selesai. Buka *Summary* untuk melihat berita apa yang tertangkap.

Bila Anda mengisi kredensial Telegram, peringatan pertama akan masuk ke ponsel
Anda dalam beberapa menit.

### 5.4 Terbitkan artikel sungguhan

1. **Actions → Ambil berita dan terbitkan situs → Run workflow**.
2. Ubah kolom **batas** dari `25` menjadi **`3`** untuk jalannya yang pertama.
3. **Run workflow**. Butuh 5–15 menit.

**Baca ketiga artikel itu sampai habis** di situs Anda sebelum menaikkan batas.
Periksa empat hal: apakah faktanya benar; apakah Bahasa Indonesianya wajar;
apakah blok "Konteks Indonesia" relevan dan tidak mengarang; dan apakah
atribusi sumbernya tepat.

Bila memuaskan, jalankan lagi dengan batas `10`, lalu `25`. Setelah itu jadwal
otomatis mengambil alih: pukul 06.00, 12.00, dan 18.00 WIB setiap hari, plus
radar tiap 30 menit.

### 5.5 Hapus artikel contoh

Artikel demo akan tergeser sendiri oleh berita sungguhan, tetapi untuk
menghapusnya sekarang juga:

**Actions → Ambil berita dan terbitkan situs → Run workflow**, lalu setelah
selesai, jalankan sekali `python scripts/seed_demo.py --bersihkan` secara lokal
dan dorong basis datanya. Cara termudah tanpa terminal: biarkan saja — spanduk
MODE DEMO hilang otomatis begitu artikel sungguhan masuk ke basis data, karena
spanduk itu hanya muncul selama seluruh isi berasal dari data contoh.

---

## TAHAP 6 — Wajib sebelum dipromosikan ke publik

Situs sudah hidup dan berisi. Tetapi ada pekerjaan redaksi yang belum selesai,
dan ini bukan formalitas — ini yang membedakan portal berita dari agregator
yang bisa dituntut.

### 6.1 Verifikasi 64 profil tokoh

Buka `config/entities.yaml`. Seluruh entri saat ini bertanda
`terverifikasi: false`, dan setiap halaman profil menampilkan catatan
"menunggu verifikasi redaksi".

Untuk setiap tokoh, periksa empat kolom terhadap sumber primer — situs resmi
perusahaan, siaran pers, atau akun X terverifikasi milik tokoh itu sendiri:

```yaml
- slug: michael-saylor
  jabatan: Ketua Eksekutif        # jabatan terkini?
  organisasi: Strategy            # afiliasi terkini?
  x: saylor                       # handle X benar?
  bio: "..."                      # isi biografi akurat?
  terverifikasi: false            # ubah ke true setelah diperiksa
```

Jabatan eksekutif di industri ini berubah cukup sering. Sebagian biografi
disusun dari pengetahuan umum dan perlu diperiksa ulang. Kerjakan bertahap —
20 tokoh per sesi lebih realistis daripada memaksakan sekali duduk.

### 6.2 Verifikasi 63 domain perusahaan

Kolom `situs_web` di `config/organisasi.yaml` berisi dugaan terbaik. Alur radar
menguji setiap domain otomatis dan melaporkan yang gagal di *Summary*. Perbaiki
yang gagal secara manual.

Perhatikan juga kolom `generik`. Nilainya `true` untuk nama yang terlalu umum
(Strategy, Galaxy, Gemini) sehingga kuerinya selalu diberi pembatas topik.
Tambahkan `generik: true` bila Anda menemukan organisasi lain yang menarik
hasil melenceng.

### 6.3 Tinjauan hukum

Halaman `/disclaimer/` dan `/pedoman/` sudah berisi draf. **Mintalah penasihat
hukum meninjaunya** sebelum situs dipromosikan. Portal yang membahas produk
investasi di Indonesia menyentuh wilayah pengawasan OJK dan Bappebti, dan
ketentuannya berubah. Draf yang ada adalah titik awal, bukan pendapat hukum.

### 6.4 Daftarkan ke Google

1. <https://search.google.com/search-console> → **Add property** → *Domain* →
   `manajerdanakripto.com`.
2. Verifikasi lewat record TXT di DNS.
3. **Sitemaps** → ajukan `sitemap.xml` dan `sitemap-berita.xml`.

Sitemap berita membuat artikel Anda memenuhi syarat untuk Google News Showcase,
walau pendaftaran ke Google News Publisher Center adalah proses terpisah.

### 6.5 Daftar periksa akhir

- [ ] 64 tokoh diverifikasi, `terverifikasi: true`
- [ ] Domain perusahaan yang gagal sudah diperbaiki
- [ ] `base_url` dan alamat surel redaksi benar, dan surel bisa diterima
- [ ] Teks sanggahan sudah ditinjau penasihat hukum
- [ ] Minimal sepuluh artikel dibaca manual dan dinilai layak terbit
- [ ] Satu kanal notifikasi sudah diuji
- [ ] Terdaftar di Google Search Console, kedua sitemap diajukan
- [ ] Kanal hak jawab sesuai halaman `/pedoman/` sudah siap dijawab
- [ ] Usage limit di console.anthropic.com sudah dipasang

---

## Pemecahan masalah

| Gejala | Penyebab | Tindakan |
|---|---|---|
| Tab Actions kosong | Alur kerja belum diaktifkan | Klik tombol persetujuan di tab Actions |
| `.github` tidak ada di repo | Peramban melewatkan folder tersembunyi | Buat manual lewat *Create new file* (Tahap 2, opsi A) |
| Actions gagal: `Pages site not found` | Source belum disetel | Settings → Pages → Source = **GitHub Actions** |
| Actions gagal di langkah *Terbitkan* | Repositori privat di paket Free | Ubah jadi Public, atau naik ke Pro |
| Situs 404 setelah alur sukses | Cache CDN | Tunggu 5 menit, muat ulang paksa (Ctrl+Shift+R) |
| Pages: *domain does not resolve* | DNS belum menyebar | Tunggu, periksa dengan `dig`, pastikan record parkir registrar dihapus |
| *Enforce HTTPS* tetap kelabu | Sertifikat belum terbit | Tunggu 1 jam; bila tetap, hapus dan tulis ulang custom domain |
| Domain hilang sendiri setelah deploy | CNAME tertimpa | Sudah dicegah oleh langkah `echo ... > dist/CNAME` di alur kerja |
| Cloudflare: HTTPS gagal terus | Proxy menyala | Setel record ke **DNS only** (awan abu-abu) |
| Artikel tidak ditulis, situs kosong | Kunci API salah/saldo habis | Periksa log langkah *Tulis ulang*; cek saldo di console.anthropic.com |
| Terlalu banyak berita tak relevan | Ambang terlalu rendah | Naikkan `radar.skor_minimum` di `config/settings.yaml` |
| Radar tidak menemukan apa pun | Ambang terlalu tinggi | Turunkan `radar.skor_minimum` |
| Biaya API membengkak | Terlalu banyak artikel | Turunkan `batas` di `terbit.yml`, naikkan `skor_minimum_terjemah` |

Log lengkap ada di **Actions → klik jalannya alur → klik langkah yang merah**.
Pesan kesalahan hampir selalu ada di sepuluh baris terakhir.

---

## Setelah semuanya berjalan

Anda tidak perlu menyentuh apa pun. Yang berjalan sendiri:

| Alur | Jadwal |
|---|---|
| Radar memantau 489 sumber | tiap 30 menit |
| Menulis artikel dan menerbitkan | 06.00, 12.00, 18.00 WIB |

Yang tetap perlu Anda kerjakan:

- **Harian** — baca artikel yang terbit. Anda penanggung jawab redaksinya.
- **Mingguan** — periksa *Usage* di console.anthropic.com.
- **Bulanan** — jalankan `mdk radar periksa --nonaktifkan-mati` untuk membuang
  sumber yang sudah mati.
- **Tahunan** — perpanjang domain. Pasang auto-renew.

---

*Berkas ini adalah pelengkap `RUNBOOK.md`, yang memuat jalur pemasangan lokal
lengkap beserta seluruh 20 langkah asli.*
