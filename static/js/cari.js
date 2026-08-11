/* Pencarian sisi klien atas indeks JSON yang dibangkitkan saat build. */
(function () {
  'use strict';

  var kotak = document.getElementById('kotak-cari');
  var wadah = document.getElementById('hasil-cari');
  var pesan = document.getElementById('pesan-cari');
  var jumlah = document.getElementById('jumlah-hasil');
  if (!kotak || !wadah) return;

  var indeks = [];
  var rubrikAktif = '';

  fetch('/indeks-cari.json')
    .then(function (r) { return r.json(); })
    .then(function (j) {
      indeks = j.artikel || [];
      if (jumlah) jumlah.textContent = indeks.length + ' artikel dalam arsip';
      terapkanKueriURL();
    })
    .catch(function () { pesan.textContent = 'Indeks pencarian belum tersedia.'; });

  function skor(a, kata) {
    var judul = a.judul.toLowerCase();
    var badan = (a.teks || '').toLowerCase();
    var nilai = 0;
    for (var i = 0; i < kata.length; i++) {
      var k = kata[i];
      if (judul.indexOf(k) !== -1) nilai += 10;
      if (badan.indexOf(k) !== -1) nilai += 3;
      if ((a.tokoh || '').toLowerCase().indexOf(k) !== -1) nilai += 6;
      if ((a.tag || '').toLowerCase().indexOf(k) !== -1) nilai += 4;
    }
    return nilai;
  }

  function cari(kueri) {
    var kata = kueri.toLowerCase().split(/\s+/).filter(Boolean);
    if (!kata.length) return [];
    return indeks
      .filter(function (a) { return !rubrikAktif || a.rubrik === rubrikAktif; })
      .map(function (a) { return { a: a, s: skor(a, kata) }; })
      .filter(function (x) { return x.s > 0; })
      .sort(function (x, y) { return y.s - x.s || (y.a.waktu > x.a.waktu ? 1 : -1); })
      .slice(0, 36)
      .map(function (x) { return x.a; });
  }

  function amankan(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function gambar(hasil) {
    wadah.innerHTML = hasil.map(function (a) {
      return '<article class="kartu">' +
        '<div style="display:flex;align-items:center;justify-content:space-between;gap:.75rem">' +
        '<span class="lencana-rubrik" data-rubrik="' + amankan(a.rubrik) + '">' + amankan(a.rubrik_label) + '</span>' +
        '<span class="sinyal" data-sinyal="' + amankan(a.sinyal) + '">' + amankan(a.sinyal_tanda) + '</span></div>' +
        '<h3 class="kartu__judul"><a href="' + amankan(a.url) + '">' + amankan(a.judul) + '</a></h3>' +
        '<p class="kartu__dek">' + amankan(a.dek || '') + '</p>' +
        '<div class="kartu__kaki"><span class="meta">' + amankan(a.tanggal) + '</span>' +
        '<span class="meta">' + amankan(a.tokoh || '') + '</span></div></article>';
    }).join('');
  }

  function jalankan() {
    var kueri = kotak.value.trim();
    if (!kueri) {
      wadah.innerHTML = '';
      pesan.hidden = false;
      pesan.textContent = 'Ketik kata kunci untuk mulai mencari.';
      return;
    }
    var hasil = cari(kueri);
    gambar(hasil);
    pesan.hidden = hasil.length > 0;
    if (!hasil.length) pesan.textContent = 'Tidak ada artikel yang cocok dengan “' + kueri + '”.';
    if (jumlah) jumlah.textContent = hasil.length + ' hasil ditemukan';
    var url = new URL(window.location);
    url.searchParams.set('q', kueri);
    history.replaceState(null, '', url);
  }

  function terapkanKueriURL() {
    var q = new URLSearchParams(window.location.search).get('q');
    if (q) { kotak.value = q; jalankan(); }
  }

  var tunda;
  kotak.addEventListener('input', function () {
    clearTimeout(tunda);
    tunda = setTimeout(jalankan, 140);
  });

  document.querySelectorAll('[data-rubrik]').forEach(function (b) {
    if (b.tagName !== 'BUTTON') return;
    b.addEventListener('click', function () {
      document.querySelectorAll('button[data-rubrik]').forEach(function (x) {
        x.setAttribute('aria-pressed', 'false');
      });
      b.setAttribute('aria-pressed', 'true');
      rubrikAktif = b.getAttribute('data-rubrik');
      jalankan();
    });
  });
})();
