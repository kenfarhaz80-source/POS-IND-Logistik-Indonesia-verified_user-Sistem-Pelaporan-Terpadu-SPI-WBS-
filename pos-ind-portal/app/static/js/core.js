/* Inti front-end: klien API, modal, toast, format tanggal, shell navigasi. */
(() => {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const POS = (window.POS = { $, $$, esc, me: null, pages: {} });
  const PAGE = document.body.dataset.page;
  const PUBLIC = ['beranda', 'masuk', 'pelapor_masuk', 'daftar', 'pelapor_daftar', 'registrasi_berhasil', 'reset_sandi', 'lacak'];

  /* ---------------------------------------------------------------- API */
  POS.api = async (method, url, body) => {
    const opt = { method, headers: {}, credentials: 'same-origin' };
    if (POS.me) opt.headers['X-CSRF-Token'] = POS.me.csrf;
    if (body instanceof FormData) opt.body = body;
    else if (body !== undefined) { opt.headers['Content-Type'] = 'application/json'; opt.body = JSON.stringify(body); }
    let res;
    try { res = await fetch(url, opt); }
    catch { throw { status: 0, error: 'Tidak dapat terhubung ke server. Periksa koneksi Anda.', errors: [] }; }
    let json = null;
    try { json = await res.json(); } catch { /* bukan JSON */ }
    if (res.status === 401 && POS.me) { location.href = '/masuk?next=' + encodeURIComponent(location.pathname + location.search); throw { status: 401, error: 'Sesi berakhir.', errors: [] }; }
    if (!res.ok || !json || json.ok === false) throw { status: res.status, error: (json && json.error) || 'Terjadi kesalahan pada server.', errors: (json && json.errors) || [], body: json };
    return json.data !== undefined ? json.data : json;
  };

  /* ---------------------------------------------------------------- unggah berkas (dengan progres & pembatalan) */
  POS.upload = (url, file, onProgress) => {
    const xhr = new XMLHttpRequest();
    const promise = new Promise((resolve, reject) => {
      xhr.open('POST', url);
      if (POS.me) xhr.setRequestHeader('X-CSRF-Token', POS.me.csrf);
      xhr.responseType = 'json';
      xhr.upload.onprogress = (e) => { if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100)); };
      xhr.onload = () => {
        const j = xhr.response;
        if (xhr.status >= 200 && xhr.status < 300 && j && j.ok !== false) resolve(j.data);
        else reject({ status: xhr.status, error: (j && j.error) || (xhr.status === 413 ? 'Ukuran berkas melebihi batas 50 MB.' : 'Gagal mengunggah berkas.'), errors: (j && j.errors) || [] });
      };
      xhr.onerror = () => reject({ status: 0, error: 'Koneksi terputus saat mengunggah. Coba lagi.', errors: [] });
      xhr.onabort = () => reject({ status: 0, aborted: true, error: 'Unggahan dibatalkan.', errors: [] });
      const fd = new FormData(); fd.append('berkas', file); xhr.send(fd);
    });
    return { promise, abort: () => xhr.abort() };
  };
  POS.UPLOAD = { exts: ['mp4', 'm4a', 'pdf', 'jpg', 'jpeg', 'png', 'csv', 'xlsx'], maxBytes: 50 * 1024 * 1024 };
  POS.checkFile = (file) => {
    const ext = (file.name.split('.').pop() || '').toLowerCase();
    if (!POS.UPLOAD.exts.includes(ext)) return `${file.name}: format .${ext || '?'} tidak didukung (mp4, m4a, pdf, jpg, png, csv, xlsx).`;
    if (file.size === 0) return `${file.name}: berkas kosong.`;
    if (file.size > POS.UPLOAD.maxBytes) return `${file.name}: ${POS.size(file.size)} melebihi batas 50 MB.`;
    return null;
  };

  /* ---------------------------------------------------------------- toast */
  POS.toast = (msg, type = 'ok') => {
    let box = $('#pos-toasts');
    if (!box) { box = document.createElement('div'); box.id = 'pos-toasts'; box.className = 'fixed bottom-6 right-6 z-[300] flex flex-col gap-2'; document.body.appendChild(box); }
    const t = document.createElement('div');
    const bad = type === 'err';
    t.className = `flex items-center gap-2 px-4 py-3 rounded-lg shadow-xl font-label-md text-label-md text-white ${bad ? 'bg-error' : 'bg-primary'} transition-all`;
    t.setAttribute('role', bad ? 'alert' : 'status');
    t.innerHTML = `<span class="material-symbols-outlined text-lg ${bad ? '' : 'text-secondary-container'}">${bad ? 'error' : 'check_circle'}</span><span>${esc(msg)}</span>`;
    box.appendChild(t);
    setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, 3800);
  };

  /* ---------------------------------------------------------------- modal */
  POS.modal = ({ tone = 'info', icon, title, subtitle = '', body = '', actions = [], wide = false, dismissible = true }) => {
    const color = { ok: 'bg-emerald-100 text-emerald-700', err: 'bg-error-container text-error', info: 'bg-primary-fixed text-primary', warn: 'bg-secondary-fixed text-secondary' }[tone];
    const ic = icon || { ok: 'check_circle', err: 'error', info: 'info', warn: 'warning' }[tone];
    const wrap = document.createElement('div');
    wrap.className = 'fixed inset-0 z-[200] flex items-center justify-center p-4 bg-primary/60 backdrop-blur-sm';
    wrap.setAttribute('role', 'dialog'); wrap.setAttribute('aria-modal', 'true');
    wrap.innerHTML = `<div class="bg-surface-container-lowest rounded-xl shadow-[0_24px_48px_-12px_rgba(22,43,100,0.22)] w-full ${wide ? 'max-w-2xl' : 'max-w-lg'} max-h-[90vh] overflow-y-auto p-space-lg space-y-space-md">
      <div class="flex items-start gap-3"><div class="w-12 h-12 rounded-full ${color} flex items-center justify-center shrink-0"><span class="material-symbols-outlined text-2xl">${ic}</span></div>
      <div class="min-w-0 flex-1"><h2 class="font-headline-sm text-headline-sm font-extrabold text-primary">${esc(title)}</h2>${subtitle ? `<p class="font-body-sm text-body-sm text-on-surface-variant mt-1">${esc(subtitle)}</p>` : ''}</div>
      ${dismissible ? '<button type="button" data-close class="text-outline hover:text-on-surface" aria-label="Tutup"><span class="material-symbols-outlined">close</span></button>' : ''}</div>
      <div data-body>${body}</div>
      <div class="flex flex-wrap justify-end gap-2 pt-1" data-actions></div></div>`;
    document.body.appendChild(wrap);
    let done;
    const promise = new Promise((r) => (done = r));
    const close = (v = null) => { document.removeEventListener('keydown', onKey); wrap.remove(); done(v); };
    const onKey = (e) => { if (e.key === 'Escape' && dismissible) close(null); };
    document.addEventListener('keydown', onKey);
    const box = $('[data-actions]', wrap);
    actions.forEach((a) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = a.primary
        ? 'inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-secondary-container hover:brightness-110 text-white font-label-md text-label-md font-bold transition-all disabled:opacity-60'
        : 'inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-surface-container-high hover:bg-surface-container-highest text-primary font-label-md text-label-md font-bold transition-all';
      b.innerHTML = (a.icon ? `<span class="material-symbols-outlined text-lg">${a.icon}</span>` : '') + `<span>${esc(a.label)}</span>`;
      b.onclick = async () => { if (a.onClick) { const keep = await a.onClick({ close, el: wrap, btn: b }); if (keep === false) return; } close(a.id ?? true); };
      box.appendChild(b);
    });
    $$('[data-close]', wrap).forEach((b) => (b.onclick = () => close(null)));
    wrap.addEventListener('mousedown', (e) => { if (e.target === wrap && dismissible) close(null); });
    const first = $('input,select,textarea,button[class*="bg-secondary-container"]', wrap);
    if (first) setTimeout(() => first.focus(), 30);
    return { el: wrap, close, promise };
  };

  POS.errorList = (errors) => `<ul class="space-y-2">${errors.map((e, i) => `<li class="flex gap-3 p-3 rounded-lg bg-error-container/40 border border-error/10">
      <span class="w-6 h-6 rounded-full bg-error text-white flex items-center justify-center font-label-sm text-label-sm font-bold shrink-0">${i + 1}</span>
      <div><p class="font-label-md text-label-md font-bold text-on-surface">${esc(e.title)}</p><p class="font-body-sm text-body-sm text-on-surface-variant">${esc(e.message)}</p></div></li>`).join('')}</ul>`;

  POS.showErrors = (title, err, extra = {}) => {
    const list = err.errors && err.errors.length ? err.errors : [{ title: 'Kesalahan', message: err.error }];
    return POS.modal({ tone: 'err', title, subtitle: extra.subtitle || 'Mohon periksa kembali data yang Anda masukkan:', body: POS.errorList(list),
      actions: [{ label: extra.button || 'Perbaiki Data', icon: 'edit', primary: true }] });
  };

  POS.summary = (rows) => `<dl class="rounded-lg bg-surface-container-low divide-y divide-outline-variant/30">${rows.map(([k, v]) => `<div class="flex justify-between gap-4 px-4 py-2.5"><dt class="font-label-md text-label-md text-on-surface-variant">${esc(k)}</dt><dd class="font-label-md text-label-md font-bold text-on-surface text-right break-all">${esc(v)}</dd></div>`).join('')}</dl>`;

  /* ---------------------------------------------------------------- form helpers */
  POS.clearFieldErrors = (root = document) => {
    $$('[data-field-err]', root).forEach((e) => e.remove());
    $$('[data-has-err]', root).forEach((e) => { e.classList.remove('!border-error', 'ring-2', 'ring-error/30'); e.removeAttribute('data-has-err'); });
    $$('[data-form-error]', root).forEach((e) => e.remove());
  };
  POS.fieldError = (input, msg) => {
    if (!input) return;
    input.classList.add('!border-error', 'ring-2', 'ring-error/30'); input.setAttribute('data-has-err', '1');
    const host = input.closest('div') || input.parentElement;
    const p = document.createElement('p');
    p.setAttribute('data-field-err', '1'); p.className = 'text-error font-label-sm text-label-sm mt-1 flex items-center gap-1';
    p.innerHTML = `<span class="material-symbols-outlined text-sm">error</span><span>${esc(msg)}</span>`;
    (host.parentElement && host.parentElement !== document.body ? host.parentElement : host).appendChild(p);
    input.addEventListener('input', () => { input.classList.remove('!border-error', 'ring-2', 'ring-error/30'); p.remove(); }, { once: true });
  };
  POS.formError = (form, msg) => {
    $$('[data-form-error]', form).forEach((e) => e.remove());
    const d = document.createElement('div');
    d.setAttribute('data-form-error', '1'); d.setAttribute('role', 'alert');
    d.className = 'flex items-start gap-2 p-3 rounded-lg bg-error-container text-on-error-container font-body-sm text-body-sm';
    d.innerHTML = `<span class="material-symbols-outlined text-lg">error</span><span>${esc(msg)}</span>`;
    form.prepend(d);
  };
  POS.busy = (btn, on, label) => {
    if (on) { btn.dataset.html = btn.innerHTML; btn.disabled = true; btn.classList.add('opacity-80', 'cursor-wait');
      btn.innerHTML = `<span class="material-symbols-outlined text-[20px] animate-spin">progress_activity</span><span>${esc(label || 'Memproses...')}</span>`; }
    else { btn.disabled = false; btn.classList.remove('opacity-80', 'cursor-wait'); if (btn.dataset.html) btn.innerHTML = btn.dataset.html; }
  };

  /* ---------------------------------------------------------------- tanggal */
  const OFF = { WIB: 7, WITA: 8, WIT: 9 };
  const BLN = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'];
  const p2 = (n) => String(n).padStart(2, '0');
  const zona = () => (POS.me && POS.me.pref.zona_waktu) || 'WIB';
  POS.fmtDT = (iso, withTime = true) => {
    if (!iso) return '-';
    const d = new Date(iso.length === 10 ? iso + 'T00:00:00Z' : iso);
    if (isNaN(d)) return '-';
    const u = new Date(d.getTime() + (OFF[zona()] || 7) * 3600000);
    const [y, m, dd] = [u.getUTCFullYear(), u.getUTCMonth(), u.getUTCDate()];
    const f = (POS.me && POS.me.pref.format_tanggal) || 'DD/MM/YYYY';
    const date = f === 'YYYY-MM-DD' ? `${y}-${p2(m + 1)}-${p2(dd)}` : f === 'DD MMM YYYY' ? `${p2(dd)} ${BLN[m]} ${y}` : `${p2(dd)}/${p2(m + 1)}/${y}`;
    return withTime ? `${date}, ${p2(u.getUTCHours())}:${p2(u.getUTCMinutes())} ${zona()}` : date;
  };
  POS.toLocalInput = (iso) => { // untuk <input type=datetime-local> dalam zona pengguna
    if (!iso) return '';
    const u = new Date(new Date(iso).getTime() + (OFF[zona()] || 7) * 3600000);
    return `${u.getUTCFullYear()}-${p2(u.getUTCMonth() + 1)}-${p2(u.getUTCDate())}T${p2(u.getUTCHours())}:${p2(u.getUTCMinutes())}`;
  };
  POS.nowLocalInput = () => POS.toLocalInput(new Date().toISOString());
  POS.size = (b) => (b >= 1048576 ? (b / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(b / 1024)) + ' KB');
  POS.fileIcon = (ext) => ({ mp4: ['videocam', 'text-primary'], m4a: ['mic', 'text-primary'], pdf: ['picture_as_pdf', 'text-error'], jpg: ['image', 'text-secondary'], jpeg: ['image', 'text-secondary'], png: ['image', 'text-secondary'], csv: ['description', 'text-tertiary'], xlsx: ['table_chart', 'text-tertiary'] }[ext] || ['attach_file', 'text-outline']);
  POS.debounce = (fn, ms = 300) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
  POS.safeNext = (n) => (n && n.startsWith('/') && !n.startsWith('//') && !n.includes('\\') ? n : null);

  /* ---------------------------------------------------------------- logout */
  POS.logout = async () => {
    try { const r = await POS.api('POST', '/api/auth/keluar'); location.href = r.redirect; }
    catch { location.href = '/masuk'; }
  };

  /* ---------------------------------------------------------------- shell */
  const NAV = () => {
    const home = POS.me ? POS.me.home : '/masuk';
    return { 'lihat-laporan': home, 'ringkasan-operasional': home, dashboard: home, 'buat-laporan-baru': '/pelapor/laporan-baru', 'pengaturan-akun': POS.me && POS.me.user.portal === 'pelapor' ? '/pelapor/pengaturan' : '/staf/pengaturan',
      'help-desk': '/info/pusat-bantuan', 'pusat-bantuan': '/info/pusat-bantuan', 'pusat-bantuan-it': '/info/pusat-bantuan', bantuan: '/info/pusat-bantuan',
      'help-center': '/info/pusat-bantuan', 'kontak-dukungan': '/info/pusat-bantuan', 'kebijakan-privasi': '/info/kebijakan-privasi', 'privacy-policy': '/info/kebijakan-privasi',
      'syarat-ketentuan': '/info/syarat-ketentuan', 'syarat-dan-ketentuan': '/info/syarat-ketentuan', 'terms-of-service': '/info/syarat-ketentuan',
      'whistleblower-protection': '/info/perlindungan-pelapor', 'track-report': '/lacak', login: '/pelapor/masuk', masuk: '/masuk' };
  };
  function wireLinks() {
    const map = NAV();
    $$('a[data-path]').forEach((a) => {
      const p = a.dataset.path;
      if (p === 'keluar') { a.href = '#'; a.addEventListener('click', (e) => { e.preventDefault(); POS.logout(); }); }
      else if (map[p]) a.href = map[p];
    });
    $$('[data-action="logout"]').forEach((a) => a.addEventListener('click', (e) => { e.preventDefault(); POS.logout(); }));
  }
  POS.wireLinks = wireLinks;
  function fixDeadLinks() {
    $$('a[href="#"]:not([data-action]):not([data-path])').forEach((a) => {
      if (/Helpdesk|Bantuan/i.test(a.textContent)) a.href = '/info/pusat-bantuan';
      else if (a.querySelector('img') || /Portal|BUMN/i.test(a.textContent) || a.closest('header')) a.href = POS.me ? POS.me.home : '/';
    });
  }

  /* pemilih portal di halaman masuk/daftar: jelas mana pintu Pelapor dan mana Staf/SPI */
  function portalSwitch() {
    const cur = { masuk: 'staf', daftar: 'staf', pelapor_masuk: 'pelapor', pelapor_daftar: 'pelapor' }[PAGE];
    const form = $('form[data-form]');
    if (!cur || !form) return;
    const login = PAGE.endsWith('masuk');
    const tab = (href, on, icon, t, sub) => `<a href="${href}" ${on ? 'aria-current="page"' : ''} class="flex-1 px-3 py-2 rounded-lg text-center transition-all ${on ? 'bg-primary-container text-white shadow-sm' : 'text-on-surface-variant hover:bg-surface-container-high'}">
      <span class="flex items-center justify-center gap-1 font-label-md text-label-md font-bold"><span class="material-symbols-outlined text-base">${icon}</span>${t}</span><span class="block font-label-sm text-label-sm ${on ? 'opacity-90' : 'text-outline'}">${sub}</span></a>`;
    const bar = document.createElement('nav');
    bar.setAttribute('aria-label', 'Pilih portal'); bar.dataset.portalSwitch = '1';
    bar.className = 'mb-4 p-1 rounded-xl bg-surface-container flex gap-1';
    bar.innerHTML = tab(login ? '/pelapor/masuk' : '/pelapor/daftar', cur === 'pelapor', 'campaign', 'Pelapor', 'Buat & pantau laporan')
      + tab(login ? '/masuk' : '/daftar', cur === 'staf', 'fact_check', 'Staf / SPI', 'Lihat semua laporan masuk');
    const card = form.closest('[class*="shadow"]') || form.parentElement;
    card.insertBefore(bar, card.firstChild);
  }

  function bindUser() {
    const u = POS.me.user;
    const set = (n, v) => $$(`[data-bind="${n}"]`).forEach((e) => (e.textContent = v));
    set('identifier', u.identifier); set('nama', u.nama); set('email', u.email); set('hub', u.hub || u.unit_kerja || '-');
    $$('img[data-bind-avatar]').forEach((img) => {
      if (u.avatar) img.src = u.avatar;
      else { const d = document.createElement('div'); d.className = 'w-8 h-8 rounded-full bg-primary-container text-white flex items-center justify-center font-label-sm text-label-sm font-bold'; d.textContent = u.inisial; img.replaceWith(d); }
    });
    $$('[data-bind="badge"]').forEach((e) => (e.textContent = POS.me.badge_laporan));
  }

  function bell() {
    const btn = $$('button').find((b) => /notifications/.test(b.textContent) && b.closest('header'));
    if (!btn) return;
    btn.classList.add('relative'); btn.setAttribute('aria-label', 'Notifikasi');
    $$('span', btn).filter((x) => !x.classList.contains('material-symbols-outlined')).forEach((x) => x.remove());
    const dot = document.createElement('span');
    dot.className = 'absolute top-1 right-1 min-w-4 h-4 px-1 rounded-full bg-secondary-container text-white text-[10px] font-bold flex items-center justify-center';
    btn.appendChild(dot);
    const paint = (n) => { dot.textContent = n > 9 ? '9+' : n; dot.style.display = n > 0 ? 'flex' : 'none'; };
    paint(POS.me.notif_unread);
    let panel;
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      if (panel) { panel.remove(); panel = null; return; }
      panel = document.createElement('div');
      panel.className = 'absolute right-0 top-11 w-80 max-w-[90vw] bg-surface-container-lowest rounded-xl shadow-[0_24px_48px_-12px_rgba(22,43,100,0.22)] border border-outline-variant/30 z-[150] text-left cursor-default';
      panel.innerHTML = '<p class="p-4 font-body-sm text-body-sm text-on-surface-variant">Memuat...</p>';
      btn.appendChild(panel);
      panel.addEventListener('click', (ev) => ev.stopPropagation());
      try {
        const r = await POS.api('GET', '/api/notifikasi');
        panel.innerHTML = `<div class="flex items-center justify-between px-4 py-3 border-b border-outline-variant/30"><span class="font-label-lg text-label-lg font-bold text-primary">Notifikasi</span>
          <button type="button" data-readall class="font-label-sm text-label-sm text-secondary font-bold">Tandai semua dibaca</button></div>
          <div class="max-h-80 overflow-y-auto divide-y divide-outline-variant/20">${r.items.length ? r.items.map((n) => `<a href="${esc(n.tautan || '#')}" class="block px-4 py-3 hover:bg-surface-container-low ${n.dibaca ? '' : 'bg-primary-fixed/30'}">
            <p class="font-label-md text-label-md font-bold text-on-surface">${esc(n.judul)}</p>${n.isi ? `<p class="font-body-sm text-body-sm text-on-surface-variant">${esc(n.isi)}</p>` : ''}
            <span class="font-label-sm text-label-sm text-outline">${esc(POS.fmtDT(n.waktu))}</span></a>`).join('') : '<p class="p-4 font-body-sm text-body-sm text-on-surface-variant">Belum ada notifikasi.</p>'}</div>`;
        $('[data-readall]', panel).onclick = async () => { await POS.api('POST', '/api/notifikasi/baca', {}); paint(0); $$('a', panel).forEach((a) => a.classList.remove('bg-primary-fixed/30')); };
        if (r.unread) { POS.api('POST', '/api/notifikasi/baca', {}).then(() => paint(0)).catch(() => {}); }
      } catch (er) { panel.innerHTML = `<p class="p-4 text-error font-body-sm text-body-sm">${esc(er.error)}</p>`; }
    });
    document.addEventListener('click', () => { if (panel) { panel.remove(); panel = null; } });
  }

  function langToggle() {
    const btns = $$('nav button').filter((b) => ['ID', 'EN'].includes(b.textContent.trim()));
    if (!btns.length) return;
    btns.forEach((b) => b.addEventListener('click', async () => {
      const code = b.textContent.trim().toLowerCase();
      localStorage.setItem('pos_lang', code);
      if (POS.me) { try { await POS.api('PUT', '/api/akun/preferensi', { bagian: 'bahasa', bahasa: code, zona_waktu: POS.me.pref.zona_waktu, format_tanggal: POS.me.pref.format_tanggal }); POS.me.pref.bahasa = code; } catch { /* abaikan */ } }
      POS.toast(code === 'id' ? 'Bahasa antarmuka: Bahasa Indonesia' : 'Preferensi English tersimpan. Terjemahan penuh antarmuka belum tersedia.');
    }));
  }

  /* ---------------------------------------------------------------- boot */
  async function boot() {
    const needAuth = !PUBLIC.includes(PAGE);
    try { POS.me = await POS.api('GET', '/api/me'); }
    catch (e) { if (needAuth) { location.href = '/masuk?next=' + encodeURIComponent(location.pathname + location.search); return; } }
    if (POS.me) { bindUser(); bell(); }
    wireLinks(); fixDeadLinks(); portalSwitch(); langToggle();
    const fn = POS.pages[PAGE];
    if (fn) await fn();
  }
  document.addEventListener('DOMContentLoaded', boot);
})();
