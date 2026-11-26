import html
import re
from functools import lru_cache
from pathlib import Path

from flask import Blueprint, Response, g, redirect, request

from . import security as sec
from .akun_api import avatar_response
from .db import ex, q
from .laporan_api import kirim_berkas
from .mailer import verification_serializer
from .security import page_auth

bp = Blueprint("pages", __name__)
HTML_DIR = Path(__file__).with_name("pages_html")


@lru_cache(maxsize=None)
def _read(name):
    return (HTML_DIR / f"{name}.html").read_text(encoding="utf-8")


# ------------------------------------------------------------ navigasi sidebar (dirender server)
# Satu sumber kebenaran: urutan, label, dan menu aktif ditentukan di sini, bukan di HTML statis / JS.
NAV_STAF = [("/dashboard", "Laporan Masuk", "insert_chart", True),
            ("/staf/pengaturan", "Pengaturan Akun", "settings", False)]
NAV_PELAPOR = [("/pelapor/laporan-saya", "Laporan Saya", "assignment", True),
               ("/pelapor/laporan-baru", "Buat Laporan Baru", "post_add", False),
               ("/pelapor/pengaturan", "Pengaturan Akun", "settings", False)]
BADGE = ('<span data-bind="badge" class="px-2 py-0.5 rounded-full bg-secondary-container text-white '
         'text-[10px] font-bold ml-auto">{n}</span>')


def nav_html(user, path):
    pelapor = user["portal"] == "pelapor"
    items = NAV_PELAPOR if pelapor else NAV_STAF if sec.boleh_lihat_semua(user) else NAV_STAF[1:]
    out = []
    for href, label, icon, badge in items:
        on = path.rstrip("/") == href
        if pelapor:   # gaya sidebar portal pelapor (lebar w-72)
            cls = ("flex items-center gap-space-md px-space-md py-space-sm rounded-lg transition-all group "
                   + ("bg-primary-container text-on-primary font-bold shadow-sm" if on else
                      "text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface"))
            ic = ('<span class="material-symbols-outlined text-[20px] text-secondary-container '
                  f'group-hover:scale-105 transition-transform">{icon}</span>')
            lab = f'<span class="font-label-lg text-label-lg">{label}</span>'
        else:         # gaya sidebar portal staf (lebar w-64)
            cls = ("flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all "
                   + ("bg-primary-container text-on-primary font-semibold shadow-sm" if on else
                      "text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface font-medium"))
            ic = f'<span class="material-symbols-outlined text-xl">{icon}</span>'
            lab = f'<span class="font-label-lg text-label-lg">{label}</span>'
        cur = ' aria-current="page"' if on else ""
        out.append(f'<a class="{cls}" href="{href}"{cur}>{ic}{lab}{BADGE.format(n=0) if badge else ""}</a>')
    wrap = "flex flex-col gap-1 px-space-md" if pelapor else "space-y-1.5"
    return f'<nav class="{wrap}" aria-label="Navigasi utama">{"".join(out)}</nav>'


_NAV_RE = re.compile(r"(<aside\b.*?)<nav\b[^>]*>.*?</nav>", re.S)


def page(name, status=200, nav=False):
    body = _read(name)
    if nav and getattr(g, "user", None):
        html_nav = nav_html(g.user, request.path)
        body = _NAV_RE.sub(lambda m: m.group(1) + html_nav, body, count=1)
    resp = Response(body, status=status, mimetype="text/html")
    resp.headers["Cache-Control"] = "no-store"
    return resp


def render_info(slug, status=200):
    row = q("SELECT judul, isi FROM halaman_info WHERE slug=?", (slug,), one=True)
    if not row:
        return page_simple("Halaman Tidak Ditemukan", "Halaman yang Anda cari tidak tersedia.", 404)
    return page_simple(row["judul"], row["isi"], status)


def page_simple(judul, isi, status=200):
    paras = "".join(f"<p>{html.escape(p).replace(chr(10), '<br>')}</p>" for p in isi.split("\n\n"))
    back = sec.home_for(g.user) if getattr(g, "user", None) else "/"
    doc = f"""<!DOCTYPE html><html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(judul)} — POS IND</title>
<style>body{{margin:0;font-family:'Plus Jakarta Sans',system-ui,sans-serif;background:#f7f9fc;color:#191c1e}}
header{{background:#162b64;color:#fff;padding:16px 24px;font-weight:800;letter-spacing:-.02em}}
main{{max-width:760px;margin:32px auto;padding:0 20px}}.card{{background:#fff;border:1px solid rgba(22,43,100,.08);
border-radius:16px;padding:32px;box-shadow:0 4px 16px -2px rgba(22,43,100,.05)}}h1{{margin:0 0 16px;color:#162b64;letter-spacing:-.02em}}
p{{line-height:1.7;color:#454650}}a.btn{{display:inline-block;margin-top:16px;background:#ff642d;color:#fff;padding:10px 20px;
border-radius:8px;text-decoration:none;font-weight:600}}</style></head><body>
<header>POS IND • Logistik Indonesia</header><main><div class="card"><h1>{html.escape(judul)}</h1>{paras}
<a class="btn" href="{back}">Kembali</a></div></main></body></html>"""
    return Response(doc, status=status, mimetype="text/html")


# ---------------------------------------------------------------- publik
@bp.get("/")
def index():
    """Beranda: pintu masuk yang jelas — Pelapor (membuat/memantau laporan) vs Staf/SPI (melihat semua laporan)."""
    return redirect(sec.home_for(g.user)) if g.user else page("beranda")


@bp.get("/masuk")
def masuk():
    return redirect(sec.home_for(g.user)) if g.user else page("masuk")


@bp.get("/daftar")
def daftar():
    return redirect(sec.home_for(g.user)) if g.user else page("daftar")


@bp.get("/pelapor/masuk")
def pelapor_masuk():
    return redirect(sec.home_for(g.user)) if g.user else page("pelapor_masuk")


@bp.get("/pelapor/daftar")
def pelapor_daftar():
    return redirect(sec.home_for(g.user)) if g.user else page("pelapor_daftar")


@bp.get("/reset-sandi")
def reset_sandi():
    return page("reset_sandi")


@bp.get("/registrasi-berhasil")
def registrasi_berhasil():
    return page("registrasi_berhasil")


@bp.get("/lacak")
def lacak():
    return page("lacak")


@bp.get("/info/<slug>")
def info(slug):
    return render_info(slug)


@bp.get("/health")
def health():
    q("SELECT 1")
    return {"status": "ok"}


@bp.get("/verifikasi-email")
def verifikasi_email():
    from itsdangerous import BadSignature, SignatureExpired
    try:
        data = verification_serializer().loads(request.args.get("token", ""), max_age=3 * 86400)
    except (BadSignature, SignatureExpired):
        return page_simple("Verifikasi Email Gagal", "Tautan verifikasi tidak valid atau sudah kedaluwarsa. "
                           "Minta tautan baru dari menu Pengaturan Akun.", 400)
    u = q("SELECT id, email FROM users WHERE id=?", (data["u"],), one=True)
    if not u or u["email"] != data["e"]:
        return page_simple("Verifikasi Email Gagal", "Tautan ini tidak lagi berlaku untuk alamat email saat ini.", 400)
    ex("UPDATE users SET email_verified=1 WHERE id=?", (u["id"],))
    return page_simple("Email Terverifikasi", "Alamat email Anda berhasil diverifikasi. Terima kasih.")


# ---------------------------------------------------------------- terautentikasi
@bp.get("/login-berhasil")
@page_auth()
def login_berhasil():
    return page("login_berhasil")


# ---- Area STAF / SPI: melihat semua laporan dari pelapor (bukan tempat membuat laporan)
@bp.get("/dashboard")
@page_auth(portal="karyawan", roles=sec.ROLES_LIHAT_SEMUA)
def dashboard():
    return page("dashboard", nav=True)


@bp.get("/staf/pengaturan")
@page_auth(portal="karyawan")
def pengaturan_staf():
    return page("pengaturan_karyawan", nav=True)


# ---- Area PELAPOR: membuat & memantau laporan milik sendiri
@bp.get("/pelapor/laporan-saya")
@page_auth(portal="pelapor")
def laporan_saya():
    return page("laporan_saya", nav=True)


@bp.get("/pelapor/laporan-baru")
@page_auth(portal="pelapor")
def laporan_baru():
    return page("laporan_baru", nav=True)


@bp.get("/pelapor/pengaturan")
@page_auth(portal="pelapor")
def pengaturan_pelapor():
    return page("pengaturan_pelapor", nav=True)


# ---- URL lama -> diarahkan ke area yang sesuai dengan jenis akun (query string dipertahankan)
def _ke(path):
    qs = request.query_string.decode()
    return redirect(path + ("?" + qs if qs else ""))


@bp.get("/laporan-saya")
@page_auth()
def lama_laporan_saya():
    return _ke(sec.home_for(g.user))


@bp.get("/laporan/baru")
@page_auth()
def lama_laporan_baru():
    return _ke("/pelapor/laporan-baru" if g.user["portal"] == "pelapor" else sec.home_for(g.user))


@bp.get("/pengaturan")
@page_auth()
def lama_pengaturan():
    return _ke("/pelapor/pengaturan" if g.user["portal"] == "pelapor" else "/staf/pengaturan")


@bp.get("/berkas/<int:aid>")
@page_auth()
def berkas(aid):
    return kirim_berkas(aid)


@bp.get("/avatar/<int:uid>")
@page_auth()
def avatar(uid):
    return avatar_response(uid)


@bp.get("/keluar")
def keluar_get():
    return redirect(sec.home_for(g.user) if g.user else "/masuk")
