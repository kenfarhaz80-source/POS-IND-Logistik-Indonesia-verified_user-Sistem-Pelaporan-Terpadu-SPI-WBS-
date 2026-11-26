"""Pemisahan area pelapor vs staf SPI, dan menu sidebar yang konsisten (tepat satu menu aktif)."""
import re
from test_api import C, make_app
from test_laporan import BASE


def nav_items(html):
    """[(href, label, aktif)] dari <aside><nav> hasil render server."""
    aside = re.search(r"<aside\b.*?</aside>", html, re.S).group(0)
    nav = re.search(r"<nav\b.*?</nav>", aside, re.S).group(0)
    out = []
    for m in re.finditer(r'<a class="([^"]*)" href="([^"]+)"(?: aria-current="page")?>(.*?)</a>', nav, re.S):
        label = re.sub(r"<[^>]+>", "", m.group(3)).strip().rstrip("0123456789")
        out.append((m.group(2), label, "bg-primary-container" in m.group(1)))
    return out


def test_staf_menu_tanpa_buat_laporan_dan_satu_aktif(cl):
    cl.login("karyawan", "100000001")
    for path, aktif in [("/dashboard", "/dashboard"), ("/staf/pengaturan", "/staf/pengaturan")]:
        items = nav_items(cl.c.get(path).get_data(as_text=True))
        assert [i[0] for i in items] == ["/dashboard", "/staf/pengaturan"], items
        assert [i[0] for i in items if i[2]] == [aktif], items          # TEPAT satu menu aktif
    assert not any("Buat Laporan" in i[1] for i in items)


def test_pelapor_menu_urutan_sama_dan_satu_aktif(cl):
    cl.login("pelapor", "987654321")
    for path in ("/pelapor/laporan-saya", "/pelapor/laporan-baru", "/pelapor/pengaturan"):
        items = nav_items(cl.c.get(path).get_data(as_text=True))
        assert [i[0] for i in items] == ["/pelapor/laporan-saya", "/pelapor/laporan-baru", "/pelapor/pengaturan"], items
        assert [i[0] for i in items if i[2]] == [path], items


def test_halaman_dipisah_per_portal(cl, app):
    spi = C(app); spi.login("karyawan", "100000001")
    for p in ("/pelapor/laporan-baru", "/pelapor/laporan-saya", "/pelapor/pengaturan"):
        r = spi.c.get(p); assert r.status_code == 302 and r.headers["Location"].endswith("/dashboard"), p
    pel = C(app); pel.login("pelapor", "987654321")
    for p in ("/dashboard", "/staf/pengaturan"):
        r = pel.c.get(p); assert r.status_code == 302 and r.headers["Location"].endswith("/pelapor/laporan-saya"), p


def test_url_lama_dialihkan_sesuai_portal(cl, app):
    pel = C(app); pel.login("pelapor", "987654321")
    r = pel.c.get("/laporan/baru?draf=5"); assert r.headers["Location"].endswith("/pelapor/laporan-baru?draf=5")
    assert pel.c.get("/laporan-saya").headers["Location"].endswith("/pelapor/laporan-saya")
    assert pel.c.get("/pengaturan").headers["Location"].endswith("/pelapor/pengaturan")
    spi = C(app); spi.login("karyawan", "100000001")
    assert spi.c.get("/laporan/baru").headers["Location"].endswith("/dashboard")
    assert spi.c.get("/pengaturan").headers["Location"].endswith("/staf/pengaturan")


def test_staf_tidak_bisa_membuat_laporan_lewat_api(cl):
    cl.login("karyawan", "100000001")
    for method, url, body in [("post", "/api/laporan", BASE), ("post", "/api/laporan/draf", BASE), ("get", "/api/laporan/saya", None)]:
        r, j = cl.req(method, url, body) if body is not None else cl.req(method, url)
        assert r.status_code == 403, (url, r.status_code)


def test_badge_menghitung_laporan_berjalan(cl):
    cl.login("karyawan", "100000001")
    me = cl.req("get", "/api/me")[1]["data"]
    st = cl.req("get", "/api/statistik")[1]["data"]
    assert me["badge_laporan"] == st["berjalan"] == st["total"] - st["selesai"]
    assert sum(st["per_tingkat"].values()) == st["total"]               # ringkasan per tingkat menjumlah ke total


def test_karyawan_biasa_tidak_punya_dasbor(cl, app):
    kar = C(app); kar.login("karyawan", "987654322")
    assert kar.c.get("/dashboard").headers["Location"].endswith("/staf/pengaturan")
    items = nav_items(kar.c.get("/staf/pengaturan").get_data(as_text=True))
    assert [i[0] for i in items] == ["/staf/pengaturan"] and items[0][2]
    assert kar.req("get", "/api/me")[1]["data"]["home"] == "/staf/pengaturan"
    assert kar.req("get", "/api/statistik")[0].status_code == 403
