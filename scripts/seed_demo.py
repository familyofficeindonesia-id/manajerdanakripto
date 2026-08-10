"""Isi basis data dengan artikel CONTOH agar situs dapat dipratinjau tanpa kunci API.

PENTING — INTEGRITAS REDAKSI
Berkas ini TIDAK memuat berita rekaan tentang tokoh nyata. Seluruh isinya adalah
artikel penjelas (explainer) bersifat umum dan faktual mengenai mekanisme produk
serta cara membaca data — bukan laporan peristiwa. Artikel ditandai ke entitas
terkait semata-mata agar seluruh komponen tampilan dapat diuji.

Situs yang dibangun dari data ini menampilkan spanduk "MODE DEMO".
Hapus dengan:  python scripts/seed_demo.py --bersihkan
"""
from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR / "src"))

from mdk.config import muat_konfigurasi          # noqa: E402
from mdk.entities import registri                # noqa: E402
from mdk.models import Artikel                   # noqa: E402
from mdk.store import buka                       # noqa: E402
from mdk.utils import sekarang_wib, sidik_jari, slugify   # noqa: E402

# ---------------------------------------------------------------------------
# Setiap entri: (rubrik, sinyal, entitas, judul, dek, ringkasan, paragraf,
#                konteks_indonesia, tag, kutipan)
# ---------------------------------------------------------------------------
CONTOH = [
    dict(
        rubrik="etf-dan-arus-dana", sinyal="netral",
        entitas=["james-butterfill", "jean-marie-mognetti", "matt-hougan"],
        judul="Cara membaca laporan arus dana mingguan produk investasi aset digital",
        dek="Angka arus masuk dan keluar kerap dikutip sebagai penanda minat institusi, tetapi maknanya bergantung pada metodologi penyusunnya.",
        ringkasan=[
            "Arus dana bersih mengukur selisih uang masuk dan keluar, bukan perubahan nilai aset.",
            "Laporan mingguan umumnya menggabungkan ETF, ETP, dan produk trust lintas yurisdiksi.",
            "Kenaikan dana kelolaan dapat terjadi karena harga naik meski arus dana justru negatif.",
        ],
        paragraf=[
            "Setiap pekan, sejumlah manajer aset digital global menerbitkan laporan arus dana yang merangkum berapa banyak uang baru masuk atau keluar dari produk investasi aset kripto terregulasi. Laporan semacam ini menjadi salah satu rujukan yang paling sering dikutip media ketika membahas minat investor institusional, termasuk oleh redaksi kami sendiri. Karena itu, memahami cara membacanya penting sebelum menarik kesimpulan.",
            "Hal pertama yang perlu dipisahkan adalah arus dana bersih dan dana kelolaan. Arus dana bersih mengukur selisih antara uang yang masuk melalui penciptaan unit baru dan uang yang keluar melalui penebusan unit. Dana kelolaan, sebaliknya, adalah nilai pasar seluruh aset yang dipegang produk tersebut. Dana kelolaan bisa membengkak semata-mata karena harga aset naik, meskipun pada periode yang sama investor justru menarik dananya.",
            "Cakupan laporan juga berbeda-beda. Sebagian penyusun hanya menghitung ETF spot di Amerika Serikat, sebagian lain menggabungkan produk yang diperdagangkan di bursa Eropa, Kanada, Brasil, dan Australia, termasuk instrumen berstruktur utang yang secara hukum bukan reksa dana. Perbedaan cakupan ini menjelaskan mengapa dua laporan pada pekan yang sama dapat menghasilkan angka yang tidak identik.",
            "Faktor ketiga adalah waktu penyelesaian transaksi. Pemesanan yang dilakukan menjelang akhir pekan kerap baru tercatat pada periode laporan berikutnya, sehingga lonjakan atau penurunan tajam pada satu pekan tertentu tidak selalu mencerminkan perubahan sikap investor. Membaca tren empat sampai delapan pekan biasanya memberi gambaran yang lebih stabil daripada membaca satu titik data.",
            "Terakhir, arus dana adalah data historis, bukan proyeksi. Ia menjelaskan apa yang sudah terjadi pada periode yang telah lewat dan tidak memuat informasi tentang arah harga ke depan. Pembaca yang menggunakannya sebagai satu-satunya dasar keputusan berisiko menyamakan korelasi masa lalu dengan sebab-akibat di masa depan.",
        ],
        konteks_indonesia="Investor Indonesia umumnya tidak dapat membeli ETF aset kripto luar negeri secara langsung melalui pedagang aset kripto domestik, sehingga angka arus dana global lebih tepat dibaca sebagai indikator sentimen ketimbang sebagai peluang produk yang dapat diakses. Pengawasan aset keuangan digital di dalam negeri berada pada Otoritas Jasa Keuangan setelah peralihan kewenangan dari otoritas perdagangan berjangka, dan kerangka produk investasi kolektif berbasis aset kripto masih terus berkembang. Bagi pembaca domestik, arus dana global tetap relevan karena memengaruhi likuiditas dan harga acuan yang dipakai bursa lokal.",
        tag=["etf", "arus-dana", "data-pasar", "edukasi"],
    ),
    dict(
        rubrik="treasury-korporasi", sinyal="netral",
        entitas=["michael-saylor", "anthony-pompliano"],
        judul="Mengenal struktur pendanaan di balik strategi treasury Bitcoin korporasi",
        dek="Perusahaan yang menempatkan kripto di neraca umumnya mendanainya lewat penerbitan saham baru atau surat utang, dan masing-masing membawa konsekuensi berbeda bagi pemegang saham.",
        ringkasan=[
            "Pendanaan lewat penerbitan saham menambah jumlah saham beredar dan berpotensi mendilusi pemegang saham lama.",
            "Obligasi konversi menunda dilusi tetapi menambah kewajiban dengan jatuh tempo tertentu.",
            "Nilai perusahaan menjadi sangat terkait pada harga aset yang dipegang di neraca.",
        ],
        paragraf=[
            "Sejumlah perusahaan terbuka menempatkan sebagian kas mereka pada Bitcoin sebagai bagian dari strategi neraca. Pola ini lazim disebut strategi treasury aset digital. Pertanyaan yang sering luput dari pemberitaan bukanlah berapa banyak aset yang dibeli, melainkan dari mana uang pembeliannya berasal.",
            "Terdapat tiga sumber utama. Pertama, kas hasil operasi, yaitu uang yang benar-benar dihasilkan bisnis inti perusahaan. Kedua, penerbitan saham baru, termasuk melalui skema penawaran bertahap di pasar. Ketiga, penerbitan surat utang, umumnya obligasi konversi yang dapat ditukar menjadi saham pada harga tertentu.",
            "Masing-masing membawa konsekuensi berbeda. Penerbitan saham baru menambah jumlah saham beredar sehingga kepemilikan pemegang saham lama terdilusi, meski nilai aset per saham dapat tetap naik jika harga beli aset lebih rendah dari valuasi pasar saham. Obligasi konversi menunda dilusi tersebut, tetapi menciptakan kewajiban dengan tanggal jatuh tempo yang harus dipenuhi terlepas dari kondisi pasar saat itu.",
            "Konsekuensi lanjutannya adalah harga saham perusahaan menjadi sangat terkait dengan pergerakan aset yang dipegangnya. Investor yang membeli saham semacam ini pada praktiknya membeli dua hal sekaligus: bisnis operasional perusahaan dan eksposur berleverage terhadap aset digital di neracanya. Keduanya tidak selalu bergerak searah.",
            "Karena itu, membaca laporan keuangan menjadi lebih informatif daripada membaca pengumuman pembelian. Struktur permodalan, jadwal jatuh tempo utang, dan kebijakan akuntansi atas aset digital menentukan seberapa besar ruang gerak perusahaan ketika harga aset turun dalam waktu lama.",
        ],
        konteks_indonesia="Di Bursa Efek Indonesia belum ada emiten dengan strategi treasury aset digital berskala besar seperti yang dijalankan sejumlah perusahaan di Amerika Serikat. Kerangka akuntansi dan keterbukaan informasi untuk kepemilikan aset kripto pada perusahaan terbuka domestik juga masih terbatas. Bagi investor Indonesia yang mempertimbangkan saham semacam ini melalui fasilitas perdagangan efek luar negeri, penting memahami bahwa risikonya berlapis: risiko aset digital, risiko permodalan perusahaan, sekaligus risiko nilai tukar rupiah.",
        tag=["treasury", "korporasi", "permodalan", "edukasi"],
    ),
    dict(
        rubrik="analisis-pasar", sinyal="netral",
        entitas=["lyn-alden", "raoul-pal", "jim-bianco"],
        judul="Kerangka likuiditas global yang sering dipakai analis makro membaca siklus kripto",
        dek="Beberapa analis menghubungkan pergerakan aset berisiko dengan ketersediaan likuiditas dolar, meski hubungan itu tidak berlaku seragam di setiap periode.",
        ringkasan=[
            "Likuiditas global mencakup neraca bank sentral, kondisi kredit, dan aliran modal lintas negara.",
            "Korelasi antara likuiditas dan harga aset berisiko bersifat longgar, bukan mekanis.",
            "Indikator makro paling berguna untuk memahami konteks, bukan untuk menentukan waktu transaksi.",
        ],
        paragraf=[
            "Analisis makro terhadap aset digital umumnya berangkat dari satu premis: aset berisiko cenderung menguat ketika likuiditas dalam sistem keuangan global berlimpah, dan melemah ketika likuiditas mengetat. Premis ini menjadi kerangka yang sering dipakai untuk menjelaskan siklus pasar kripto dalam rentang beberapa tahun.",
            "Yang dimaksud likuiditas global bukan satu angka tunggal. Ia merupakan gabungan beberapa hal: ukuran neraca bank sentral utama, arah suku bunga acuan, kondisi penyaluran kredit perbankan, penerbitan surat utang pemerintah, serta pergerakan modal lintas negara yang dipengaruhi nilai tukar dolar. Analis berbeda menyusun indeks yang berbeda pula dari komponen-komponen ini.",
            "Kritik utama terhadap kerangka ini adalah bahwa hubungan tersebut longgar dan tidak mekanis. Terdapat periode ketika likuiditas melonggar tetapi harga aset berisiko tetap tertekan, dan sebaliknya. Faktor spesifik sektor — perubahan regulasi, kegagalan sebuah lembaga besar, atau pergeseran struktur pasar — dapat mendominasi pengaruh makro dalam jangka pendek.",
            "Karena itu, kerangka makro lebih berguna untuk memahami konteks daripada untuk menentukan waktu transaksi. Ia membantu menjelaskan mengapa suatu periode terasa berbeda dari periode lain, tetapi tidak memberikan sinyal masuk atau keluar yang presisi.",
            "Pembaca yang mengikuti analisis makro sebaiknya memperhatikan asumsi yang mendasarinya: rentang waktu yang dipakai, komponen yang dimasukkan ke dalam indeks, dan apakah penulisnya memiliki posisi pada aset yang dibahas. Ketiga hal itu memengaruhi bagaimana sebuah kesimpulan sebaiknya ditimbang.",
        ],
        konteks_indonesia="Bagi investor Indonesia, dimensi tambahan yang tidak dihadapi investor berbasis dolar adalah nilai tukar. Ketika dolar menguat terhadap rupiah, imbal hasil aset berdenominasi dolar dalam rupiah dapat berbeda jauh dari imbal hasil nominalnya. Kondisi likuiditas global juga memengaruhi arus modal asing ke pasar keuangan domestik dan kebijakan suku bunga Bank Indonesia, sehingga kerangka makro yang sama relevan untuk membaca pasar saham dan obligasi dalam negeri.",
        tag=["makro", "likuiditas", "siklus-pasar", "edukasi"],
        kutipan=("", ""),
    ),
    dict(
        rubrik="syariah-dan-halal", sinyal="netral",
        entitas=["junaid-wahedna", "hann-liew"],
        judul="Prinsip penyaringan syariah pada produk investasi berbasis aset digital",
        dek="Penilaian kepatuhan syariah atas aset kripto berfokus pada kejelasan akad, kegunaan, dan struktur imbal hasil produknya.",
        ringkasan=[
            "Penyaringan syariah menilai aset dasar sekaligus struktur produk yang membungkusnya.",
            "Unsur riba, gharar berlebihan, dan maysir menjadi tiga hal yang paling sering ditelaah.",
            "Fatwa dan pendapat ulama berbeda antarnegara sehingga status suatu aset tidak selalu seragam.",
        ],
        paragraf=[
            "Permintaan atas produk investasi yang sesuai prinsip syariah mendorong sejumlah pengelola dana global menyusun kerangka penyaringan untuk aset digital. Kerangka ini umumnya menilai dua lapis sekaligus: aset dasarnya dan struktur produk yang membungkusnya.",
            "Pada lapis aset dasar, telaah berfokus pada apakah aset tersebut memiliki kegunaan yang jelas, apakah kepemilikannya dapat ditentukan secara pasti, dan apakah nilainya bersumber dari aktivitas yang diperbolehkan. Aset yang imbal hasilnya berasal dari pembayaran bunga, misalnya, umumnya tidak lolos penyaringan karena mengandung unsur riba.",
            "Pada lapis produk, yang dinilai adalah akad yang digunakan, cara aset disimpan, dan sumber imbal hasil yang dijanjikan kepada investor. Produk yang menggunakan pinjam-meminjam berbunga, penjualan aset yang belum dimiliki, atau derivatif dengan ketidakpastian tinggi berpotensi tidak memenuhi kriteria meski aset dasarnya sendiri dinilai sesuai.",
            "Perbedaan pendapat antaryurisdiksi merupakan hal yang wajar dalam bidang ini. Dewan pengawas syariah di satu negara dapat sampai pada kesimpulan berbeda dari lembaga di negara lain untuk aset yang sama, karena perbedaan pendekatan metodologi maupun konteks pasar setempat. Investor karena itu perlu memeriksa lembaga mana yang mengeluarkan penilaian atas suatu produk.",
            "Transparansi menjadi kunci. Produk yang menyediakan dokumen metodologi, komposisi portofolio, dan susunan dewan pengawas syariahnya secara terbuka memberi ruang bagi investor untuk menilai sendiri, alih-alih hanya mengandalkan label yang tercantum pada materi pemasaran.",
        ],
        konteks_indonesia="Indonesia memiliki ekosistem keuangan syariah yang mapan dengan Dewan Syariah Nasional Majelis Ulama Indonesia sebagai rujukan fatwa dan Otoritas Jasa Keuangan sebagai pengawas produk. Status aset kripto dalam pandangan lembaga keagamaan di Indonesia masih beragam, dengan sebagian ulama menekankan persoalan gharar dan ketiadaan aset dasar yang jelas. Investor Muslim di Indonesia yang mempertimbangkan produk semacam ini sebaiknya merujuk pada fatwa yang berlaku di dalam negeri dan tidak menyamakannya secara langsung dengan sertifikasi syariah dari yurisdiksi lain.",
        tag=["syariah", "penyaringan", "produk-investasi", "edukasi"],
    ),
    dict(
        rubrik="regulasi", sinyal="netral",
        entitas=["ric-edelman", "peter-mintzberg"],
        judul="Peran kustodian dan pemisahan aset dalam produk investasi kripto terregulasi",
        dek="Aturan kustodian menentukan siapa yang memegang aset, bagaimana ia dipisahkan dari harta pengelola, dan apa yang terjadi bila penyedia jasa gagal.",
        ringkasan=[
            "Pemisahan aset melindungi kepemilikan investor bila pengelola atau kustodian bermasalah.",
            "Kustodian terregulasi umumnya wajib menjalani audit dan pembuktian cadangan berkala.",
            "Struktur hukum produk menentukan hak investor ketika terjadi sengketa.",
        ],
        paragraf=[
            "Salah satu pembeda utama antara produk investasi kripto terregulasi dan penyimpanan mandiri adalah keberadaan kustodian. Kustodian merupakan lembaga yang bertugas menyimpan aset atas nama investor, mengelola kunci privat, dan memastikan aset tersebut tidak bercampur dengan harta milik pengelola dana.",
            "Prinsip pemisahan aset menjadi inti perlindungan investor. Bila aset investor tercampur dengan aset operasional pengelola, kegagalan pengelola dapat menyeret aset nasabah ke dalam proses kepailitan. Sebaliknya, aset yang dipisahkan secara hukum dan operasional idealnya tetap menjadi milik investor terlepas dari kondisi keuangan pengelola.",
            "Kerangka pengawasan di berbagai negara umumnya mensyaratkan kustodian menjalani audit independen berkala, menyimpan sebagian besar aset pada penyimpanan luring, dan memiliki prosedur pemulihan bila terjadi insiden keamanan. Sebagian juga mewajibkan penerbitan bukti cadangan yang dapat diverifikasi pihak ketiga.",
            "Struktur hukum produk turut menentukan hak investor. Reksa dana, trust, dan produk berstruktur utang memberikan posisi hukum yang berbeda kepada pemegangnya ketika terjadi sengketa. Dokumen penawaran biasanya memuat penjelasan ini, meski sering luput dibaca karena panjang dan teknis.",
            "Bagi investor, tiga pertanyaan praktis dapat menjadi titik awal: siapa kustodiannya, di yurisdiksi mana ia diawasi, dan apa yang terjadi terhadap aset saya bila pengelola atau kustodian berhenti beroperasi. Jawaban ketiganya lebih menentukan keamanan jangka panjang daripada besaran biaya pengelolaan.",
        ],
        konteks_indonesia="Kerangka Indonesia mengenal pemisahan fungsi antara penyelenggara perdagangan, lembaga kliring, dan pengelola tempat penyimpanan aset kripto, dengan pengawasan yang kini berada pada Otoritas Jasa Keuangan. Investor domestik sebaiknya memastikan platform yang digunakan terdaftar resmi dan memahami bagaimana aset mereka disimpan serta dipisahkan. Prinsip pemisahan aset yang berlaku pada produk global relevan sebagai pembanding ketika menilai perlindungan yang ditawarkan penyedia jasa di dalam negeri.",
        tag=["regulasi", "kustodian", "perlindungan-investor", "edukasi"],
    ),
    dict(
        rubrik="pendanaan-dan-ventura", sinyal="netral",
        entitas=["chris-dixon", "fred-wilson", "katie-haun", "marc-andreessen"],
        judul="Membaca pengumuman pendanaan ventura di sektor infrastruktur blockchain",
        dek="Nilai putaran pendanaan sering menjadi berita utama, padahal struktur kesepakatan dan tahapannya lebih menjelaskan kondisi sebenarnya.",
        ringkasan=[
            "Valuasi yang diumumkan umumnya merupakan valuasi setelah pendanaan, bukan nilai perusahaan hari ini.",
            "Struktur kesepakatan seperti preferensi likuidasi dapat mengubah hasil akhir pemegang saham.",
            "Tahapan pendanaan menandakan tingkat kematangan produk, bukan jaminan keberhasilan.",
        ],
        paragraf=[
            "Pengumuman pendanaan modal ventura merupakan salah satu jenis berita yang paling sering muncul di sektor aset digital. Angka yang dikutip biasanya dua: besaran dana yang dihimpun dan valuasi perusahaan. Keduanya perlu dibaca dengan hati-hati.",
            "Valuasi yang diumumkan umumnya adalah valuasi setelah pendanaan, yaitu nilai perusahaan setelah uang baru masuk. Ia merupakan hasil negosiasi antara pendiri dan investor pada satu titik waktu, bukan harga pasar yang terbentuk dari transaksi banyak pihak. Perusahaan swasta tidak memiliki harga pasar harian sebagaimana perusahaan tercatat di bursa.",
            "Struktur kesepakatan sering kali lebih menentukan daripada valuasinya. Ketentuan seperti preferensi likuidasi, hak partisipasi, dan proteksi anti-dilusi menentukan siapa mendapat apa ketika perusahaan dijual. Sebuah perusahaan dapat terjual dengan nilai besar sementara pemegang saham biasa memperoleh porsi yang jauh lebih kecil dari perkiraan.",
            "Tahapan pendanaan memberi petunjuk tentang kematangan produk. Pendanaan tahap awal umumnya mendanai pembuktian gagasan, sementara tahap lanjutan mendanai perluasan skala. Namun tahapan bukanlah jaminan keberhasilan; sebagian besar perusahaan tahap awal tidak mencapai tahap berikutnya.",
            "Bagi pembaca yang bukan investor ventura, nilai informasi dari berita pendanaan terletak pada arah minat modal: sektor mana yang sedang menarik pendanaan dan masalah apa yang sedang dicoba dipecahkan. Itu memberi gambaran tentang infrastruktur yang mungkin tersedia beberapa tahun ke depan.",
        ],
        konteks_indonesia="Ekosistem modal ventura Indonesia memiliki dinamika sendiri, dengan sebagian pendanaan sektor teknologi keuangan mengalir ke pembayaran, pinjaman, dan infrastruktur pasar modal. Perusahaan rintisan aset digital di dalam negeri menghadapi persyaratan perizinan yang berbeda dari yurisdiksi lain, termasuk ketentuan modal disetor dan struktur kepemilikan. Berita pendanaan global tetap relevan sebagai penanda teknologi dan model bisnis yang mungkin masuk ke pasar domestik pada tahap berikutnya.",
        tag=["ventura", "pendanaan", "startup", "edukasi"],
    ),
    dict(
        rubrik="edukasi", sinyal="netral",
        entitas=["hunter-horsley", "matthew-sigel", "samir-kerbage"],
        judul="Perbedaan indeks, dana indeks, dan produk yang diperdagangkan di bursa",
        dek="Tiga istilah ini sering dipertukarkan dalam pemberitaan, padahal masing-masing merujuk pada hal yang berbeda.",
        ringkasan=[
            "Indeks adalah aturan penghitungan, bukan produk yang bisa dibeli.",
            "Dana indeks adalah kendaraan investasi yang berupaya mereplikasi indeks tertentu.",
            "Produk yang diperdagangkan di bursa memiliki struktur hukum yang beragam antarnegara.",
        ],
        paragraf=[
            "Pemberitaan pasar sering menyebut indeks, dana indeks, dan produk yang diperdagangkan di bursa seolah-olah sinonim. Ketiganya berbeda, dan perbedaan itu berpengaruh pada apa yang sebenarnya dibeli investor.",
            "Indeks adalah seperangkat aturan untuk memilih dan menimbang sekumpulan aset, lalu menghitung nilainya menjadi satu angka. Indeks sendiri bukan produk yang dapat dibeli. Yang menentukan karakter sebuah indeks adalah kriteria kelayakan aset, metode pembobotan, jadwal penyeimbangan ulang, dan bagaimana sumber harga ditentukan.",
            "Dana indeks adalah kendaraan investasi yang berupaya mereplikasi kinerja sebuah indeks. Selalu terdapat selisih antara kinerja dana dan indeks acuannya akibat biaya pengelolaan, biaya transaksi, dan waktu penyeimbangan. Selisih ini disebut galat penjejakan.",
            "Produk yang diperdagangkan di bursa merupakan payung yang lebih luas. Di Amerika Serikat, sebagian besar berbentuk dana. Di Eropa, banyak produk aset digital berbentuk surat utang tanpa bunga yang dijamin aset, sehingga pemegangnya secara hukum adalah kreditor, bukan pemilik unit penyertaan. Konsekuensinya berbeda ketika penerbit mengalami kesulitan.",
            "Karena itu, membaca lembar fakta produk lebih informatif daripada membaca namanya. Struktur hukum, kustodian, biaya, dan mekanisme penciptaan serta penebusan unit menjelaskan risiko yang sebenarnya ditanggung.",
        ],
        konteks_indonesia="Di Indonesia, reksa dana indeks dan produk yang diperdagangkan di bursa untuk kelas aset konvensional sudah tersedia dan diawasi Otoritas Jasa Keuangan, sementara kerangka untuk produk berbasis aset kripto masih dalam pengembangan. Pemahaman atas perbedaan ketiga istilah tersebut membantu investor domestik menilai produk baru yang mungkin ditawarkan di kemudian hari, termasuk produk berbasis emas dan aset nyata yang ditokenisasi.",
        tag=["indeks", "etf", "produk-investasi", "edukasi"],
    ),
    dict(
        rubrik="analisis-pasar", sinyal="netral",
        entitas=["arthur-hayes", "jeffrey-park", "ari-paul"],
        judul="Mengenal perdagangan basis, strategi yang banyak dipakai dana institusional",
        dek="Strategi ini memanfaatkan selisih harga antara pasar spot dan kontrak berjangka, dengan risiko yang berbeda dari sekadar memegang aset.",
        ringkasan=[
            "Perdagangan basis mengambil posisi berlawanan di pasar spot dan berjangka secara bersamaan.",
            "Imbal hasilnya berasal dari selisih harga, bukan dari arah pergerakan aset.",
            "Risiko utamanya adalah likuiditas, jaminan, dan keandalan bursa tempat posisi dibuka.",
        ],
        paragraf=[
            "Perdagangan basis merupakan salah satu strategi yang paling sering digunakan dana institusional di pasar aset digital. Prinsipnya sederhana: membeli aset di pasar spot sekaligus menjual kontrak berjangka atas aset yang sama, lalu menahan kedua posisi hingga kontrak jatuh tempo.",
            "Ketika harga kontrak berjangka lebih tinggi dari harga spot, selisih tersebut akan menyempit menuju nol saat mendekati jatuh tempo. Selisih yang menyempit itulah yang menjadi sumber imbal hasil. Karena kedua posisi berlawanan arah, pergerakan harga aset secara umum tidak menentukan hasil akhir strategi ini.",
            "Sifat itu membuat strategi tersebut kerap digolongkan netral pasar. Namun netral terhadap arah harga bukan berarti bebas risiko. Risiko utamanya terletak pada pengelolaan jaminan: bila harga bergerak tajam, posisi berjangka dapat memerlukan tambahan jaminan dalam waktu singkat, dan kegagalan memenuhinya dapat memicu likuidasi paksa.",
            "Risiko lain berkaitan dengan tempat transaksi dilakukan. Karena posisi spot dan berjangka sering berada di dua platform berbeda, kegagalan salah satu platform dapat memutus struktur lindung nilai dan mengubah posisi yang semula seimbang menjadi terbuka sepihak.",
            "Besaran selisih harga juga berubah-ubah mengikuti kondisi pasar. Pada periode permintaan tinggi terhadap posisi beli berleverage, selisih melebar dan imbal hasil strategi ini meningkat. Pada periode sebaliknya, selisih dapat menyempit sampai tidak lagi menutupi biaya modal dan biaya transaksi.",
        ],
        konteks_indonesia="Kontrak berjangka aset kripto di Indonesia diperdagangkan dalam kerangka yang berbeda dari bursa derivatif global, dengan ketentuan margin dan jenis kontrak yang lebih terbatas. Investor ritel domestik umumnya tidak memiliki akses ke struktur jaminan lintas bursa yang diperlukan strategi ini. Pemahaman atas perdagangan basis tetap berguna untuk menafsirkan pemberitaan mengenai arus dana institusional, karena sebagian permintaan terhadap produk spot berasal dari kebutuhan lindung nilai strategi semacam ini.",
        tag=["strategi", "derivatif", "netral-pasar", "edukasi"],
    ),
    dict(
        rubrik="etf-dan-arus-dana", sinyal="netral",
        entitas=["larry-fink", "abigail-johnson", "jenny-johnson"],
        judul="Mekanisme penciptaan dan penebusan unit yang menjaga harga ETF tetap wajar",
        dek="Peserta resmi berperan menjaga selisih harga pasar terhadap nilai aktiva bersih tetap sempit melalui arbitrase.",
        ringkasan=[
            "Peserta resmi dapat menciptakan atau menebus unit dalam jumlah besar langsung ke penerbit.",
            "Arbitrase yang mereka lakukan menjaga harga pasar mendekati nilai aktiva bersih.",
            "Mekanisme ini dapat terganggu saat likuiditas aset dasar mengering.",
        ],
        paragraf=[
            "Salah satu perbedaan mendasar antara ETF dan produk trust tertutup terletak pada mekanisme penciptaan dan penebusan unit. Mekanisme inilah yang menjaga harga ETF di pasar tetap dekat dengan nilai aset yang dipegangnya.",
            "Prosesnya melibatkan pihak yang disebut peserta resmi, umumnya perusahaan perantara berskala besar. Ketika harga ETF di pasar lebih tinggi dari nilai aktiva bersihnya, peserta resmi dapat menyerahkan aset dasar kepada penerbit untuk memperoleh unit baru, lalu menjualnya di pasar. Pasokan unit bertambah dan harga terdorong turun mendekati nilai wajarnya.",
            "Sebaliknya, ketika harga pasar berada di bawah nilai aktiva bersih, peserta resmi dapat membeli unit di pasar dan menebusnya kepada penerbit untuk memperoleh aset dasar. Permintaan unit meningkat dan harga terdorong naik. Aktivitas arbitrase inilah yang membuat selisih harga umumnya tetap sempit.",
            "Mekanisme tersebut dapat terganggu pada kondisi tertentu. Bila likuiditas aset dasar mengering atau akses peserta resmi terhambat, selisih harga dapat melebar dan bertahan lebih lama dari biasanya. Produk yang penebusannya dilakukan dalam bentuk tunai, bukan aset, memiliki dinamika yang sedikit berbeda karena penerbit harus menjual aset di pasar.",
            "Bagi investor, implikasinya praktis: memeriksa selisih harga terhadap nilai aktiva bersih sebelum bertransaksi, terutama pada produk dengan volume perdagangan tipis atau pada jam perdagangan ketika pasar aset dasar sedang tutup.",
        ],
        konteks_indonesia="Bursa Efek Indonesia telah mengenal mekanisme dealer partisipan untuk produk yang diperdagangkan di bursa dengan aset dasar konvensional. Pemahaman atas mekanisme ini relevan bagi investor domestik yang mengikuti perkembangan produk berbasis emas maupun aset yang ditokenisasi, karena prinsip penjagaan harga terhadap nilai wajar bekerja dengan logika serupa. Perbedaan zona waktu antara Jakarta dan bursa Amerika Serikat juga memengaruhi kapan selisih harga cenderung melebar.",
        tag=["etf", "mekanisme-pasar", "likuiditas", "edukasi"],
    ),
    dict(
        rubrik="regulasi", sinyal="netral",
        entitas=["cameron-winklevoss", "tyler-winklevoss", "nic-carter"],
        judul="Perbedaan pendekatan pengaturan aset digital di beberapa yurisdiksi utama",
        dek="Kerangka aturan berbeda dalam hal klasifikasi aset, kewajiban perizinan, dan perlindungan konsumen.",
        ringkasan=[
            "Klasifikasi aset menentukan otoritas mana yang berwenang mengawasi.",
            "Sebagian yurisdiksi menyusun kerangka khusus, sebagian lain memperluas aturan yang ada.",
            "Perbedaan aturan memengaruhi produk apa yang tersedia bagi investor di tiap negara.",
        ],
        paragraf=[
            "Pengaturan aset digital berkembang dengan kecepatan dan pendekatan yang berbeda di tiap yurisdiksi. Perbedaan tersebut menjelaskan mengapa sebuah produk dapat tersedia luas di satu negara tetapi tidak dapat ditawarkan di negara lain.",
            "Titik awalnya biasanya klasifikasi. Apakah suatu aset digolongkan sebagai efek, komoditas, alat pembayaran, atau kategori tersendiri menentukan otoritas mana yang berwenang dan aturan mana yang berlaku. Aset yang sama dapat digolongkan berbeda di dua negara.",
            "Pendekatan penyusunan aturan juga berbeda. Sebagian yurisdiksi memilih menyusun kerangka khusus yang komprehensif untuk aset kripto, mencakup penerbitan, perdagangan, kustodian, dan stablecoin dalam satu paket. Sebagian lain memperluas penerapan aturan pasar modal yang sudah ada melalui penafsiran dan penegakan kasus per kasus.",
            "Dimensi ketiga adalah perlindungan konsumen: kewajiban keterbukaan informasi, pembatasan pemasaran kepada investor ritel, persyaratan pemisahan aset, serta ketersediaan mekanisme penyelesaian sengketa. Aspek ini sering kurang mendapat perhatian dalam pemberitaan dibanding aspek perizinan.",
            "Bagi pembaca, implikasi praktisnya adalah bahwa berita regulasi dari satu negara tidak dapat langsung dipindahkan konteksnya ke negara lain. Yang relevan bagi keputusan sehari-hari adalah aturan yang berlaku di yurisdiksi tempat investor berdomisili dan tempat platform yang digunakannya diawasi.",
        ],
        konteks_indonesia="Indonesia menjalani peralihan pengawasan aset kripto dari otoritas perdagangan berjangka kepada Otoritas Jasa Keuangan, sejalan dengan penetapan aset kripto sebagai bagian dari aset keuangan digital. Peralihan ini membawa konsekuensi pada perizinan penyelenggara, kewajiban pelaporan, dan standar perlindungan konsumen. Investor domestik sebaiknya mengikuti perkembangan peraturan pelaksana yang diterbitkan otoritas, karena kerangka tersebut menentukan produk apa yang boleh ditawarkan secara sah di dalam negeri.",
        tag=["regulasi", "yurisdiksi", "perlindungan-konsumen", "edukasi"],
    ),
    dict(
        rubrik="berita-utama", sinyal="netral",
        entitas=["cathie-wood", "tom-lee", "mark-yusko"],
        judul="Mengapa target harga jangka panjang perlu dibaca sebagai skenario, bukan ramalan",
        dek="Angka proyeksi umumnya merupakan keluaran model dengan asumsi tertentu yang jarang ikut dikutip dalam pemberitaan.",
        ringkasan=[
            "Target harga adalah hasil model dengan asumsi yang dapat diperdebatkan.",
            "Rentang waktu proyeksi menentukan seberapa besar ketidakpastian yang terkandung.",
            "Asumsi tingkat adopsi merupakan variabel yang paling menentukan hasil model.",
        ],
        paragraf=[
            "Proyeksi harga jangka panjang untuk aset digital kerap menjadi berita utama karena angkanya mencolok. Yang jarang ikut dikutip adalah asumsi di baliknya, padahal asumsi itulah yang menentukan hasil akhir sebuah model.",
            "Sebagian besar model proyeksi bekerja dengan cara yang mirip: memperkirakan ukuran pasar yang dapat dijangkau, lalu mengalikannya dengan asumsi pangsa yang mungkin diraih, dan membaginya dengan jumlah unit yang beredar. Perubahan kecil pada asumsi tingkat adopsi dapat mengubah hasil akhirnya secara dramatis.",
            "Rentang waktu juga penting. Proyeksi lima sampai sepuluh tahun mengandung ketidakpastian yang jauh lebih besar dibanding proyeksi satu tahun, karena semakin panjang horizonnya semakin banyak variabel yang dapat berubah — teknologi, regulasi, struktur pasar, dan kondisi makro.",
            "Praktik yang lebih informatif adalah menyajikan beberapa skenario sekaligus: skenario dasar, skenario optimistis, dan skenario pesimistis, masing-masing dengan asumsi yang dinyatakan terbuka. Penyaji riset yang kredibel umumnya melakukan ini, meski media sering hanya mengutip angka tertingginya.",
            "Bagi pembaca, pertanyaan yang berguna bukan berapa angkanya, melainkan asumsi apa yang harus terbukti benar agar angka tersebut tercapai, dan seberapa masuk akal asumsi tersebut menurut penilaian sendiri.",
        ],
        konteks_indonesia="Proyeksi harga yang beredar luas di media sosial Indonesia sering dikutip tanpa asumsi pendukungnya, dan dalam beberapa kasus dipakai sebagai materi pemasaran oleh pihak yang tidak berizin. Otoritas Jasa Keuangan secara berkala mengingatkan masyarakat mengenai penawaran investasi yang menjanjikan imbal hasil pasti. Pembaca Indonesia sebaiknya membedakan antara riset yang menyatakan asumsinya secara terbuka dan materi promosi yang menggunakan angka proyeksi sebagai daya tarik.",
        tag=["proyeksi", "riset", "valuasi", "edukasi"],
    ),
    dict(
        rubrik="edukasi", sinyal="netral",
        entitas=["dan-morehead", "anatoly-crachilov", "mitchell-dong"],
        judul="Struktur biaya dana investasi dan pengaruhnya terhadap imbal hasil bersih",
        dek="Biaya pengelolaan, biaya kinerja, dan biaya transaksi bekerja secara berbeda dan terakumulasi seiring waktu.",
        ringkasan=[
            "Biaya pengelolaan dipungut atas dana kelolaan terlepas dari kinerja.",
            "Biaya kinerja dipungut atas keuntungan, umumnya dengan batas tertinggi sebelumnya.",
            "Biaya kecil yang berulang berdampak besar pada imbal hasil jangka panjang.",
        ],
        paragraf=[
            "Perbandingan antarproduk investasi sering berhenti pada perbandingan kinerja masa lalu. Padahal struktur biaya merupakan salah satu dari sedikit variabel yang dapat diketahui pasti di muka dan pasti memengaruhi hasil akhir.",
            "Biaya pengelolaan dipungut sebagai persentase tahunan dari dana kelolaan dan dibebankan terlepas dari apakah dana mencatat untung atau rugi. Pada produk yang diperdagangkan di bursa, biaya ini biasanya sudah tercermin dalam nilai aktiva bersih harian sehingga tidak terlihat sebagai potongan terpisah.",
            "Biaya kinerja dipungut sebagai persentase dari keuntungan yang dihasilkan. Struktur yang lazim menyertakan batas tertinggi sebelumnya, yang berarti pengelola hanya memungut biaya kinerja setelah dana melampaui puncak nilai yang pernah dicapai. Tanpa ketentuan tersebut, investor dapat membayar biaya kinerja atas pemulihan dari kerugian.",
            "Biaya transaksi jarang tercantum sebagai satu angka. Ia mencakup komisi, selisih harga beli-jual, dan dampak harga ketika dana melakukan transaksi besar. Strategi dengan frekuensi transaksi tinggi menanggung biaya ini jauh lebih besar dibanding strategi yang jarang bertransaksi.",
            "Efek akumulasi biaya sering diremehkan. Selisih biaya tahunan yang tampak kecil dapat menjadi perbedaan besar pada nilai akhir setelah sepuluh tahun, terutama pada portofolio yang tumbuh. Karena itu, membaca lembar fakta produk sampai bagian biaya merupakan kebiasaan yang sepadan dengan waktunya.",
        ],
        konteks_indonesia="Reksa dana di Indonesia wajib mencantumkan biaya pengelolaan dan biaya lain dalam prospektus serta fund fact sheet yang diawasi Otoritas Jasa Keuangan. Untuk platform aset kripto domestik, biaya umumnya berbentuk komisi transaksi ditambah pajak final yang dipungut penyelenggara, sehingga struktur biayanya berbeda dari produk pengelolaan dana. Investor sebaiknya menjumlahkan seluruh komponen biaya sebelum membandingkan dua produk yang tampak serupa.",
        tag=["biaya", "reksa-dana", "imbal-hasil", "edukasi"],
    ),
    dict(
        rubrik="analisis-pasar", sinyal="netral",
        entitas=["ray-dalio", "paul-tudor-jones", "robert-kiyosaki"],
        judul="Konsep diversifikasi portofolio ketika aset baru dimasukkan ke dalam alokasi",
        dek="Manfaat diversifikasi bergantung pada korelasi antaraset, dan korelasi itu sendiri berubah menurut kondisi pasar.",
        ringkasan=[
            "Diversifikasi bekerja bila aset tidak bergerak searah pada waktu bersamaan.",
            "Korelasi cenderung meningkat pada periode tekanan pasar.",
            "Ukuran alokasi menentukan seberapa besar pengaruh aset baru terhadap risiko portofolio.",
        ],
        paragraf=[
            "Diversifikasi merupakan salah satu prinsip paling mapan dalam pengelolaan portofolio. Gagasannya adalah menggabungkan aset yang tidak bergerak searah sehingga penurunan pada satu bagian dapat diimbangi bagian lain, dan volatilitas keseluruhan portofolio menjadi lebih rendah daripada rata-rata komponennya.",
            "Ukuran yang dipakai untuk menilai hal itu adalah korelasi. Aset dengan korelasi rendah terhadap portofolio yang sudah ada memberikan manfaat diversifikasi lebih besar dibanding aset yang bergerak seiring. Persoalannya, korelasi bukan angka tetap; ia berubah menurut periode pengukuran dan kondisi pasar.",
            "Pola yang sering diamati adalah korelasi antaraset berisiko cenderung meningkat justru pada saat tekanan pasar, ketika manfaat diversifikasi paling dibutuhkan. Investor yang mengandalkan korelasi historis pada kondisi normal dapat mendapati portofolionya kurang terlindungi pada saat penurunan tajam.",
            "Ukuran alokasi juga menentukan. Aset dengan volatilitas sangat tinggi dapat mendominasi risiko portofolio meski porsinya kecil dari sisi nilai. Perhitungan kontribusi risiko, bukan sekadar bobot nilai, memberi gambaran yang lebih akurat tentang dari mana fluktuasi portofolio sebenarnya berasal.",
            "Kerangka ini tidak menjawab pertanyaan berapa alokasi yang tepat bagi seseorang, karena jawabannya bergantung pada horizon waktu, kebutuhan likuiditas, dan toleransi risiko masing-masing. Yang dapat diberikan kerangka tersebut adalah cara berpikir yang lebih terstruktur ketimbang menilai satu aset secara terpisah.",
        ],
        konteks_indonesia="Bagi investor Indonesia, portofolio umumnya sudah memuat instrumen berdenominasi rupiah seperti deposito, obligasi negara ritel, saham domestik, dan emas. Menambahkan aset berdenominasi dolar memperkenalkan eksposur nilai tukar yang dapat memperbesar maupun meredam fluktuasi, bergantung arah pergerakan rupiah. Perhitungan kontribusi risiko sebaiknya dilakukan dalam rupiah, bukan dalam dolar, agar mencerminkan pengalaman investor yang sesungguhnya.",
        tag=["portofolio", "diversifikasi", "manajemen-risiko", "edukasi"],
    ),
    dict(
        rubrik="pendanaan-dan-ventura", sinyal="netral",
        entitas=["yat-siu", "chris-burniske", "balaji-srinivasan"],
        judul="Membedakan nilai token, nilai jaringan, dan nilai perusahaan penerbitnya",
        dek="Tiga hal ini kerap disamakan dalam pemberitaan, padahal hubungan di antaranya tidak selalu langsung.",
        ringkasan=[
            "Kapitalisasi pasar token bukan ukuran uang yang masuk ke sebuah jaringan.",
            "Nilai jaringan berkaitan dengan penggunaan, bukan semata dengan harga token.",
            "Perusahaan penerbit dan jaringan yang dibangunnya merupakan entitas berbeda.",
        ],
        paragraf=[
            "Pemberitaan sektor aset digital sering menyatukan tiga hal yang sebenarnya terpisah: harga token, nilai jaringan yang digunakannya, dan valuasi perusahaan yang mengembangkannya. Menyamakan ketiganya menghasilkan kesimpulan yang menyesatkan.",
            "Kapitalisasi pasar token dihitung dari harga dikalikan jumlah unit yang beredar. Angka ini bukan jumlah uang yang telah masuk ke dalam sebuah jaringan. Transaksi pada harga tertentu untuk sebagian kecil pasokan dapat mengubah kapitalisasi seluruh pasokan, meski dana yang benar-benar berpindah jauh lebih kecil.",
            "Nilai jaringan berkaitan dengan seberapa banyak aktivitas nyata yang terjadi di atasnya: jumlah pengguna aktif, nilai transaksi yang diselesaikan, dan biaya yang dibayarkan pengguna. Metrik ini dapat bergerak berlawanan dengan harga token dalam periode tertentu, terutama ketika perhatian pasar dipengaruhi faktor spekulatif.",
            "Perusahaan penerbit merupakan entitas hukum tersendiri dengan pendapatan, biaya, dan struktur kepemilikannya sendiri. Perusahaan dapat bernilai tinggi meski token yang terkait dengannya berkinerja lemah, dan sebaliknya. Hak pemegang token terhadap perusahaan umumnya tidak sama dengan hak pemegang saham.",
            "Karena itu, pembaca sebaiknya memeriksa entitas mana yang sedang dibahas sebuah berita: token, jaringan, atau perusahaan. Dokumen resmi seperti kertas kerja teknis dan laporan transparansi biasanya menjelaskan pemisahan tersebut, meski tidak selalu mudah ditemukan.",
        ],
        konteks_indonesia="Otoritas di Indonesia menetapkan daftar aset kripto yang boleh diperdagangkan melalui penyelenggara berizin, dengan proses penilaian yang mempertimbangkan aspek teknologi, tata kelola, dan risiko. Pemisahan antara token, jaringan, dan perusahaan penerbit relevan dalam proses penilaian tersebut. Bagi investor ritel domestik, memeriksa apakah suatu aset termasuk dalam daftar yang diperbolehkan merupakan langkah awal sebelum menelaah aspek fundamentalnya.",
        tag=["token", "valuasi", "jaringan", "edukasi"],
    ),
]


def bangun_artikel(kfg, reg) -> list[Artikel]:
    sekarang = sekarang_wib()
    artikel: list[Artikel] = []
    for i, c in enumerate(CONTOH):
        waktu = sekarang - timedelta(hours=i * 5 + 1)
        entitas = [e for e in c["entitas"] if e in reg.tokoh]
        organisasi = sorted({reg.tokoh[e].org_slug for e in entitas})
        kutipan_teks, kutipan_oleh = c.get("kutipan", ("", ""))
        artikel.append(Artikel(
            id=sidik_jari("demo", c["judul"]),
            slug=slugify(c["judul"], 70),
            judul=c["judul"], dek=c["dek"],
            ringkasan=c["ringkasan"], paragraf=c["paragraf"],
            rubrik=c["rubrik"], tag=c["tag"],
            entitas=entitas, organisasi=organisasi,
            konteks_indonesia=c["konteks_indonesia"],
            sinyal=c["sinyal"], kutipan_teks=kutipan_teks, kutipan_oleh=kutipan_oleh,
            sumber_nama="Artikel penjelas redaksi (data contoh)",
            sumber_url=kfg.base_url + "/tentang/",
            sumber_terbit=waktu.isoformat(), terbit_pada=waktu.isoformat(),
            penulis="Redaksi ManajerDanaKripto", status="terbit", skor=90))
    return artikel


def main(bangun: bool = False, bersihkan: bool = False) -> int:
    kfg, reg = muat_konfigurasi(), registri()
    simpan = buka(kfg)

    if bersihkan:
        for a in bangun_artikel(kfg, reg):
            simpan.hapus_artikel(a.id)
        print("✓ Artikel contoh dihapus dari basis data.")
        return 0

    artikel = bangun_artikel(kfg, reg)
    for a in artikel:
        simpan.simpan_artikel(a)
    print(f"✓ {len(artikel)} artikel contoh dimuat ke {kfg.basis_data.name}")

    if bangun:
        from mdk.build import Pembangun
        pem = Pembangun(kfg, reg, simpan)
        pem.env.globals["mode_demo"] = True         # tampilkan spanduk MODE DEMO
        hasil = pem.bangun(verbose=True)
        print(f"✓ {hasil['halaman']} halaman dibangun ke {hasil['keluaran']}/")
        print("  Pratinjau: python -m mdk sajikan")
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Muat artikel contoh ManajerDanaKripto")
    p.add_argument("--bangun", action="store_true", help="langsung bangun situs setelah memuat")
    p.add_argument("--bersihkan", action="store_true", help="hapus artikel contoh")
    a = p.parse_args()
    raise SystemExit(main(bangun=a.bangun, bersihkan=a.bersihkan))
