import os, sys, tempfile, threading, time, json
os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright

app = create_app({"TESTING": True})
srv = make_server("127.0.0.1", 5055, app, threaded=True)
threading.Thread(target=srv.serve_forever, daemon=True).start()
B = "http://127.0.0.1:5055"
errors = []

def run(pw):
    br = pw.chromium.launch()
    ctx = br.new_context(viewport={"width": 1400, "height": 900})
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errors.append(("pageerror", pg.url, str(e))))
    pg.on("console", lambda m: m.type == "error" and "Failed to load resource" not in m.text and "net::" not in m.text and errors.append(("console", pg.url, m.text)))
    return br, ctx, pg

with sync_playwright() as pw:
    br, ctx, pg = run(pw)
    # 1. login pelapor
    pg.goto(B + "/pelapor/masuk")
    pg.fill("#nippos-input", "987654321"); pg.fill("#password-input", "salah"); pg.click("button[type=submit]")
    pg.wait_for_selector("[data-form-error]"); print("login salah ->", pg.inner_text("[data-form-error]"))
    pg.fill("#password-input", "PosInd2025!"); pg.click("button[type=submit]")
    pg.wait_for_url("**/pelapor/laporan-saya", timeout=8000); print("login ok ->", pg.url)
    pg.wait_for_selector("[data-card]")
    print("kartu:", pg.locator("[data-card]").count(), "| total:", pg.inner_text("[data-bind=s_total]"))
    # 2. buat laporan: kirim kosong -> modal galat
    pg.goto(B + "/pelapor/laporan-baru"); pg.wait_for_selector("#f-waktu")
    pg.click("#btn-kirim"); pg.wait_for_selector("text=Pengiriman Laporan Gagal")
    print("validasi kosong -> item galat:", pg.locator("[role=dialog] li").count()); pg.click("[role=dialog] >> text=Batal")
    # isi lengkap + unggah PDF palsu & PDF valid
    open("/tmp/bukti.pdf","wb").write(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF")
    open("/tmp/palsu.pdf","wb").write(b"bukan pdf")
    pg.set_input_files("#file-uploader", "/tmp/palsu.pdf"); pg.wait_for_timeout(600)
    print("berkas palsu ditolak ->", pg.locator("#file-list > div").count() == 0)
    pg.set_input_files("#file-uploader", "/tmp/bukti.pdf"); pg.wait_for_selector("text=Terunggah")
    pg.select_option("#f-tipologi", index=1); pg.fill("#f-awb", "POS99281746210ID"); pg.fill("#f-plat", "D-8812-POS")
    pg.select_option("#f-rute", index=1); pg.fill("#f-deviasi", "3 Koli / -12 Kg")
    pg.select_option("#f-terl-tingkat", index=2); pg.fill("#f-terl-nama", "Sdr. Tes"); pg.fill("#f-terl-unit", "Divisi Bongkar")
    pg.fill("#f-waktu", "2026-10-04T10:30"); pg.fill("#f-lokasi", "Dock 4 SPP Bandung")
    pg.fill("#incident-text", "Ditemukan segel terbuka pada tiga koli saat unloading feeder, selisih berat terdeteksi.")
    pg.check("#f-pernyataan")
    pg.click("#btn-draf"); pg.wait_for_selector("text=tersimpan di server")
    pg.click("#btn-kirim"); pg.wait_for_selector("text=Laporan Insiden Berhasil Terkirim")
    tiket = pg.inner_text("#tiket-no").strip("#"); print("tiket baru ->", tiket)
    pg.click("text=Lihat Status Laporan"); pg.wait_for_url("**/pelapor/laporan-saya?tiket=*")
    pg.wait_for_selector("[data-card]"); print("laporan-saya total:", pg.inner_text("[data-bind=s_total]"), "| kartu:", pg.locator("[data-card]").count())
    # filter pencarian
    pg.fill("#f-q", "Lembang"); pg.wait_for_timeout(700); print("cari 'Lembang' ->", pg.locator("[data-card]").count(), "(milik sendiri, harus 0)")
    pg.fill("#f-q", tiket); pg.wait_for_timeout(700); print("cari tiket ->", pg.locator("[data-card]").count())
    # 3. pengaturan pelapor
    pg.goto(B + "/pengaturan"); pg.wait_for_selector("#operationalPhone")
    pg.fill("#operationalPhone", "12345"); pg.click("#contactForm button[type=submit]"); pg.wait_for_selector("text=Gagal Menyimpan Identitas")
    print("telepon salah -> modal galat OK"); pg.click("text=Perbaiki Data")
    pg.fill("#operationalPhone", "+62 812-9999-0000"); pg.click("#contactForm button[type=submit]"); pg.wait_for_selector("text=berhasil disimpan")
    print("telepon benar ->", pg.input_value("#operationalPhone"))
    pg.click("#btn-save-privacy"); pg.wait_for_selector("text=privasi pelapor disimpan"); print("privasi OK | skor:", pg.inner_text("[data-bind=skor]"))
    # logout
    pg.click("a[data-path=keluar]"); pg.wait_for_url("**/pelapor/masuk"); print("logout OK")
    # 4. SPI dasbor
    pg.goto(B + "/masuk"); pg.fill("#nippos", "100000001"); pg.fill("#password", "PosInd2025!"); pg.click("#posLoginForm button[type=submit]")
    pg.wait_for_url("**/dashboard", timeout=8000); pg.wait_for_selector("[data-card]")
    print("dasbor kartu:", pg.locator("[data-card]").count(), "| total:", pg.inner_text("[data-bind=s_total]"), "| sla:", pg.inner_text("[data-bind=s_sla]"))
    pg.fill("#f-q", tiket); pg.wait_for_timeout(700); print("SPI cari tiket ->", pg.locator("[data-card]").count())
    pg.click(f"[data-card] [data-open]"); pg.wait_for_selector("#d-status")
    print("opsi Selesai dikunci sebelum investigasi ->", pg.eval_on_selector("#d-status option[value=Selesai]", "o => o.disabled"))
    pg.select_option("#d-status", "Investigasi SPI Lapangan"); pg.click("text=Simpan Perubahan"); pg.wait_for_selector("text=Disposisi berhasil dicatat")
    pg.wait_for_selector("#d-status", state="detached"); pg.click(f"[data-card] [data-open]"); pg.wait_for_selector("#d-status")
    pg.select_option("#d-status", "Selesai"); pg.click("text=Simpan Perubahan"); pg.wait_for_selector("#d-err:not(:empty)")
    print("tutup tanpa resolusi ->", pg.inner_text("#d-err"))
    pg.fill("#d-cat", "Selisih terselesaikan lewat BAP bersama."); pg.click("text=Simpan Perubahan"); pg.wait_for_selector("text=Disposisi berhasil dicatat")
    pg.wait_for_timeout(800); print("setelah selesai, badge status:", pg.locator("[data-card]").first.inner_text().split("\n")[-6:][0:1])
    with pg.expect_download() as d: pg.click("[data-action=export]")
    print("ekspor CSV ->", d.value.suggested_filename)
    br.close()
print("ERRORS:", json.dumps([e for e in errors if "tailwind" not in e[2]], indent=1))
