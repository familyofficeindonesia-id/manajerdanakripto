"""Penulisan ulang berita menjadi artikel orisinal berbahasa Indonesia.

PRINSIP KEPATUHAN HAK CIPTA (dipaksakan oleh kode, bukan sekadar imbauan):
  1. Model TIDAK menerjemahkan artikel sumber. Model menulis laporan baru
     berdasarkan fakta yang terkandung dalam judul dan ringkasan umpan.
  2. Kutipan langsung dibatasi satu per artikel dan maksimum 14 kata.
     Pelanggaran dipangkas otomatis oleh `_terapkan_pagar_kutipan`.
  3. Setiap artikel wajib menautkan sumber asli dengan atribusi penerbit.
  4. Panjang artikel dibatasi agar tidak menggantikan artikel sumber.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

import requests

from .config import Konfigurasi
from .entities import Registri
from .models import Artikel
from .utils import (hitung_kata, potong, sekarang_wib, sidik_jari, slugify)

# Modul pemutus arus kuota bersifat opsional: bila belum diunggah, penulisan
# tetap berjalan seperti sebelumnya. Ini disengaja agar rewrite.py tidak pernah
# gagal diimpor hanya karena satu berkas pendamping belum ada.
try:
    from . import kuota as _kuota
except ImportError:                                  # pragma: no cover
    _kuota = None

API_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class KesalahanPenulisan(RuntimeError):
    """Model gagal menghasilkan keluaran yang sah."""


class KuotaHabis(KesalahanPenulisan):
    """Kuota harian API tercapai. Percobaan berikutnya pasti gagal juga."""


# Penanda pada pesan galat 429 yang membedakan kuota HARIAN dari batas
# permintaan per menit. Batas per menit layak ditunggu; kuota harian tidak.
#
# CATATAN 3 September 2026 — dipakai HANYA sebagai cadangan terakhir.
# Versi sebelumnya mencocokkan penanda ini terhadap SELURUH badan respons 429.
# Itu keliru: badan respons memuat blok QuotaFailure yang dapat menyebut metrik
# harian walaupun yang benar-benar dilanggar adalah metrik per menit. Satu
# kemunculan substring sudah cukup untuk memasang penanda harian dan mematikan
# penerbitan sampai jendela reset berikutnya — persis yang terjadi pada jalan
# #113, ketika badai percobaan ulang 503 pada artikel pertama menembus RPM 5
# dan 429 per-menit yang menyusul disalahartikan sebagai kuota harian habis.
#
# Sekarang keputusan diambil dari `quotaId` di dalam struktur JSON-nya.
PENANDA_KUOTA_HARIAN = ("perday", "per day", "requests per day", "daily limit")

# Penanda pada `quotaId` yang menandakan metrik PER MENIT. Bila salah satu ini
# muncul, 429 tersebut sesaat dan TIDAK boleh memasang penanda harian, berapa
# pun banyaknya kata "per day" yang tercecer di bagian lain respons.
PENANDA_KUOTA_MENIT = ("perminute", "per minute")


def _baca_pelanggaran_kuota(teks: str) -> tuple[bool, str]:
    """
    Tentukan apakah 429 ini benar-benar kuota HARIAN.

    Kembalikan (harian, keterangan). Sumber kebenarannya berurutan:

      1. `error.details[].violations[].quotaId` — paling tepercaya. Google
         menyebut metrik yang dilanggar secara eksplisit di sini.
      2. `RetryInfo.retryDelay` — bila Google menyuruh mencoba lagi dalam
         hitungan detik, yang dilanggar mustahil kuota harian.
      3. Sapuan substring pada seluruh teks — cadangan terakhir bila JSON tidak
         terbaca sama sekali.

    Saat ragu, kembalikan False. Salah menyimpulkan "per menit" hanya membuang
    beberapa percobaan ulang; salah menyimpulkan "harian" menghentikan seluruh
    penerbitan berjam-jam. Asimetri itu yang menentukan arah default di sini.
    """
    try:
        data = json.loads(teks)
    except (json.JSONDecodeError, TypeError):
        rendah = " ".join(str(teks).split()).lower()
        if any(t in rendah for t in PENANDA_KUOTA_MENIT):
            return False, "quotaId per menit (dari teks)"
        if any(t in rendah for t in PENANDA_KUOTA_HARIAN):
            return True, "penanda harian (dari teks, JSON tidak terbaca)"
        return False, "tidak dapat dipastikan, dianggap per menit"

    rincian = ((data.get("error") or {}).get("details") or [])
    jeda_coba = ""
    id_kuota: list[str] = []

    for butir in rincian:
        if not isinstance(butir, dict):
            continue
        jenis = str(butir.get("@type", ""))
        if "QuotaFailure" in jenis:
            for langgar in (butir.get("violations") or []):
                if isinstance(langgar, dict):
                    id_kuota.append(str(langgar.get("quotaId", "")))
        elif "RetryInfo" in jenis:
            jeda_coba = str(butir.get("retryDelay", ""))

    # 1. quotaId — bukti paling langsung.
    if id_kuota:
        gabung = " ".join(id_kuota).lower()
        if any(t in gabung for t in PENANDA_KUOTA_MENIT):
            return False, f"quotaId per menit: {', '.join(id_kuota)}"
        if any(t in gabung for t in PENANDA_KUOTA_HARIAN):
            return True, f"quotaId harian: {', '.join(id_kuota)}"

    # 2. retryDelay — kuota harian tidak pernah pulih dalam hitungan detik.
    if jeda_coba:
        angka = re.match(r"([\d.]+)s", jeda_coba.strip())
        if angka:
            try:
                if float(angka.group(1)) <= 300:
                    return False, f"retryDelay {jeda_coba} — terlalu pendek"
            except ValueError:
                pass

    return False, "quotaId tidak disebutkan, dianggap per menit"


# Berapa kegagalan kuota berturut-turut sebelum seluruh sisa antrean dilepas.
# Tanpa ambang ini, satu jalan dapat menghabiskan belasan menit hanya untuk
# menabrak tembok yang sama berulang kali.
MAKS_GAGAL_KUOTA_BERUNTUN = 3

# Kelebihan beban server (503) berbeda sifatnya dari kuota habis: ia datang dan
# pergi dalam hitungan detik, jadi layak dicoba ulang. Ambangnya dibuat lebih
# longgar agar satu gelombang kepadatan tidak membatalkan seluruh jalan.
MAKS_GAGAL_SIBUK_BERUNTUN = 8

# Status yang menandakan server sibuk, bukan kesalahan permintaan.
STATUS_SIBUK = (500, 502, 503, 504)

# Penanda pada pesan galat yang menandakan kegagalan SEMENTARA.
#
# Pembedaan ini menentukan nasib sebuah berita. Kegagalan sementara berasal dari
# sisi layanan — server sibuk (5xx), kuota harian tercapai, gangguan jaringan.
# Beritanya sendiri tidak bermasalah, jadi menguburnya sebagai 'gagal' berarti
# membuang berita layak tanpa sebab.
#
# Kegagalan PERMANEN berasal dari isi beritanya — model menilai tidak layak
# tayang, metadata terlalu tipis untuk ditulis, keluaran bukan JSON yang sah.
# Mengulang berita semacam itu hanya membakar kuota untuk hasil yang sama.
_POLA_SEMENTARA = tuple(f"api {k}" for k in STATUS_SIBUK) + (
    "api 429",
    "kuota",
    "dilewati",
    "timeout",
    "timed out",
    "connection",
    "temporarily",
    "overloaded",
    "unavailable",
)


def kegagalan_sementara(pesan: str) -> bool:
    """True bila kegagalan ini pantas dicoba ulang pada jalan berikutnya."""
    p = (pesan or "").lower()
    return any(t in p for t in _POLA_SEMENTARA)


# --------------------------------------------------------------------- prompt -
def bangun_prompt_sistem(kfg: Konfigurasi, reg: Registri) -> str:
    ed = kfg.editorial
    rubrik = "\n".join(f"  - {r['slug']}: {r['label']} — {r['deskripsi']}" for r in kfg.rubrik)
    return f"""Anda adalah redaktur senior ManajerDanaKripto.com, portal berita
berbahasa Indonesia yang meliput manajer dana dan investor institusional aset
kripto global untuk pembaca Indonesia.

TUGAS
Tulis satu artikel berita ORISINAL dalam Bahasa Indonesia formal (ragam
jurnalistik, sesuai PUEBI) berdasarkan metadata berita yang diberikan.

ATURAN HAK CIPTA — WAJIB, TIDAK DAPAT DITAWAR
1. JANGAN menerjemahkan artikel sumber kalimat per kalimat. Tulis laporan baru
   dengan struktur, urutan, dan pilihan kata Anda sendiri.
2. Kutipan langsung maksimum {ed.get('maks_kata_kutipan', 14)} kata dan hanya
   {ed.get('maks_kutipan_per_sumber', 1)} kutipan untuk seluruh artikel. Kutipan
   hanya dipakai bila kata persisnya bermakna (misalnya pernyataan resmi).
   Bila ragu, gunakan parafrase dan kosongkan kolom kutipan.
3. Jangan meniru struktur paragraf atau alur narasi artikel sumber.
4. Jangan mengarang fakta, angka, tanggal, atau pernyataan yang tidak ada dalam
   metadata. Bila sebuah detail tidak tersedia, jangan sebutkan. Lebih baik
   artikel pendek daripada artikel yang berisi karangan.

ATURAN REDAKSI
5. Panjang isi artikel {ed.get('min_kata_artikel', 280)}–{ed.get('maks_kata_artikel', 480)} kata,
   terbagi dalam 4–6 paragraf. Paragraf pertama adalah teras berita (lead) yang
   menjawab apa, siapa, dan mengapa penting.
6. Judul maksimum 90 karakter, informatif, tanpa umpan klik, tanpa huruf kapital
   seluruhnya, dan tanpa tanda seru.
7. Sertakan "konteks_indonesia": 2–3 kalimat yang menjelaskan relevansi bagi
   investor Indonesia — misalnya keterkaitan dengan pengawasan OJK atas aset
   keuangan digital, pajak transaksi kripto, akses melalui pedagang aset kripto
   terdaftar, atau dampak pada likuiditas rupiah dan harga di bursa lokal.
   Bersikap netral dan jangan memberi rekomendasi beli/jual.
8. Nada: tenang, faktual, seperti Bisnis Indonesia atau Kontan. Hindari
   sensasi, hindari kata "cuan", "meroket", "ambyar", dan sejenisnya.
9. Jelaskan istilah teknis secara singkat saat pertama kali muncul.
10. JANGAN memberi nasihat investasi dalam bentuk apa pun.

RUBRIK YANG TERSEDIA (pilih tepat satu, gunakan nilai slug)
{rubrik}

SINYAL POSISI (pilih tepat satu)
  - akumulasi  : tokoh/lembaga menambah eksposur, bersikap konstruktif, atau meluncurkan produk baru
  - netral     : informasi, penjelasan, atau pernyataan tanpa arah posisi yang jelas
  - distribusi : tokoh/lembaga mengurangi eksposur, memperingatkan risiko, atau bersikap negatif

FORMAT KELUARAN
Balas HANYA dengan satu objek JSON yang sah. Tanpa pengantar, tanpa penjelasan,
tanpa pagar kode markdown. Skema:

{{
  "judul": "string",
  "dek": "satu kalimat penjelas di bawah judul, maksimum 160 karakter",
  "ringkasan": ["poin kilat 1", "poin kilat 2", "poin kilat 3"],
  "paragraf": ["paragraf 1", "paragraf 2", "paragraf 3", "paragraf 4"],
  "rubrik": "slug-rubrik",
  "tag": ["3-6 tag pendek huruf kecil"],
  "konteks_indonesia": "2-3 kalimat",
  "sinyal": "akumulasi|netral|distribusi",
  "kutipan_teks": "kutipan langsung maksimum {ed.get('maks_kata_kutipan', 14)} kata, atau string kosong",
  "kutipan_oleh": "nama penutur, atau string kosong",
  "layak_tayang": true
}}

Setel "layak_tayang" menjadi false bila metadata terlalu tipis untuk menulis
artikel yang akurat, bila berita tidak berkaitan dengan pengelolaan dana/aset
kripto, atau bila isinya hanya promosi."""


def bangun_prompt_pengguna(baris: dict, reg: Registri) -> str:
    tokoh = [reg.tokoh[s] for s in json.loads(baris["entitas"] or "[]") if s in reg.tokoh]
    profil = "\n".join(
        f"  - {t.nama} — {t.jabatan}, {t.organisasi} ({t.negara})" for t in tokoh) or "  - (tidak terdeteksi)"
    return f"""METADATA BERITA

Judul sumber (bahasa asli) : {baris['judul']}
Ringkasan umpan            : {baris['ringkasan_sumber'] or '(tidak tersedia)'}
Penerbit                   : {baris['penerbit']}
Waktu terbit sumber        : {baris['terbit_pada']}
URL sumber                 : {baris['url']}

TOKOH TERDETEKSI (gunakan jabatan berikut bila menyebut mereka)
{profil}

Tulis artikel sesuai aturan pada instruksi sistem. Balas hanya dengan JSON."""


# ----------------------------------------------------------------- panggilan --
def panggil_model(kfg: Konfigurasi, sistem: str, pengguna: str) -> str:
    """Panggil Gemini generateContent dan kembalikan teks jawabannya.

    Tingkat gratis Gemini membatasi permintaan per menit, maka kode ini mengulang
    percobaan dengan jeda menaik saat menerima 429 alih-alih langsung menyerah.
    """
    if not kfg.kunci_api:
        raise KesalahanPenulisan(
            "GEMINI_API_KEY belum disetel. Simpan kunci Google AI Studio sebagai "
            "secret repositori bernama GEMINI_API_KEY.")

    model = str(kfg.ai.get("model", "gemini-2.5-flash"))
    url = f"{API_URL}/{model}:generateContent"
    kepala = {"x-goog-api-key": kfg.kunci_api, "content-type": "application/json"}

    muatan: dict[str, Any] = {
        "system_instruction": {"parts": [{"text": sistem}]},
        "contents": [{"role": "user", "parts": [{"text": pengguna}]}],
        "generationConfig": {
            "temperature": float(kfg.ai.get("suhu", 0.3)),
            "maxOutputTokens": int(kfg.ai.get("maks_token", 3000)),
        },
    }

    tanggapan = None
    tunggu = 5.0
    for percobaan in range(4):
        tanggapan = requests.post(url, timeout=120, headers=kepala, json=muatan)

        # Sebagian model menolak thinkingConfig; coba sekali lagi tanpa itu.
        if (tanggapan.status_code == 400
                and "thinking" in tanggapan.text.lower()
                and "thinkingConfig" in muatan["generationConfig"]):
            muatan["generationConfig"].pop("thinkingConfig")
            continue

        # Server sibuk — tunggu sebentar lalu coba lagi. Ini penyebab kegagalan
        # paling sering pada model bertanda "-latest", yang lalu lintasnya padat.
        if tanggapan.status_code in STATUS_SIBUK and percobaan < 3:
            time.sleep(tunggu)
            tunggu *= 1.8
            continue

        if tanggapan.status_code == 429:
            mentah = tanggapan.text
            rinci = " ".join(mentah.split()).lower()
            harian, keterangan = _baca_pelanggaran_kuota(mentah)

            # Badan respons 429 dicetak UTUH. Tanpa ini, `quotaId` tidak pernah
            # tercatat di mana pun dan setiap penyelidikan kuota berhenti pada
            # pesan terpotong yang tidak dapat disimpulkan.
            print(f"  ! 429 diterima — {keterangan}")
            print(f"    {rinci[:900]}")

            # Kuota harian habis: menunggu tidak akan menolong sama sekali.
            if harian:
                raise KuotaHabis(
                    f"API 429 kuota harian habis ({keterangan}): {rinci[:300]}")

            if percobaan < 2:          # batas per menit — layak ditunggu
                # Batas per menit pulih dalam hitungan puluhan detik. Jeda 5
                # detik terlalu pendek: ia hanya menghasilkan 429 berikutnya dan
                # membakar jatah RPM yang justru sedang kita tunggu pulihnya.
                time.sleep(max(tunggu, 20.0))
                tunggu = max(tunggu, 20.0) * 2
                continue
        break

    if tanggapan is None or tanggapan.status_code != 200:
        kode = "tanpa tanggapan" if tanggapan is None else tanggapan.status_code
        rinci = "" if tanggapan is None else " ".join(tanggapan.text.split())[:600]
        raise KesalahanPenulisan(f"API {kode}: {rinci}")

    data = tanggapan.json()
    kandidat = data.get("candidates") or []
    if not kandidat:
        alasan = (data.get("promptFeedback") or {}).get("blockReason", "tidak diketahui")
        raise KesalahanPenulisan(f"Model tidak mengembalikan kandidat (alasan: {alasan})")

    bagian = (kandidat[0].get("content") or {}).get("parts") or []
    teks = "".join(b.get("text", "") for b in bagian if isinstance(b.get("text"), str))
    if not teks.strip():
        raise KesalahanPenulisan(
            f"Keluaran model kosong (finishReason: {kandidat[0].get('finishReason')}). "
            "Coba naikkan `ai.maks_token` di config/settings.yaml.")
    return teks


def urai_json(teks: str) -> dict[str, Any]:
    """Ambil objek JSON dari keluaran model, toleran terhadap pagar kode."""
    teks = (teks or "").strip()
    teks = re.sub(r"^```(?:json)?\s*|\s*```$", "", teks, flags=re.S).strip()
    try:
        return json.loads(teks)
    except json.JSONDecodeError:
        awal, akhir = teks.find("{"), teks.rfind("}")
        if awal == -1 or akhir <= awal:
            raise KesalahanPenulisan(f"Keluaran model bukan JSON: {teks[:200]}")
        return json.loads(teks[awal:akhir + 1])


# ---------------------------------------------------------------- pagar mutu --
# Semua varian tanda kutip yang mungkin dihasilkan model.
_POLA_KUTIPAN = re.compile(r'["\u201c\u2018]([^"\u201c\u201d\u2018\u2019]{25,})["\u201d\u2019]')


def _terapkan_pagar_kutipan(data: dict, kfg: Konfigurasi) -> dict:
    """Terapkan dua batas sekaligus: panjang kutipan dan jumlah kutipan.

    Aturan yang dipaksakan:
      1. Kutipan langsung tidak boleh melebihi `maks_kata_kutipan` kata.
         Kutipan yang melebihi batas DIBUANG, bukan dipotong — memotong akan
         mengubah makna pernyataan narasumber.
      2. Seluruh artikel hanya boleh memuat `maks_kutipan_per_sumber` kutipan.
         Kutipan berlebih di dalam paragraf diturunkan menjadi parafrase dengan
         cara menanggalkan tanda kutipnya.
    """
    maks_kata = int(kfg.editorial.get("maks_kata_kutipan", 14))
    maks_jumlah = int(kfg.editorial.get("maks_kutipan_per_sumber", 1))

    kutipan = (data.get("kutipan_teks") or "").strip().strip('"\u201c\u201d\u2018\u2019')
    if kutipan and hitung_kata(kutipan) > maks_kata:
        kutipan, data["kutipan_oleh"] = "", ""
    data["kutipan_teks"] = kutipan

    # Kuota kutipan yang tersisa untuk badan artikel.
    tersisa = maks_jumlah - (1 if kutipan else 0)

    bersih: list[str] = []
    for paragraf in data.get("paragraf", []):
        for temuan in _POLA_KUTIPAN.findall(paragraf):
            terlalu_panjang = hitung_kata(temuan) > maks_kata
            if terlalu_panjang or tersisa <= 0:
                # Turunkan menjadi parafrase: buang pasangan tanda kutipnya.
                paragraf = re.sub(
                    r'["\u201c\u2018]' + re.escape(temuan) + r'["\u201d\u2019]',
                    temuan, paragraf)
            else:
                tersisa -= 1
        bersih.append(paragraf.strip())

    data["paragraf"] = [p for p in bersih if p]
    return data


def _terapkan_pagar_panjang(data: dict, kfg: Konfigurasi) -> dict:
    maks = int(kfg.editorial.get("maks_kata_artikel", 480))
    paragraf, total = [], 0
    for p in data.get("paragraf", []):
        n = hitung_kata(p)
        if total + n > maks and paragraf:
            break
        paragraf.append(p)
        total += n
    data["paragraf"] = paragraf
    data["judul"] = potong(data.get("judul", "").strip().rstrip("."), 95)
    data["dek"] = potong(data.get("dek", "").strip(), 180)
    data["ringkasan"] = [potong(r, 140) for r in (data.get("ringkasan") or [])[:3]]
    return data


def _terapkan_pagar_taksonomi(data: dict, kfg: Konfigurasi) -> dict:
    if data.get("rubrik") not in kfg.slug_rubrik:
        data["rubrik"] = "berita-utama"
    if data.get("sinyal") not in {"akumulasi", "netral", "distribusi"}:
        data["sinyal"] = "netral"
    data["tag"] = [slugify(t, 30) for t in (data.get("tag") or [])[:6] if t]
    return data


def validasi(data: dict, kfg: Konfigurasi) -> tuple[bool, str]:
    if not data.get("layak_tayang", True):
        return False, "model menilai berita tidak layak tayang"
    if not data.get("judul"):
        return False, "judul kosong"
    total = sum(hitung_kata(p) for p in data.get("paragraf", []))
    minimum = int(kfg.editorial.get("min_kata_artikel", 280))
    if total < minimum * 0.6:
        return False, f"isi terlalu pendek ({total} kata)"
    if kfg.editorial.get("wajib_konteks_indonesia") and not data.get("konteks_indonesia"):
        return False, "konteks Indonesia kosong"
    return True, "ok"


# ------------------------------------------------------------------- publik ---
class Penulis:
    def __init__(self, kfg: Konfigurasi, reg: Registri):
        self.kfg, self.reg = kfg, reg
        self.sistem = bangun_prompt_sistem(kfg, reg)

    def tulis(self, baris: dict) -> Artikel:
        """Ubah satu baris `mentah` menjadi Artikel siap tayang."""
        mentah = panggil_model(self.kfg, self.sistem, bangun_prompt_pengguna(baris, self.reg))
        data = urai_json(mentah)
        data = _terapkan_pagar_kutipan(data, self.kfg)
        data = _terapkan_pagar_panjang(data, self.kfg)
        data = _terapkan_pagar_taksonomi(data, self.kfg)

        sah, alasan = validasi(data, self.kfg)
        if not sah:
            raise KesalahanPenulisan(alasan)

        sekarang = sekarang_wib()
        return Artikel(
            id=sidik_jari(baris["url_kanonik"]),
            slug=f"{slugify(data['judul'], 70)}-{sekarang.strftime('%d%m')}",
            judul=data["judul"], dek=data.get("dek", ""),
            ringkasan=data.get("ringkasan", []), paragraf=data["paragraf"],
            rubrik=data["rubrik"], tag=data["tag"],
            entitas=json.loads(baris["entitas"] or "[]"),
            organisasi=json.loads(baris["organisasi"] or "[]"),
            konteks_indonesia=data.get("konteks_indonesia", ""),
            sinyal=data["sinyal"], kutipan_teks=data.get("kutipan_teks", ""),
            kutipan_oleh=data.get("kutipan_oleh", ""),
            sumber_nama=baris["penerbit"], sumber_url=baris["url"],
            sumber_terbit=baris["terbit_pada"], terbit_pada=sekarang.isoformat(),
            skor=int(baris["skor"] or 0))

    def tulis_banyak(self, baris_list: list, verbose: bool = True) -> tuple[list[Artikel], list[tuple[str, str]]]:
        jeda = float(self.kfg.ai.get("jeda_antar_permintaan_detik", 1.0))
        berhasil: list[Artikel] = []
        gagal: list[tuple[str, str]] = []
        gagal_kuota_beruntun = 0
        gagal_sibuk_beruntun = 0

        for i, baris in enumerate(baris_list, 1):
            b = dict(baris)
            try:
                artikel = self.tulis(b)
                berhasil.append(artikel)
                gagal_kuota_beruntun = gagal_sibuk_beruntun = 0
                if verbose:
                    print(f"  [{i}/{len(baris_list)}] ✓ {artikel.judul[:70]}")
            except (KesalahanPenulisan, requests.RequestException,
                    json.JSONDecodeError) as e:
                pesan = str(e)[:160]
                gagal.append((b["id"], pesan))
                if verbose:
                    print(f"  [{i}/{len(baris_list)}] ✗ {b['judul'][:50]} → {pesan[:70]}")

                # Bedakan kuota habis dari server sibuk — keduanya sementara,
                # tetapi ambang menyerahnya tidak sama.
                if isinstance(e, KuotaHabis):
                    # Kuota HARIAN, bukan batas per menit. Mencoba berita
                    # berikutnya pada jalan yang sama pasti gagal juga dan hanya
                    # membakar sisa kuota. Langsung angkat ke ambang berhenti
                    # alih-alih menunggu tiga kegagalan beruntun.
                    gagal_kuota_beruntun = MAKS_GAGAL_KUOTA_BERUNTUN
                    gagal_sibuk_beruntun = 0

                    # Pasang penanda agar jalan-jalan berikutnya melewati tahap
                    # tulis sepenuhnya sampai kuota reset. Tanpa ini, setiap
                    # jalan berjadwal tetap membakar satu request hanya untuk
                    # menemukan tembok yang sama.
                    #
                    # Penanda HANYA dipasang di cabang ini. Batas per menit juga
                    # bermuatan kode 429, tetapi sifatnya sesaat dan tidak boleh
                    # menghentikan penulisan berjam-jam.
                    if _kuota is not None:
                        try:
                            _kuota.catat_habis(pesan)
                        except Exception as galat:       # noqa: BLE001
                            if verbose:
                                print(f"  ! Penanda kuota gagal dipasang: {galat}")
                elif "429" in pesan:
                    gagal_kuota_beruntun += 1
                    gagal_sibuk_beruntun = 0
                elif any(f"API {k}" in pesan for k in STATUS_SIBUK):
                    gagal_sibuk_beruntun += 1
                    gagal_kuota_beruntun = 0
                else:
                    gagal_kuota_beruntun = gagal_sibuk_beruntun = 0

                sebab = None
                if gagal_kuota_beruntun >= MAKS_GAGAL_KUOTA_BERUNTUN:
                    sebab = (f"Kuota API habis — {gagal_kuota_beruntun} "
                             f"kegagalan beruntun")
                elif gagal_sibuk_beruntun >= MAKS_GAGAL_SIBUK_BERUNTUN:
                    sebab = (f"Server model sibuk terus-menerus — "
                             f"{gagal_sibuk_beruntun} kegagalan beruntun")

                if sebab:
                    sisa = baris_list[i:]
                    if verbose:
                        print(f"\n  ⏹ {sebab}. Menghentikan jalan ini.")
                        print(f"  {len(sisa)} berita sisa dilepas tanpa dicoba; "
                              f"semuanya kembali ke antrean untuk jalan berikutnya.")
                    # Label harus menyebut sebab yang benar: pipeline.py membaca
                    # pesan ini untuk memutuskan apakah item kembali ke antrean.
                    label = ("API 429: dilewati, kuota habis pada jalan ini"
                             if gagal_kuota_beruntun >= MAKS_GAGAL_KUOTA_BERUNTUN
                             else "API 503: dilewati, layanan sibuk pada jalan ini")
                    for lain in sisa:
                        gagal.append((dict(lain)["id"], label))
                    return berhasil, gagal

            time.sleep(jeda)
        return berhasil, gagal
