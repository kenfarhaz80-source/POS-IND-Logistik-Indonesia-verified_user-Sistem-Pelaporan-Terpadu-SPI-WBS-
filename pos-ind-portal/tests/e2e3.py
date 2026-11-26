"""E2E tahap ini: beranda & pemilih portal, UPLOAD lewat klik/drag, progres tiket, pesan dua arah, bukti susulan."""
import os, sys, tempfile, threading, json
os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright

app = create_app({"TESTING": True})
srv = make_server("127.0.0.1", 5057, app, threaded=True); threading.Thread(target=srv.serve_forever, daemon=True).start()
B = "http://127.0.0.1:5057"; errors = []
open("/tmp/bukti1.pdf", "wb").write(b"%PDF-1.4\n" + b"x" * 300000)          # 300 KB agar progres terukur
open("/tmp/foto.png", "wb").write(b"\x89PNG\r\n\x1a\n" + b"0" * 2000)
open("/tmp/susulan.pdf", "wb").write(b"%PDF-1.4 susulan")
open("/tmp/jahat.exe", "wb").write(b"MZ\x90\x00")
open("/tmp/palsu.pdf", "wb").write(b"ini bukan pdf")

def ok(cond, label):
    print(("OK   " if cond else "GAGAL"), label)
    if not cond: errors.append(label)

with sync_playwright() as pw:
    br = pw.chromium.launch(); ctx = br.new_context(viewport={"width": 1400, "height": 900}); pg = ctx.new_page()
    pg.on("pageerror", lambda e: "tailwind" not in str(e) and errors.append(f"JS error {pg.url}: {e}"))
    # ---------- 1. beranda & pemilih portal ----------
    pg.goto(B + "/")
    ok(pg.locator("a[href='/pelapor/masuk']").count() >= 1 and pg.locator("a[href='/masuk']").count() >= 1, "beranda: dua pintu masuk (Pelapor & Staf/SPI) tampil")
    pg.click("text=Masuk sebagai Pelapor"); pg.wait_for_url("**/pelapor/masuk")
    sw = pg.locator("[data-portal-switch] a")
    ok(sw.count() == 2 and sw.nth(0).get_attribute("aria-current") == "page", "pelapor/masuk: pemilih portal, tab Pelapor aktif")
    sw.nth(1).click(); pg.wait_for_url("**/masuk")
    ok(pg.locator("[data-portal-switch] a[aria-current=page]").inner_text().startswith("Staf") or "Staf" in pg.locator("[data-portal-switch] a[aria-current=page]").inner_text(), "masuk: tab Staf/SPI aktif")
    for u in ("/daftar", "/pelapor/daftar"):
        pg.goto(B + u)
        try: pg.wait_for_selector("[data-portal-switch]", timeout=4000)
        except Exception: pass
        ok(pg.locator("[data-portal-switch]").count() == 1, f"{u}: pemilih portal ada")

    # ---------- 2. pelapor: UPLOAD ----------
    pg.goto(B + "/pelapor/masuk"); pg.fill("#nippos-input", "987654321"); pg.fill("#password-input", "PosInd2025!"); pg.click("button[type=submit]")
    pg.wait_for_url("**/pelapor/laporan-saya", timeout=8000)
    pg.goto(B + "/pelapor/laporan-baru"); pg.wait_for_selector("#dropzone")
    with pg.expect_file_chooser(timeout=3000) as fc:
        pg.click("text=Pilih dari Komputer")                                   # KLIK sungguhan (bug yang dilaporkan)
    ok(True, "klik 'Pilih dari Komputer' membuka dialog berkas")
    fc.value.set_files(["/tmp/bukti1.pdf", "/tmp/foto.png"]); pg.wait_for_selector("text=Terunggah", timeout=8000)
    pg.wait_for_function("document.querySelectorAll('#file-list [data-del]').length === 2")
    ok("2 Dokumen" in pg.inner_text("#file-count"), "2 berkas terunggah & hitungan dokumen: " + pg.inner_text("#file-count"))
    with pg.expect_file_chooser(timeout=3000) as fc2:
        pg.focus("#dropzone"); pg.keyboard.press("Enter")
    ok(True, "dropzone dapat dibuka dengan keyboard (Enter)"); fc2.value.set_files([])
    # validasi klien: ekstensi salah, isi palsu, duplikat
    pg.set_input_files("#file-uploader", ["/tmp/jahat.exe", "/tmp/palsu.pdf", "/tmp/bukti1.pdf"]); pg.wait_for_timeout(1200)
    teks = pg.inner_text("#file-list")
    ok("tidak didukung" in teks and "tidak sesuai" in teks and "sudah dilampirkan" in teks, "berkas .exe / isi palsu / duplikat ditolak dengan pesan jelas")
    pg.locator("[data-dismiss]").first.click(); 
    while pg.locator("[data-dismiss]").count(): pg.locator("[data-dismiss]").first.click()
    # drag & drop
    pg.evaluate("""() => { const dt = new DataTransfer(); dt.items.add(new File([new Uint8Array([0x25,0x50,0x44,0x46,0x2d,0x31])], 'drop.pdf', {type:'application/pdf'}));
        document.querySelector('#dropzone').dispatchEvent(new DragEvent('drop', {dataTransfer: dt, bubbles: true, cancelable: true})); }""")
    pg.wait_for_function("document.querySelectorAll('#file-list [data-del]').length === 3", timeout=8000); ok(True, "drag-and-drop mengunggah berkas (3 berkas)")
    pg.locator("[data-del]").nth(2).click(); pg.wait_for_function("document.querySelectorAll('#file-list [data-del]').length === 2"); ok(True, "hapus berkas dari daftar")
    # isi form & kirim
    pg.select_option("#f-tipologi", index=1); pg.fill("#f-awb", "POS99281746210ID"); pg.fill("#f-plat", "D-8812-POS"); pg.select_option("#f-rute", index=1); pg.fill("#f-deviasi", "3 Koli")
    pg.select_option("#f-terl-tingkat", index=2); pg.fill("#f-terl-nama", "Sdr. Tes"); pg.fill("#f-terl-unit", "Divisi Bongkar"); pg.fill("#f-waktu", "2026-10-05T10:30")
    pg.fill("#f-lokasi", "Dock 4"); pg.fill("#incident-text", "Segel terbuka pada tiga koli saat unloading feeder, selisih berat terdeteksi petugas."); pg.check("#f-pernyataan")
    pg.click("#btn-kirim"); pg.wait_for_selector("text=Laporan Insiden Berhasil Terkirim"); tiket = pg.inner_text("#tiket-no").strip("#")
    pg.click("text=Lihat Status Laporan"); pg.wait_for_selector("[data-card]"); print("     tiket:", tiket)

    # ---------- 3. cuplikan tiket: proses & progres (pelapor) ----------
    pg.click(f"[data-card='{tiket}']"); pg.wait_for_selector("#preview >> text=Progres Penanganan")
    pv = pg.inner_text("#preview")
    ok("25%" in pv and "Tahap 1 dari 4" in pv and "Menunggu" in pv and "Sisa 5 hari kerja" in pv, "pelapor: pratinjau menampilkan 25%, tahap, menunggu, sisa SLA")
    ok(pg.locator("#preview [role=progressbar]").count() == 1 and "2 berkas" in pv, "pelapor: bar progres & jumlah bukti")

    # ---------- 4. SPI: dasbor, progres, permintaan info, catatan internal ----------
    spi = ctx.browser.new_context(viewport={"width": 1400, "height": 900}).new_page()
    spi.on("pageerror", lambda e: "tailwind" not in str(e) and errors.append(f"JS error SPI: {e}"))
    spi.goto(B + "/masuk"); spi.fill("#nippos", "100000001"); spi.fill("#password", "PosInd2025!"); spi.click("#posLoginForm button[type=submit]"); spi.wait_for_url("**/dashboard", timeout=8000)
    spi.fill("#f-q", tiket); spi.wait_for_selector(f"[data-card='{tiket}']"); spi.click(f"[data-card='{tiket}']"); spi.wait_for_selector(f"#preview >> text={tiket}")
    pv = spi.inner_text("#preview"); ok("Jalur Disposisi" in pv and "25%" in pv and "Penanggung jawab" in pv, "SPI: pratinjau memuat progres + jalur disposisi + penanggung jawab")
    spi.click("#preview >> text=Detail, Pesan & Disposisi"); spi.wait_for_selector("#pesan-isi")
    ok(spi.eval_on_selector("#d-status option[value=Selesai]", "o => o.disabled"), "SPI: opsi 'Selesai' terkunci sebelum investigasi")
    spi.select_option("#pesan-jenis", "catatan"); spi.fill("#pesan-isi", "Catatan rahasia: cek CCTV dock 4."); spi.click("#pesan-kirim"); spi.wait_for_selector("text=Catatan internal SPI")
    spi.select_option("#pesan-jenis", "permintaan"); spi.fill("#pesan-isi", "Mohon unggah foto segel yang rusak."); spi.click("#pesan-kirim"); spi.wait_for_selector("text=Permintaan informasi")
    ok(True, "SPI: catatan internal + permintaan informasi terkirim")
    spi.select_option("#d-status", "Investigasi SPI Lapangan"); spi.fill("#d-inv", "Tim SPI Regional III"); spi.fill("#d-cat", "Rahasia: oknum A terdeteksi."); spi.uncheck("#d-publik"); spi.click("text=Simpan Perubahan")
    spi.wait_for_selector("text=Disposisi berhasil dicatat")

    # ---------- 5. pelapor melihat progres, permintaan, balas, bukti susulan ----------
    pg.reload(); pg.wait_for_selector(f"[data-card='{tiket}']"); pg.click(f"[data-card='{tiket}']"); pg.wait_for_selector("#preview >> text=50%")
    pv = pg.inner_text("#preview")
    ok("50%" in pv and "Tahap 2 dari 4" in pv and "Tim SPI Regional III" in pv and "SPI meminta informasi tambahan" in pv, "pelapor: progres 50%, penanggung jawab, & peringatan permintaan SPI")
    ok("Rahasia" not in pv and "CCTV" not in pv, "pelapor: catatan internal TIDAK bocor di pratinjau")
    pg.click("#preview >> text=Detail, Pesan & Bukti Susulan"); pg.wait_for_selector("#pesan-isi")
    dlg = pg.inner_text("[role=dialog]"); ok("Rahasia" not in dlg and "CCTV" not in dlg and "Mohon unggah foto segel" in dlg, "pelapor: modal detail menampilkan permintaan SPI, tanpa catatan internal")
    with pg.expect_file_chooser() as fc3: pg.click("#btn-susulan")
    fc3.value.set_files(["/tmp/susulan.pdf"]); pg.wait_for_selector("text=bukti tambahan terkirim ke SPI"); pg.wait_for_selector("[role=dialog] >> text=susulan")
    ok(True, "pelapor: bukti susulan terunggah dan ditandai 'susulan'")
    pg.fill("#pesan-isi", "Foto sudah saya lampirkan sebagai bukti susulan."); pg.click("#pesan-kirim"); pg.wait_for_selector("text=Balasan pelapor")
    ok("Bukti Terlampir (3)" in pg.inner_text("[role=dialog]"), "pelapor: total bukti kini 3")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(500)
    pg.reload(); pg.wait_for_selector(f"[data-card='{tiket}']"); pg.click(f"[data-card='{tiket}']"); pg.wait_for_selector("#preview >> text=Progres Penanganan")
    ok("SPI meminta informasi tambahan" not in pg.inner_text("#preview"), "pelapor: peringatan hilang setelah membalas")
    # SPI melihat balasan + susulan
    spi.reload(); spi.fill("#f-q", tiket); spi.wait_for_selector(f"[data-card='{tiket}']"); spi.click(f"[data-card='{tiket}']"); spi.wait_for_selector(f"#preview >> text={tiket}"); spi.wait_for_selector("#preview >> text=3 berkas")
    ok("3 berkas" in spi.inner_text("#preview") and "SPI (pemeriksaan lapangan)" in spi.inner_text("#preview"), "SPI: pratinjau menunjukkan 3 berkas & menunggu SPI lagi")
    br.close()
print("\nRINGKASAN:", "SEMUA LULUS" if not errors else json.dumps(errors, indent=1))
sys.exit(1 if errors else 0)
