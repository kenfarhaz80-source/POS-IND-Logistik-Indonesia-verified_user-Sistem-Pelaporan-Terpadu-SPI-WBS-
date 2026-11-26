/* Laporan: dasbor SPI, laporan saya, form buat laporan, detail & disposisi, bukti digital. */
(() => {
  'use strict';
  const P = window.POS;
  const { $, $$, esc, api, modal, showErrors, fieldError, clearFieldErrors, busy, fmtDT, toast, size, debounce } = P;
  const qs = new URLSearchParams(location.search);
  const isSPI = () => P.me.user.role === 'spi';
  const bindAll = (n, v) => $$(`[data-bind="${n}"]`).forEach((e) => (e.textContent = v));

  const KAT_ICON = { deviasi: 'inventory_2', sop: 'fact_check', disiplin: 'gavel' };
  const STATUS_CLS = {
    'Draf': 'bg-amber-100 text-amber-900', 'Terdaftar': 'bg-surface-container-high text-on-surface-variant',
    'Investigasi SPI Lapangan': 'bg-surface-container-high text-secondary', 'Klarifikasi Satker': 'bg-primary-fixed text-primary',
    'Selesai': 'bg-emerald-100 text-emerald-800',
  };
  const PRIO = { Mendesak: ['Prioritas Urgent', 'bg-error-container text-on-error-container'], Tinggi: ['Prioritas Tinggi', 'bg-secondary-fixed text-on-secondary-fixed'] };
  const LVL_CLS = { KCP: 'bg-tertiary-fixed text-tertiary', KC: 'bg-secondary-fixed text-secondary', KCU: 'bg-secondary-fixed text-secondary', SPP: 'bg-secondary-fixed text-secondary', REGIONAL: 'bg-primary-container text-white', PUSAT: 'bg-primary text-white', MITRA: 'bg-surface-container-high text-on-surface' };
  const statusBadge = (r) => `<span class="px-3 py-1 rounded-full ${STATUS_CLS[r.status]} font-label-sm text-label-sm font-bold flex items-center gap-1.5">${r.status === 'Investigasi SPI Lapangan' ? '<span class="w-2 h-2 rounded-full bg-secondary animate-ping"></span>' : ''}${esc(r.status_label)}</span>`;
  const fileChip = (a) => { const [ic, cl] = P.fileIcon(a.ekstensi); return `<a href="${a.url}" target="_blank" rel="noopener" class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-container text-on-surface hover:bg-surface-container-high font-label-sm text-label-sm font-medium"><span class="material-symbols-outlined text-xs ${cl}">${ic}</span>${esc(a.nama)} <span class="text-outline">(${size(a.ukuran)})</span>${a.terverifikasi ? '<span class="material-symbols-outlined text-xs text-emerald-600" title="Terverifikasi SPI">verified</span>' : ''}</a>`; };
  const pelaporLine = (r) => r.pelapor.terlihat ? `${esc(r.pelapor.nama)}` : '<span class="italic">Pelapor Terlindungi</span>';

  /* ====================================================== bukti digital */
  function showEvidence(r) {
    const body = r.lampiran.length ? `<div class="grid sm:grid-cols-2 gap-3">${r.lampiran.map((a) => {
      const img = ['jpg', 'jpeg', 'png'].includes(a.ekstensi), vid = a.ekstensi === 'mp4', aud = a.ekstensi === 'm4a';
      const [ic, cl] = P.fileIcon(a.ekstensi);
      return `<div class="rounded-lg bg-surface-container-low p-3 space-y-2">${img ? `<img src="${a.url}" alt="${esc(a.nama)}" class="w-full h-36 object-cover rounded-lg bg-primary">` : vid ? `<video src="${a.url}" controls preload="metadata" class="w-full h-36 rounded-lg bg-black"></video>` : aud ? `<audio src="${a.url}" controls class="w-full"></audio>` : `<div class="h-20 rounded-lg bg-surface-container flex items-center justify-center"><span class="material-symbols-outlined text-4xl ${cl}">${ic}</span></div>`}
        <div class="min-w-0"><p class="font-label-md text-label-md font-bold truncate">${esc(a.nama)}</p><p class="font-label-sm text-label-sm text-on-surface-variant">${size(a.ukuran)} • ${a.ekstensi.toUpperCase()}${a.terverifikasi ? ' • Terverifikasi SPI' : ''}</p></div>
        <div class="flex gap-2"><a class="px-3 py-1 rounded-lg bg-surface-container-high text-primary font-label-sm text-label-sm font-bold" href="${a.url}" target="_blank" rel="noopener">Buka</a><a class="px-3 py-1 rounded-lg bg-surface-container-high text-primary font-label-sm text-label-sm font-bold" href="${a.url}?unduh=1">Unduh</a></div></div>`;
    }).join('')}</div>` : '<p class="font-body-md text-body-md text-on-surface-variant">Laporan ini tidak memiliki bukti digital terlampir.</p>';
    modal({ tone: 'info', icon: 'folder_shared', title: `Bukti Digital #${r.ref}`, subtitle: `${r.lampiran.length} berkas pada Evidence Vault`, body, wide: true, actions: [{ label: 'Tutup', primary: true }] });
  }

  async function verifyEvidence(r, after) {
    try { await api('POST', `/api/laporan/${r.ref}/disposisi`, { aksi: 'verifikasi_bukti' }); toast('Bukti lapangan diverifikasi. Status diteruskan ke Investigasi SPI.'); after && after(); }
    catch (er) { toast(er.error, 'err'); }
  }

  /* ====================================================== tanda terima */
  function printReceipt(r) {
    const w = window.open('', '_blank', 'width=820,height=900');
    if (!w) { toast('Pop-up diblokir peramban. Izinkan pop-up untuk mencetak tanda terima.', 'err'); return; }
    const rows = [['Nomor Tiket', '#' + r.ref], ['Klasifikasi', 'WASUM (Pengawasan Umum & SOP)'], ['Kategori', r.kategori_label],
      ['Judul', r.judul], ['Waktu Pelaporan', fmtDT(r.dikirim_pada)], ['Waktu Kejadian', fmtDT(r.waktu_kejadian)], ['Lokasi', r.lokasi],
      ['Pelapor', r.anonim && !r.milik_saya && !isSPI() ? 'Pelapor Terlindungi' : r.anonim ? 'Pelapor Anonim (identitas dikelola SPI)' : `${r.pelapor.nama} (NIPPOS: ${r.pelapor.nippos})`],
      ['Pihak Terlapor', r.terlapor.nama], ['Status', r.status_label], ['Prioritas', r.prioritas], ['Jumlah Bukti', r.jumlah_lampiran + ' berkas']];
    w.document.write(`<!DOCTYPE html><html lang="id"><head><meta charset="utf-8"><title>Tanda Terima ${esc(r.ref)}</title><style>
      body{font-family:system-ui,sans-serif;color:#191c1e;max-width:700px;margin:32px auto;padding:0 24px}h1{color:#162b64;margin:0}.sub{color:#454650;margin:4px 0 24px}
      table{width:100%;border-collapse:collapse}td{padding:9px 6px;border-bottom:1px solid #e0e3e6;vertical-align:top}td:first-child{width:36%;color:#454650;font-weight:600}
      .bar{height:6px;background:linear-gradient(90deg,#162b64,#ff642d);margin-bottom:20px}.foot{margin-top:28px;font-size:12px;color:#757681}@media print{button{display:none}}</style></head><body>
      <div class="bar"></div><h1>Tanda Terima Laporan Resmi</h1><p class="sub">Satuan Pengawasan Intern (SPI) — PT Pos Indonesia (Persero)</p>
      <table>${rows.map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join('')}</table>
      <p class="foot">Dicetak ${esc(fmtDT(new Date().toISOString()))}. Dokumen ini adalah bukti registrasi laporan dan tidak menyatakan hasil pemeriksaan.</p>
      <button onclick="window.print()" style="margin-top:16px;padding:10px 18px">Cetak / Simpan sebagai PDF</button></body></html>`);
    w.document.close(); setTimeout(() => w.print(), 400);
  }

  /* ====================================================== detail & disposisi */
  const SLA_UI = {
    aman: ['bg-emerald-100 text-emerald-800', 'schedule', (p) => `Sisa ${p.sisa_hari} hari kerja`],
    mendekati: ['bg-amber-100 text-amber-900', 'warning', (p) => (p.sisa_hari <= 0 ? 'Jatuh tempo hari ini' : `Tinggal ${p.sisa_hari} hari kerja`)],
    terlambat: ['bg-error-container text-on-error-container', 'alarm', (p) => `Terlambat ${Math.abs(p.sisa_hari)} hari kerja`],
    selesai_tepat: ['bg-emerald-100 text-emerald-800', 'verified', () => 'Selesai tepat waktu'],
    selesai_terlambat: ['bg-error-container text-on-error-container', 'history', () => 'Selesai, melewati SLA'],
  };
  const slaChip = (p) => { const u = SLA_UI[p.sla]; return u ? `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full ${u[0]} font-label-sm text-label-sm font-bold"><span class="material-symbols-outlined text-sm">${u[1]}</span>${esc(u[2](p))}</span>` : ''; };
  const progressBar = (p) => `<div class="flex gap-1" role="progressbar" aria-valuenow="${p.persen}" aria-valuemin="0" aria-valuemax="100" aria-label="Progres penanganan ${p.persen}%">${[1, 2, 3, 4].map((n) => `<div class="h-2 flex-1 rounded-full ${p.tahap > n || (p.tahap === n && p.selesai) ? 'bg-primary' : p.tahap === n ? 'bg-secondary-container animate-pulse' : 'bg-surface-container-high'}"></div>`).join('')}</div>`;
  const ORDER = ['Terdaftar', 'Investigasi SPI Lapangan', 'Klarifikasi Satker', 'Selesai'];

  function pesanHtml(r) {
    const spi = r.peran_lihat === 'spi';
    const items = r.pesan.map((m) => {
      const internal = m.jenis === 'catatan', mine = m.saya;
      const tone = internal ? 'bg-amber-50 border border-amber-200' : m.peran === 'spi' ? 'bg-primary-fixed/50' : 'bg-surface-container-low';
      const label = internal ? 'Catatan internal SPI' : m.jenis === 'permintaan' ? 'Permintaan informasi' : m.peran === 'spi' ? 'Pesan SPI' : 'Balasan pelapor';
      return `<div class="rounded-lg p-3 ${tone} ${mine ? 'ml-6' : 'mr-6'}"><div class="flex items-center justify-between gap-2 mb-1"><span class="font-label-sm text-label-sm font-bold ${internal ? 'text-amber-800' : 'text-primary'}">${esc(label)} • ${esc(m.nama)}</span><span class="font-label-sm text-label-sm text-outline">${esc(fmtDT(m.waktu))}</span></div><p class="font-body-sm text-body-sm whitespace-pre-line">${esc(m.isi)}</p></div>`;
    }).join('') || '<p class="font-body-sm text-body-sm text-on-surface-variant">Belum ada percakapan pada laporan ini.</p>';
    const composer = r.boleh_pesan ? `<div class="space-y-2 pt-1">${spi ? `<select id="pesan-jenis" class="h-9 px-2 rounded-lg border border-outline-variant bg-white font-label-md text-label-md"><option value="permintaan">Permintaan informasi ke pelapor (pelapor diberi tahu)</option><option value="catatan">Catatan internal SPI (tidak terlihat pelapor)</option></select>` : ''}
        <textarea id="pesan-isi" rows="2" maxlength="2000" class="w-full px-3 py-2 rounded-lg border border-outline-variant" placeholder="${spi ? 'Tulis pertanyaan untuk pelapor atau catatan internal…' : 'Tulis balasan atau keterangan tambahan untuk SPI…'}"></textarea>
        <div class="flex items-center justify-between gap-2"><p id="pesan-err" class="text-error font-body-sm text-body-sm"></p><button type="button" id="pesan-kirim" class="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary text-white font-label-md text-label-md font-bold hover:bg-primary-container"><span class="material-symbols-outlined text-base">send</span>${spi ? 'Kirim' : 'Kirim Balasan'}</button></div></div>`
      : (r.status === 'Selesai' ? '<p class="font-label-sm text-label-sm text-outline">Laporan telah ditutup; percakapan dikunci.</p>' : '');
    return `<div><p class="font-label-sm text-label-sm text-outline font-bold uppercase mb-2">Komunikasi dengan ${spi ? 'Pelapor' : 'SPI'}</p><div class="space-y-2 max-h-64 overflow-y-auto" id="pesan-list">${items}</div>${composer}</div>`;
  }

  function detailBody(r) {
    const p = r.progres, spi = r.peran_lihat === 'spi';
    const kv = [['Klasifikasi', 'WASUM'], ['Kategori', r.kategori_label], ['Prioritas', r.prioritas], ['Waktu Kejadian', fmtDT(r.waktu_kejadian)], ['Lokasi', r.lokasi],
      ['Pelapor', r.pelapor.terlihat ? `${r.pelapor.nama} (${r.pelapor.nippos})` : 'Pelapor Terlindungi'], ['Unit Pelapor', [r.pelapor.tingkat, r.pelapor.unit].filter(Boolean).join(' • ')],
      ['Pihak Terlapor', r.terlapor.nama + (r.terlapor.nippos ? ` (${r.terlapor.nippos})` : '')], ['Unit Terlapor', [r.terlapor.tingkat, r.terlapor.unit].filter(Boolean).join(' • ')]];
    kv.push(['AWB / Connote', r.awb], ['Armada', r.plat_armada], ['Rute', r.rute], ['Deviasi', r.deviasi], ['Tipologi', r.tipologi]);
    if (r.investigator) kv.push(['Investigator', r.investigator]);
    if (r.tenggat) kv.push(['Tenggat', fmtDT(r.tenggat, false)]);
    if (r.no_berita_acara) kv.push(['No. Berita Acara', r.no_berita_acara]);
    const timeline = (r.disposisi || []).map((d) => `<li class="relative pl-6"><span class="absolute left-0 top-1 w-3 h-3 rounded-full ${d.internal ? 'bg-amber-500' : 'bg-primary'}"></span>
      <p class="font-label-md text-label-md font-bold">${esc(d.catatan || d.aksi)}${d.internal ? ' <span class="px-1.5 rounded bg-amber-100 text-amber-900 font-label-sm text-label-sm">internal</span>' : ''}</p><p class="font-label-sm text-label-sm text-outline">${esc(fmtDT(d.waktu))}${d.unit ? ' • ' + esc(d.unit) : ''}${d.oleh ? ' • ' + esc(d.oleh) : ''}</p></li>`).join('');
    const bukti = r.lampiran.map(fileChip).map((c, i) => r.lampiran[i].susulan ? c.replace('</a>', ' <em class="text-secondary">susulan</em></a>') : c).join('') || `<span class="font-body-sm text-body-sm text-on-surface-variant">${r.jumlah_lampiran ? 'Hanya dapat dilihat oleh pelapor dan tim SPI.' : 'Tidak ada bukti.'}</span>`;
    let form = '';
    if (r.boleh_disposisi) {
      const idx = Math.max(0, ORDER.indexOf(r.status));
      form = `<div class="rounded-xl border border-outline-variant/50 p-space-md space-y-3" id="disp-form"><p class="font-label-lg text-label-lg font-bold text-primary flex items-center gap-2"><span class="material-symbols-outlined">alt_route</span>Tindakan Disposisi SPI</p>
        <div class="grid sm:grid-cols-2 gap-3"><label class="font-label-sm text-label-sm font-bold">Status Penanganan<select id="d-status" class="mt-1 w-full h-10 px-2 rounded-lg border border-outline-variant bg-white">
          ${ORDER.map((s, i) => `<option value="${s}" ${s === r.status ? 'selected' : ''} ${i < idx || (s === 'Selesai' && r.tahap < 2) ? 'disabled' : ''}>${s}${s === 'Selesai' && r.tahap < 2 ? ' (setelah investigasi)' : ''}</option>`).join('')}</select></label>
        <label class="font-label-sm text-label-sm font-bold">Investigator<input id="d-inv" value="${esc(r.investigator || '')}" class="mt-1 w-full h-10 px-3 rounded-lg border border-outline-variant" placeholder="Tim / nama pemeriksa"></label>
        <label class="font-label-sm text-label-sm font-bold">Tenggat Klarifikasi<input id="d-tenggat" type="date" value="${esc(r.tenggat || '')}" class="mt-1 w-full h-10 px-3 rounded-lg border border-outline-variant"></label>
        <label class="font-label-sm text-label-sm font-bold">Prioritas<select id="d-prio" class="mt-1 w-full h-10 px-2 rounded-lg border border-outline-variant bg-white">${['Normal', 'Tinggi', 'Mendesak'].map((s) => `<option ${s === r.prioritas ? 'selected' : ''}>${s}</option>`).join('')}</select></label></div>
        <label class="font-label-sm text-label-sm font-bold block">Catatan / Keterangan Resolusi <span class="text-outline font-normal">(wajib saat menutup laporan)</span><textarea id="d-cat" rows="2" class="mt-1 w-full px-3 py-2 rounded-lg border border-outline-variant" maxlength="1000"></textarea></label>
        <label class="flex items-center gap-2 font-label-md text-label-md"><input type="checkbox" id="d-publik" checked> Tampilkan catatan ini kepada pelapor <span class="text-outline font-normal">(hilangkan centang untuk catatan internal)</span></label>
        <p id="d-err" class="text-error font-body-sm text-body-sm"></p></div>`;
    }
    const prog = p ? `<div class="rounded-xl bg-surface-container-low p-space-md space-y-2"><div class="flex items-center justify-between"><span class="font-label-lg text-label-lg font-bold text-primary">Progres ${p.persen}% • Tahap ${p.tahap} dari 4</span>${slaChip(p)}</div>${progressBar(p)}
        <p class="font-body-sm text-body-sm text-on-surface-variant"><strong>${esc(p.tahap_nama)}.</strong> ${p.selesai ? 'Laporan telah ditutup.' : 'Berikutnya: ' + esc(p.langkah_berikut)}</p>
        ${p.selesai || !p.menunggu ? '' : `<p class="font-label-md text-label-md ${p.menunggu === 'Pelapor' ? 'text-secondary' : 'text-on-surface'} font-bold">Menunggu: ${esc(p.menunggu === 'Pelapor' && !spi ? 'Anda (pelapor)' : p.menunggu)}</p>`}</div>` : '';
    const tambah = r.boleh_susulan ? `<button type="button" id="btn-susulan" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container-high text-primary font-label-sm text-label-sm font-bold hover:bg-surface-container-highest"><span class="material-symbols-outlined text-base">upload_file</span>Tambah Bukti Susulan</button><input id="susulan-input" class="hidden" type="file" multiple accept=".mp4,.m4a,.pdf,.jpg,.jpeg,.png,.csv,.xlsx"><div id="susulan-status" class="mt-2 space-y-1"></div>` : '';
    return `<div class="space-y-space-md"><div class="flex flex-wrap gap-2">${statusBadge(r)}</div>${prog}
      <dl class="grid sm:grid-cols-2 gap-x-6 gap-y-2">${kv.filter(([, v]) => v).map(([k, v]) => `<div><dt class="font-label-sm text-label-sm text-outline font-bold uppercase">${esc(k)}</dt><dd class="font-body-md text-body-md text-on-surface break-words">${esc(v)}</dd></div>`).join('')}</dl>
      <div><p class="font-label-sm text-label-sm text-outline font-bold uppercase mb-1">Uraian Kronologis</p><p class="font-body-md text-body-md whitespace-pre-line">${esc(r.uraian)}</p></div>
      ${r.resolusi ? `<div class="p-3 rounded-lg bg-emerald-50 text-emerald-900 font-body-sm text-body-sm"><strong>Resolusi:</strong> ${esc(r.resolusi)}</div>` : ''}
      <div><p class="font-label-sm text-label-sm text-outline font-bold uppercase mb-1">Bukti Terlampir (${r.jumlah_lampiran})</p><div class="flex flex-wrap gap-2 mb-2">${bukti}</div>${tambah}</div>
      ${r.status !== 'Draf' ? pesanHtml(r) : ''}
      ${timeline ? `<div><p class="font-label-sm text-label-sm text-outline font-bold uppercase mb-2">Riwayat Penanganan</p><ol class="space-y-3 border-l-2 border-primary/20 ml-1.5">${timeline}</ol></div>` : ''}${form}</div>`;
  }

  async function openDetail(ref, after) {
    let r;
    try { r = await api('GET', '/api/laporan/' + encodeURIComponent(ref)); } catch (er) { toast(er.error, 'err'); return; }
    let actions = [];
    if (r.boleh_disposisi) {
      const send = (build) => async () => {
        const err = $('#d-err'); err.textContent = '';
        try { await api('POST', `/api/laporan/${r.ref}/disposisi`, build()); toast('Disposisi berhasil dicatat.'); after && after(r.ref); }
        catch (er) { err.textContent = er.error; return false; }
      };
      const pub = () => $('#d-publik').checked;
      actions.push({ label: 'Verifikasi Bukti', icon: 'checklist', onClick: send(() => ({ aksi: 'verifikasi_bukti', catatan: $('#d-cat').value, tampilkan_pelapor: pub() })) });
      if (r.level_berikut) actions.push({ label: `Teruskan ke ${r.level_berikut}`, icon: 'forward_to_inbox', onClick: send(() => ({ aksi: 'teruskan', level: r.level_berikut, catatan: $('#d-cat').value, tampilkan_pelapor: pub() })) });
      actions.push({ label: 'Simpan Perubahan', primary: true, icon: 'save', onClick: send(() => ({ aksi: 'ubah_status', status: $('#d-status').value, investigator: $('#d-inv').value, tenggat: $('#d-tenggat').value, prioritas: $('#d-prio').value, catatan: $('#d-cat').value, tampilkan_pelapor: pub() })) });
    } else if (r.boleh_ubah) {
      actions.push({ label: 'Hapus Draf', icon: 'delete', onClick: async () => { if (!confirm('Hapus draf ini beserta bukti yang terlampir?')) return false; try { await api('DELETE', '/api/laporan/draf/' + r.id); toast('Draf dihapus.'); after && after(); } catch (er) { toast(er.error, 'err'); } } });
      actions.push({ label: 'Lanjutkan Draf', primary: true, icon: 'edit_document', onClick: () => { location.href = '/pelapor/laporan-baru?draf=' + r.id; return false; } });
    } else {
      actions.push({ label: 'Cetak Tanda Terima', icon: 'print', onClick: () => { printReceipt(r); return false; } }, { label: 'Tutup', primary: true });
    }
    const m = modal({ tone: 'info', icon: 'description', wide: true, title: `#${r.ref}`, subtitle: r.judul, body: detailBody(r), actions });
    const wire = () => {
      const box = $('[data-body]', m.el);
      const refresh = (nr) => { r = nr; box.innerHTML = detailBody(r); wire(); after && after(r.ref, true); };
      const kirim = $('#pesan-kirim', box);
      if (kirim) kirim.onclick = async () => {
        const isi = $('#pesan-isi', box).value.trim(), err = $('#pesan-err', box); err.textContent = '';
        if (isi.length < 3) { err.textContent = 'Tulis pesan minimal 3 karakter.'; return; }
        busy(kirim, true, 'Mengirim…');
        try { const nr = await api('POST', `/api/laporan/${r.ref}/pesan`, { isi, jenis: ($('#pesan-jenis', box) || {}).value }); toast('Pesan terkirim.'); refresh(nr); const l = $('#pesan-list', m.el); l && (l.scrollTop = l.scrollHeight); }
        catch (er) { busy(kirim, false); err.textContent = er.error; }
      };
      const bs = $('#btn-susulan', box), inp = $('#susulan-input', box);
      if (bs) {
        bs.onclick = () => inp.click();
        inp.onchange = async () => {
          const files = [...inp.files]; inp.value = ''; const st = $('#susulan-status', box); let nr = null;
          for (const f of files) {
            const bad = P.checkFile(f); if (bad) { toast(bad, 'err'); continue; }
            const row = document.createElement('div'); row.className = 'font-label-sm text-label-sm'; st.appendChild(row);
            const up = P.upload(`/api/laporan/${r.ref}/lampiran`, f, (pct) => (row.innerHTML = `${esc(f.name)} — mengunggah ${pct}% <span class="inline-block align-middle w-24 h-1.5 bg-surface-container-high rounded"><span class="block h-full bg-secondary-container rounded" style="width:${pct}%"></span></span>`));
            try { nr = await up.promise; row.remove(); } catch (er) { row.className += ' text-error'; row.textContent = er.error; }
          }
          if (nr) { toast(`${files.length} bukti tambahan terkirim ke SPI.`); refresh(nr); }
        };
      }
    };
    wire();
  }

  /* ====================================================== pratinjau (panel kanan): proses & progres */
  function renderPreview(r, mode) {
    const box = $('#preview');
    if (!r) { box.innerHTML = '<div class="py-8 text-center text-on-surface-variant font-body-sm text-body-sm">Pilih satu laporan untuk melihat cuplikan tiket, proses, dan progresnya.</div>'; return; }
    const p = r.progres, spi = mode !== 'pelapor', draf = r.status === 'Draf';
    const img = r.lampiran.find((a) => ['jpg', 'jpeg', 'png'].includes(a.ekstensi));
    const others = r.lampiran.filter((a) => a !== img).slice(0, 2);
    const verif = r.lampiran.filter((a) => a.terverifikasi).length;
    const lvlIdx = ['KCP', 'KC', 'REGIONAL', 'PUSAT'].indexOf(r.level_disposisi) + 1;
    const node = { done: ['bg-primary text-white', 'check'], aktif: ['bg-secondary-container ring-4 ring-secondary-container/20 text-white', 'pending'], menunggu: ['bg-surface-container-high border-2 border-outline text-outline', 'hourglass_empty'] };
    const steps = (r.langkah || []).map((l) => `<div class="relative ${l.state === 'menunggu' ? 'opacity-60' : ''}"><div class="absolute -left-6 top-0.5 w-5 h-5 rounded-full ${node[l.state][0]} flex items-center justify-center"><span class="material-symbols-outlined text-xs">${node[l.state][1]}</span></div>
      <div class="space-y-0.5"><span class="font-label-md text-label-md font-bold ${l.state === 'aktif' ? 'text-secondary' : 'text-on-surface'}">${esc(l.judul)}</span><p class="font-body-sm text-body-sm text-on-surface-variant">${esc(l.deskripsi)}</p>
      ${l.waktu ? `<span class="font-label-sm text-label-sm text-outline">${esc(fmtDT(l.waktu))}</span>` : l.state === 'aktif' ? '<span class="font-label-sm text-label-sm text-secondary font-bold">Sedang berlangsung</span>' : ''}</div></div>`).join('');
    const hier = spi ? (r.hierarki || []).map((h) => `<div class="relative ${h.state === 'menunggu' ? 'opacity-60' : ''}"><div class="absolute -left-6 top-0.5 w-5 h-5 rounded-full ${node[h.state][0]} flex items-center justify-center"><span class="material-symbols-outlined text-xs">${node[h.state][1]}</span></div>
      <div class="space-y-0.5"><div class="flex items-center gap-2"><span class="px-1.5 rounded ${LVL_CLS[h.level]} font-label-sm text-label-sm font-extrabold">${h.level}</span><span class="font-label-md text-label-md font-bold ${h.state === 'aktif' ? 'text-secondary' : 'text-on-surface'}">${esc(h.unit)}</span></div>
      ${h.catatan ? `<p class="font-body-sm text-body-sm text-on-surface-variant">${esc(h.catatan)}</p>` : ''}${h.waktu ? `<span class="font-label-sm text-label-sm text-outline">${esc(fmtDT(h.waktu))}</span>` : ''}</div></div>`).join('') : '';
    const prio = PRIO[r.prioritas];
    const needsReply = p && p.permintaan_terbuka;
    const info = (ic, k, v) => `<div class="p-2 rounded-lg bg-surface-container-lowest"><div class="flex items-center gap-1 font-label-sm text-label-sm text-outline font-bold"><span class="material-symbols-outlined text-sm">${ic}</span>${k}</div><div class="font-label-md text-label-md font-bold text-on-surface break-words">${v}</div></div>`;
    const progress = draf ? `<div class="p-3 rounded-xl bg-amber-50 text-amber-900 font-body-sm text-body-sm flex gap-2"><span class="material-symbols-outlined">edit_note</span><span>Draf — belum dikirim ke SPI. Lengkapi dan kirim agar proses penanganan dimulai.</span></div>` :
      `<div class="space-y-3 p-3 rounded-xl bg-surface-container-low"><div class="flex items-end justify-between"><div><div class="font-label-sm text-label-sm uppercase tracking-wider text-outline font-bold">Progres Penanganan</div><div class="font-headline-md text-headline-md font-extrabold text-primary leading-none mt-1">${p.persen}%</div></div>${slaChip(p)}</div>
        ${progressBar(p)}<p class="font-label-md text-label-md text-on-surface-variant">Tahap <strong>${p.tahap}</strong> dari 4 • <strong>${esc(p.tahap_nama)}</strong></p>
        <div class="grid grid-cols-2 gap-2">${info('hourglass_top', 'Menunggu', p.selesai ? 'Selesai' : esc(p.menunggu === 'Pelapor' && !spi ? 'Anda (pelapor)' : p.menunggu || '-'))}${info('badge', 'Penanggung jawab', esc(p.penanggung_jawab))}
        ${info('event', 'Batas SLA', esc(fmtDT(p.batas_sla, false)))}${info('update', 'Diperbarui', esc(fmtDT(p.diperbarui_pada)))}</div>
        ${p.tenggat_klarifikasi && !p.selesai ? `<p class="font-label-sm text-label-sm text-secondary font-bold">Tenggat klarifikasi Satker: ${esc(fmtDT(p.tenggat_klarifikasi, false))}</p>` : ''}
        ${p.selesai ? '' : `<p class="font-body-sm text-body-sm text-on-surface-variant"><strong>Berikutnya:</strong> ${esc(p.langkah_berikut)}</p>`}
        ${needsReply ? `<button type="button" data-pv="detail" class="w-full text-left p-2.5 rounded-lg bg-secondary-fixed text-on-secondary-fixed font-label-md text-label-md font-bold flex items-center gap-2"><span class="material-symbols-outlined">mark_chat_unread</span>${spi ? 'Menunggu balasan pelapor atas permintaan SPI' : 'SPI meminta informasi tambahan — balas sekarang'}</button>` : ''}</div>`;
    const aktivitas = !draf && p && p.aktivitas.length ? `<div class="space-y-2"><span class="font-label-sm text-label-sm uppercase tracking-wider text-outline font-bold">Aktivitas Terakhir</span>${p.aktivitas.map((a) => `<div class="flex gap-2 font-body-sm text-body-sm"><span class="material-symbols-outlined text-base ${a.internal ? 'text-amber-600' : 'text-primary'}">${a.internal ? 'lock' : 'history'}</span><div class="min-w-0"><p class="text-on-surface">${esc(a.catatan || '-')}</p><span class="font-label-sm text-label-sm text-outline">${esc(fmtDT(a.waktu))}</span></div></div>`).join('')}</div>` : '';
    box.innerHTML = `<div class="flex items-center justify-between pb-1"><div class="flex items-center gap-2"><span class="material-symbols-outlined text-secondary-container text-2xl">visibility</span><h3 class="font-headline-sm text-headline-sm font-extrabold text-primary">Cuplikan Tiket Aktif</h3></div>
      <span class="px-2.5 py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed font-label-sm text-label-sm font-bold">Live Preview</span></div>
      <div class="p-3 rounded-xl bg-surface-container-low space-y-2"><div class="flex items-center justify-between gap-2"><span class="font-label-lg text-label-lg font-black text-primary break-all">#${esc(r.ref)}</span>${prio ? `<span class="px-2 py-0.5 rounded ${prio[1]} font-label-sm text-label-sm font-bold">${prio[0].replace('Prioritas ', '')}</span>` : ''}</div>
        <p class="font-body-sm text-body-sm text-on-surface font-medium leading-tight">${esc(r.judul)}</p><div class="flex">${statusBadge(r)}</div></div>
      ${progress}
      <div class="space-y-2"><span class="font-label-sm text-label-sm uppercase tracking-wider text-outline font-bold">Dokumentasi Bukti Lapangan${r.jumlah_lampiran ? ` • ${r.jumlah_lampiran} berkas${verif ? `, ${verif} terverifikasi` : ''}` : ''}</span>
        ${img ? `<a href="${img.url}" target="_blank" rel="noopener" class="block relative rounded-xl overflow-hidden shadow-sm h-40 bg-primary"><img class="w-full h-full object-cover" src="${img.url}" alt="${esc(img.nama)}"><div class="absolute inset-0 bg-gradient-to-t from-primary/90 via-primary/20 to-transparent flex items-end p-3"><div class="text-white min-w-0"><span class="font-label-sm text-label-sm text-secondary-container font-extrabold flex items-center gap-1"><span class="material-symbols-outlined text-sm">photo_camera</span>${esc(img.nama)}</span></div></div></a>`
          : `<div class="h-20 rounded-xl bg-surface-container-low flex flex-col items-center justify-center text-outline"><span class="material-symbols-outlined text-3xl">${r.lampiran.length ? 'folder_open' : 'image_not_supported'}</span><span class="font-label-sm text-label-sm">${r.lampiran.length ? 'Tidak ada foto — lihat berkas lain' : r.jumlah_lampiran ? 'Bukti hanya terlihat oleh pelapor & SPI' : 'Tidak ada bukti terlampir'}</span></div>`}
        ${others.length ? `<div class="grid grid-cols-2 gap-2 pt-1">${others.map((a) => { const [ic, cl] = P.fileIcon(a.ekstensi); return `<a href="${a.url}" target="_blank" rel="noopener" class="p-2.5 rounded-lg bg-surface-container flex items-center gap-2 hover:bg-surface-container-high"><span class="material-symbols-outlined ${cl} text-xl">${ic}</span><div class="min-w-0"><p class="font-label-sm text-label-sm font-bold text-on-surface truncate">${esc(a.nama)}</p><p class="font-label-sm text-label-sm text-on-surface-variant">${size(a.ukuran)}</p></div></a>`; }).join('')}</div>` : ''}</div>
      ${draf ? '' : `<div class="space-y-3 pt-1"><span class="font-label-sm text-label-sm uppercase tracking-wider text-outline font-bold">Proses Penanganan</span><div class="relative pl-6 space-y-4"><div class="absolute left-2.5 top-2 bottom-2 w-0.5 bg-primary/20"></div>${steps}</div></div>`}
      ${spi && !draf ? `<div class="space-y-3 pt-1"><div class="flex items-center justify-between"><span class="font-label-sm text-label-sm uppercase tracking-wider text-outline font-bold">Jalur Disposisi Hierarki Pos</span><span class="font-label-sm text-label-sm text-secondary font-bold">Level ${lvlIdx} dari 4</span></div><div class="relative pl-6 space-y-4"><div class="absolute left-2.5 top-2 bottom-2 w-0.5 bg-primary/20"></div>${hier}</div></div>` : ''}
      ${aktivitas}
      <div class="flex flex-col gap-2 pt-1"><button type="button" data-pv="detail" class="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-primary text-white font-label-md text-label-md font-bold hover:bg-primary-container"><span class="material-symbols-outlined text-lg">open_in_full</span>${draf ? 'Kelola Draf' : spi ? 'Detail, Pesan & Disposisi' : 'Detail, Pesan & Bukti Susulan'}</button>
        ${isSPI() && r.boleh_disposisi && r.level_berikut ? `<button type="button" data-pv="teruskan" class="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-secondary-container text-white font-label-md text-label-md font-bold hover:brightness-110"><span class="material-symbols-outlined text-lg">forward_to_inbox</span>Teruskan Disposisi ke ${esc(r.level_berikut)}</button>` : ''}
        ${r.no_tiket ? `<button type="button" data-pv="cetak" class="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-surface-container-high text-primary font-label-md text-label-md font-bold hover:bg-surface-container-highest"><span class="material-symbols-outlined text-lg">print</span>${r.no_berita_acara ? `Cetak Berita Acara (${esc(r.no_berita_acara)})` : 'Cetak Tanda Terima'}</button>` : ''}</div>`;
    $$('[data-pv=detail]', box).forEach((b) => (b.onclick = () => openDetail(r.ref, (ref) => ctl.load(ref))));
    const t = $('[data-pv=teruskan]', box);
    if (t) t.onclick = async () => { busy(t, true, 'Meneruskan...'); try { await api('POST', `/api/laporan/${r.ref}/disposisi`, { aksi: 'teruskan' }); toast('Disposisi diteruskan.'); ctl.load(r.ref); } catch (er) { busy(t, false); toast(er.error, 'err'); } };
    const c = $('[data-pv=cetak]', box); if (c) c.onclick = () => printReceipt(r);
  }

  /* ====================================================== kontroler daftar */
  let ctl = null;
  function makeList({ endpoint, card, mode, onStats, lingkup }) {
    const st = { page: 1, per: 10, items: [], selected: null, tingkat: [] };
    const val = (id) => (($('#' + id) || {}).value || '').trim();
    const params = (withPage = true) => {
      const p = new URLSearchParams();
      [['q', 'f-q'], ['kategori', 'f-kategori'], ['status', 'f-status'], ['dari', 'f-dari'], ['sampai', 'f-sampai'], ['urut', 'f-urut']].forEach(([k, id]) => val(id) && p.set(k, val(id)));
      const t = val('f-tingkat'); const tl = t ? [t.toUpperCase()] : st.tingkat; if (tl.length) p.set('tingkat', tl.join(','));
      if (withPage) { p.set('page', st.page); p.set('per_page', st.per); }
      return p;
    };
    const chips = () => {
      const box = $('#chips'); if (!box) return;
      const defs = [['f-q', (v) => `Cari: ${v}`], ['f-kategori', (v) => `Kategori: ${({ deviasi: 'Deviasi Muatan & Rusak', sop: 'Pelanggaran SOP Manifest', disiplin: 'Disiplin Kerja & Fraud' })[v]}`],
        ['f-status', (v) => `Status: ${v}`], ['f-tingkat', (v) => `Satker: ${v.toUpperCase()}`], ['f-dari', (v) => `Dari: ${v}`], ['f-sampai', (v) => `Sampai: ${v}`]];
      const act = defs.filter(([id]) => val(id)).map(([id, f]) => ({ id, t: f(val(id)) }));
      if (st.tingkat.length) act.push({ id: 'tingkat', t: 'Satker: ' + st.tingkat.join(', ') });
      box.querySelectorAll('[data-chip],[data-reset]').forEach((e) => e.remove());
      act.forEach((a) => { const s = document.createElement('span'); s.dataset.chip = a.id; s.className = 'inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-primary-fixed text-primary font-label-sm text-label-sm font-bold';
        s.innerHTML = `${esc(a.t)} <button type="button" aria-label="Hapus filter" class="flex"><span class="material-symbols-outlined text-sm">close</span></button>`;
        s.querySelector('button').onclick = () => { if (a.id === 'tingkat') st.tingkat = []; else $('#' + a.id).value = ''; st.page = 1; load(); }; box.appendChild(s); });
      if (act.length) { const b = document.createElement('button'); b.type = 'button'; b.dataset.reset = '1'; b.className = 'text-secondary hover:underline font-label-sm text-label-sm font-bold'; b.textContent = 'Reset Semua Filter';
        b.onclick = () => { ['f-q', 'f-kategori', 'f-status', 'f-tingkat', 'f-dari', 'f-sampai'].forEach((id) => $('#' + id) && ($('#' + id).value = '')); st.tingkat = []; st.page = 1; load(); }; box.appendChild(b); }
      else { const s = document.createElement('span'); s.dataset.chip = '0'; s.className = 'text-outline font-label-sm text-label-sm'; s.textContent = 'Tidak ada filter aktif'; box.appendChild(s); }
    };
    const pager = (r) => {
      const box = $('#pager'); const from = r.total ? (r.page - 1) * r.per_page + 1 : 0, to = Math.min(r.total, r.page * r.per_page);
      const nums = []; for (let i = 1; i <= r.halaman; i++) if (i === 1 || i === r.halaman || Math.abs(i - r.page) <= 1) nums.push(i); else if (nums[nums.length - 1] !== '…') nums.push('…');
      box.innerHTML = `<span class="font-body-sm text-body-sm text-on-surface-variant">Menampilkan <strong>${from} - ${to}</strong> dari <strong>${r.total}</strong> laporan</span>
        <div class="flex items-center gap-1"><button type="button" data-pg="${r.page - 1}" ${r.page <= 1 ? 'disabled' : ''} class="w-9 h-9 rounded-lg flex items-center justify-center hover:bg-surface-container disabled:opacity-40" aria-label="Sebelumnya"><span class="material-symbols-outlined">chevron_left</span></button>
        ${nums.map((n) => n === '…' ? '<span class="px-1 text-outline">…</span>' : `<button type="button" data-pg="${n}" class="w-9 h-9 rounded-lg font-label-md text-label-md font-bold ${n === r.page ? 'bg-primary text-white' : 'hover:bg-surface-container'}">${n}</button>`).join('')}
        <button type="button" data-pg="${r.page + 1}" ${r.page >= r.halaman ? 'disabled' : ''} class="w-9 h-9 rounded-lg flex items-center justify-center hover:bg-surface-container disabled:opacity-40" aria-label="Berikutnya"><span class="material-symbols-outlined">chevron_right</span></button></div>`;
      $$('[data-pg]', box).forEach((b) => (b.onclick = () => { st.page = +b.dataset.pg; load(); window.scrollTo({ top: 0, behavior: 'smooth' }); }));
    };
    const select = async (ref) => {
      st.selected = ref;
      $$('[data-card]').forEach((c) => c.classList.toggle('ring-2', c.dataset.card === ref)); $$('[data-card]').forEach((c) => c.classList.toggle('ring-secondary-container', c.dataset.card === ref));
      try { renderPreview(await api('GET', '/api/laporan/' + encodeURIComponent(ref)), mode); } catch { renderPreview(null, mode); }
    };
    const render = (r) => {
      const list = $('#report-list');
      list.innerHTML = r.items.length ? r.items.map(card).join('') : `<div class="bg-surface-container-lowest rounded-xl p-space-lg text-center space-y-2"><span class="material-symbols-outlined text-5xl text-outline">search_off</span>
        <p class="font-headline-sm text-headline-sm font-bold text-primary">Tidak ada laporan yang cocok</p><p class="font-body-md text-body-md text-on-surface-variant">Ubah kata kunci atau reset filter untuk melihat laporan lainnya.</p></div>`;
      $$('[data-open]', list).forEach((b) => (b.onclick = (e) => { e.stopPropagation(); openDetail(b.dataset.open, (ref) => load(ref)); }));
      $$('[data-evidence]', list).forEach((b) => (b.onclick = (e) => { e.stopPropagation(); showEvidence(st.items.find((x) => x.ref === b.dataset.evidence)); }));
      $$('[data-verify]', list).forEach((b) => (b.onclick = (e) => { e.stopPropagation(); verifyEvidence(st.items.find((x) => x.ref === b.dataset.verify), () => load(b.dataset.verify)); }));
      $$('[data-receipt]', list).forEach((b) => (b.onclick = (e) => { e.stopPropagation(); printReceipt(st.items.find((x) => x.ref === b.dataset.receipt)); }));
      $$('[data-card]', list).forEach((c) => (c.onclick = () => select(c.dataset.card)));
      bindAll('s_label', `${r.total} Laporan Terdata`);
    };
    let seq = 0;
    async function load(keep) {
      const my = ++seq;
      try {
        const r = await api('GET', endpoint + '?' + params());
        if (my !== seq) return;
        st.items = r.items; render(r); pager(r); chips();
        const target = keep || st.selected || qs.get('tiket');
        const pick = r.items.find((x) => x.ref === target) || r.items[0];
        if (pick) select(pick.ref); else renderPreview(null, mode);
        onStats && onStats();
      } catch (er) { $('#report-list').innerHTML = `<div class="p-4 rounded-xl bg-error-container text-on-error-container">${esc(er.error)}</div>`; }
    }
    ['f-q', 'f-dari', 'f-sampai'].forEach((id) => $('#' + id) && $('#' + id).addEventListener('input', debounce(() => { st.page = 1; load(); }, 350)));
    ['f-tingkat', 'f-kategori', 'f-status', 'f-urut'].forEach((id) => $('#' + id) && $('#' + id).addEventListener('change', () => { st.page = 1; load(); }));
    $$('[data-action=export]').forEach((b) => (b.onclick = () => { const p = params(false); if (lingkup) p.set('lingkup', lingkup); location.href = '/api/laporan-ekspor.csv?' + p; }));
    ctl = { load, st, params };
    return ctl;
  }

  /* ====================================================== kartu dasbor */
  function cardDash(r) {
    const k = KAT_ICON[r.kategori_masalah], pr = PRIO[r.prioritas];
    const summary = r.status === 'Selesai' && r.resolusi ? `<strong>Keterangan Resolusi:</strong> ${esc(r.resolusi)}` : `<strong>Ringkasan Deviasi:</strong> ${esc(r.uraian.length > 300 ? r.uraian.slice(0, 300) + '…' : r.uraian)}`;
    const side = (lbl, o, who, cls) => `<div class="space-y-1 ${cls}"><div class="flex items-center gap-2 flex-wrap"><span class="font-label-sm text-label-sm font-bold text-outline uppercase">${lbl}</span><span class="px-2 rounded ${LVL_CLS[o.tingkat] || 'bg-surface-container'} font-label-sm text-label-sm font-extrabold uppercase">${esc(o.tingkat || '-')}</span><span class="font-label-sm text-label-sm text-on-surface font-semibold">${esc(o.tingkat_nama || '')}</span></div>
      <div class="flex items-center gap-2.5"><div class="w-8 h-8 rounded-full ${lbl === 'Pelapor' ? 'bg-primary' : 'bg-secondary'} flex items-center justify-center text-white font-label-sm text-label-sm font-bold shrink-0">${esc(o.inisial)}</div>
      <div class="min-w-0"><p class="font-label-lg text-label-lg font-bold text-on-surface truncate">${who}</p><p class="font-body-sm text-body-sm text-on-surface-variant truncate">${o.nippos ? 'NIPPOS: ' + esc(o.nippos) + ' • ' : ''}${esc(o.unit || '')}</p></div></div></div>`;
    const done = r.status === 'Selesai';
    return `<div data-card="${esc(r.ref)}" class="bg-surface-container-lowest rounded-xl p-space-md shadow-sm transition-all hover:shadow-md space-y-space-md cursor-pointer">
      <div class="flex flex-wrap items-center justify-between gap-2"><div class="flex items-center gap-2 flex-wrap"><span class="px-3 py-1 rounded bg-primary-container text-white font-label-md text-label-md font-bold tracking-wider">#${esc(r.ref)}</span>
        <span class="px-2.5 py-1 rounded-full bg-secondary-fixed text-on-secondary-fixed font-label-sm text-label-sm font-bold flex items-center gap-1"><span class="material-symbols-outlined text-sm">${k}</span>${esc(r.kategori_label)}</span>
        ${pr ? `<span class="px-2.5 py-1 rounded-full ${pr[1]} font-label-sm text-label-sm font-bold">${pr[0]}</span>` : ''}</div>${statusBadge(r)}</div>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-space-sm p-space-sm bg-surface-container-low rounded-lg">${side('Pelapor', r.pelapor, pelaporLine(r), '')}${side('Pihak Terlapor', r.terlapor, esc(r.terlapor.nama || '-'), 'md:border-l md:pl-space-sm md:border-outline-variant/30')}</div>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-space-sm font-body-sm text-body-sm"><div class="flex items-center gap-2 text-on-surface-variant"><span class="material-symbols-outlined text-base text-primary">schedule_send</span><span><strong>Waktu Pelaporan:</strong> ${esc(fmtDT(r.dikirim_pada))}</span></div>
        <div class="flex items-center gap-2 text-on-surface-variant"><span class="material-symbols-outlined text-base text-secondary">event_busy</span><span><strong>Waktu Kejadian:</strong> ${esc(fmtDT(r.waktu_kejadian))}${r.lokasi ? ' • ' + esc(r.lokasi) : ''}</span></div></div>
      <div class="space-y-2"><p class="font-body-md text-body-md text-on-surface leading-normal">${summary}</p>
        <div class="flex flex-wrap items-center gap-2 pt-1"><span class="font-label-sm text-label-sm text-outline font-bold flex items-center gap-1"><span class="material-symbols-outlined text-sm">attachment</span>${r.jumlah_lampiran ? r.jumlah_lampiran + ' Berkas Bukti' + (r.bukti_boleh_dilihat ? ' Terlampir:' : ' (akses terbatas)') : 'Tanpa berkas bukti'}</span>${r.lampiran.slice(0, 3).map(fileChip).join('')}</div></div>
      <div class="pt-2 flex flex-wrap items-center justify-between gap-space-sm"><div class="flex items-center gap-2 flex-wrap">
        ${done ? `<button data-open="${esc(r.ref)}" type="button" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container-high hover:bg-surface-container-highest text-primary font-label-sm text-label-sm font-bold"><span class="material-symbols-outlined text-base">inventory</span>Buka Berkas Arsip</button>`
        : `<button data-evidence="${esc(r.ref)}" type="button" ${r.lampiran.length ? '' : 'disabled'} class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container-high hover:bg-surface-container-highest text-primary font-label-sm text-label-sm font-bold disabled:opacity-50 disabled:cursor-not-allowed"><span class="material-symbols-outlined text-base">visibility</span>Lihat Bukti Digital</button>
        ${isSPI() && r.jumlah_lampiran ? `<button data-verify="${esc(r.ref)}" type="button" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary-fixed hover:bg-primary-fixed-dim text-primary font-label-sm text-label-sm font-bold"><span class="material-symbols-outlined text-base">checklist</span>Verifikasi Bukti Lapangan</button>` : ''}`}</div>
        <button data-open="${esc(r.ref)}" type="button" class="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary hover:bg-primary-container text-white font-label-md text-label-md font-bold shadow-xs"><span>${done ? 'Rincian Berkas' : isSPI() ? 'Detail Lengkap & Disposisi' : 'Detail Lengkap'}</span><span class="material-symbols-outlined text-base">arrow_forward</span></button></div></div>`;
  }

  /* ====================================================== kartu pelapor */
  function cardMine(r) {
    const accent = { Draf: 'bg-amber-500', Terdaftar: 'bg-outline', 'Investigasi SPI Lapangan': 'bg-secondary-container', 'Klarifikasi Satker': 'bg-primary', Selesai: 'bg-emerald-500' }[r.status];
    const pr = PRIO[r.prioritas];
    const meta = [['person', 'Terlapor:', r.terlapor.nama || '-'], ['schedule', 'Waktu Kejadian:', fmtDT(r.waktu_kejadian)]];
    r.awb && meta.unshift(['qr_code_2', 'Connote/AWB:', r.awb]); r.plat_armada && meta.unshift(['local_shipping', 'Feeder Truk:', r.plat_armada]);
    r.lokasi && meta.push(['pin_drop', 'Lokasi:', r.lokasi]); r.no_berita_acara && meta.push(['verified', 'No. Berita Acara:', r.no_berita_acara]);
    const draf = r.status === 'Draf';
    return `<div data-card="${esc(r.ref)}" class="relative overflow-hidden bg-surface-container-lowest rounded-xl p-space-lg shadow-sm hover:shadow-md transition-all cursor-pointer"><div class="absolute top-0 left-0 w-1.5 h-full ${accent}"></div>
      <div class="flex flex-wrap items-center justify-between gap-2"><div class="flex flex-wrap items-center gap-2"><span class="font-label-md text-label-md font-bold text-primary tracking-wide">#${esc(r.ref)}</span>
        <span class="px-2.5 py-0.5 rounded-full bg-primary-fixed text-primary font-label-sm text-label-sm font-bold">WASUM (Pengawasan Umum & SOP)</span>
        ${pr ? `<span class="px-2.5 py-0.5 rounded-full ${pr[1]} font-label-sm text-label-sm font-bold">${pr[0]}</span>` : ''}</div>${statusBadge(r)}</div>
      <div class="mt-space-md flex flex-col gap-1"><h2 class="font-headline-sm text-headline-sm text-primary font-bold">${esc(r.judul)}</h2><p class="font-body-md text-body-md text-on-surface-variant">${esc(r.uraian.length > 260 ? r.uraian.slice(0, 260) + '…' : r.uraian)}</p></div>
      <div class="mt-space-md bg-surface-container-low p-space-md rounded-lg grid sm:grid-cols-2 gap-2">${meta.map(([ic, k, v]) => `<div class="flex items-center gap-2 font-body-sm text-body-sm min-w-0"><span class="material-symbols-outlined text-base text-primary">${ic}</span><span class="font-bold text-on-surface-variant">${k}</span><span class="truncate">${esc(v)}</span></div>`).join('')}</div>
      ${r.lampiran.length ? `<div class="mt-space-md flex flex-wrap items-center gap-2"><span class="font-label-sm text-label-sm font-bold text-outline">Bukti Terlampir:</span>${r.lampiran.slice(0, 4).map(fileChip).join('')}</div>` : ''}
      <div class="mt-space-lg pt-space-sm border-t border-outline-variant/30 flex flex-wrap items-center justify-between gap-2"><div class="flex items-center gap-1.5 font-label-sm text-label-sm ${r.status === 'Klarifikasi Satker' && r.tenggat ? 'text-secondary font-bold' : 'text-on-surface-variant'}"><span class="material-symbols-outlined text-base">${draf ? 'edit_note' : r.status === 'Klarifikasi Satker' ? 'history_toggle_off' : r.investigator ? 'verified_user' : 'schedule'}</span>
        ${draf ? 'Draf — belum dikirim ke SPI' : r.status === 'Klarifikasi Satker' && r.tenggat ? 'Tenggat klarifikasi: ' + esc(fmtDT(r.tenggat, false)) : r.investigator ? 'Investigator: ' + esc(r.investigator) : 'Dilaporkan ' + esc(fmtDT(r.dikirim_pada))}</div>
        <div class="flex items-center gap-2">${draf ? '' : `<button data-receipt="${esc(r.ref)}" type="button" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container-high text-primary font-label-sm text-label-sm font-bold hover:bg-surface-container-highest"><span class="material-symbols-outlined text-base">download</span>Tanda Terima</button>`}
        <button data-open="${esc(r.ref)}" type="button" class="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary text-white font-label-md text-label-md font-bold hover:bg-primary-container">${draf ? 'Lanjutkan / Kelola Draf' : 'Lihat Detail & Disposisi'}<span class="material-symbols-outlined text-base">arrow_forward</span></button></div></div></div>`;
  }

  /* ====================================================== halaman: dasbor */
  P.pages.dashboard = async () => {
    const loadStats = async () => {
      const s = await api('GET', '/api/statistik');
      bindAll('s_total', s.total); bindAll('badge', s.berjalan); bindAll('s_pekan', `+${s.pekan_ini} mgg ini`);
      bindAll('s_tingkat', `KCP: ${s.per_tingkat.KCP} • KC: ${s.per_tingkat.KC} • KCU: ${s.per_tingkat.KCU}${s.per_tingkat.LAINNYA ? ` • Lainnya: ${s.per_tingkat.LAINNYA}` : ''}`); bindAll('s_verif', `${s.persen_terverifikasi}% Terverifikasi`);
      bindAll('s_invest', s.investigasi); bindAll('s_prio', `${s.investigasi_prioritas_tinggi} Prioritas Tinggi`);
      bindAll('s_durasi', `Durasi rata-rata: ${s.durasi_rata ?? '-'} Hari`); bindAll('s_sla', `SLA: ${s.sla}%`);
      bindAll('s_klar', s.klarifikasi); bindAll('s_unit', `Disposisi aktif: ${s.unit_aktif} Kantor`);
      bindAll('s_selesai', s.selesai); bindAll('s_persen', `${s.persen_selesai}% Closed`); bindAll('s_tenggat', s.lewat_tenggat ? `${s.lewat_tenggat} lewat tenggat` : 'Tidak ada lewat tenggat');
    };
    makeList({ endpoint: '/api/laporan', card: cardDash, mode: 'dasbor', onStats: loadStats });
    $('[data-action=toggle-filter]').onclick = () => { const f = $('#f-q'); f.scrollIntoView({ behavior: 'smooth', block: 'center' }); f.focus(); };
    await ctl.load();
  };

  /* ====================================================== halaman: laporan saya */
  P.pages.laporan_saya = async () => {
    const u = P.me.user;
    const loadStats = async () => {
      const s = await api('GET', '/api/statistik');
      bindAll('s_total', s.total); bindAll('badge', s.berjalan); bindAll('s_invest', s.investigasi); bindAll('s_klar', s.klarifikasi); bindAll('s_selesai', s.selesai);
      bindAll('s_note_total', `Akumulasi akun NIPPOS: ${u.identifier}${s.draf ? ` • ${s.draf} draf` : ''}`);
      bindAll('s_note_invest', `${s.investigasi ? 'Sedang diperiksa SPI' : 'Tidak ada kasus aktif'}`); bindAll('s_note_sla', 'SLA maks. 5 hari kerja');
      bindAll('s_note_klar', s.terdekat_tenggat ? `Tenggat terdekat: ${fmtDT(s.terdekat_tenggat.tenggat, false)}` : 'Tidak ada tenggat klarifikasi'); bindAll('s_note_selesai', `${s.selesai} berkas final`);
    };
    makeList({ endpoint: '/api/laporan/saya', card: cardMine, mode: 'pelapor', onStats: loadStats, lingkup: 'saya' });
    $('[data-action=unit-filter]').onclick = () => {
      const all = ['KCP', 'KC', 'KCU', 'SPP', 'REGIONAL', 'PUSAT', 'MITRA'];
      const m = modal({ tone: 'info', icon: 'account_tree', title: 'Filter Unit Satker', subtitle: 'Tampilkan laporan yang melibatkan tingkat kantor berikut (pelapor atau terlapor).',
        body: `<div class="grid grid-cols-2 gap-2">${all.map((t) => `<label class="flex items-center gap-2 p-2 rounded-lg bg-surface-container-low"><input type="checkbox" value="${t}" ${ctl.st.tingkat.includes(t) ? 'checked' : ''}><span class="font-label-md text-label-md font-bold">${t}</span></label>`).join('')}</div>`,
        actions: [{ label: 'Batal' }, { label: 'Terapkan', primary: true, onClick: ({ el }) => { ctl.st.tingkat = $$('input:checked', el).map((i) => i.value); ctl.st.page = 1; ctl.load(); } }] });
    };
    await ctl.load();
  };

  /* ====================================================== halaman: buat laporan */
  P.pages.laporan_baru = async () => {
    const u = P.me.user, form = $('#whistleblower-form');
    const S = { drafId: null, files: [], dirty: false };
    const F = { tipologi: '#f-tipologi', awb: '#f-awb', plat_armada: '#f-plat', rute: '#f-rute', deviasi: '#f-deviasi', pelapor_tingkat: '#f-pel-tingkat', pelapor_unit: '#f-pel-unit', terlapor_nama: '#f-terl-nama',
      terlapor_nippos: '#f-terl-nippos', terlapor_tingkat: '#f-terl-tingkat', terlapor_unit: '#f-terl-unit', waktu_kejadian: '#f-waktu', lokasi: '#f-lokasi', uraian: '#incident-text', pernyataan: '#f-pernyataan' };

    // identitas pelapor
    const jab = $('[data-bind=jabatan]'); if (jab) jab.textContent = u.jabatan ? `(${u.jabatan})` : '';
    const nippos = $('#pelapor-nippos'), nama = $('#pelapor-nama');
    const nipHtml = nippos.innerHTML, namaHtml = nama.innerHTML;
    $('#anon-toggle').checked = P.me.pref.samarkan_nama;
    const anon = () => { if ($('#anon-toggle').checked) { nippos.innerHTML = '<span class="font-mono text-secondary-container">***-TERLINDUNGI-***</span>'; nama.innerHTML = '<span class="text-secondary font-bold">Pelapor Anonim Terverifikasi</span> <span class="font-normal text-on-surface-variant">(Identitas Dikelola Sistem Enkripsi SPI)</span>'; } else { nippos.innerHTML = nipHtml; nama.innerHTML = namaHtml; bindAll('nama', u.nama); bindAll('identifier', u.identifier); } };
    $('#anon-toggle').addEventListener('change', anon); anon();
    bindAll('nama', u.nama); bindAll('identifier', u.identifier);
    if ([...$('#f-pel-tingkat').options].some((o) => o.value === u.tingkat_kantor)) $('#f-pel-tingkat').value = u.tingkat_kantor;
    $('#f-pel-unit').value = u.unit_kerja || '';
    $('#f-waktu').max = P.nowLocalInput();

    // penghitung karakter
    const ta = $('#incident-text'); const cnt = () => ($('#char-counter').textContent = `${ta.value.length} / 2000 karakter`); ta.addEventListener('input', cnt);
    form.addEventListener('input', () => (S.dirty = true)); form.addEventListener('change', () => (S.dirty = true));
    window.addEventListener('beforeunload', (e) => { if (S.dirty) { e.preventDefault(); e.returnValue = ''; } });

    // berkas: klik / keyboard / drag-and-drop, validasi di sisi klien, progres per berkas, batal, pratinjau, hapus
    const MAX_N = 10, input = $('#file-uploader'), dz = $('#dropzone');
    const paintFiles = () => {
      const total = S.files.filter((f) => !f.busy && !f.error).reduce((a, f) => a + (f.ukuran || 0), 0);
      $('#file-count').textContent = `Daftar Dokumen Pendukung Terlampir (${S.files.filter((f) => !f.error).length} Dokumen${total ? ' • ' + size(total) : ''})`;
      $('#file-list').innerHTML = S.files.map((f) => {
        const [ic, cl] = P.fileIcon(f.ekstensi);
        const status = f.error ? `<span class="font-label-sm text-label-sm text-error font-bold">Gagal</span>`
          : f.busy ? `<span class="font-label-sm text-label-sm text-secondary font-bold">${f.pct || 0}%</span>`
          : '<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-label-sm text-label-sm font-bold"><span class="material-symbols-outlined text-sm">check_circle</span>Terunggah</span>';
        const acts = f.busy ? `<button type="button" data-cancel="${f.id}" title="Batalkan unggahan" class="p-1 text-outline hover:text-error"><span class="material-symbols-outlined">close</span></button>`
          : f.error ? `<button type="button" data-dismiss="${f.id}" title="Tutup" class="p-1 text-outline hover:text-error"><span class="material-symbols-outlined">close</span></button>`
          : `<a href="${f.url}" target="_blank" rel="noopener" title="Pratinjau Berkas" class="p-1 text-outline hover:text-primary"><span class="material-symbols-outlined">visibility</span></a><button type="button" data-del="${f.id}" title="Hapus Berkas" class="p-1 text-outline hover:text-error"><span class="material-symbols-outlined">delete</span></button>`;
        return `<div class="p-3 rounded-lg ${f.error ? 'bg-error-container/40' : 'bg-surface-container-low'} space-y-2"><div class="flex items-center justify-between gap-3"><div class="flex items-center gap-3 min-w-0"><div class="w-9 h-9 rounded-lg bg-surface-container flex items-center justify-center"><span class="material-symbols-outlined ${cl}">${ic}</span></div>
          <div class="min-w-0"><p class="font-label-md text-label-md font-bold truncate">${esc(f.nama)}</p><p class="font-label-sm text-label-sm ${f.error ? 'text-error' : 'text-on-surface-variant'}">${f.error ? esc(f.error) : size(f.ukuran) + ' • ' + esc(f.ekstensi.toUpperCase())}</p></div></div>
          <div class="flex items-center gap-1.5 shrink-0">${status}${acts}</div></div>
          ${f.busy ? `<div class="h-1.5 rounded-full bg-surface-container-high overflow-hidden" role="progressbar" aria-valuenow="${f.pct || 0}" aria-valuemin="0" aria-valuemax="100"><div class="h-full bg-secondary-container transition-all" style="width:${f.pct || 0}%"></div></div>` : ''}</div>`;
      }).join('');
      $$('[data-del]').forEach((b) => (b.onclick = async () => { try { await api('DELETE', '/api/lampiran/' + b.dataset.del); S.files = S.files.filter((f) => f.id != b.dataset.del); S.dirty = true; paintFiles(); } catch (er) { toast(er.error, 'err'); } }));
      $$('[data-cancel]').forEach((b) => (b.onclick = () => { const f = S.files.find((x) => x.id === b.dataset.cancel); f && f.abort && f.abort(); }));
      $$('[data-dismiss]').forEach((b) => (b.onclick = () => { S.files = S.files.filter((f) => f.id !== b.dataset.dismiss); paintFiles(); }));
    };
    const upload = async (files) => {
      for (const file of files) {
        if (S.files.filter((f) => !f.error).length >= MAX_N) { toast(`Maksimal ${MAX_N} berkas per laporan.`, 'err'); break; }
        const tmp = { id: 't' + Math.random().toString(36).slice(2), nama: file.name, ukuran: file.size, ekstensi: (file.name.split('.').pop() || '').toLowerCase(), busy: true, pct: 0 };
        const bad = P.checkFile(file) || (S.files.some((f) => !f.error && f.nama === file.name && f.ukuran === file.size) ? `${file.name}: berkas yang sama sudah dilampirkan.` : null);
        if (bad) { tmp.busy = false; tmp.error = bad.replace(file.name + ': ', ''); S.files.push(tmp); paintFiles(); continue; }
        const up = P.upload('/api/lampiran', file, (pct) => { tmp.pct = pct; paintFiles(); });
        tmp.abort = up.abort; S.files.push(tmp); paintFiles();
        try { const r = await up.promise; Object.assign(tmp, r, { busy: false, abort: null }); S.dirty = true; }
        catch (er) { if (er.aborted) S.files = S.files.filter((x) => x !== tmp); else Object.assign(tmp, { busy: false, error: er.error, abort: null }); }
        paintFiles();
      }
    };
    const pick = (e) => { if (e.target === input) return; input.click(); };         // jangan memicu diri sendiri (klik pada input ikut menggelembung)
    dz.setAttribute('role', 'button'); dz.setAttribute('tabindex', '0'); dz.setAttribute('aria-label', 'Pilih berkas bukti dari komputer atau tarik dan lepaskan di sini');
    dz.addEventListener('click', pick);
    dz.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); } });
    input.addEventListener('change', () => { upload([...input.files]); input.value = ''; });
    ['dragover', 'dragenter'].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add('ring-2', 'ring-secondary-container'); }));
    ['dragleave', 'drop'].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove('ring-2', 'ring-secondary-container'); }));
    dz.addEventListener('drop', (e) => upload([...e.dataTransfer.files]));
    document.addEventListener('dragover', (e) => { if (!dz.contains(e.target)) e.preventDefault(); });      // lepas di luar area tidak membuka berkas di tab
    document.addEventListener('drop', (e) => { if (!dz.contains(e.target)) e.preventDefault(); });
    paintFiles();

    // payload
    const payload = () => {
      const g = (k) => { const el = $(F[k]); return el.type === 'checkbox' ? el.checked : el.value; };
      return { draf_id: S.drafId, klasifikasi: 'WASUM', anonim: $('#anon-toggle').checked, lampiran_ids: S.files.filter((f) => !f.busy && !f.error).map((f) => f.id), ...Object.fromEntries(Object.keys(F).map((k) => [k, g(k)])) };
    };
    const fill = (r) => {
      S.drafId = r.id; $('#anon-toggle').checked = r.anonim; anon();
      const map = { tipologi: r.tipologi, awb: r.awb, plat_armada: r.plat_armada, rute: r.rute, deviasi: r.deviasi, pelapor_tingkat: r.pelapor.tingkat, pelapor_unit: r.pelapor.unit, terlapor_nama: r.terlapor.nama, terlapor_nippos: r.terlapor.nippos,
        terlapor_tingkat: r.terlapor.tingkat, terlapor_unit: r.terlapor.unit, waktu_kejadian: P.toLocalInput(r.waktu_kejadian), lokasi: r.lokasi, uraian: r.uraian };
      Object.entries(map).forEach(([k, v]) => { const el = $(F[k]); if (v != null && v !== '') el.value = v; });
      S.files = r.lampiran.map((a) => ({ ...a, busy: false })); paintFiles(); cnt();
    };
    if (qs.get('draf')) { try { fill(await api('GET', '/api/laporan/draf/' + qs.get('draf'))); toast('Draf dimuat. Lanjutkan pengisian formulir.'); } catch (er) { toast(er.error, 'err'); } S.dirty = false; }

    const masihUnggah = () => { if (S.files.some((f) => f.busy)) { toast('Tunggu hingga semua berkas selesai diunggah.', 'err'); return true; } return false; };
    const saveDraft = async (btn) => {
      if (masihUnggah()) return false;
      busy(btn, true, 'Menyimpan...');
      try { const r = await api('POST', '/api/laporan/draf', payload()); S.drafId = r.id; S.dirty = false; toast(`Draf ${r.kode_draf} tersimpan di server.`); return true; }
      catch (er) { toast(er.error, 'err'); return false; }
      finally { busy(btn, false); }
    };
    $('#btn-draf').onclick = (e) => saveDraft(e.currentTarget);

    form.addEventListener('submit', async (e) => {
      e.preventDefault(); clearFieldErrors(form);
      if (masihUnggah()) return;
      const btn = $('#btn-kirim'); busy(btn, true, 'Mengirim ke SPI...');
      try {
        const r = await api('POST', '/api/laporan', payload()); S.dirty = false; busy(btn, false);
        const m = modal({ tone: 'ok', icon: 'task_alt', title: 'Laporan Insiden Berhasil Terkirim', subtitle: 'Laporan Anda telah diregistrasi ke Sistem Audit & Investigasi Pengawasan Internal (SPI) PT Pos Indonesia (Persero).', dismissible: false,
          body: `<div class="rounded-xl bg-surface-container-low p-space-md space-y-3"><div class="flex items-center justify-between gap-3"><div><p class="font-label-sm text-label-sm text-outline font-bold uppercase">Nomor Tiket Registrasi</p><p class="font-headline-sm text-headline-sm font-extrabold text-primary" id="tiket-no">#${esc(r.tiket)}</p></div>
            <button type="button" id="copy-tiket" class="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-surface-container-high text-primary font-label-sm text-label-sm font-bold"><span class="material-symbols-outlined text-sm">content_copy</span><span>Salin</span></button></div>
            ${P.summary([['Klasifikasi Insiden', 'WASUM (Pengawasan Umum & SOP)'], ['Kategori', r.kategori_label], ['Waktu Pelaporan', fmtDT(r.waktu)], ['Identitas Pelapor', r.pelapor], ['Prioritas', r.prioritas], ['Status Disposisi', r.status_label + ' (Maks. 1x24 Jam)']])}</div>`,
          actions: [{ label: 'Kembali ke Beranda Logistik', onClick: () => { location.href = P.me.home; return false; } }, { label: 'Unduh Tanda Terima (PDF)', icon: 'picture_as_pdf', onClick: async () => { try { printReceipt(await api('GET', '/api/laporan/' + r.tiket)); } catch (er) { toast(er.error, 'err'); } return false; } },
            { label: 'Lihat Status Laporan', primary: true, icon: 'timeline', onClick: () => { location.href = `${P.me.home}?tiket=${encodeURIComponent(r.tiket)}`; return false; } }] });
        $('#copy-tiket', m.el).onclick = async (ev) => { const b = ev.currentTarget; try { await navigator.clipboard.writeText(r.tiket); b.lastElementChild.textContent = 'Disalin!'; } catch { b.lastElementChild.textContent = r.tiket; } };
      } catch (er) {
        busy(btn, false);
        const errs = er.errors || []; errs.forEach((x) => F[x.field] && fieldError($(F[x.field]), x.message));
        const kel = er.body && er.body.kelengkapan;
        const first = errs.find((x) => F[x.field]); const m = modal({ tone: 'err', icon: 'error_outline', title: 'Pengiriman Laporan Gagal', wide: true,
          subtitle: `Formulir belum dapat diproses — ${errs.length || 1} bagian wajib belum lengkap${kel ? ` (kelengkapan data ${kel.persen}%)` : ''}.`, body: P.errorList(errs.length ? errs : [{ title: 'Kesalahan', message: er.error }]),
          actions: [{ label: 'Batal' }, { label: 'Simpan sebagai Draf Terlebih Dahulu', icon: 'save', onClick: async () => { await saveDraft($('#btn-draf')); } },
            { label: 'Lengkapi Formulir Sekarang', primary: true, icon: 'edit_square', onClick: () => { if (first) { const el = $(F[first.field]); el.scrollIntoView({ behavior: 'smooth', block: 'center' }); setTimeout(() => el.focus(), 350); } } }] });
      }
    });
  };
})();
