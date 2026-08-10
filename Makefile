# ManajerDanaKripto.com — perintah pintasan
PY := python3
export PYTHONPATH := src

.PHONY: help pasang periksa demo ambil tulis bangun jalankan sajikan bersih og \
        radar-bangun radar-temukan radar-periksa radar-pantau radar-jaga radar-dasbor radar-uji

help:            ## tampilkan daftar perintah
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	 awk 'BEGIN{FS=":.*?## "};{printf "  \033[1m%-12s\033[0m %s\n", $$1, $$2}'

mulai:           ## persiapan awal sekali jalan (langkah 1-11 RUNBOOK)
	./mulai.sh

pasang:          ## pasang dependensi
	$(PY) -m pip install -r requirements.txt

periksa:         ## uji kesehatan konfigurasi & templat
	$(PY) -m mdk periksa

demo:            ## muat artikel contoh lalu bangun pratinjau
	$(PY) scripts/seed_demo.py --bangun

ambil:           ## ambil umpan berita ke antrean
	$(PY) -m mdk ambil

tulis:           ## tulis ulang antrean menjadi artikel Indonesia
	$(PY) -m mdk tulis

bangun:          ## bangun situs statis ke dist/
	$(PY) -m mdk bangun

jalankan:        ## pipeline penuh: ambil + tulis + bangun
	$(PY) -m mdk jalankan

sajikan:         ## pratinjau di http://localhost:8000
	$(PY) -m mdk sajikan

og:              ## bangkitkan ulang gambar Open Graph
	$(PY) scripts/buat_og.py

radar-bangun:    ## bangun daftar sumber pemantauan
	$(PY) -m mdk radar bangun

radar-temukan:   ## temukan umpan RSS resmi tiap perusahaan
	$(PY) -m mdk radar temukan

radar-periksa:   ## uji seluruh URL sumber, nonaktifkan yang mati
	$(PY) -m mdk radar periksa --nonaktifkan-mati

radar-pantau:    ## satu putaran pemantauan + teruskan ke antrean
	$(PY) -m mdk radar pantau --teruskan

radar-jaga:      ## pemantauan berkelanjutan (Ctrl+C untuk berhenti)
	$(PY) -m mdk radar jaga --interval 20 --teruskan

radar-dasbor:    ## bangkitkan dasbor HTML pemantauan
	$(PY) -m mdk radar dasbor

radar-uji:       ## uji ujung-ke-ujung radar dengan server tiruan
	$(PY) scripts/uji_radar_lokal.py

pratinjau:       ## gabung situs jadi satu berkas HTML mandiri
	$(PY) scripts/bangun_pratinjau.py

bersih:          ## hapus keluaran build
	rm -rf dist dist-pratinjau
