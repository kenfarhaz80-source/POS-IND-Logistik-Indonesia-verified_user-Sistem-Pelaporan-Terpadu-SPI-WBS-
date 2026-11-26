import io
from test_api import C, make_app, PW

BASE = {"klasifikasi": "WASUM", "tipologi": "Unmanifested Cargo & Skip Barcode SPP (Barang Gelap / Kargo Tak Teregistrasi)",
        "awb": "POS99281746210ID", "plat_armada": "D-8812-POS", "rute": "Hub Sentral Jakarta - Sentral Pengolahan Pos Bandung",
        "deviasi": "3 Koli / -12.4 Kg", "pelapor_tingkat": "KCP", "pelapor_unit": "KCP Tes", "terlapor_nama": "Regu Muat X",
        "terlapor_tingkat": "KCU", "terlapor_unit": "KCU Tes", "waktu_kejadian": "2026-10-01T09:00", "lokasi": "Dock Inbound 4",
        "uraian": "Ditemukan segel kantong terbuka dan selisih timbangan saat unloading feeder di dock inbound.", "pernyataan": True}

def pdf(): return (io.BytesIO(b"%PDF-1.4 tes"), "bukti.pdf")

def kirim(cl, **kw):
    return cl.req("post", "/api/laporan", {**BASE, **kw})

def test_validasi_wasum(cl):
    cl.login("pelapor", "987654321")
    r, j = kirim(cl, tipologi="", awb="", plat_armada="", rute="", deviasi="", pernyataan=False)
    assert r.status_code == 422 and {e["field"] for e in j["errors"]} >= {"tipologi", "awb", "plat_armada", "rute", "deviasi", "pernyataan"}
    r, j = kirim(cl, waktu_kejadian="2999-01-01T00:00")
    assert any(e["field"] == "waktu_kejadian" for e in j["errors"])

def test_kirim_nomor_unik_dan_prioritas(cl):
    cl.login("pelapor", "987654321")
    a = kirim(cl, tipologi="Kerusakan / Kehilangan Koli & Pembobolan Segel Kantong Pos")[1]["data"]
    b = kirim(cl, tipologi="Keterlambatan Feeder & Deviasi Rute Armada Truk Pos Tanpa Otorisasi")[1]["data"]
    assert a["tiket"] != b["tiket"] and a["tiket"].startswith("LAP-WASUM-")
    assert a["prioritas"] == "Tinggi" and b["prioritas"] == "Normal"             # deviasi muatan = tinggi, pelanggaran SOP = normal

def test_bukti_akses_terbatas(cl, app):
    cl.login("pelapor", "987654321")
    r, j = cl.req("post", "/api/lampiran", data={"berkas": pdf()}, content_type="multipart/form-data")
    assert r.status_code == 201
    aid = j["data"]["id"]
    r, j = cl.req("post", "/api/laporan", {**BASE, "lampiran_ids": [aid]}); tiket = j["data"]["tiket"]
    assert cl.c.get(f"/berkas/{aid}").status_code == 200                        # pemilik
    siti = C(app); siti.login("pelapor", "981120340")
    assert siti.c.get(f"/berkas/{aid}").status_code == 403                      # pelapor lain
    spi = C(app); spi.login("karyawan", "100000001")
    assert spi.c.get(f"/berkas/{aid}").status_code == 200                       # SPI
    kar = C(app); kar.login("karyawan", "987654322")
    assert kar.c.get(f"/berkas/{aid}").status_code == 403                       # karyawan biasa
    assert C(app).c.get(f"/berkas/{aid}").status_code == 302                    # anonim -> login
    # karyawan/mitra biasa sama sekali tidak boleh membuka laporan orang lain
    assert kar.req("get", f"/api/laporan/{tiket}")[0].status_code == 404

def test_isolasi_laporan_saya_dan_draf(cl, app):
    cl.login("pelapor", "987654321")
    r, j = cl.req("post", "/api/laporan/draf", {**BASE}); did = j["data"]["id"]
    siti = C(app); siti.login("pelapor", "981120340")
    assert siti.req("get", f"/api/laporan/draf/{did}")[0].status_code == 404
    mine = siti.req("get", "/api/laporan/saya")[1]["data"]["items"]
    assert all(not x["ref"].startswith("DRF") for x in mine)
    assert siti.req("get", "/api/laporan")[0].status_code == 403                # portal pelapor tak boleh daftar global
    assert siti.req("get", f"/api/laporan/{j['data']['kode_draf']}")[0].status_code == 404

def test_anonimitas_pelapor(cl, app):
    cl.login("pelapor", "987654321")
    t = kirim(cl, anonim=True)[1]["data"]["tiket"]
    kar = C(app); kar.login("karyawan", "987654322")
    assert kar.req("get", f"/api/laporan/{t}")[0].status_code == 404
    spi = C(app); spi.login("karyawan", "100000001")
    assert spi.req("get", f"/api/laporan/{t}")[1]["data"]["pelapor"]["nama"].startswith("Budi")
    # daftar global tertutup untuk karyawan biasa (tidak ada celah pencarian nama pelapor)
    assert kar.req("get", "/api/laporan?q=Budi")[0].status_code == 403

def test_disposisi_hak_akses_dan_alur(cl, app):
    cl.login("pelapor", "987654321")
    t = kirim(cl)[1]["data"]["tiket"]
    assert cl.req("post", f"/api/laporan/{t}/disposisi", {"aksi": "teruskan"})[0].status_code == 403
    kar = C(app); kar.login("karyawan", "987654322")
    assert kar.req("post", f"/api/laporan/{t}/disposisi", {"aksi": "teruskan"})[0].status_code == 403
    spi = C(app); spi.login("karyawan", "100000001")
    assert spi.req("post", f"/api/laporan/{t}/disposisi", {"aksi": "verifikasi_bukti"})[0].status_code == 409   # tanpa bukti
    # alur harus berurutan: tidak boleh langsung menutup dari "Terdaftar"
    r, j = spi.req("post", f"/api/laporan/{t}/disposisi", {"aksi": "ubah_status", "status": "Selesai", "catatan": "Selisih sudah dikembalikan penuh."})
    assert r.status_code == 409
    assert spi.req("post", f"/api/laporan/{t}/disposisi", {"aksi": "ubah_status", "status": "Investigasi SPI Lapangan"})[0].status_code == 200
    assert spi.req("post", f"/api/laporan/{t}/disposisi", {"aksi": "ubah_status", "status": "Terdaftar"})[0].status_code == 409   # tak boleh mundur
    r, j = spi.req("post", f"/api/laporan/{t}/disposisi", {"aksi": "ubah_status", "status": "Selesai", "catatan": "x"})
    assert r.status_code == 422
    r, j = spi.req("post", f"/api/laporan/{t}/disposisi", {"aksi": "ubah_status", "status": "Selesai", "catatan": "Selisih sudah dikembalikan penuh."})
    assert r.status_code == 200 and j["data"]["no_berita_acara"].startswith("BA-WASUM/") and j["data"]["status"] == "Selesai"
    notif = cl.req("get", "/api/notifikasi")[1]["data"]
    assert any(t in n["judul"] for n in notif["items"])                          # pelapor diberi tahu
    pub = C(app).req("get", f"/api/lacak/{t}")[1]["data"]
    assert pub["status"] == "Selesai" and "pelapor" not in pub

def test_csv_injection_dan_ekspor(cl, app):
    cl.login("pelapor", "987654321")
    kirim(cl, terlapor_nama="=HYPERLINK(\"http://x\")")
    r = cl.c.get("/api/laporan-ekspor.csv")
    body = r.data.decode("utf-8-sig")
    assert r.status_code == 200 and "'=HYPERLINK" in body and ",=HYPERLINK" not in body

def test_upload_ditolak(cl):
    cl.login("pelapor", "987654321")
    r, _ = cl.req("post", "/api/lampiran", data={"berkas": (io.BytesIO(b"MZ\x90"), "virus.exe")}, content_type="multipart/form-data")
    assert r.status_code == 415
    r, _ = cl.req("post", "/api/lampiran", data={"berkas": (io.BytesIO(b"<html>"), "x.pdf")}, content_type="multipart/form-data")
    assert r.status_code == 415

def test_filter_dan_halaman(cl):
    cl.login("karyawan", "100000001")
    d = cl.req("get", "/api/laporan?per_page=2&page=2&urut=prioritas")[1]["data"]
    assert d["per_page"] == 2 and len(d["items"]) == 2 and d["total"] == 4
    assert cl.req("get", "/api/laporan?q=%25")[1]["data"]["total"] == 0           # wildcard di-escape
    assert cl.req("get", "/api/laporan?q=' OR 1=1--")[1]["data"]["total"] == 0    # SQL injection tak berefek
    s = cl.req("get", "/api/statistik")[1]["data"]
    assert s["total"] == 4 and s["selesai"] == 1

def test_terlapor_tertutup_untuk_non_spi(cl, app):
    cl.login("pelapor", "987654321")
    tk = kirim(cl, terlapor_nama="Rahmat Hidayat", terlapor_nippos="123123123")[1]["data"]["tiket"]
    kar = C(app); kar.login("karyawan", "987654322")
    assert kar.req("get", f"/api/laporan/{tk}")[0].status_code == 404
    assert kar.req("get", "/api/laporan?q=Rahmat")[0].status_code == 403
    assert kar.req("get", "/api/laporan-ekspor.csv")[0].status_code == 403
    spi = C(app); spi.login("karyawan", "100000001")
    assert spi.req("get", f"/api/laporan/{tk}")[1]["data"]["terlapor"]["nama"] == "Rahmat Hidayat"
    assert spi.req("get", "/api/laporan?q=Rahmat")[1]["data"]["total"] == 1
    assert cl.req("get", f"/api/laporan/{tk}")[1]["data"]["terlapor"]["nama"] == "Rahmat Hidayat"   # pemilik


def test_laporan_ditutup_tidak_bisa_diubah_lagi(cl, app):
    cl.login("pelapor", "987654321")
    tk = kirim(cl)[1]["data"]["tiket"]
    spi = C(app); spi.login("karyawan", "100000001")
    spi.req("post", f"/api/laporan/{tk}/disposisi", {"aksi": "ubah_status", "status": "Investigasi SPI Lapangan"})
    assert spi.req("post", f"/api/laporan/{tk}/disposisi", {"aksi": "ubah_status", "status": "Selesai", "catatan": "Selisih sudah dikembalikan penuh."})[0].status_code == 200
    r, _ = spi.req("post", f"/api/laporan/{tk}/disposisi", {"aksi": "ubah_status", "status": "Terdaftar"})
    assert r.status_code == 409

def test_bukti_draf_tidak_terbaca_spi(cl, app):
    cl.login("pelapor", "987654321")
    r, j = cl.req("post", "/api/lampiran", data={"berkas": pdf()}, content_type="multipart/form-data")
    aid = j["data"]["id"]
    spi = C(app); spi.login("karyawan", "100000001")
    assert spi.c.get(f"/berkas/{aid}").status_code == 403          # belum dikirim -> hanya pemilik
    did = cl.req("post", "/api/laporan/draf", {**BASE, "lampiran_ids": [aid]})[1]["data"]["id"]
    assert spi.c.get(f"/berkas/{aid}").status_code == 403          # masih draf
    cl.req("post", "/api/laporan", {**BASE, "draf_id": did, "lampiran_ids": [aid]})
    assert spi.c.get(f"/berkas/{aid}").status_code == 200          # setelah dikirim -> SPI boleh

def test_avatar_tidak_bisa_diintip_pengguna_lain(cl, app):
    cl.login("pelapor", "987654321")
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 32
    r, j = cl.req("post", "/api/akun/avatar", data={"foto": (io.BytesIO(png), "a.png")}, content_type="multipart/form-data")
    assert r.status_code == 200
    uid = cl.req("get", "/api/me")[1]["data"]["user"]["id"]
    assert cl.c.get(f"/avatar/{uid}").status_code == 200
    siti = C(app); siti.login("pelapor", "981120340")
    assert siti.c.get(f"/avatar/{uid}").status_code == 404


# ------------------------------------------------------------------ JASKUG/ASKUG sudah dihapus: hanya WASUM
def test_hanya_wasum_klasifikasi_lain_diabaikan(cl, app):
    cl.login("pelapor", "987654321")
    d = kirim(cl, klasifikasi="ASKUG")[1]["data"]                      # klien yang masih mengirim ASKUG tidak bisa membuat laporan ASKUG
    assert d["klasifikasi"] == "WASUM" and d["tiket"].startswith("LAP-WASUM-")
    spi = C(app); spi.login("karyawan", "100000001")
    r = spi.req("get", f"/api/laporan/{d['tiket']}")[1]["data"]
    assert r["klasifikasi"] == "WASUM" and "nominal" not in r
    assert spi.req("get", "/api/laporan?klasifikasi=ASKUG")[1]["data"]["total"] == spi.req("get", "/api/laporan")[1]["data"]["total"]   # filter tak dikenal
    st = spi.req("get", "/api/statistik")[1]["data"]
    assert "askug" not in st and "wasum" not in st


def test_nominal_tidak_lagi_disimpan_atau_diekspor(cl, app):
    cl.login("pelapor", "987654321")
    d = kirim(cl, nominal="9.999.999")[1]["data"]
    from app.db import q
    with app.app_context():
        cols = [c[1] for c in q("PRAGMA table_info(laporan)")]
    assert "nominal" not in cols
    spi = C(app); spi.login("karyawan", "100000001")
    csv = spi.c.get("/api/laporan-ekspor.csv").data.decode("utf-8-sig")
    assert "Nominal" not in csv and "9999999" not in csv and "9.999.999" not in csv


def test_halaman_form_tanpa_pilihan_jaskug(cl):
    cl.login("pelapor", "987654321")
    html = cl.c.get("/pelapor/laporan-baru?klas=askug").get_data(as_text=True)
    for kata in ("JASKUG", "ASKUG", "card-askug", "input-nominal", "FIN-LOG", "Jasa Keuangan"):
        assert kata not in html, kata
    assert "WASUM" in html and 'id="wasum-fields"' in html
