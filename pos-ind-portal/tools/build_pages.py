"""Mengubah desain Stitch (code.html) menjadi halaman dinamis di app/pages_html/.

Pemakaian:  python tools/build_pages.py /path/ke/stitch_pos_indonesia_auth_portal
Skrip hanya menandai elemen (id / data-*) dan membuang skrip simulasi; seluruh perilaku ada di static/js/app.js.
"""
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "stitch_pos_indonesia_auth_portal")
OUT = Path(__file__).resolve().parent.parent / "app" / "pages_html"
OUT.mkdir(exist_ok=True)


def load(folder):
    return BeautifulSoup((SRC / folder / "code.html").read_text(encoding="utf-8"), "html.parser")


def txt(el):
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True))


def find(root, tag, text=None, **attrs):
    for el in root.find_all(tag, **attrs):
        if text is None or text in txt(el):
            return el
    return None


def find_all(root, tag, text):
    return [el for el in root.find_all(tag) if text in txt(el)]


def bind(root, needle, name, exact=False):
    """Bungkus teks (NavigableString) yang memuat needle dengan <span data-bind=name>."""
    for s in root.find_all(string=True):
        if s.parent.name in ("script", "style"):
            continue
        t = s.strip()
        if (t == needle) if exact else (needle in t):
            span = BeautifulSoup(f'<span data-bind="{name}"></span>', "html.parser").span
            span.string = str(s)
            s.replace_with(span)
            return span
    raise SystemExit(f"[bind] tidak ditemukan: {needle!r} -> {name}")


def bind_all(root, needle, name):
    n = 0
    for s in list(root.find_all(string=True)):
        if s.parent.name in ("script", "style"):
            continue
        if needle in s:
            span = BeautifulSoup(f'<span data-bind="{name}"></span>', "html.parser").span
            span.string = str(s)
            s.replace_with(span)
            n += 1
    return n


def drop_scripts(soup, keep=()):
    for sc in soup.find_all("script"):
        if sc.get("src") or sc.get("id") == "tailwind-config":
            continue
        body = sc.string or ""
        if any(k in body for k in keep):
            continue
        sc.decompose()


def strip_attrs(soup, attrs=("onsubmit",), tags=None):
    for el in soup.find_all(True):
        for a in attrs:
            if el.has_attr(a):
                del el[a]


def finish(soup, name, page):
    for sc in soup.find_all("script", src=re.compile("/static/js/")):
        sc.decompose()
    soup.body["data-page"] = page
    for js in ("core", "auth", "settings", "laporan"):
        soup.body.append(BeautifulSoup(f'<script src="/static/js/{js}.js" defer></script>', "html.parser"))
    for t in soup.find_all("title"):
        t.decompose()
    soup.head.append(BeautifulSoup("<title>POS IND — Portal Logistik</title>", "html.parser"))
    # logo lokal (bukan hotlink)
    (OUT / f"{name}.html").write_text(str(soup), encoding="utf-8")
    print("ok", name)


def remove_remote_imgs(soup, keep_alt=("POS IND", "Logo")):
    for img in soup.find_all("img"):
        alt = img.get("alt", "")
        if "POS IND" in alt or "Logo" in alt:
            img["src"] = "/static/img/logo.png"
        elif alt == "Profile":
            img["data-bind-avatar"] = "1"
            img["src"] = "/static/img/logo.png"
        else:
            img.decompose()


def set_href(root, text, href, tag="a"):
    el = find(root, tag, text)
    if not el:
        raise SystemExit(f"[href] tidak ditemukan: {text}")
    el["href"] = href
    for k in ("data-path",):
        el.attrs.pop(k, None)
    return el


# ============================================================ AUTH
def build_masuk():
    s = load("masuk_portal_karyawan_pos_ind")
    remove_remote_imgs(s)
    f = s.find("form", id="posLoginForm")
    del f["onsubmit"]
    f["data-form"] = "login-karyawan"
    a = find(f, "a", "Lupa Kata Sandi")
    a["href"] = "#"
    a["data-action"] = "lupa"
    set_href(s.body, "Daftar Akun Baru", "/daftar")
    finish(s, "masuk", "masuk")


def build_pelapor_masuk():
    s = load("masuk_portal_pelapor_pos_ind")
    remove_remote_imgs(s)
    f = s.find("form")
    f["data-form"] = "login-pelapor"
    del f["onsubmit"]
    a = find(f, "a", "Lupa Kata Sandi")
    a["href"] = "#"
    a["data-action"] = "lupa"
    f.find("input", type="checkbox")["id"] = "remember"
    set_href(s.body, "Daftar Akun Pelapor Baru", "/pelapor/daftar")
    finish(s, "pelapor_masuk", "pelapor_masuk")


def build_daftar():
    s = load("daftar_registrasi_akun_pos_ind")
    remove_remote_imgs(s)
    f = s.find("form", id="pos_ind_registration_form")
    del f["onsubmit"]
    f["data-form"] = "daftar-karyawan"
    for a in f.find_all("a"):
        if "Ketentuan Layanan" in txt(a):
            a["href"], a["target"] = "/info/syarat-ketentuan", "_blank"
        elif "Kebijakan Privasi" in txt(a):
            a["href"], a["target"] = "/info/kebijakan-privasi", "_blank"
        elif "Helpdesk" in txt(a):
            a["href"] = "/info/pusat-bantuan"
    finish(s, "daftar", "daftar")


def build_pelapor_daftar():
    s = load("daftar_registrasi_akun_pelapor_pos_ind")
    remove_remote_imgs(s)
    f = s.find("form", id="registerForm")
    del f["onsubmit"]
    f["data-form"] = "daftar-pelapor"
    for sp in f.find_all("span"):
        if "Pakta Integritas" in sp.get_text() and sp.find("span") is None:
            sp.name = "a"
            sp["href"], sp["target"] = "/info/perlindungan-pelapor", "_blank"
            break
    finish(s, "pelapor_daftar", "pelapor_daftar")


def build_registrasi_berhasil():
    s = load("notifikasi_berhasil_registrasi_akun_pos_ind")
    remove_remote_imgs(s)
    bind(s.body, "987654321", "identifier", exact=True)
    bind(s.body, "Sesuai SK / Data HRMS", "nama", exact=True)
    em = find(s.body, "span", "nama@posindonesia.co.id")
    bind(em, "nama@posindonesia.co.id", "email")
    em.attrs.pop("title", None)
    lanjut = find(s.body, "a", "Lanjut ke Halaman Masuk")
    lanjut["data-bind-href-login"] = "1"
    lanjut["href"] = "/masuk"
    kembali = find(s.body, "a", "Kembali ke Beranda Utama")
    kembali["href"] = "/masuk"
    help_ = find(s.body, "a", "Helpdesk SDM")
    help_["href"] = "/info/pusat-bantuan"
    finish(s, "registrasi_berhasil", "registrasi_berhasil")


def build_login_berhasil():
    s = load("notifikasi_berhasil_masuk_login_pos_ind")
    remove_remote_imgs(s)
    drop_scripts(s)
    bind(s.body, "NIPPOS 987654321", "ident_label")
    bind(s.body, "Karyawan Internal Kantor Pusat", "afiliasi", exact=True)
    f = find(s.body, "span", "Akses Penuh Seluruh Regional")
    bind(f, "Akses Penuh Seluruh Regional", "akses")
    find(s.body, "span", "Waktu Masuk:").find_next_sibling("span")["data-bind"] = "waktu_masuk"
    find(s.body, "a", "Keluar / Batalkan")["data-action"] = "logout"
    for l in s.find_all("a", href="#"):
        pass
    finish(s, "login_berhasil", "login_berhasil")


def simple_page(name, page, title, inner):
    base = load("masuk_portal_pelapor_pos_ind")
    head = base.head
    doc = BeautifulSoup("<!DOCTYPE html><html lang='id'></html>", "html.parser")
    doc.html.append(head.extract())
    body = BeautifulSoup(
        f"""<body class="bg-surface text-on-surface font-body-md min-h-screen flex flex-col">
<header class="bg-primary-container text-white"><div class="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
<a href="/" class="flex items-center gap-2 font-headline-sm text-headline-sm font-extrabold tracking-tight">POS IND <span class="font-label-md text-label-md font-medium text-on-primary-container">Logistik Indonesia</span></a>
<a data-path="help-center" href="#" class="font-label-md text-label-md hover:underline">Pusat Bantuan</a></div></header>
<main class="flex-1 flex items-start justify-center p-4 pt-10"><div class="w-full max-w-xl bg-surface-container-lowest rounded-xl shadow-md p-space-lg space-y-space-md">
<h1 class="font-headline-md text-headline-md font-extrabold text-primary tracking-tight">{title}</h1>{inner}</div></main>
<footer class="py-4 text-center font-label-sm text-label-sm text-on-surface-variant">© PT Pos Indonesia (Persero). Seluruh hak cipta dilindungi.
 • <a data-path="kebijakan-privasi" href="#" class="hover:underline">Kebijakan Privasi</a> • <a data-path="syarat-ketentuan" href="#" class="hover:underline">Syarat &amp; Ketentuan</a></footer></body>""",
        "html.parser")
    doc.html.append(body)
    finish(doc, name, page)


INPUT = "w-full h-12 px-4 rounded-lg border border-outline-variant bg-white focus:ring-2 focus:ring-primary outline-none"


def build_simple_pages():
    simple_page("reset_sandi", "reset_sandi", "Buat Kata Sandi Baru", f"""
<p class="font-body-md text-body-md text-on-surface-variant">Masukkan kata sandi baru untuk akun Anda. Minimal 8 karakter dengan huruf besar, huruf kecil, dan angka.</p>
<form id="reset-form" class="space-y-space-md" novalidate>
<div><label class="block font-label-md text-label-md font-bold mb-1" for="rp-pass">Kata Sandi Baru</label><input id="rp-pass" type="password" autocomplete="new-password" required class="{INPUT}"></div>
<div><label class="block font-label-md text-label-md font-bold mb-1" for="rp-conf">Konfirmasi Kata Sandi</label><input id="rp-conf" type="password" autocomplete="new-password" required class="{INPUT}"></div>
<button type="submit" class="w-full h-12 rounded-lg bg-secondary-container text-white font-label-lg text-label-lg font-bold flex items-center justify-center gap-2 hover:brightness-110">Simpan Kata Sandi</button></form>""")
    simple_page("lacak", "lacak", "Lacak Aduan", f"""
<p class="font-body-md text-body-md text-on-surface-variant">Masukkan nomor tiket laporan Anda (contoh: <span class="font-bold">LAP-WASUM-2026-0001</span>) untuk melihat status penanganan. Identitas pelapor tidak ditampilkan.</p>
<form id="lacak-form" class="flex gap-2" novalidate><input id="lacak-no" type="text" placeholder="LAP-WASUM-2026-0001" class="{INPUT} uppercase" required>
<button type="submit" class="px-5 rounded-lg bg-secondary-container text-white font-label-lg text-label-lg font-bold hover:brightness-110">Lacak</button></form>
<div id="lacak-hasil"></div>""")


if __name__ == "__main__":
    build_simple_pages()
    build_masuk()
    build_pelapor_masuk()
    build_daftar()
    build_pelapor_daftar()
    build_registrasi_berhasil()
    build_login_berhasil()
    import build_app_pages
    build_app_pages.build_all()
