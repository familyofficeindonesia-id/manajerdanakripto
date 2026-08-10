"""Bangkitkan gambar Open Graph bawaan (1200x630) untuk pratinjau media sosial.

Jalankan ulang bila identitas visual berubah:  python scripts/buat_og.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

TINTA, KERTAS, RUPIAH, EMAS = (14, 22, 38), (238, 241, 246), (11, 110, 79), (185, 138, 34)
KELUAR = Path(__file__).resolve().parents[1] / "static" / "img" / "og-default.png"


def _fon(ukuran: int, tebal: bool = False):
    kandidat = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf" if tebal
        else "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for j in kandidat:
        if Path(j).exists():
            return ImageFont.truetype(j, ukuran)
    return ImageFont.load_default()


def bangun() -> Path:
    gbr = Image.new("RGB", (1200, 630), TINTA)
    d = ImageDraw.Draw(gbr)

    # pita aksen atas — mengutip elemen "Pita Manajer" di situs
    d.rectangle([0, 0, 1200, 10], fill=RUPIAH)
    for i in range(0, 1200, 150):
        d.rectangle([i, 0, i + 3, 10], fill=TINTA)

    d.text((72, 96), "MANAJER DANA KRIPTO", font=_fon(26), fill=EMAS)
    d.text((72, 168), "Lensa Indonesia atas", font=_fon(72, True), fill=KERTAS)
    d.text((72, 258), "pergerakan manajer", font=_fon(72, True), fill=KERTAS)
    d.text((72, 348), "dana kripto dunia.", font=_fon(72, True), fill=RUPIAH)

    d.line([72, 470, 1128, 470], fill=(60, 74, 98), width=1)
    d.text((72, 500), "manajerdanakripto.com", font=_fon(30), fill=KERTAS)
    d.text((72, 546), "Berita · Analisis · Direktori 64 manajer dana global",
           font=_fon(24), fill=(140, 155, 180))

    KELUAR.parent.mkdir(parents=True, exist_ok=True)
    gbr.save(KELUAR, "PNG", optimize=True)
    return KELUAR


if __name__ == "__main__":
    print(f"Gambar Open Graph ditulis ke: {bangun()}")
