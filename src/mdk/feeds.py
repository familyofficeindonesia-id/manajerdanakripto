"""Pembangkit umpan mesin: RSS, sitemap, sitemap berita, robots, indeks pencarian."""
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from xml.sax.saxutils import escape

from .models import Artikel
from .utils import ke_wib, potong, sekarang_wib

TANDA_SINYAL = {"akumulasi": "▲", "distribusi": "▼", "netral": "▬"}


def _rfc822(iso: str) -> str:
    dt = ke_wib(iso) or sekarang_wib()
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")


def tulis_rss(artikel: list[Artikel], kfg, dir_keluar: Path, batas: int = 50) -> Path:
    """Umpan RSS 2.0 berisi ringkasan — tidak pernah memuat isi artikel penuh."""
    situs, base = kfg.situs, kfg.base_url
    butir = []
    for a in artikel[:batas]:
        deskripsi = a.dek or (a.ringkasan[0] if a.ringkasan else "")
        butir.append(f"""    <item>
      <title>{escape(a.judul)}</title>
      <link>{base}{a.url}</link>
      <guid isPermaLink="true">{base}{a.url}</guid>
      <description>{escape(potong(deskripsi, 300))}</description>
      <category>{escape(kfg.rubrik_by_slug(a.rubrik)['label'])}</category>
      <pubDate>{_rfc822(a.terbit_pada)}</pubDate>
      <source url="{escape(a.sumber_url)}">{escape(a.sumber_nama)}</source>
    </item>""")

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{escape(situs['nama'])}</title>
    <link>{base}/</link>
    <atom:link href="{base}/rss.xml" rel="self" type="application/rss+xml"/>
    <description>{escape(situs['deskripsi'])}</description>
    <language>id-ID</language>
    <copyright>© {sekarang_wib().year} {escape(situs['penerbit'])}</copyright>
    <lastBuildDate>{_rfc822(sekarang_wib().isoformat())}</lastBuildDate>
    <ttl>30</ttl>
{chr(10).join(butir)}
  </channel>
</rss>
"""
    jalur = dir_keluar / "rss.xml"
    jalur.write_text(xml, encoding="utf-8")
    return jalur


def tulis_sitemap(url_list: list[tuple[str, str, str]], kfg, dir_keluar: Path) -> Path:
    """url_list: (jalur, waktu_iso, prioritas)"""
    base = kfg.base_url
    baris = []
    for jalur, waktu, prioritas in url_list:
        dt = ke_wib(waktu) or sekarang_wib()
        baris.append(f"""  <url>
    <loc>{base}{jalur}</loc>
    <lastmod>{dt.strftime('%Y-%m-%d')}</lastmod>
    <priority>{prioritas}</priority>
  </url>""")
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "\n".join(baris) + "\n</urlset>\n")
    jalur = dir_keluar / "sitemap.xml"
    jalur.write_text(xml, encoding="utf-8")
    return jalur


def tulis_sitemap_berita(artikel: list[Artikel], kfg, dir_keluar: Path) -> Path:
    """Sitemap Google News — hanya artikel dua hari terakhir, sesuai spesifikasi."""
    base, nama = kfg.base_url, kfg.situs["nama"]
    batas = sekarang_wib() - timedelta(days=2)
    baris = []
    for a in artikel:
        dt = ke_wib(a.terbit_pada)
        if not dt or dt < batas:
            continue
        baris.append(f"""  <url>
    <loc>{base}{a.url}</loc>
    <news:news>
      <news:publication>
        <news:name>{escape(nama)}</news:name>
        <news:language>id</news:language>
      </news:publication>
      <news:publication_date>{dt.isoformat()}</news:publication_date>
      <news:title>{escape(a.judul)}</news:title>
    </news:news>
  </url>""")
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
           '        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">\n'
           + "\n".join(baris) + "\n</urlset>\n")
    jalur = dir_keluar / "sitemap-berita.xml"
    jalur.write_text(xml, encoding="utf-8")
    return jalur


def tulis_robots(kfg, dir_keluar: Path) -> Path:
    base = kfg.base_url
    isi = f"""User-agent: *
Allow: /
Disallow: /cari/?

Sitemap: {base}/sitemap.xml
Sitemap: {base}/sitemap-berita.xml
"""
    jalur = dir_keluar / "robots.txt"
    jalur.write_text(isi, encoding="utf-8")
    return jalur


def tulis_indeks_cari(artikel: list[Artikel], kfg, reg, dir_keluar: Path) -> Path:
    """Indeks ringan untuk pencarian sisi klien (tanpa isi artikel penuh)."""
    from .utils import format_tanggal_id

    data = []
    for a in artikel:
        nama_tokoh = ", ".join(reg.tokoh[s].nama for s in a.entitas if s in reg.tokoh)
        data.append({
            "judul": a.judul,
            "dek": potong(a.dek, 150),
            "url": a.url,
            "rubrik": a.rubrik,
            "rubrik_label": kfg.rubrik_by_slug(a.rubrik)["label"],
            "sinyal": a.sinyal,
            "sinyal_tanda": TANDA_SINYAL.get(a.sinyal, "▬"),
            "tokoh": nama_tokoh,
            "tag": " ".join(a.tag),
            "teks": potong(" ".join(a.ringkasan), 260),
            "tanggal": format_tanggal_id(a.terbit_pada, dengan_jam=False),
            "waktu": a.terbit_pada,
        })
    jalur = dir_keluar / "indeks-cari.json"
    jalur.write_text(json.dumps({"artikel": data}, ensure_ascii=False), encoding="utf-8")
    return jalur
