/* Halaman autentikasi: masuk, registrasi, lupa/reset sandi, login berhasil. */
(() => {
  'use strict';
  const { $, $$, esc, api, modal, showErrors, fieldError, clearFieldErrors, formError, busy, pages } = window.POS;
  const q = new URLSearchParams(location.search);

  /* ---------- lupa sandi (modal) ---------- */
  function wireLupa(portal) {
    $$('[data-action="lupa"]').forEach((a) => a.addEventListener('click', (e) => {
      e.preventDefault();
      const label = portal === 'pelapor' ? 'NIPPOS (9 digit)' : 'NIPPOS / ID Mitra';
      const m = modal({ tone: 'info', icon: 'lock_reset', title: 'Pemulihan Kata Sandi', subtitle: 'Kami akan mengirim tautan pemulihan (berlaku 30 menit) ke email terdaftar.',
        body: `<label class="block font-label-md text-label-md font-bold text-on-surface mb-1" for="lupa-id">${label}</label>
          <input id="lupa-id" type="text" autocomplete="username" class="w-full h-12 px-4 rounded-lg border border-outline-variant bg-white focus:ring-2 focus:ring-primary outline-none" placeholder="Masukkan identitas akun Anda" value="${esc(($('#nippos') || $('#nippos-input') || {}).value || '')}">
          <p id="lupa-msg" class="mt-3 font-body-sm text-body-sm"></p>`,
        actions: [{ label: 'Batal' }, { label: 'Kirim Tautan', primary: true, icon: 'send', onClick: async ({ btn }) => {
          const msg = $('#lupa-msg', m.el); const v = $('#lupa-id', m.el).value.trim();
          if (!v) { msg.className = 'mt-3 font-body-sm text-body-sm text-error'; msg.textContent = 'Identitas wajib diisi.'; return false; }
          btn.disabled = true;
          try { const r = await api('POST', '/api/auth/lupa-sandi', { portal, identifier: v }); msg.className = 'mt-3 font-body-sm text-body-sm text-emerald-700'; msg.textContent = r.pesan; btn.style.display = 'none'; }
          catch (er) { msg.className = 'mt-3 font-body-sm text-body-sm text-error'; msg.textContent = er.error; btn.disabled = false; }
          return false;
        } }] });
    }));
  }

  /* ---------- login ---------- */
  function wireLogin(portal) {
    const form = $('form[data-form]');
    const idEl = $('#nippos') || $('#nippos-input'), pwEl = $('#password') || $('#password-input');
    const remember = $('#remember');
    const saved = localStorage.getItem('pos_nippos_' + portal);
    if (saved && idEl) { idEl.value = saved; if (remember) remember.checked = true; }
    if (portal === 'pelapor' && idEl) idEl.addEventListener('input', () => (idEl.value = idEl.value.replace(/\D/g, '')));
    form.addEventListener('submit', async (e) => {
      e.preventDefault(); clearFieldErrors(form);
      const btn = $('button[type=submit]', form);
      const tipe = portal === 'karyawan' && $('#tab-mitra') && $('#tab-mitra').classList.contains('active') ? 'mitra' : 'karyawan';
      busy(btn, true, 'Memverifikasi Akses...');
      try {
        const r = await api('POST', '/api/auth/masuk', { portal, tipe, identifier: idEl.value, password: pwEl.value, next: q.get('next') });
        if (remember && remember.checked) localStorage.setItem('pos_nippos_' + portal, idEl.value.trim()); else localStorage.removeItem('pos_nippos_' + portal);
        location.href = r.redirect;
      } catch (er) { busy(btn, false); pwEl.value = ''; formError(form, er.error); pwEl.focus(); }
    });
    wireLupa(portal);
  }
  pages.masuk = () => {
    const t = $('[data-bind=tls]'); if (t) t.textContent = location.protocol === 'https:' ? 'Koneksi aman (HTTPS)' : 'Mode pengembangan (HTTP) — gunakan HTTPS di produksi';
    wireLogin('karyawan');
  };
  pages.pelapor_masuk = () => wireLogin('pelapor');

  /* ---------- registrasi ---------- */
  const FIELDS = {
    daftar: { identifier: '#reg_nippos', nama: '#reg_nama_lengkap', email: '#reg_email', password: '#reg_password', konfirmasi: '#reg_password_confirmation', setuju: '#terms_consent' },
    pelapor_daftar: { identifier: '#nippos', nama: '#namaLengkap', email: '#emailKedinasan', password: '#password', konfirmasi: '#confirmPassword', setuju: '#paktaIntegritas' },
  };
  function wireRegister(page, portal) {
    const form = $('form[data-form]'), F = FIELDS[page];
    const val = (k) => $(F[k]).type === 'checkbox' ? $(F[k]).checked : $(F[k]).value;
    if (portal === 'pelapor') $(F.identifier).addEventListener('input', (e) => (e.target.value = e.target.value.replace(/\D/g, '')));
    form.addEventListener('submit', async (e) => {
      e.preventDefault(); clearFieldErrors(form);
      const btn = $('button[type=submit]', form);
      busy(btn, true, 'Mendaftarkan...');
      try {
        const r = await api('POST', '/api/auth/daftar', { portal, identifier: val('identifier'), nama: val('nama'), email: val('email'), password: val('password'), konfirmasi: val('konfirmasi'), setuju: val('setuju') });
        location.href = r.redirect;
      } catch (er) {
        busy(btn, false);
        (er.errors || []).forEach((x) => F[x.field] && fieldError($(F[x.field]), x.message));
        showErrors('Registrasi Belum Berhasil', er);
      }
    });
  }
  pages.daftar = () => wireRegister('daftar', 'karyawan');
  pages.pelapor_daftar = () => wireRegister('pelapor_daftar', 'pelapor');

  pages.registrasi_berhasil = async () => {
    try {
      const d = await api('GET', '/api/auth/registrasi-ringkasan?t=' + encodeURIComponent(q.get('t') || ''));
      $$('[data-bind=identifier]').forEach((e) => (e.textContent = d.identifier));
      $$('[data-bind=nama]').forEach((e) => (e.textContent = d.nama));
      $$('[data-bind=email]').forEach((e) => (e.textContent = d.email));
      const l = $('[data-bind-href-login]'); if (l) l.href = d.portal === 'pelapor' ? '/pelapor/masuk' : '/masuk';
      const b = $$('a').find((a) => /Beranda Utama/.test(a.textContent)); if (b) b.href = d.portal === 'pelapor' ? '/pelapor/masuk' : '/masuk';
    } catch { location.href = '/masuk'; }
  };

  /* ---------- login berhasil ---------- */
  pages.login_berhasil = () => {
    const { user } = window.POS.me;
    const set = (n, v) => $$(`[data-bind="${n}"]`).forEach((e) => (e.textContent = v));
    set('ident_label', (user.tipe === 'mitra' ? 'ID Mitra ' : 'NIPPOS ') + user.identifier);
    set('afiliasi', user.tipe === 'mitra' ? 'Mitra Agen POS' : user.portal === 'pelapor' ? 'Pelapor SPI (WBS)' : 'Karyawan Internal' + (user.unit_kerja ? ' • ' + user.unit_kerja : ''));
    set('akses', user.level_akses || 'Akses standar');
    set('waktu_masuk', window.POS.fmtDT(new Date().toISOString()));
    const dest = window.POS.safeNext(q.get('next')) || window.POS.me.home;
    const btn = $('#btn-redirect'); btn.href = dest;
    const total = 3000, start = Date.now(), bar = $('#progress-bar'), cd = $('#countdown-text');
    const t = setInterval(() => {
      const el = Date.now() - start;
      bar.style.width = Math.min(100, (el / total) * 100) + '%';
      cd.textContent = Math.max(0, Math.ceil((total - el) / 1000)) + 's';
      if (el >= total) { clearInterval(t); location.href = dest; }
    }, 50);
  };

  /* ---------- reset sandi ---------- */
  pages.reset_sandi = () => {
    const form = $('#reset-form'), token = q.get('token') || '';
    if (!token) { formError(form, 'Tautan pemulihan tidak lengkap. Minta tautan baru dari halaman masuk.'); form.querySelector('button[type=submit]').disabled = true; return; }
    form.addEventListener('submit', async (e) => {
      e.preventDefault(); clearFieldErrors(form);
      const btn = $('button[type=submit]', form); busy(btn, true, 'Menyimpan...');
      try {
        const r = await api('POST', '/api/auth/reset-sandi', { token, password: $('#rp-pass').value, konfirmasi: $('#rp-conf').value });
        modal({ tone: 'ok', title: 'Kata Sandi Diperbarui', subtitle: 'Silakan masuk dengan kata sandi baru Anda.', dismissible: false,
          actions: [{ label: 'Menuju Halaman Masuk', primary: true, onClick: () => { location.href = r.redirect; return false; } }] });
      } catch (er) { busy(btn, false); (er.errors || []).forEach((x) => fieldError($(x.field === 'password' ? '#rp-pass' : '#rp-conf'), x.message)); if (!er.errors.length) formError(form, er.error); }
    });
  };
})();

/* ---------- lacak aduan (publik) ---------- */
(() => {
  const { $, esc, api, fmtDT } = window.POS;
  window.POS.pages.lacak = () => {
    const form = $('#lacak-form'), out = $('#lacak-hasil');
    const run = async (no) => {
      out.innerHTML = '<p class="text-on-surface-variant font-body-sm text-body-sm">Mencari...</p>';
      try {
        const r = await api('GET', '/api/lacak/' + encodeURIComponent(no));
        out.innerHTML = `<div class="rounded-xl bg-surface-container-low p-space-md space-y-3">
          <div class="flex flex-wrap items-center justify-between gap-2"><span class="px-3 py-1 rounded bg-primary-container text-white font-label-md text-label-md font-bold">#${esc(r.no_tiket)}</span>
          <span class="px-3 py-1 rounded-full bg-surface-container-high text-secondary font-label-sm text-label-sm font-bold">${esc(r.status_label)}</span></div>
          <ol class="space-y-3 pt-1">${r.langkah.map((l) => `<li class="flex gap-3 ${l.state === 'menunggu' ? 'opacity-50' : ''}">
            <span class="w-6 h-6 rounded-full flex items-center justify-center shrink-0 ${l.state === 'done' ? 'bg-primary text-white' : l.state === 'aktif' ? 'bg-secondary-container text-white' : 'bg-surface-container-high text-outline'}"><span class="material-symbols-outlined text-sm">${l.state === 'done' ? 'check' : l.state === 'aktif' ? 'pending' : 'hourglass_empty'}</span></span>
            <div><p class="font-label-md text-label-md font-bold">${esc(l.judul)}</p>${l.waktu ? `<p class="font-label-sm text-label-sm text-outline">${esc(fmtDT(l.waktu))}</p>` : ''}</div></li>`).join('')}</ol></div>`;
      } catch (e) { out.innerHTML = `<div class="p-3 rounded-lg bg-error-container text-on-error-container font-body-sm text-body-sm">${esc(e.error)}</div>`; }
    };
    form.addEventListener('submit', (e) => { e.preventDefault(); const v = $('#lacak-no').value.trim(); if (v) run(v); });
    const pre = new URLSearchParams(location.search).get('no'); if (pre) { $('#lacak-no').value = pre; run(pre); }
  };
})();
