import os, sys, tempfile, threading, json, re, sqlite3
os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright
app = create_app({"TESTING": True})
srv = make_server("127.0.0.1", 5056, app, threaded=True); threading.Thread(target=srv.serve_forever, daemon=True).start()
B = "http://127.0.0.1:5056"; errors = []
with sync_playwright() as pw:
    br = pw.chromium.launch(); pg = br.new_context(viewport={"width":1400,"height":900}).new_page()
    pg.on("pageerror", lambda e: "tailwind" not in str(e) and errors.append((pg.url, str(e))))
    # registrasi karyawan via UI (galat dulu)
    pg.goto(B + "/daftar")
    pg.fill("#reg_nippos", "555666777"); pg.fill("#reg_nama_lengkap", "Rina Tes"); pg.fill("#reg_email", "rina@gmail.com")
    pg.fill("#reg_password", "Abcdefg1"); pg.fill("#reg_password_confirmation", "Abcdefg1"); pg.check("#terms_consent")
    pg.click("#submit_register_btn"); pg.wait_for_selector("text=Registrasi Belum Berhasil"); print("daftar email salah ->", pg.inner_text("[role=dialog] li p").strip()); pg.click("[role=dialog] >> text=Perbaiki Data")
    pg.fill("#reg_email", "rina@posindonesia.co.id"); pg.click("#submit_register_btn"); pg.wait_for_url("**/registrasi-berhasil**")
    pg.wait_for_function("document.querySelector('[data-bind=identifier]').textContent=='555666777'"); print("registrasi ok ->", pg.inner_text("[data-bind=email]"))
    # registrasi pelapor
    pg.goto(B + "/pelapor/daftar")
    pg.fill("#namaLengkap","Joko Pelapor"); pg.fill("#emailKedinasan","joko@posindonesia.co.id"); pg.fill("#nippos","444333222")
    pg.fill("#password","Abcdefg1"); pg.fill("#confirmPassword","Abcdefg1"); pg.check("#paktaIntegritas"); pg.click("#registerForm button[type=submit]")
    pg.wait_for_url("**/registrasi-berhasil**"); print("pelapor daftar ok ->", pg.url.split("?")[0])
    pg.click("[data-bind-href-login]"); pg.wait_for_url("**/pelapor/masuk"); print("tautan masuk -> portal pelapor")
    # lupa sandi
    pg.click("[data-action=lupa]"); pg.fill("#lupa-id", "444333222"); pg.click("[role=dialog] >> text=Kirim Tautan"); pg.wait_for_selector("#lupa-msg:has-text('tautan pemulihan')"); print("lupa sandi -> pesan generik OK"); pg.keyboard.press("Escape")
    row = sqlite3.connect(app.config["DB_PATH"]).execute("SELECT isi FROM email_outbox WHERE subjek LIKE 'Pemulihan%'").fetchone()
    tok = re.search(r"token=(\S+)", row[0]).group(1)
    pg.goto(f"{B}/reset-sandi?token={tok}"); pg.fill("#rp-pass","Baru12345"); pg.fill("#rp-conf","Baru12345"); pg.click("#reset-form button[type=submit]"); pg.wait_for_selector("text=Kata Sandi Diperbarui")
    pg.click("text=Menuju Halaman Masuk"); pg.wait_for_url("**/pelapor/masuk"); pg.fill("#nippos-input","444333222"); pg.fill("#password-input","Baru12345"); pg.click("button[type=submit]")
    pg.wait_for_url("**/pelapor/laporan-saya", timeout=8000); print("login pelapor baru setelah reset OK | kartu:", pg.locator("[data-card]").count(), "(harus 0)")
    # form WASUM (satu-satunya lingkup): tanpa kartu pilihan, tanpa kolom nominal
    pg.goto(B + "/pelapor/laporan-baru?klas=askug"); pg.wait_for_selector("#f-waktu")
    body = pg.inner_text("body")
    print("tanpa JASKUG/ASKUG/nominal di form ->", all(k not in body for k in ("JASKUG", "ASKUG", "Nominal")) and pg.locator("#card-askug, #input-nominal").count() == 0,
          "| wasum-fields tampil:", pg.locator("#wasum-fields").is_visible(), "| tombol:", pg.inner_text("#kirim-label"))
    pg.select_option("#f-tipologi", index=1); pg.fill("#f-awb", "POS99281746210ID"); pg.fill("#f-plat", "D-8812-POS"); pg.select_option("#f-rute", index=1); pg.fill("#f-deviasi", "3 Koli / -12.4 Kg")
    pg.select_option("#f-pel-tingkat", index=1); pg.fill("#f-pel-unit","KCP Tes"); pg.fill("#f-terl-nama","Regu Muat"); pg.select_option("#f-terl-tingkat", index=1); pg.fill("#f-terl-unit","KCU Tes")
    pg.fill("#f-waktu","2026-10-03T08:15"); pg.fill("#f-lokasi","Dock Inbound 4")
    pg.fill("#incident-text","Ditemukan segel kantong terbuka dan selisih timbangan saat unloading feeder di dock inbound."); pg.check("#f-pernyataan"); pg.check("#anon-toggle")
    pg.click("#btn-kirim"); pg.wait_for_selector("text=Laporan Insiden Berhasil Terkirim"); print("wasum terkirim ->", pg.inner_text("#tiket-no"), "|", pg.locator("[role=dialog] dd").nth(3).inner_text())
    pg.click("text=Lihat Status Laporan"); pg.wait_for_selector("[data-card]"); print("hierarki pratinjau pelapor:", pg.locator("#preview").inner_text().count("Tahap 1 dari 4"))
    pg.click("a[data-path=keluar]"); pg.wait_for_url("**/pelapor/masuk")
    # mitra + tab
    pg.goto(B + "/daftar"); pg.fill("#reg_nippos","ZZ-1234567"); pg.fill("#reg_nama_lengkap","Agen Zeta"); pg.fill("#reg_email","zeta@mitra.id"); pg.fill("#reg_password","Abcdefg1"); pg.fill("#reg_password_confirmation","Abcdefg1"); pg.check("#terms_consent"); pg.click("#submit_register_btn"); pg.wait_for_url("**/registrasi-berhasil**")
    pg.goto(B + "/masuk"); pg.click("#tab-mitra"); pg.fill("#nippos","ZZ-1234567"); pg.fill("#password","Abcdefg1"); pg.click("#posLoginForm button[type=submit]"); pg.wait_for_url("**/staf/pengaturan", timeout=8000)
    pg.wait_for_selector("#fullName"); print("mitra login ok -> halaman:", pg.url.replace(B, ""), "| tanpa menu laporan:", pg.locator("aside nav a").count() == 1)
    print("mitra ditolak API laporan:", pg.evaluate("fetch('/api/laporan').then(r => r.status)"))
    # pengaturan karyawan
    pg.goto(B + "/pengaturan"); pg.wait_for_selector("#fullName"); print("pengaturan: nama =", pg.input_value("#fullName"), "| nippos =", pg.input_value("#nippos"))
    pg.fill("#fullName","Agen Zeta Baru"); pg.fill("#phoneNumber","08123456789"); pg.click("#profileForm button[type=submit]"); pg.wait_for_selector("text=Identitas & Kontak Berhasil Disimpan"); pg.click("[role=dialog] >> text=Kembali ke Pengaturan")
    pg.evaluate("switchSection('tab-keamanan')"); pg.fill("#currentPassword","salah"); pg.fill("#newPassword","Baru12345"); pg.fill("#confirmPassword","Baru12345"); pg.click("#passwordForm button[type=submit]")
    pg.wait_for_selector("text=Gagal Memperbarui Kata Sandi"); pg.click("[role=dialog] >> text=Perbaiki Data")
    pg.fill("#currentPassword","Abcdefg1"); pg.click("#passwordForm button[type=submit]"); pg.wait_for_selector("text=Kata Sandi Berhasil Diperbarui"); pg.click("[role=dialog] >> text=Kembali ke Pengaturan")
    pg.evaluate("switchSection('tab-bahasa')"); pg.select_option("#timezone","WIT"); pg.click("#langForm button[type=submit]"); pg.wait_for_selector("text=Preferensi Bahasa Berhasil Disimpan"); print("zona WIT diterima (mitra tanpa penugasan zona)")
    pg.click("[role=dialog] >> text=Kembali ke Pengaturan")
    print("skor:", pg.locator("#skor-card").inner_text().split("\n")[3:5], "| sesi:", pg.locator("#sesi-card").inner_text().count("Saat Ini"))
    # halaman publik
    for u in ("/info/kebijakan-privasi", "/info/tidak-ada", "/lacak?no=LAP-WASUM-2026-0001", "/health"):
        r = pg.goto(B + u); print(u, r.status)
    pg.wait_for_timeout(600); print("lacak publik langkah:", pg.goto(B+"/lacak?no=LAP-WASUM-2026-0001") and pg.wait_for_selector("#lacak-hasil li").inner_text()[:40].replace("\n"," "))
    # akses tanpa login
    ctx2 = br.new_context(); p2 = ctx2.new_page(); r = p2.goto(B + "/dashboard"); print("tanpa login /dashboard ->", p2.url.replace(B,""))
    br.close()
print("JS ERRORS:", json.dumps(errors))
