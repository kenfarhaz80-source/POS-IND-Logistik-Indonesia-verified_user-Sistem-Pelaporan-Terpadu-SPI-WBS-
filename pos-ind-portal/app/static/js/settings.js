/* Pengaturan akun: profil, kata sandi, bahasa/zona, privasi, sesi perangkat, avatar. */
(() => {
  'use strict';
  const P = window.POS;
  const { $, $$, esc, api, modal, showErrors, fieldError, clearFieldErrors, busy, fmtDT, toast } = P;
  const bindAll = (n, v) => $$(`[data-bind="${n}"]`).forEach((e) => (e.textContent = v));
  const ok = (title, subtitle, rows, extra = '') => modal({ tone: 'ok', title, subtitle, body: (rows ? P.summary(rows) : '') + extra, actions: [{ label: 'Kembali ke Pengaturan', primary: true, icon: 'arrow_forward' }] });
  const AVATAR_BOX = (u, size = 'w-20 h-20') => u.avatar ? `<img src="${esc(u.avatar)}?v=${Date.now()}" alt="Foto profil" class="${size} rounded-full object-cover">` : esc(u.inisial);
  let loadScore = null, loadSessions = null;

  /* ---------- verifikasi email: kirim ulang tautan ---------- */
  document.addEventListener('click', async (e) => {
    const b = e.target.closest('[data-resend]');
    if (!b) return;
    e.preventDefault(); b.disabled = true;
    try { const r = await api('POST', '/api/akun/verifikasi-email'); toast(`Tautan verifikasi dikirim ke ${r.email}.`); b.textContent = 'Tautan terkirim — periksa email Anda'; }
    catch (er) { toast(er.error, 'err'); b.disabled = false; }
  });
  function emailVerifyHint(selector) {
    const u = P.me.user, inp = $(selector);
    if (!inp || !inp.parentElement) return;
    const host = inp.closest('div') && inp.closest('div').parentElement ? inp.closest('div').parentElement : inp.parentElement;
    $$('[data-email-hint]', host).forEach((x) => x.remove());
    const el = document.createElement('div'); el.dataset.emailHint = '1'; el.className = 'mt-1 font-label-sm text-label-sm';
    el.innerHTML = u.email_verified ? '<span class="inline-flex items-center gap-1 text-emerald-700 font-bold"><span class="material-symbols-outlined text-sm">verified</span>Email terverifikasi</span>'
      : '<span class="text-on-surface-variant">Email belum terverifikasi.</span> <button type="button" data-resend class="text-secondary font-bold hover:underline disabled:opacity-60">Kirim ulang tautan verifikasi</button>';
    host.appendChild(el);
  }

  /* ---------- umum: profil ---------- */
  function fillIdentity() {
    const u = P.me.user;
    bindAll('nama', u.nama); bindAll('inisial', u.inisial);
    bindAll('jabatan_unit', [u.jabatan, u.unit_kerja].filter(Boolean).join(' • ') || '-');
    bindAll('chip_hub', 'Hub ' + (u.hub || '-'));
    bindAll('chip_tmt', 'TMT: ' + (u.tmt ? fmtDT(u.tmt, false) : '-'));
    bindAll('chip_level', 'Level Akses: ' + (u.level_akses || '-'));
    bindAll('level_akses', u.level_akses || 'Standar');
    bindAll('bind_valid', u.identifier + (u.hrms_terverifikasi ? ' (Valid)' : ' (Belum sinkron HRMS)'));
    bindAll('login_terakhir', P.me.login_sebelumnya ? fmtDT(P.me.login_sebelumnya) : 'Pertama kali masuk');
    const mitra = u.tipe === 'mitra';
    bindAll('status_pegawai', mitra ? 'Mitra Agen' : u.role === 'spi' ? 'Petugas SPI' : 'Karyawan');
    bindAll('status_sk', mitra ? 'Mitra Aktif' : 'SK Pegawai Aktif');
    bindAll('hrms_label', u.hrms_terverifikasi ? 'Terverifikasi HRMS Pusat' : 'Belum sinkron HRMS');
    bindAll('hrms_desc', u.hrms_terverifikasi ? 'Data terintegrasi secara otomatis dengan Sistem HRMS Kantor Pusat Bandung.' : 'Data diisi saat registrasi dan belum dicocokkan dengan Sistem HRMS.');
    $$('input[data-field]').forEach((i) => (i.value = u[i.dataset.field] || ''));
    const umur = Math.max(0, Math.floor((Date.now() - new Date(u.password_changed_at)) / 86400000));
    bindAll('umur_sandi', umur === 0 ? 'Terakhir diubah: hari ini' : `Terakhir diubah: ${umur} hari lalu`);
  }

  async function saveProfile(payload, form) {
    clearFieldErrors(form);
    try {
      const r = await api('PUT', '/api/akun/profil', payload);
      P.me.user = r.user; fillIdentity();
      const ph = $('#phoneNumber') || $('#operationalPhone'); if (ph) ph.value = r.user.telepon || '';
      return r;
    } catch (er) {
      (er.errors || []).forEach((x) => {
        const m = { telepon: '#phoneNumber, #operationalPhone', email: '#companyEmail', nama: '#fullName', identifier: '#nippos' }[x.field];
        if (m) fieldError($(m), x.message);
      });
      showErrors('Gagal Menyimpan Identitas & Kontak', er);
      return null;
    }
  }

  /* ---------- umum: kata sandi ---------- */
  function wirePassword(form, ids) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault(); clearFieldErrors(form);
      const btn = $('button[type=submit]', form);
      busy(btn, true, 'Memperbarui...');
      try {
        const r = await api('PUT', '/api/akun/kata-sandi', { saat_ini: $(ids[0]).value, baru: $(ids[1]).value, konfirmasi: $(ids[2]).value });
        busy(btn, false); form.reset(); if (window.evaluateStrength) window.evaluateStrength('');
        P.me.user.password_changed_at = new Date().toISOString(); fillIdentity();
        ok('Kata Sandi Berhasil Diperbarui', 'Gunakan kata sandi baru untuk login berikutnya.', null,
          `<div class="flex gap-2 p-3 rounded-lg bg-primary-fixed/50 text-on-surface-variant font-body-sm text-body-sm"><span class="material-symbols-outlined text-primary">info</span><span>Sesi Anda saat ini tetap aktif. ${r.sesi_dicabut ? r.sesi_dicabut + ' sesi di perangkat lain telah diakhiri.' : 'Tidak ada sesi lain yang aktif.'}</span></div>`);
        if (loadScore) loadScore();
        if (loadSessions) loadSessions();
      } catch (er) {
        busy(btn, false);
        (er.errors || []).forEach((x) => fieldError($({ saat_ini: ids[0], baru: ids[1], konfirmasi: ids[2] }[x.field]), x.message));
        showErrors('Gagal Memperbarui Kata Sandi', er, { subtitle: 'Perubahan kata sandi tidak dapat diproses karena alasan berikut:' });
      }
    });
  }

  /* ---------- kartu skor & sesi ---------- */
  function scoreHtml(r) {
    const col = r.skor >= 80 ? 'text-emerald-600' : r.skor >= 60 ? 'text-amber-600' : 'text-error';
    return `<div class="flex items-center justify-between"><h3 class="font-headline-sm text-headline-sm font-extrabold text-primary">Skor Keamanan Akun</h3>
      <span class="px-2.5 py-0.5 rounded-full bg-surface-container-high ${col} font-label-sm text-label-sm font-bold">${esc(r.label)}</span></div>
      <div class="flex items-center justify-center py-3"><div class="w-28 h-28 rounded-full flex items-center justify-center" style="background:conic-gradient(#162b64 ${r.skor * 3.6}deg,#e0e3e6 0)">
      <div class="w-20 h-20 rounded-full bg-surface-container-lowest flex flex-col items-center justify-center"><span class="font-headline-md text-headline-md font-extrabold text-primary">${r.skor}%</span><span class="font-label-sm text-label-sm text-outline">Terproteksi</span></div></div></div>
      <div class="space-y-2">${r.rows.map((x) => `<div class="flex items-center justify-between font-body-sm text-body-sm"><span class="flex items-center gap-1.5 text-on-surface-variant"><span class="material-symbols-outlined text-base ${x.ok ? 'text-emerald-600' : 'text-outline'}">${x.ok ? 'check' : 'info'}</span>${esc(x.nama)}</span><span class="font-bold ${x.ok ? 'text-emerald-700' : 'text-on-surface-variant'}">${esc(x.nilai)}${x.nama === 'Email Terverifikasi' && !x.ok ? ' <button type="button" data-resend class="ml-1 text-secondary font-bold hover:underline disabled:opacity-60">Kirim ulang</button>' : ''}</span></div>`).join('')}</div>
      <button type="button" data-goto-sec class="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-primary-container text-white font-label-md text-label-md font-bold hover:bg-primary"><span class="material-symbols-outlined text-lg">sync</span><span>Perbarui Keamanan Sekarang</span></button>`;
  }

  function sessionsHtml(list) {
    return `<div class="flex items-center justify-between"><h3 class="font-headline-sm text-headline-sm font-extrabold text-primary">Sesi Perangkat Aktif</h3><span class="material-symbols-outlined text-outline">devices</span></div>
      <div class="space-y-3">${list.map((s) => `<div class="flex gap-3 p-3 rounded-lg bg-surface-container-low"><span class="material-symbols-outlined text-primary">${/Android|iOS/.test(s.perangkat) ? 'smartphone' : 'desktop_windows'}</span>
        <div class="min-w-0"><div class="flex items-center gap-2 flex-wrap"><span class="font-label-md text-label-md font-bold text-on-surface">${esc(s.perangkat)}</span>${s.current ? '<span class="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-label-sm text-label-sm font-bold">Saat Ini</span>' : ''}</div>
        <p class="font-body-sm text-body-sm text-on-surface-variant">IP: ${esc(s.ip)} • Aktif terakhir ${esc(fmtDT(s.last_seen))}</p></div></div>`).join('')}</div>
      <button type="button" data-kill-sessions ${list.length < 2 ? 'disabled' : ''} class="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg border border-error/40 text-error font-label-md text-label-md font-bold hover:bg-error-container/40 disabled:opacity-50 disabled:cursor-not-allowed"><span class="material-symbols-outlined text-lg">logout</span><span>Putus Sesi dari Perangkat Lain</span></button>`;
  }

  function pickAvatar(done) {
    const f = document.createElement('input'); f.type = 'file'; f.accept = 'image/png,image/jpeg,image/webp';
    f.onchange = async () => {
      if (!f.files[0]) return;
      const fd = new FormData(); fd.append('foto', f.files[0]);
      try { const r = await api('POST', '/api/akun/avatar', fd); P.me.user.avatar = r.avatar.split('?')[0]; done(); toast('Foto profil diperbarui.'); }
      catch (er) { toast(er.error, 'err'); }
    };
    f.click();
  }

  /* ================= KARYAWAN ================= */
  P.pages.pengaturan_karyawan = async () => {
    const pref = P.me.pref;
    fillIdentity();
    const set = (id, v) => ($('#' + id).value = v);
    const resetProfile = () => { const u = P.me.user; set('fullName', u.nama); set('nippos', u.identifier); set('companyEmail', u.email); set('phoneNumber', u.telepon || ''); };
    resetProfile(); emailVerifyHint('#companyEmail');
    const avatarBox = () => $('#tab-profil [data-bind="inisial"]');
    if (avatarBox() && P.me.user.avatar) avatarBox().innerHTML = AVATAR_BOX(P.me.user, 'w-full h-full');

    $('#profileForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = $('button[type=submit]', e.target); busy(btn, true, 'Menyimpan...');
      const r = await saveProfile({ nama: $('#fullName').value, email: $('#companyEmail').value, telepon: $('#phoneNumber').value, identifier: $('#nippos').value }, e.target);
      busy(btn, false);
      if (r) ok('Identitas & Kontak Berhasil Disimpan', 'Perubahan informasi profil Anda telah berhasil diperbarui di sistem.', r.ringkasan,
        r.perlu_verifikasi_email ? '<p class="mt-3 font-body-sm text-body-sm text-on-surface-variant">Email diubah — tautan verifikasi telah dikirim ke alamat baru.</p>' : '');
    });
    $('[data-action="profil-reset"]').addEventListener('click', () => { clearFieldErrors($('#profileForm')); resetProfile(); });

    wirePassword($('#passwordForm'), ['#currentPassword', '#newPassword', '#confirmPassword']);

    const paintLang = (v) => window.updateLangCard && window.updateLangCard(v);
    $$('input[name=systemLanguage]').forEach((r) => { r.checked = r.value === pref.bahasa; r.addEventListener('change', () => paintLang(r.value)); });
    paintLang(pref.bahasa);
    $('#timezone').value = pref.zona_waktu; $('#dateFormat').value = pref.format_tanggal;
    $('#langForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = $('button[type=submit]', e.target); busy(btn, true, 'Menerapkan...');
      const body = { bagian: 'bahasa', bahasa: ($('input[name=systemLanguage]:checked') || {}).value, zona_waktu: $('#timezone').value, format_tanggal: $('#dateFormat').value };
      try {
        const r = await api('PUT', '/api/akun/preferensi', body); P.me.pref = r.pref; busy(btn, false);
        ok('Preferensi Bahasa Berhasil Disimpan', 'Pengaturan bahasa antarmuka dan format regional telah diterapkan.', [
          ['Bahasa Antarmuka', r.pref.bahasa === 'id' ? 'Bahasa Indonesia' : 'English'], ['Zona Waktu', r.pref.zona_waktu], ['Format Tanggal', r.pref.format_tanggal]]);
        fillIdentity();
      } catch (er) {
        busy(btn, false);
        showErrors('Gagal Menyimpan Preferensi Bahasa', er, { subtitle: 'Pengaturan bahasa dan zona waktu tidak dapat disimpan:', button: 'Kembali ke Form' });
      }
    });

    $('input[name=consentProcessing]').checked = pref.consent_pemrosesan;
    $('input[name=consentManifest]').checked = pref.consent_manifest;
    $('input[name=consentAuditTrail]').checked = pref.audit_trail_email;
    $('#privacyForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = $('button[type=submit]', e.target); busy(btn, true, 'Menyimpan...');
      const body = { bagian: 'privasi', consent_pemrosesan: $('input[name=consentProcessing]').checked, consent_manifest: $('input[name=consentManifest]').checked, audit_trail_email: $('input[name=consentAuditTrail]').checked };
      try {
        const r = await api('PUT', '/api/akun/preferensi', body); P.me.pref = r.pref; busy(btn, false);
        const yn = (v) => (v ? 'Diizinkan' : 'Nonaktif');
        ok('Pengaturan Privasi Berhasil Disimpan', 'Preferensi privasi dan persetujuan kebijakan data Anda telah diperbarui.', [
          ['Pemrosesan Data Kepegawaian & Logistik', yn(r.pref.consent_pemrosesan)], ['Visibilitas NIPPOS pada Manifest', yn(r.pref.consent_manifest)], ['Notifikasi Audit Akses via Email', yn(r.pref.audit_trail_email)]]);
      } catch (er) {
        busy(btn, false); $('input[name=consentProcessing]').checked = P.me.pref.consent_pemrosesan;
        showErrors('Gagal Menyimpan Pengaturan Privasi', er, { subtitle: 'Terjadi kendala saat menyimpan pilihan privasi Anda:', button: 'Coba Lagi' });
      }
    });

    $('[data-action="avatar"]').addEventListener('click', () => pickAvatar(() => { if (avatarBox()) avatarBox().innerHTML = AVATAR_BOX(P.me.user, 'w-full h-full'); }));

    loadScore = async () => {
      const r = await api('GET', '/api/akun/ringkasan'); const c = $('#skor-card'); c.innerHTML = scoreHtml(r);
      $('[data-goto-sec]', c).onclick = () => window.switchSection && window.switchSection('tab-keamanan');
    };
    loadSessions = async () => {
      const list = await api('GET', '/api/akun/sesi'); const c = $('#sesi-card'); c.innerHTML = sessionsHtml(list);
      const b = $('[data-kill-sessions]', c);
      b.onclick = async () => {
        busy(b, true, 'Memutus...');
        try { const r = await api('DELETE', '/api/akun/sesi'); toast(`${r.dicabut} sesi perangkat lain diputus.`); } catch (er) { toast(er.error, 'err'); }
        loadSessions(); loadScore();
      };
    };
    await Promise.all([loadScore(), loadSessions()]);
  };

  /* ================= PELAPOR ================= */
  P.pages.pengaturan_pelapor = async () => {
    const pref = P.me.pref;
    fillIdentity();
    $('#operationalPhone').value = P.me.user.telepon || ''; emailVerifyHint('input[data-field=email]');
    $('#contactForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = $('button[type=submit]', e.target); busy(btn, true, 'Menyimpan...');
      const r = await saveProfile({ telepon: $('#operationalPhone').value }, e.target);
      busy(btn, false);
      if (r) toast('Kontak operasional ' + (r.user.telepon || '-') + ' berhasil disimpan.');
    });
    wirePassword($('#passwordForm'), ['#currentPassword', '#newPassword', '#confirmPassword']);

    $('#n-sms').checked = pref.notif_sms_wa; $('#n-email').checked = pref.notif_email; $('#n-push').checked = pref.notif_push; $('#n-anon').checked = pref.samarkan_nama;
    const a = $('#lang-id'), b = $('#lang-en');
    const onCls = (/Aktif/.test(a.textContent) ? a : b).className, offCls = (/Aktif/.test(a.textContent) ? b : a).className;
    let lang = pref.bahasa;
    const paint = () => [[a, 'id', 'Bahasa Indonesia'], [b, 'en', 'English (US)']].forEach(([el, c, t]) => { el.className = c === lang ? onCls : offCls; el.textContent = t + (c === lang ? ' (Aktif)' : ''); });
    a.onclick = () => { lang = 'id'; paint(); }; b.onclick = () => { lang = 'en'; paint(); }; paint();
    $('#btn-apply-notif').onclick = async (e) => {
      const btn = e.currentTarget; busy(btn, true, 'Menerapkan...');
      try { const r = await api('PUT', '/api/akun/preferensi', { bagian: 'notifikasi', notif_sms_wa: $('#n-sms').checked, notif_email: $('#n-email').checked, notif_push: $('#n-push').checked, bahasa: lang }); P.me.pref = r.pref; toast('Preferensi notifikasi dan bahasa berhasil disimpan.'); }
      catch (er) { showErrors('Gagal Menyimpan Preferensi', er); }
      busy(btn, false);
    };
    $('#btn-save-privacy').onclick = async (e) => {
      const btn = e.currentTarget; busy(btn, true, 'Menyimpan...');
      try { const r = await api('PUT', '/api/akun/preferensi', { bagian: 'privasi', consent_pemrosesan: P.me.pref.consent_pemrosesan, samarkan_nama: $('#n-anon').checked }); P.me.pref = r.pref; toast('Pengaturan privasi pelapor disimpan.'); }
      catch (er) { showErrors('Gagal Menyimpan Pengaturan Privasi', er); }
      busy(btn, false);
    };
    if (P.me.user.avatar) $$('[data-bind="inisial"]').forEach((x) => (x.innerHTML = AVATAR_BOX(P.me.user, 'w-full h-full')));

    loadScore = async () => {
      const r = await api('GET', '/api/akun/ringkasan');
      bindAll('skor', r.skor + '%'); bindAll('skor_label', r.label);
      bindAll('skor_note', r.rows.filter((x) => x.ok).length + ' dari ' + r.rows.length + ' pemeriksaan keamanan terpenuhi');
      const t = r.aktivitas || {};
      bindAll('a_total', t.total ?? 0); bindAll('a_selesai', t.selesai ?? 0);
      bindAll('a_wasum', (t.total ?? 0) + ' Tiket'); bindAll('a_proses', (t.investigasi ?? 0) + ' Proses');
    };
    await loadScore();
  };
})();
