"""Kanal pengiriman notifikasi.

TUJUH KANAL, semuanya opsional dan dapat dinyalakan bersamaan:
  konsol   — cetak ke terminal (selalu tersedia)
  berkas   — tambahkan ke JSONL + CSV, untuk arsip dan spreadsheet
  rss      — bangkitkan umpan RSS pribadi; berlangganan dari Feedly/Inoreader
  telegram — Bot API sendMessage
  webhook  — POST JSON generik; cocok untuk Slack, Discord, n8n, Zapier, Make
  surel    — ringkasan lewat SMTP
  whatsapp — POST ke penyedia WhatsApp Business API pilihan Anda

Semua kredensial dibaca dari variabel lingkungan, tidak pernah dari berkas
konfigurasi yang ikut terkomit.
"""
from __future__ import annotations

import csv
import json
import os
import smtplib
from abc import ABC, abstractmethod
from email.message import EmailMessage
from html import escape
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

import requests

from ..utils import format_tanggal_id, potong, sekarang_wib

TANDA_JENIS = {
    "situs_resmi": "🏛", "sec_edgar": "📄", "google_news_en": "📰",
    "google_news_id": "🇮🇩", "bing_news": "🔎", "youtube": "▶", "reddit": "💬",
    "nitter": "𝕏",
}


# --------------------------------------------------------------- dasar -------
class Kanal(ABC):
    nama = "dasar"

    def tersedia(self) -> tuple[bool, str]:
        return True, ""

    @abstractmethod
    def kirim(self, klaster: list[dict], konteks: dict) -> tuple[bool, str]:
        ...


def _baris_teks(k: dict, konteks: dict) -> str:
    """Satu klaster sebagai teks polos."""
    nama = konteks["nama_entitas"]
    entitas = ", ".join(nama.get(e, e) for e in k["entitas"][:4]) or "—"
    lain = f" · +{k['jumlah_sumber'] - 1} media lain" if k["jumlah_sumber"] > 1 else ""
    return (f"{k['judul_utama']}\n"
            f"  {entitas}\n"
            f"  {k['penerbit']}{lain} · skor {k['skor']:.0f}\n"
            f"  {k['url_utama']}")


# -------------------------------------------------------------- konsol -------
class KanalKonsol(Kanal):
    nama = "konsol"

    def kirim(self, klaster, konteks):
        if not klaster:
            return True, "tidak ada yang baru"
        print(f"\n\033[1m▸ {len(klaster)} berita baru\033[0m")
        print("─" * 74)
        for k in klaster:
            nama = konteks["nama_entitas"]
            entitas = ", ".join(nama.get(e, e) for e in k["entitas"][:3]) or "—"
            print(f"\n  \033[1m{potong(k['judul_utama'], 92)}\033[0m")
            print(f"  \033[2m{entitas}\033[0m")
            lain = f" · +{k['jumlah_sumber'] - 1} media lain" if k["jumlah_sumber"] > 1 else ""
            print(f"  {k['penerbit']}{lain} · skor {k['skor']:.0f}")
            print(f"  \033[4m{k['url_utama']}\033[0m")
        print()
        return True, f"{len(klaster)} ditampilkan"


# -------------------------------------------------------------- berkas -------
class KanalBerkas(Kanal):
    nama = "berkas"

    def __init__(self, dir_keluar: Path):
        self.dir = Path(dir_keluar)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.jsonl = self.dir / "temuan.jsonl"
        self.csv = self.dir / "temuan.csv"

    def kirim(self, klaster, konteks):
        if not klaster:
            return True, "tidak ada yang baru"
        waktu = sekarang_wib().isoformat()
        nama = konteks["nama_entitas"]

        with self.jsonl.open("a", encoding="utf-8") as f:
            for k in klaster:
                f.write(json.dumps({
                    "waktu": waktu, "klaster": k["id"], "judul": k["judul_utama"],
                    "url": k["url_utama"], "penerbit": k["penerbit"],
                    "entitas": k["entitas"],
                    "nama_entitas": [nama.get(e, e) for e in k["entitas"]],
                    "jumlah_sumber": k["jumlah_sumber"], "skor": k["skor"],
                    "tautan_lain": [{"penerbit": a.penerbit, "url": a.url}
                                    for a in k.get("anggota", [])[1:6]],
                }, ensure_ascii=False) + "\n")

        baru = not self.csv.exists()
        with self.csv.open("a", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            if baru:
                w.writerow(["Waktu", "Judul", "Entitas", "Penerbit",
                            "Jumlah Media", "Skor", "Tautan"])
            for k in klaster:
                w.writerow([format_tanggal_id(waktu), k["judul_utama"],
                            "; ".join(nama.get(e, e) for e in k["entitas"]),
                            k["penerbit"], k["jumlah_sumber"],
                            f"{k['skor']:.0f}", k["url_utama"]])
        return True, f"{len(klaster)} ditulis ke {self.jsonl.name} & {self.csv.name}"


# ----------------------------------------------------------------- rss -------
class KanalRSS(Kanal):
    """Umpan RSS pribadi berisi seluruh temuan — dapat dibuka di pembaca RSS mana pun."""
    nama = "rss"

    def __init__(self, dir_keluar: Path, db, base_url: str = "", batas: int = 120):
        self.jalur = Path(dir_keluar) / "radar.xml"
        self.jalur.parent.mkdir(parents=True, exist_ok=True)
        self.db, self.base_url, self.batas = db, base_url, batas

    def kirim(self, klaster, konteks):
        temuan = self.db.temuan_terbaru(jam=24 * 14, batas=self.batas)
        nama = konteks["nama_entitas"]
        butir = []
        for t in temuan:
            entitas = nama.get(t.get("entitas", ""), t.get("entitas", ""))
            butir.append(f"""    <item>
      <title>{xml_escape(t.get('judul') or '')}</title>
      <link>{xml_escape(t.get('url') or '')}</link>
      <guid isPermaLink="true">{xml_escape(t.get('url') or '')}</guid>
      <description>{xml_escape(f"{entitas} — {t.get('penerbit', '')} · skor {t.get('skor', 0):.0f}")}</description>
      <category>{xml_escape(entitas)}</category>
      <pubDate>{xml_escape(t.get('terbit_pada') or '')}</pubDate>
    </item>""")

        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Radar ManajerDanaKripto — temuan mentah</title>
    <link>{xml_escape(self.base_url or 'https://manajerdanakripto.com')}</link>
    <description>Umpan pribadi berisi berita terbaru tentang tokoh dan perusahaan yang dipantau. Belum diterjemahkan.</description>
    <language>en</language>
    <lastBuildDate>{sekarang_wib().strftime('%a, %d %b %Y %H:%M:%S %z')}</lastBuildDate>
{chr(10).join(butir)}
  </channel>
</rss>
"""
        self.jalur.write_text(xml, encoding="utf-8")
        return True, f"{len(butir)} butir → {self.jalur}"


# ------------------------------------------------------------ telegram -------
class KanalTelegram(Kanal):
    nama = "telegram"

    def __init__(self):
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat = os.environ.get("TELEGRAM_CHAT_ID", "")

    def tersedia(self):
        if not self.token or not self.chat:
            return False, "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID belum disetel"
        return True, ""

    def _pesan(self, k: dict, konteks: dict) -> str:
        nama = konteks["nama_entitas"]
        entitas = ", ".join(escape(nama.get(e, e)) for e in k["entitas"][:4]) or "—"
        tanda = TANDA_JENIS.get(k.get("jenis_sumber", ""), "📰")
        lain = (f"\n<i>Juga diberitakan {k['jumlah_sumber'] - 1} media lain</i>"
                if k["jumlah_sumber"] > 1 else "")
        return (f"{tanda} <b>{escape(potong(k['judul_utama'], 200))}</b>\n\n"
                f"👤 {entitas}\n"
                f"📡 {escape(k['penerbit'])} · skor {k['skor']:.0f}{lain}\n\n"
                f"<a href=\"{escape(k['url_utama'])}\">Buka sumber asli</a>")

    def kirim(self, klaster, konteks):
        siap, alasan = self.tersedia()
        if not siap:
            return False, alasan
        terkirim, gagal = 0, 0
        for k in klaster[:20]:              # jangan membanjiri obrolan
            try:
                r = requests.post(
                    f"https://api.telegram.org/bot{self.token}/sendMessage",
                    json={"chat_id": self.chat, "text": self._pesan(k, konteks),
                          "parse_mode": "HTML", "disable_web_page_preview": False},
                    timeout=20)
                terkirim += 1 if r.status_code == 200 else 0
                gagal += 0 if r.status_code == 200 else 1
            except requests.RequestException:
                gagal += 1
        return gagal == 0, f"{terkirim} terkirim, {gagal} gagal"


# ------------------------------------------------------------- webhook -------
class KanalWebhook(Kanal):
    """POST JSON generik. Slack dan Discord memakai kunci `text`/`content`."""
    nama = "webhook"

    def __init__(self):
        self.url = os.environ.get("RADAR_WEBHOOK_URL", "")
        self.gaya = os.environ.get("RADAR_WEBHOOK_GAYA", "generik").lower()

    def tersedia(self):
        return (bool(self.url), "" if self.url else "RADAR_WEBHOOK_URL belum disetel")

    def _muatan(self, klaster, konteks):
        nama = konteks["nama_entitas"]
        if self.gaya == "slack":
            baris = [f"*{k['judul_utama']}*\n<{k['url_utama']}|{k['penerbit']}> · "
                     f"{', '.join(nama.get(e, e) for e in k['entitas'][:3])}"
                     for k in klaster[:20]]
            return {"text": f"*{len(klaster)} berita baru*\n\n" + "\n\n".join(baris)}
        if self.gaya == "discord":
            baris = [f"**{potong(k['judul_utama'], 150)}**\n{k['url_utama']}"
                     for k in klaster[:10]]
            return {"content": f"**{len(klaster)} berita baru**\n\n" + "\n\n".join(baris)}
        return {"sumber": "radar-manajerdanakripto",
                "waktu": sekarang_wib().isoformat(),
                "jumlah": len(klaster),
                "temuan": [{"judul": k["judul_utama"], "url": k["url_utama"],
                            "penerbit": k["penerbit"], "skor": k["skor"],
                            "entitas": [nama.get(e, e) for e in k["entitas"]],
                            "jumlah_media": k["jumlah_sumber"]} for k in klaster]}

    def kirim(self, klaster, konteks):
        siap, alasan = self.tersedia()
        if not siap:
            return False, alasan
        try:
            r = requests.post(self.url, json=self._muatan(klaster, konteks), timeout=25)
            ok = 200 <= r.status_code < 300
            return ok, f"HTTP {r.status_code}"
        except requests.RequestException as e:
            return False, f"{type(e).__name__}"


# --------------------------------------------------------------- surel -------
class KanalSurel(Kanal):
    nama = "surel"

    def __init__(self):
        self.host = os.environ.get("SMTP_HOST", "")
        self.port = int(os.environ.get("SMTP_PORT", "587"))
        self.pengguna = os.environ.get("SMTP_USER", "")
        self.sandi = os.environ.get("SMTP_PASSWORD", "")
        self.dari = os.environ.get("RADAR_EMAIL_DARI", self.pengguna)
        self.ke = [a.strip() for a in os.environ.get("RADAR_EMAIL_KE", "").split(",") if a.strip()]

    def tersedia(self):
        if not (self.host and self.pengguna and self.sandi and self.ke):
            return False, "SMTP_HOST / SMTP_USER / SMTP_PASSWORD / RADAR_EMAIL_KE belum lengkap"
        return True, ""

    def _html(self, klaster, konteks):
        nama = konteks["nama_entitas"]
        blok = []
        for k in klaster:
            entitas = ", ".join(escape(nama.get(e, e)) for e in k["entitas"][:4]) or "—"
            lain = (f" · +{k['jumlah_sumber'] - 1} media lain" if k["jumlah_sumber"] > 1 else "")
            blok.append(f"""
      <tr><td style="padding:16px 0;border-bottom:1px solid #D3DAE6">
        <div style="font:600 11px/1 Arial;letter-spacing:.1em;text-transform:uppercase;color:#0B6E4F">{entitas}</div>
        <div style="font:600 17px/1.3 Georgia,serif;margin:8px 0"><a href="{escape(k['url_utama'])}" style="color:#0E1626;text-decoration:none">{escape(k['judul_utama'])}</a></div>
        <div style="font:12px/1.4 Arial;color:#6B7A94">{escape(k['penerbit'])}{lain} · skor {k['skor']:.0f}</div>
      </td></tr>""")
        return f"""<html><body style="margin:0;background:#EEF1F6;padding:24px">
  <table style="max-width:640px;margin:auto;background:#fff;border-radius:8px;padding:28px" cellpadding="0" cellspacing="0">
    <tr><td>
      <div style="font:700 20px/1 Georgia,serif;color:#0E1626">Radar ManajerDanaKripto</div>
      <div style="font:12px/1.5 Arial;color:#6B7A94;margin-top:6px">
        {len(klaster)} berita baru · {escape(format_tanggal_id(sekarang_wib()))}
      </div>
    </td></tr>
    {''.join(blok)}
    <tr><td style="padding-top:20px;font:11px/1.5 Arial;color:#6B7A94">
      Notifikasi otomatis dari sistem pemantauan internal. Tautan mengarah ke penerbit aslinya.
    </td></tr>
  </table></body></html>"""

    def kirim(self, klaster, konteks):
        siap, alasan = self.tersedia()
        if not siap:
            return False, alasan
        if not klaster:
            return True, "tidak ada yang baru"
        pesan = EmailMessage()
        pesan["Subject"] = f"[Radar] {len(klaster)} berita baru manajer dana kripto"
        pesan["From"], pesan["To"] = self.dari, ", ".join(self.ke)
        pesan.set_content("\n\n".join(_baris_teks(k, konteks) for k in klaster))
        pesan.add_alternative(self._html(klaster, konteks), subtype="html")
        try:
            with smtplib.SMTP(self.host, self.port, timeout=30) as smtp:
                smtp.starttls()
                smtp.login(self.pengguna, self.sandi)
                smtp.send_message(pesan)
            return True, f"terkirim ke {len(self.ke)} alamat"
        except (smtplib.SMTPException, OSError) as e:
            return False, f"{type(e).__name__}: {e}"


# ------------------------------------------------------------ whatsapp -------
class KanalWhatsApp(Kanal):
    """Pengiriman lewat WhatsApp Business API (Meta Cloud API atau penyedia lokal)."""
    nama = "whatsapp"

    def __init__(self):
        self.url = os.environ.get("WHATSAPP_API_URL", "")
        self.token = os.environ.get("WHATSAPP_TOKEN", "")
        self.tujuan = os.environ.get("WHATSAPP_TUJUAN", "")

    def tersedia(self):
        if not (self.url and self.token and self.tujuan):
            return False, "WHATSAPP_API_URL / WHATSAPP_TOKEN / WHATSAPP_TUJUAN belum disetel"
        return True, ""

    def kirim(self, klaster, konteks):
        siap, alasan = self.tersedia()
        if not siap:
            return False, alasan
        nama = konteks["nama_entitas"]
        baris = []
        for k in klaster[:8]:
            entitas = ", ".join(nama.get(e, e) for e in k["entitas"][:2]) or "—"
            baris.append(f"*{potong(k['judul_utama'], 120)}*\n{entitas} · {k['penerbit']}\n{k['url_utama']}")
        teks = f"*Radar — {len(klaster)} berita baru*\n\n" + "\n\n".join(baris)
        try:
            r = requests.post(
                self.url,
                headers={"Authorization": f"Bearer {self.token}",
                         "Content-Type": "application/json"},
                json={"messaging_product": "whatsapp", "to": self.tujuan,
                      "type": "text", "text": {"preview_url": True, "body": teks}},
                timeout=25)
            return 200 <= r.status_code < 300, f"HTTP {r.status_code}"
        except requests.RequestException as e:
            return False, type(e).__name__


# ------------------------------------------------------------ pengirim -------
class Pengirim:
    """Menyalurkan klaster ke seluruh kanal aktif, dengan pencegahan kirim ganda."""

    def __init__(self, kfg, db, reg, organisasi: list[dict]):
        self.kfg, self.db = kfg, db
        opsi = getattr(kfg, "radar", {}) or {}
        dir_keluar = kfg.dir_data / "radar"
        aktif = opsi.get("kanal", ["konsol", "berkas", "rss"])

        pabrik = {
            "konsol": lambda: KanalKonsol(),
            "berkas": lambda: KanalBerkas(dir_keluar),
            "rss": lambda: KanalRSS(dir_keluar, db, kfg.base_url),
            "telegram": lambda: KanalTelegram(),
            "webhook": lambda: KanalWebhook(),
            "surel": lambda: KanalSurel(),
            "whatsapp": lambda: KanalWhatsApp(),
        }
        self.kanal: list[Kanal] = [pabrik[n]() for n in aktif if n in pabrik]

        nama_entitas = {t.slug: t.nama for t in reg.daftar_tokoh()}
        nama_entitas.update({o["slug"]: o["nama"] for o in organisasi})
        self.konteks = {"nama_entitas": nama_entitas}
        self.skor_minimum = float(opsi.get("skor_minimum_notifikasi", 45))

    def status_kanal(self) -> list[tuple[str, bool, str]]:
        return [(k.nama, *k.tersedia()) for k in self.kanal]

    def salurkan(self, klaster: list[dict], verbose: bool = True) -> dict:
        layak = [k for k in klaster
                 if not k.get("lanjutan") and k.get("skor", 0) >= self.skor_minimum]
        hasil: dict[str, str] = {}

        for kanal in self.kanal:
            # Kanal ringkasan (rss) selalu dibangkitkan ulang meski tidak ada yang baru.
            if not layak and kanal.nama != "rss":
                hasil[kanal.nama] = "dilewati (tidak ada yang baru)"
                continue

            belum = [k for k in layak if not self.db.sudah_dikirim(k["id"], kanal.nama)]
            if not belum and kanal.nama != "rss":
                hasil[kanal.nama] = "dilewati (sudah pernah dikirim)"
                continue

            ok, pesan = kanal.kirim(belum, self.konteks)
            hasil[kanal.nama] = pesan
            for k in belum:
                self.db.catat_notifikasi(k["id"], kanal.nama,
                                         "terkirim" if ok else "gagal", pesan)
            if verbose and kanal.nama != "konsol":
                print(f"    {'✓' if ok else '✗'} {kanal.nama:<9} {pesan}")

        self.db.tandai_dinotifikasi([k["id"] for k in layak])
        return hasil
