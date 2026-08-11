/* ==========================================================================
   ManajerDanaKripto.com — skrip antarmuka
   Ringan, tanpa kerangka kerja, tanpa pelacak pihak ketiga.
   ========================================================================== */
(function () {
  'use strict';

  /* ---------------------------------------------------------- ganti tema -- */
  var tombolTema = document.getElementById('ganti-tema');
  if (tombolTema) {
    tombolTema.addEventListener('click', function () {
      var akar = document.documentElement;
      var baru = akar.getAttribute('data-tema') === 'gelap' ? 'terang' : 'gelap';
      akar.setAttribute('data-tema', baru);
      try { localStorage.setItem('mdk-tema', baru); } catch (e) {}
      tombolTema.setAttribute('aria-label',
        baru === 'gelap' ? 'Beralih ke mode terang' : 'Beralih ke mode gelap');
    });
  }

  /* -------------------------------------------------------- salin tautan -- */
  document.addEventListener('click', function (ev) {
    var t = ev.target.closest('[data-salin-tautan]');
    if (!t) return;
    var tautan = t.getAttribute('data-salin-tautan');
    var asli = t.textContent;
    var selesai = function () {
      t.textContent = 'Tautan disalin';
      setTimeout(function () { t.textContent = asli; }, 2000);
    };
    if (navigator.clipboard) {
      navigator.clipboard.writeText(tautan).then(selesai, selesai);
    } else {
      var kotak = document.createElement('textarea');
      kotak.value = tautan; document.body.appendChild(kotak); kotak.select();
      try { document.execCommand('copy'); } catch (e) {}
      document.body.removeChild(kotak); selesai();
    }
  });

  /* -------------------------------------------- saring daftar di halaman -- */
  document.querySelectorAll('[data-saring]').forEach(function (input) {
    var pemilih = input.getAttribute('data-saring');
    var kosong = document.getElementById('tokoh-kosong');
    input.addEventListener('input', function () {
      var kunci = input.value.trim().toLowerCase();
      var terlihat = 0;
      document.querySelectorAll(pemilih).forEach(function (el) {
        var teks = (el.getAttribute('data-cari') || el.textContent).toLowerCase();
        var cocok = !kunci || teks.indexOf(kunci) !== -1;
        el.hidden = !cocok;
        if (cocok) terlihat++;
      });
      if (kosong) kosong.hidden = terlihat !== 0;
    });
  });

  /* ------------------------------------------------ papan pasar (opsional) */
  /* Sumber harga: CoinGecko API publik. Bila gagal, papan tetap menampilkan
     tanda hubung — halaman tidak pernah bergantung pada permintaan ini.     */
  var papan = document.getElementById('papan-pasar');
  if (papan && 'fetch' in window) {
    var kunciSimpan = 'mdk-pasar';
    var render = function (d) {
      var btc = papan.querySelector('[data-pasar="btc"] [data-nilai]');
      var kurs = papan.querySelector('[data-pasar="usdidr"] [data-nilai]');
      if (btc && d.usd) {
        btc.textContent = '$' + Math.round(d.usd).toLocaleString('en-US');
        if (typeof d.perubahan === 'number') {
          btc.classList.add(d.perubahan >= 0 ? 'naik' : 'turun');
          btc.textContent += ' ' + (d.perubahan >= 0 ? '▲' : '▼') + Math.abs(d.perubahan).toFixed(1) + '%';
        }
      }
      if (kurs && d.idr && d.usd) {
        kurs.textContent = 'Rp' + Math.round(d.idr / d.usd).toLocaleString('id-ID');
      }
    };
    try {
      var simpan = JSON.parse(localStorage.getItem(kunciSimpan) || 'null');
      if (simpan && Date.now() - simpan.waktu < 300000) render(simpan);
    } catch (e) {}

    fetch('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd,idr&include_24hr_change=true')
      .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
      .then(function (j) {
        var b = j.bitcoin || {};
        var d = { usd: b.usd, idr: b.idr, perubahan: b.usd_24h_change, waktu: Date.now() };
        render(d);
        try { localStorage.setItem(kunciSimpan, JSON.stringify(d)); } catch (e) {}
      })
      .catch(function () { /* diam: papan pasar bersifat pelengkap */ });
  }

  /* ----------------------------------------------------- form buletin ----- */
  var formBuletin = document.getElementById('form-buletin');
  if (formBuletin && formBuletin.getAttribute('action') === '#') {
    formBuletin.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var tombol = formBuletin.querySelector('button');
      tombol.textContent = 'Segera hadir';
      tombol.disabled = true;
    });
  }
})();
