"""Membuat app/pages_html/beranda.html (halaman awal: pilih pintu masuk Pelapor atau Staf/SPI).
Memakai <head> (Tailwind config + font) dari pelapor_masuk.html agar gaya konsisten."""
import re
from pathlib import Path

HTML = Path(__file__).resolve().parent.parent / "app" / "pages_html"
head = re.search(r"<head>.*?</head>", (HTML / "pelapor_masuk.html").read_text(encoding="utf-8"), re.S).group(0)
head = re.sub(r"<title>.*?</title>", "<title>Portal Pengawasan &amp; Pelaporan — POS IND</title>", head, flags=re.S)

BTN_P = "inline-flex items-center justify-center gap-2 h-12 px-5 rounded-lg bg-secondary-container text-white font-label-lg text-label-lg font-bold hover:brightness-110 transition-all"
BTN_S = "inline-flex items-center justify-center gap-2 h-12 px-5 rounded-lg bg-surface-container-high text-primary font-label-lg text-label-lg font-bold hover:bg-surface-container-highest transition-all"
BTN_W = "inline-flex items-center justify-center gap-2 h-12 px-5 rounded-lg bg-white text-primary font-label-lg text-label-lg font-bold hover:bg-primary-fixed transition-all"
BTN_O = "inline-flex items-center justify-center gap-2 h-12 px-5 rounded-lg border border-white/40 text-white font-label-lg text-label-lg font-bold hover:bg-white/10 transition-all"
STEP = lambda n, t, d: (f'<li class="flex gap-3"><span class="w-8 h-8 rounded-full bg-primary-container text-white flex items-center justify-center font-label-md text-label-md font-bold shrink-0">{n}</span>'
                        f'<div><p class="font-label-lg text-label-lg font-bold text-primary">{t}</p><p class="font-body-sm text-body-sm text-on-surface-variant">{d}</p></div></li>')

body = f"""<body class="bg-surface text-on-surface font-body-md min-h-screen flex flex-col" data-page="beranda">
<header class="bg-surface-container-lowest border-b border-outline-variant/30"><div class="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
  <a href="/" class="flex items-center gap-3"><img src="/static/img/logo.png" alt="Logo POS IND" class="h-10 w-auto"><span class="hidden sm:block font-label-lg text-label-lg font-bold text-primary">Portal Pengawasan &amp; Pelaporan</span></a>
  <nav class="flex items-center gap-4 font-label-md text-label-md"><a href="/lacak" class="text-primary font-bold hover:underline">Lacak Aduan</a><a href="/info/pusat-bantuan" class="text-on-surface-variant hover:underline">Pusat Bantuan</a></nav></div></header>
<main class="flex-1 max-w-6xl w-full mx-auto px-4 py-10 space-y-10">
  <section class="text-center space-y-3 max-w-3xl mx-auto"><span class="inline-block px-3 py-1 rounded-full bg-secondary-fixed text-on-secondary-fixed font-label-sm text-label-sm font-bold">Satuan Pengawasan Intern • POS IND</span>
    <h1 class="font-headline-lg text-headline-lg font-extrabold text-primary tracking-tight">Pilih pintu masuk Anda</h1>
    <p class="font-body-lg text-body-lg text-on-surface-variant">Pelaporan dan penanganan laporan dipisah agar identitas pelapor tetap terlindungi. Pilih sesuai peran Anda.</p></section>
  <section class="grid md:grid-cols-2 gap-6">
    <article class="rounded-2xl bg-surface-container-lowest shadow-md border border-outline-variant/30 p-space-lg flex flex-col gap-4">
      <div class="flex items-center gap-3"><span class="w-12 h-12 rounded-xl bg-secondary-container text-white flex items-center justify-center"><span class="material-symbols-outlined text-3xl">campaign</span></span>
        <div><h2 class="font-headline-md text-headline-md font-extrabold text-primary">Saya Pelapor</h2><p class="font-label-md text-label-md text-secondary font-bold">Membuat &amp; memantau laporan</p></div></div>
      <p class="font-body-md text-body-md text-on-surface-variant">Laporkan penyimpangan operasional (WASUM — Pengawasan Umum & SOP), unggah bukti digital, lalu pantau proses dan progres penanganannya sampai selesai. Anda dapat melapor secara anonim.</p>
      <ul class="space-y-1 font-body-sm text-body-sm text-on-surface-variant"><li>• Buat laporan &amp; simpan draf</li><li>• Unggah bukti (foto, video, PDF, CSV/XLSX)</li><li>• Lihat progres, jawab permintaan informasi SPI</li></ul>
      <div class="mt-auto flex flex-col sm:flex-row gap-3 pt-2"><a href="/pelapor/masuk" class="{BTN_P} flex-1"><span class="material-symbols-outlined">login</span>Masuk sebagai Pelapor</a>
        <a href="/pelapor/daftar" class="{BTN_S} flex-1">Daftar Akun Pelapor</a></div></article>
    <article class="rounded-2xl bg-primary-container text-white shadow-md p-space-lg flex flex-col gap-4">
      <div class="flex items-center gap-3"><span class="w-12 h-12 rounded-xl bg-white/15 flex items-center justify-center"><span class="material-symbols-outlined text-3xl">fact_check</span></span>
        <div><h2 class="font-headline-md text-headline-md font-extrabold">Staf / Petugas SPI</h2><p class="font-label-md text-label-md text-secondary-fixed font-bold">Melihat semua laporan yang masuk</p></div></div>
      <p class="font-body-md text-body-md text-on-primary-container">Dasbor semua laporan dari pelapor: verifikasi bukti, minta informasi tambahan, disposisi berjenjang, hingga penutupan laporan dengan Berita Acara. Khusus petugas SPI yang berwenang.</p>
      <ul class="space-y-1 font-body-sm text-body-sm text-on-primary-container"><li>• Dasbor, filter, dan ekspor laporan</li><li>• Verifikasi bukti &amp; disposisi KCP → Pusat</li><li>• Karyawan/mitra non-SPI hanya dapat mengelola akunnya</li></ul>
      <div class="mt-auto flex flex-col sm:flex-row gap-3 pt-2"><a href="/masuk" class="{BTN_W} flex-1"><span class="material-symbols-outlined">login</span>Masuk Staf / SPI</a>
        <a href="/daftar" class="{BTN_O} flex-1">Daftar Karyawan / Mitra</a></div></article></section>
  <section class="rounded-2xl bg-surface-container-lowest border border-outline-variant/30 p-space-lg grid md:grid-cols-2 gap-8">
    <div class="space-y-3"><h2 class="font-headline-sm text-headline-sm font-extrabold text-primary">Bagaimana laporan ditangani?</h2>
      <ol class="space-y-3">{STEP(1, 'Laporan terdaftar', 'Nomor tiket dibuat; SPI menerima laporan dan bukti Anda.')}{STEP(2, 'Verifikasi &amp; investigasi SPI', 'Bukti diperiksa; SPI dapat meminta informasi tambahan kepada pelapor.')}
        {STEP(3, 'Klarifikasi Satker &amp; BAP', 'Unit terkait memberi klarifikasi; Berita Acara Pemeriksaan disusun.')}{STEP(4, 'Rekomendasi &amp; penutupan', 'Hasil ditetapkan, laporan ditutup, dan pelapor diberi tahu.')}</ol></div>
    <div class="space-y-3"><h2 class="font-headline-sm text-headline-sm font-extrabold text-primary">Sudah punya nomor tiket?</h2>
      <p class="font-body-md text-body-md text-on-surface-variant">Lacak status laporan tanpa masuk. Identitas pelapor tidak ditampilkan.</p>
      <form action="/lacak" method="get" class="flex gap-2"><input name="no" required placeholder="LAP-WASUM-2026-0001" aria-label="Nomor tiket" class="flex-1 h-12 px-4 rounded-lg border border-outline-variant bg-white uppercase outline-none focus:ring-2 focus:ring-primary">
        <button class="px-5 rounded-lg bg-primary text-white font-label-lg text-label-lg font-bold hover:bg-primary-container">Lacak</button></form>
      <a href="/info/perlindungan-pelapor" class="inline-flex items-center gap-1 text-secondary font-label-md text-label-md font-bold hover:underline"><span class="material-symbols-outlined text-base">shield</span>Perlindungan pelapor</a></div></section>
</main>
<footer class="py-5 text-center font-label-sm text-label-sm text-on-surface-variant">© PT Pos Indonesia (Persero). Seluruh hak cipta dilindungi. • <a href="/info/kebijakan-privasi" class="hover:underline">Kebijakan Privasi</a> • <a href="/info/syarat-ketentuan" class="hover:underline">Syarat &amp; Ketentuan</a></footer>
<script src="/static/js/core.js" defer></script></body>"""
(HTML / "beranda.html").write_text(f'<!DOCTYPE html><html lang="id">{head}{body}</html>', encoding="utf-8")
print("ok beranda.html")
