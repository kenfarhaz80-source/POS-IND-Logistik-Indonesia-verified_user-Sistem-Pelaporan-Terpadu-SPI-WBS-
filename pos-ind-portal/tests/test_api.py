import io, os, re, tempfile, json
os.environ["SEED_DEMO"] = "1"
from app import create_app

PW = "PosInd2025!"

def make_app():
    d = tempfile.mkdtemp()
    os.environ["DATA_DIR"] = d
    return create_app({"TESTING": True})

class C:
    def __init__(self, app):
        self.c = app.test_client(); self.csrf = None
    def req(self, m, url, body=None, **kw):
        h = {"X-CSRF-Token": self.csrf} if self.csrf else {}
        if body is not None and not kw: kw = {"json": body}
        r = getattr(self.c, m)(url, headers=h, **kw)
        return r, (r.get_json(silent=True) or {})
    def login(self, portal, ident, pw=PW, tipe="karyawan"):
        r, j = self.req("post", "/api/auth/masuk", {"portal": portal, "identifier": ident, "password": pw, "tipe": tipe})
        if r.status_code == 200:
            self.csrf = self.req("get", "/api/me")[1]["data"]["csrf"]
        return r, j


def test_login_ok_and_wrong(cl):
    r, j = cl.login("pelapor", "987654321", "salah")
    assert r.status_code == 401
    r, j = cl.login("pelapor", "987654321")
    assert r.status_code == 200 and "/login-berhasil" in j["data"]["redirect"]
    me = cl.req("get", "/api/me")[1]["data"]
    assert me["user"]["nama"].startswith("Budi") and me["home"] == "/pelapor/laporan-saya"

def test_portal_isolation(cl):
    # pelapor tidak bisa masuk di portal karyawan dengan NIPPOS yang sama? (akun terpisah per portal)
    r, _ = cl.login("karyawan", "987654321")
    assert r.status_code == 401

def test_lockout(cl):
    for i in range(5): cl.login("pelapor", "987654321", "x")
    r, j = cl.login("pelapor", "987654321", PW)
    assert r.status_code == 429

def test_register_validation_and_success(cl):
    base = {"portal": "karyawan", "identifier": "123456789", "nama": "Tes Pegawai", "email": "tes@posindonesia.co.id",
            "password": "Abcdefg1", "konfirmasi": "Abcdefg1", "setuju": True}
    r, j = cl.req("post", "/api/auth/daftar", {**base, "email": "x@gmail.com"})
    assert r.status_code == 422 and any(e["field"] == "email" for e in j["errors"])
    r, j = cl.req("post", "/api/auth/daftar", {**base, "password": "abc", "konfirmasi": "abd"})
    assert r.status_code == 422
    r, j = cl.req("post", "/api/auth/daftar", base)
    assert r.status_code == 201
    r2, j2 = cl.req("get", "/api/auth/registrasi-ringkasan?t=" + j["data"]["redirect"].split("t=")[1])
    assert j2["data"]["identifier"] == "123456789"
    assert cl.req("post", "/api/auth/daftar", base)[0].status_code == 409
    assert cl.login("karyawan", "123456789", "Abcdefg1")[0].status_code == 200

def test_mitra_register_and_login(cl):
    r, j = cl.req("post", "/api/auth/daftar", {"portal": "karyawan", "identifier": "ag-1234567", "nama": "Agen Baru", "email": "agen@mitra.id",
              "password": "Abcdefg1", "konfirmasi": "Abcdefg1", "setuju": True})
    assert r.status_code == 201, j
    assert cl.login("karyawan", "AG-1234567", "Abcdefg1", tipe="karyawan")[0].status_code == 401   # tab salah
    assert cl.login("karyawan", "AG-1234567", "Abcdefg1", tipe="mitra")[0].status_code == 200

def test_csrf_required(cl):
    cl.login("pelapor", "987654321")
    r = cl.c.put("/api/akun/profil", json={"telepon": "081234567890"})
    assert r.status_code == 403

def test_profile_rules(cl):
    cl.login("pelapor", "987654321")
    r, j = cl.req("put", "/api/akun/profil", {"telepon": "+62 812-345"})
    assert r.status_code == 422 and j["errors"][0]["field"] == "telepon"
    r, j = cl.req("put", "/api/akun/profil", {"identifier": "111111111"})
    assert r.status_code == 422
    r, j = cl.req("put", "/api/akun/profil", {"telepon": "+62 812-3456-7899"})
    assert r.status_code == 200 and j["data"]["user"]["telepon"] == "081234567899"

def test_password_change_and_session_revoke(cl, app):
    other = C(app); other.login("pelapor", "987654321")
    cl.login("pelapor", "987654321")
    r, j = cl.req("put", "/api/akun/kata-sandi", {"saat_ini": "salah", "baru": "Abcdefg1", "konfirmasi": "Abcdefg1"})
    assert r.status_code == 422
    r, j = cl.req("put", "/api/akun/kata-sandi", {"saat_ini": PW, "baru": "Baru12345", "konfirmasi": "Baru12345"})
    assert r.status_code == 200 and j["data"]["sesi_dicabut"] >= 1
    assert other.req("get", "/api/me")[0].status_code == 401
    assert cl.req("get", "/api/me")[0].status_code == 200

def test_preferences_zone_conflict(cl):
    cl.login("pelapor", "987654321")
    r, j = cl.req("put", "/api/akun/preferensi", {"bagian": "bahasa", "bahasa": "id", "zona_waktu": "WIT", "format_tanggal": "DD/MM/YYYY"})
    assert r.status_code == 422 and "WIB" in j["errors"][0]["message"]
    r, j = cl.req("put", "/api/akun/preferensi", {"bagian": "bahasa", "bahasa": "en", "zona_waktu": "WIB", "format_tanggal": "YYYY-MM-DD"})
    assert r.status_code == 200 and j["data"]["pref"]["format_tanggal"] == "YYYY-MM-DD"
    r, j = cl.req("put", "/api/akun/preferensi", {"bagian": "privasi", "consent_pemrosesan": False})
    assert r.status_code == 422

def test_forgot_and_reset(cl, app):
    r, j = cl.req("post", "/api/auth/lupa-sandi", {"portal": "pelapor", "identifier": "987654321"})
    assert r.status_code == 200
    r2, j2 = cl.req("post", "/api/auth/lupa-sandi", {"portal": "pelapor", "identifier": "000000000"})
    assert j["data"] == j2["data"]                      # tidak membocorkan keberadaan akun
    import sqlite3
    con = sqlite3.connect(app.config["DB_PATH"]); body = con.execute("SELECT isi FROM email_outbox WHERE subjek LIKE 'Pemulihan%'").fetchone()[0]
    tok = re.search(r"token=(\S+)", body).group(1)
    assert cl.req("post", "/api/auth/reset-sandi", {"token": tok, "password": "lemah", "konfirmasi": "lemah"})[0].status_code == 422
    assert cl.req("post", "/api/auth/reset-sandi", {"token": tok, "password": "Segar1234", "konfirmasi": "Segar1234"})[0].status_code == 200
    assert cl.req("post", "/api/auth/reset-sandi", {"token": tok, "password": "Segar1234", "konfirmasi": "Segar1234"})[0].status_code == 410
    assert cl.login("pelapor", "987654321", "Segar1234")[0].status_code == 200
