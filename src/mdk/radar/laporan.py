"""Dasbor HTML pemantauan — satu berkas mandiri, dapat dibuka langsung di peramban."""
from __future__ import annotations

from collections import Counter
from html import escape
from pathlib import Path

from ..utils import format_tanggal_id, potong, sekarang_wib, waktu_relatif_id

TANDA = {"situs_resmi": "Resmi", "sec_edgar": "SEC", "google_news_en": "GN·EN",
         "google_news_id": "GN·ID", "bing_news": "Bing", "youtube": "YT",
         "reddit": "Reddit", "nitter": "X"}


def _gaya() -> str:
    return """
:root{--tinta:#0E1626;--kertas:#EEF1F6;--permukaan:#fff;--garis:#D3DAE6;
--samar:#6B7A94;--rupiah:#0B6E4F;--emas:#B98A22;--turun:#B3392F;
--mono:"IBM Plex Mono",ui-monospace,monospace;--sans:"Archivo",system-ui,sans-serif;
--serif:"Newsreader",Georgia,serif}
*{box-sizing:border-box}
body{margin:0;background:var(--kertas);color:var(--tinta);font-family:var(--sans);
font-size:15px;line-height:1.55;-webkit-font-smoothing:antialiased}
.bungkus{max-width:1180px;margin:auto;padding:28px 20px 64px}
h1{font-family:var(--serif);font-size:30px;letter-spacing:-.02em;margin:0 0 6px}
h2{font-family:var(--serif);font-size:19px;margin:0 0 14px;padding-bottom:8px;
border-bottom:2px solid var(--tinta)}
.jam{font-family:var(--mono);font-size:12px;color:var(--samar)}
.kartu-kisi{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(138px,1fr));margin:22px 0 34px}
.stat{background:var(--permukaan);border:1px solid var(--garis);border-radius:6px;padding:14px}
.stat b{display:block;font-family:var(--mono);font-size:26px;line-height:1.1;letter-spacing:-.03em}
.stat span{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--samar)}
.bagian{margin-bottom:38px}
table{width:100%;border-collapse:collapse;background:var(--permukaan);
border:1px solid var(--garis);border-radius:6px;overflow:hidden;font-size:13.5px}
th{text-align:left;font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;
color:var(--samar);padding:10px 12px;border-bottom:1px solid var(--garis);font-weight:700}
td{padding:11px 12px;border-bottom:1px solid var(--garis);vertical-align:top}
tr:last-child td{border-bottom:0}
tr:hover td{background:#F7F9FC}
a{color:var(--tinta);text-decoration:none}
a:hover{color:var(--rupiah);text-decoration:underline}
.judul{font-family:var(--serif);font-size:15.5px;line-height:1.3;font-weight:600}
.lencana{display:inline-block;padding:2px 7px;border-radius:3px;background:#E3F1EB;
color:#085239;font-family:var(--mono);font-size:10px;font-weight:600;white-space:nowrap}
.lencana.resmi{background:#FBF3E0;color:var(--emas)}
.lencana.mati{background:#FBE9E7;color:var(--turun)}
.entitas{font-size:11.5px;color:var(--samar);margin-top:3px}
.mono{font-family:var(--mono);font-size:11.5px;color:var(--samar);white-space:nowrap}
.batang{height:5px;background:var(--garis);border-radius:3px;overflow:hidden;margin-top:5px;min-width:70px}
.batang i{display:block;height:100%;background:var(--rupiah)}
.kosong{padding:36px;text-align:center;color:var(--samar);background:var(--permukaan);
border:1px dashed var(--garis);border-radius:6px}
.catatan{background:var(--permukaan);border:1px dashed var(--garis);border-radius:6px;
padding:14px;font-size:12.5px;color:var(--samar);line-height:1.6}
@media(max-width:640px){.mono,th.opsional,td.opsional{display:none}}
"""


def bangun_dasbor(kfg, db, reg, organisasi: list[dict], sumber: list,
                  jam: int = 48) -> Path:
    nama = {t.slug: t.nama for t in reg.daftar_tokoh()}
    nama.update({o["slug"]: o["nama"] for o in organisasi})

    stat = db.statistik()
    temuan = db.temuan_terbaru(jam=jam, batas=140)
    kondisi = db.semua_kondisi()

    # --- ringkasan angka ---
    kartu = [
        ("Temuan 24 jam", stat["temuan_24jam"]),
        ("Total temuan", f"{stat['total_temuan']:,}"),
        ("Klaster peristiwa", f"{stat['klaster']:,}"),
        ("Sumber terdaftar", len(sumber)),
        ("Sumber sehat", stat["sumber_aktif"]),
        ("Nonaktif otomatis", stat["sumber_nonaktif"]),
        ("Antre terjemahan", stat["antre_terjemahan"]),
    ]
    blok_kartu = "".join(
        f'<div class="stat"><b>{v}</b><span>{escape(l)}</span></div>' for l, v in kartu)

    # --- tabel temuan ---
    if temuan:
        baris = []
        for t in temuan:
            slug = t.get("entitas", "")
            jenis = t.get("jenis_sumber", "")
            kelas = "lencana resmi" if jenis in ("situs_resmi", "sec_edgar") else "lencana"
            baris.append(f"""<tr>
  <td><div class="judul"><a href="{escape(t.get('url') or '')}" target="_blank" rel="noopener">{escape(potong(t.get('judul') or '', 118))}</a></div>
      <div class="entitas">{escape(nama.get(slug, slug))} · {escape(t.get('penerbit') or '')}</div></td>
  <td class="opsional"><span class="{kelas}">{escape(TANDA.get(jenis, jenis))}</span></td>
  <td class="mono">{escape(f"{float(t.get('skor') or 0):.0f}")}</td>
  <td class="mono">{escape(waktu_relatif_id(t.get('dilihat_pada')))}</td>
  <td class="mono opsional">{'diteruskan' if t.get('diteruskan') else 'antre'}</td>
</tr>""")
        tabel_temuan = ("<table><tr><th>Berita</th><th class='opsional'>Sumber</th>"
                        "<th>Skor</th><th>Ditemukan</th><th class='opsional'>Status</th></tr>"
                        + "".join(baris) + "</table>")
    else:
        tabel_temuan = ('<div class="kosong">Belum ada temuan dalam rentang ini. '
                        'Jalankan <code>python -m mdk radar pantau</code>.</div>')

    # --- sebaran entitas ---
    hitung = Counter(t.get("entitas", "") for t in temuan)
    if hitung:
        maks = max(hitung.values())
        baris = "".join(
            f"<tr><td>{escape(nama.get(s, s))}</td>"
            f"<td class='mono'>{n}</td>"
            f"<td><div class='batang'><i style='width:{n / maks * 100:.0f}%'></i></div></td></tr>"
            for s, n in hitung.most_common(14))
        tabel_entitas = f"<table><tr><th>Entitas</th><th>Temuan</th><th>Sebaran</th></tr>{baris}</table>"
    else:
        tabel_entitas = '<div class="kosong">Belum ada data sebaran.</div>'

    # --- kesehatan sumber ---
    bermasalah = sorted(
        [k for k in kondisi.values() if k.get("gagal_beruntun", 0) > 0 or not k.get("aktif", 1)],
        key=lambda k: -k.get("gagal_beruntun", 0))[:16]
    if bermasalah:
        peta = {s.id: s for s in sumber}
        baris = "".join(
            f"<tr><td>{escape(potong(getattr(peta.get(k['sumber_id']), 'label', k['sumber_id']), 62))}</td>"
            f"<td class='mono'>{k.get('gagal_beruntun', 0)}×</td>"
            f"<td>{'<span class=\"lencana mati\">nonaktif</span>' if not k.get('aktif', 1) else '<span class=\"lencana\">aktif</span>'}</td>"
            f"<td class='mono opsional'>{escape(potong(k.get('galat_terakhir') or '', 40))}</td></tr>"
            for k in bermasalah)
        tabel_kesehatan = ("<table><tr><th>Sumber</th><th>Gagal</th><th>Status</th>"
                           "<th class='opsional'>Galat terakhir</th></tr>" + baris + "</table>")
    else:
        tabel_kesehatan = '<div class="kosong">Seluruh sumber merespons normal.</div>'

    html = f"""<!DOCTYPE html>
<html lang="id"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Radar ManajerDanaKripto — Dasbor Pemantauan</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400..700&family=Archivo:wght@400;600;700&family=IBM+Plex+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>{_gaya()}</style></head>
<body><div class="bungkus">
  <h1>Radar Pemantauan</h1>
  <p class="jam">Dibangkitkan {escape(format_tanggal_id(sekarang_wib()))} · rentang {jam} jam terakhir</p>

  <div class="kartu-kisi">{blok_kartu}</div>

  <div class="bagian"><h2>Temuan Terbaru</h2>{tabel_temuan}</div>
  <div class="bagian"><h2>Sebaran per Entitas</h2>{tabel_entitas}</div>
  <div class="bagian"><h2>Kesehatan Sumber</h2>{tabel_kesehatan}</div>

  <div class="catatan">
    <strong>Cara membaca.</strong> Skor menggabungkan kekuatan penyebutan entitas,
    kesesuaian tema, dan bobot kepercayaan sumber. Temuan bertanda <em>antre</em>
    belum diteruskan ke pipeline penerjemahan; jalankan
    <code>python -m mdk radar teruskan</code> lalu <code>python -m mdk tulis</code>.
    Sumber yang gagal enam kali berturut-turut dinonaktifkan otomatis dan dapat
    dihidupkan kembali lewat <code>mdk radar periksa --semua</code>.
  </div>
</div></body></html>"""

    keluar = kfg.dir_data / "radar"
    keluar.mkdir(parents=True, exist_ok=True)
    jalur = keluar / "dasbor.html"
    jalur.write_text(html, encoding="utf-8")
    return jalur
