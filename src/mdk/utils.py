"""Utilitas bersama: slug, kanonikalisasi URL, waktu, dan format angka."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

WIB = timezone(timedelta(hours=7))

_BULAN_ID = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
    7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember",
}
_HARI_ID = {0: "Senin", 1: "Selasa", 2: "Rabu", 3: "Kamis", 4: "Jumat", 5: "Sabtu", 6: "Minggu"}

# Parameter pelacakan yang dibuang saat kanonikalisasi URL.
_PARAM_SAMPAH = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source", "__source",
    "amp", "at_medium", "at_campaign", "ito", "cmpid", "sh",
}


def slugify(teks: str, maks: int = 80) -> str:
    """Ubah teks bebas menjadi slug URL yang aman."""
    teks = unicodedata.normalize("NFKD", str(teks))
    teks = teks.encode("ascii", "ignore").decode("ascii").lower()
    teks = re.sub(r"[^a-z0-9]+", "-", teks).strip("-")
    teks = re.sub(r"-{2,}", "-", teks)
    if len(teks) > maks:
        teks = teks[:maks].rsplit("-", 1)[0]
    return teks or "artikel"


def kanonikalisasi_url(url: str) -> str:
    """Buang parameter pelacakan dan normalkan URL untuk keperluan deduplikasi."""
    if not url:
        return ""
    try:
        p = urlparse(url.strip())
    except ValueError:
        return url.strip()
    kueri = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=False)
             if k.lower() not in _PARAM_SAMPAH]
    host = (p.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    jalur = p.path.rstrip("/") or "/"
    return urlunparse((p.scheme or "https", host, jalur, "", urlencode(sorted(kueri)), ""))


def sidik_jari(*bagian: str) -> str:
    """Hash stabil 16 karakter untuk identitas artikel."""
    h = hashlib.sha256("||".join(str(b or "") for b in bagian).encode("utf-8"))
    return h.hexdigest()[:16]


def sekarang_wib() -> datetime:
    return datetime.now(tz=WIB)


def ke_wib(dt):
    if dt is None:
        return None
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(WIB)


def format_tanggal_id(dt, dengan_jam: bool = True) -> str:
    """'Jumat, 7 Agustus 2026 · 14.05 WIB'"""
    dt = ke_wib(dt)
    if dt is None:
        return ""
    dasar = f"{_HARI_ID[dt.weekday()]}, {dt.day} {_BULAN_ID[dt.month]} {dt.year}"
    return f"{dasar} · {dt.strftime('%H.%M')} WIB" if dengan_jam else dasar


def waktu_relatif_id(dt) -> str:
    """'12 menit lalu', '3 jam lalu', '2 hari lalu'."""
    dt = ke_wib(dt)
    if dt is None:
        return ""
    detik = max((sekarang_wib() - dt).total_seconds(), 0)
    if detik < 60:
        return "baru saja"
    if detik < 3600:
        return f"{int(detik // 60)} menit lalu"
    if detik < 86400:
        return f"{int(detik // 3600)} jam lalu"
    if detik < 604800:
        return f"{int(detik // 86400)} hari lalu"
    return format_tanggal_id(dt, dengan_jam=False)


def hitung_kata(teks: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", teks or ""))


def waktu_baca(teks: str, kpm: int = 200) -> int:
    """Perkiraan waktu baca dalam menit."""
    return max(1, round(hitung_kata(teks) / kpm))


def rupiah(nilai, desimal: int = 0) -> str:
    """1234567 -> 'Rp1.234.567'"""
    try:
        s = f"{float(nilai):,.{desimal}f}"
    except (TypeError, ValueError):
        return "-"
    return "Rp" + s.replace(",", "#").replace(".", ",").replace("#", ".")


def angka_id(nilai, desimal: int = 0) -> str:
    try:
        s = f"{float(nilai):,.{desimal}f}"
    except (TypeError, ValueError):
        return "-"
    return s.replace(",", "#").replace(".", ",").replace("#", ".")


def potong(teks: str, maks: int = 160) -> str:
    teks = re.sub(r"\s+", " ", (teks or "")).strip()
    return teks if len(teks) <= maks else teks[: maks - 1].rsplit(" ", 1)[0] + "…"


def bersihkan_html(teks: str) -> str:
    """Buang tag HTML dari ringkasan umpan RSS."""
    teks = re.sub(r"<script.*?</script>", " ", teks or "", flags=re.S | re.I)
    teks = re.sub(r"<style.*?</style>", " ", teks, flags=re.S | re.I)
    teks = re.sub(r"<[^>]+>", " ", teks)
    teks = (teks.replace("&nbsp;", " ").replace("&amp;", "&")
                .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
                .replace("&#39;", "'").replace("&#x27;", "'"))
    return re.sub(r"\s+", " ", teks).strip()


def domain_penerbit(url: str) -> str:
    host = urlparse(url or "").netloc.lower()
    return host[4:] if host.startswith("www.") else host
