"""Progres/SLA, pesan pelapor<->SPI, catatan internal, bukti susulan, email sesuai preferensi, migrasi DB lama."""
import io, os, sqlite3, tempfile
from test_api import C, make_app
from test_laporan import BASE, kirim, pdf


def siapkan(app):
    pel = C(app); pel.login("pelapor", "987654321")
    spi = C(app); spi.login("karyawan", "100000001")
    tk = kirim(pel)[1]["data"]["tiket"]
    return pel, spi, tk


def detail(c, tk):
    return c.req("get", f"/api/laporan/{tk}")[1]["data"]


def test_progres_per_tahap_dan_sla(cl, app):
    pel, spi, tk = siapkan(app)
    p = detail(pel, tk)["progres"]
    assert p["persen"] == 25 and p["tahap"] == 1 and p["menunggu"].startswith("SPI") and p["sla"] == "aman" and p["sisa_hari"] == 5
    spi.req("post", f"/api/laporan/{tk}/disposisi", {"aksi": "ubah_status", "status": "Investigasi SPI Lapangan", "investigator": "Tim Regional III"})
    p = detail(spi, tk)["progres"]
    assert p["persen"] == 50 and p["penanggung_jawab"] == "Tim Regional III" and p["langkah_berikut"]
    spi.req("post", f"/api/laporan/{tk}/disposisi", {"aksi": "ubah_status", "status": "Klarifikasi Satker"})
    p = detail(pel, tk)["progres"]; assert p["persen"] == 75 and p["menunggu"].startswith("Satker") and p["tenggat_klarifikasi"]
    spi.req("post", f"/api/laporan/{tk}/disposisi", {"aksi": "ubah_status", "status": "Selesai", "catatan": "Selisih sudah dipulihkan."})
    p = detail(pel, tk)["progres"]; assert p["persen"] == 100 and p["selesai"] and p["menunggu"] is None and p["sla"] == "selesai_tepat"


def test_sla_terlambat_dan_statistik_konsisten(cl, app):
    spi = C(app); spi.login("karyawan", "100000001")
    con = sqlite3.connect(app.config["DB_PATH"])
    con.execute("UPDATE laporan SET dikirim_pada='2020-01-06T08:00:00Z' WHERE no_tiket=(SELECT no_tiket FROM laporan WHERE status='Terdaftar' OR status='Investigasi SPI Lapangan' LIMIT 1)")
    con.commit(); con.close()
    tk = sqlite3.connect(app.config["DB_PATH"]).execute("SELECT no_tiket FROM laporan WHERE dikirim_pada LIKE '2020%'").fetchone()[0]
    p = detail(spi, tk)["progres"]
    assert p["terlambat"] and p["sla"] == "terlambat" and p["sisa_hari"] < 0
    st = spi.req("get", "/api/statistik")[1]["data"]
    assert st["sla"] < 100 and "lewat_tenggat" in st and "menunggu_pelapor" in st


def test_pesan_dua_arah_dan_catatan_internal(cl, app):
    pel, spi, tk = siapkan(app)
    r = spi.req("post", f"/api/laporan/{tk}/pesan", {"jenis": "permintaan", "isi": "Mohon lampirkan foto segel yang rusak."})
    assert r[0].status_code == 201
    spi.req("post", f"/api/laporan/{tk}/pesan", {"jenis": "catatan", "isi": "Terlapor pernah dilaporkan 2x; hati-hati."})
    d = detail(pel, tk)
    assert [m["jenis"] for m in d["pesan"]] == ["permintaan"]                   # catatan internal tak sampai ke pelapor
    assert d["pesan"][0]["nama"] == "Tim SPI" and d["progres"]["menunggu"] == "Pelapor" and d["progres"]["permintaan_terbuka"]
    assert "hati-hati" not in str(d)
    assert [m["jenis"] for m in detail(spi, tk)["pesan"]] == ["permintaan", "catatan"]
    assert pel.req("get", "/api/notifikasi")[1]["data"]["items"][0]["judul"].startswith("SPI meminta informasi")
    r = pel.req("post", f"/api/laporan/{tk}/pesan", {"isi": "Foto sudah saya unggah."})
    assert r[0].status_code == 201
    d = detail(spi, tk); assert d["progres"]["menunggu"].startswith("SPI") and not d["progres"]["permintaan_terbuka"]
    assert any(n["judul"].startswith("Balasan pelapor") for n in spi.req("get", "/api/notifikasi")[1]["data"]["items"])
    # pelapor tidak bisa menulis catatan internal / pesan kosong; pelapor lain & karyawan biasa tak punya akses
    assert pel.req("post", f"/api/laporan/{tk}/pesan", {"jenis": "catatan", "isi": "coba bobol"})[1]["data"]["pesan"][-1]["jenis"] == "balasan"
    assert pel.req("post", f"/api/laporan/{tk}/pesan", {"isi": " "})[0].status_code == 422
    siti = C(app); siti.login("pelapor", "981120340"); assert siti.req("post", f"/api/laporan/{tk}/pesan", {"isi": "halo"})[0].status_code == 404
    kar = C(app); kar.login("karyawan", "987654322"); assert kar.req("post", f"/api/laporan/{tk}/pesan", {"isi": "halo"})[0].status_code == 404


def test_pesan_ditolak_pada_laporan_selesai(cl, app):
    pel, spi, tk = siapkan(app)
    spi.req("post", f"/api/laporan/{tk}/disposisi", {"aksi": "ubah_status", "status": "Investigasi SPI Lapangan"})
    spi.req("post", f"/api/laporan/{tk}/disposisi", {"aksi": "ubah_status", "status": "Selesai", "catatan": "Selesai dan direkonsiliasi."})
    assert pel.req("post", f"/api/laporan/{tk}/pesan", {"isi": "terima kasih"})[0].status_code == 409
    assert spi.req("post", f"/api/laporan/{tk}/pesan", {"isi": "catatan"})[0].status_code == 409


def test_disposisi_internal_disamarkan_untuk_pelapor(cl, app):
    pel, spi, tk = siapkan(app)
    spi.req("post", f"/api/laporan/{tk}/disposisi", {"aksi": "ubah_status", "status": "Investigasi SPI Lapangan",
            "catatan": "Rahasia: CCTV menunjukkan oknum A.", "tampilkan_pelapor": False})
    d = detail(pel, tk)
    teks = str(d["disposisi"]); assert "Rahasia" not in teks and "oknum" not in teks
    assert all(x["oleh"] is None for x in d["disposisi"])                       # nama petugas SPI tak diperlihatkan
    ds = detail(spi, tk)["disposisi"]; assert any("Rahasia" in (x["catatan"] or "") and x["internal"] for x in ds)
    notif = pel.req("get", "/api/notifikasi")[1]["data"]["items"]
    assert not any("Rahasia" in (n["isi"] or "") for n in notif)
    # resolusi akhir selalu publik walau dicentang internal
    spi.req("post", f"/api/laporan/{tk}/disposisi", {"aksi": "ubah_status", "status": "Selesai", "catatan": "Hasil akhir: dipulihkan.", "tampilkan_pelapor": False})
    assert "Hasil akhir" in str(detail(pel, tk)["disposisi"])


def test_bukti_susulan(cl, app):
    pel, spi, tk = siapkan(app)
    r, j = pel.req("post", f"/api/laporan/{tk}/lampiran", data={"berkas": [pdf(), (io.BytesIO(b"%PDF-1.4 dua"), "dua.pdf")]}, content_type="multipart/form-data")
    assert r.status_code == 201 and j["data"]["jumlah_lampiran"] == 2 and all(a["susulan"] for a in j["data"]["lampiran"])
    assert any(x["aksi"] == "bukti_susulan" and x["publik"] for x in j["data"]["disposisi"])
    aid = j["data"]["lampiran"][0]["id"]
    assert spi.c.get(f"/berkas/{aid}").status_code == 200 and any("Bukti tambahan" in n["judul"] for n in spi.req("get", "/api/notifikasi")[1]["data"]["items"])
    assert pel.req("delete", f"/api/lampiran/{aid}")[0].status_code == 409      # bukti terkirim tak bisa dihapus
    bad = pel.req("post", f"/api/laporan/{tk}/lampiran", data={"berkas": (io.BytesIO(b"MZ"), "x.exe")}, content_type="multipart/form-data")[0]
    assert bad.status_code == 415
    siti = C(app); siti.login("pelapor", "981120340")
    assert siti.req("post", f"/api/laporan/{tk}/lampiran", data={"berkas": pdf()}, content_type="multipart/form-data")[0].status_code == 404
    assert spi.req("post", f"/api/laporan/{tk}/lampiran", data={"berkas": pdf()}, content_type="multipart/form-data")[0].status_code == 403
    spi.req("post", f"/api/laporan/{tk}/disposisi", {"aksi": "ubah_status", "status": "Investigasi SPI Lapangan"})
    spi.req("post", f"/api/laporan/{tk}/disposisi", {"aksi": "ubah_status", "status": "Selesai", "catatan": "Selesai dan ditutup."})
    assert pel.req("post", f"/api/laporan/{tk}/lampiran", data={"berkas": pdf()}, content_type="multipart/form-data")[0].status_code == 409


def test_email_mengikuti_preferensi(cl, app):
    pel, spi, tk = siapkan(app)
    n = lambda: sqlite3.connect(app.config["DB_PATH"]).execute("SELECT COUNT(*) FROM email_outbox WHERE tujuan='budi.santoso@posindonesia.co.id'").fetchone()[0]
    awal = n(); assert awal >= 1                                              # konfirmasi laporan terkirim (notif_email aktif)
    spi.req("post", f"/api/laporan/{tk}/disposisi", {"aksi": "ubah_status", "status": "Investigasi SPI Lapangan"})
    assert n() == awal + 1
    pel.req("put", "/api/akun/preferensi", {"bagian": "notifikasi", "notif_sms_wa": True, "notif_email": False, "notif_push": True})
    spi.req("post", f"/api/laporan/{tk}/pesan", {"jenis": "permintaan", "isi": "Mohon jelaskan kronologi tambahan."})
    assert n() == awal + 1                                                    # email dimatikan -> hanya notifikasi dalam aplikasi
    assert pel.req("get", "/api/notifikasi")[1]["data"]["items"][0]["judul"].startswith("SPI meminta")


def test_migrasi_database_lama():
    from app.db import init_db
    d = tempfile.mkdtemp(); path = os.path.join(d, "lama.db")
    con = sqlite3.connect(path)
    con.executescript("CREATE TABLE disposisi(id INTEGER PRIMARY KEY, laporan_id INTEGER, aksi TEXT, tahap INTEGER, status TEXT, level TEXT, unit TEXT, catatan TEXT, oleh_id INTEGER, waktu TEXT);"
                      "CREATE TABLE lampiran(id INTEGER PRIMARY KEY, laporan_id INTEGER, pemilik_id INTEGER, nama_asli TEXT, path TEXT, ukuran INTEGER, ekstensi TEXT, mime TEXT, terverifikasi INTEGER, dibuat TEXT);"
                      "INSERT INTO disposisi(aksi,waktu) VALUES('registrasi','x');"); con.commit(); con.close()
    init_db(path); init_db(path)                                              # idempoten
    con = sqlite3.connect(path)
    assert "publik" in [r[1] for r in con.execute("PRAGMA table_info(disposisi)")] and "susulan" in [r[1] for r in con.execute("PRAGMA table_info(lampiran)")]
    assert con.execute("SELECT publik FROM disposisi").fetchone()[0] == 1 and con.execute("SELECT name FROM sqlite_master WHERE name='pesan'").fetchone()


def test_cli_manage_buat_spi_dan_nonaktifkan():
    import subprocess, sys
    d = tempfile.mkdtemp(); env = dict(os.environ, DATA_DIR=d, SEED_DEMO="0")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    run = lambda *a: subprocess.run([sys.executable, "manage.py", *a], cwd=root, env=env, capture_output=True, text=True)
    r = run("buat-spi", "111222333", "Petugas Uji", "uji@posindonesia.co.id", "--sandi", "Abcdefg1"); assert r.returncode == 0, r.stderr
    assert run("buat-spi", "111222333", "Dobel", "lain@posindonesia.co.id", "--sandi", "Abcdefg1").returncode != 0      # duplikat ditolak
    assert run("buat-spi", "123", "Salah", "x@posindonesia.co.id", "--sandi", "Abcdefg1").returncode != 0              # NIPPOS tidak valid
    assert run("buat-spi", "444555666", "Lemah", "l@posindonesia.co.id", "--sandi", "abc").returncode != 0             # sandi lemah
    os.environ["DATA_DIR"] = d; os.environ["SEED_DEMO"] = "0"
    from app import create_app
    app = create_app({"TESTING": True}); c = C(app)
    r, _ = c.login("karyawan", "111222333", "Abcdefg1"); assert r.status_code == 200
    assert c.req("get", "/api/statistik")[0].status_code == 200                      # peran SPI -> boleh melihat dasbor
    assert "111222333" in run("daftar-pengguna").stdout
    assert run("nonaktifkan", "karyawan", "111222333").returncode == 0
    assert c.req("get", "/api/me")[0].status_code == 401                              # sesi langsung dicabut
    assert C(app).login("karyawan", "111222333", "Abcdefg1")[0].status_code == 403   # tidak bisa masuk lagi
    assert run("aktifkan", "karyawan", "111222333").returncode == 0 and C(app).login("karyawan", "111222333", "Abcdefg1")[0].status_code == 200
    os.environ["SEED_DEMO"] = "1"
