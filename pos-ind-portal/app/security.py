"""Sesi berbasis database, validasi input, audit, notifikasi, dan dekorator otorisasi."""
import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import current_app, g, jsonify, redirect, request, has_request_context
from werkzeug.security import check_password_hash, generate_password_hash

from .db import ex, q

COOKIE = "pos_sid"
SESSION_HOURS = 8
MAX_FAILED = 5
LOCK_MINUTES = 15
FMT = "%Y-%m-%dT%H:%M:%SZ"
DUMMY_HASH = generate_password_hash("dummy-password-untuk-timing")


# ---------------------------------------------------------------- waktu & respons
def now():
    return datetime.now(timezone.utc)


def iso(dt=None):
    return (dt or now()).strftime(FMT)


def parse_iso(s):
    return datetime.strptime(s, FMT).replace(tzinfo=timezone.utc) if s else None


def ok(data=None, **extra):
    return jsonify({"ok": True, "data": data, **extra})


def fail(message, status=400, errors=None, **extra):
    body = {"ok": False, "error": message, **extra}
    if errors:
        body["errors"] = errors
    return jsonify(body), status


def err_item(field, title, message):
    return {"field": field, "title": title, "message": message}


def client_ip():
    if not has_request_context():          # dipanggil dari manage.py (CLI)
        return "cli"
    return request.remote_addr or "0.0.0.0"


# ---------------------------------------------------------------- validasi
RE_NIPPOS = re.compile(r"^\d{9}$")
RE_MITRA = re.compile(r"^[A-Z]{2,8}-[A-Z0-9]{3,12}$")
RE_EMAIL = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
EMAIL_DOMAIN = "posindonesia.co.id"


def normalize_identifier(raw):
    """Kembalikan (identifier, tipe) atau (None, None)."""
    v = (raw or "").strip().upper().replace(" ", "")
    if RE_NIPPOS.match(v):
        return v, "karyawan"
    if RE_MITRA.match(v):
        return v, "mitra"
    return None, None


def valid_email(v):
    return bool(v) and len(v) <= 120 and bool(RE_EMAIL.match(v))


def password_errors(pw):
    errs = []
    if len(pw or "") < 8:
        errs.append("Minimal 8 karakter.")
    if len(pw or "") > 128:
        errs.append("Maksimal 128 karakter.")
    if not re.search(r"[A-Z]", pw or "") or not re.search(r"[a-z]", pw or ""):
        errs.append("Wajib mengandung huruf besar dan huruf kecil.")
    if not re.search(r"\d", pw or ""):
        errs.append("Wajib mengandung angka.")
    return errs


def normalize_phone(raw):
    """Nomor telepon Indonesia -> '08xxxxxxxxx' (10-13 digit) atau None bila tidak valid."""
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("62"):
        digits = "0" + digits[2:]
    if digits.startswith("0") and 10 <= len(digits) <= 13:
        return digits
    return None


def hash_password(pw):
    return generate_password_hash(pw)


def verify_password(hashed, pw):
    return check_password_hash(hashed, pw)


# ---------------------------------------------------------------- audit & notifikasi
def audit(user_id, aksi, detail=None):
    ex("INSERT INTO audit_log(user_id,aksi,detail,ip,waktu) VALUES(?,?,?,?,?)",
       (user_id, aksi, detail, client_ip(), iso()))


def notify(user_id, judul, isi=None, tautan=None):
    ex("INSERT INTO notifikasi(user_id,judul,isi,tautan,waktu) VALUES(?,?,?,?,?)",
       (user_id, judul, isi, tautan, iso()))


def notify_user(user_id, judul, isi=None, tautan=None):
    """Notifikasi dalam aplikasi (selalu) + email bila pengguna mengaktifkan notif_email.
    Catatan: SMS/WhatsApp/push belum ada integrasinya; preferensinya hanya disimpan."""
    notify(user_id, judul, isi, tautan)
    u = q("SELECT u.email, u.nama, p.notif_email FROM users u LEFT JOIN preferensi p ON p.user_id=u.id WHERE u.id=?",
          (user_id,), one=True)
    if u and u["email"] and (u["notif_email"] is None or u["notif_email"]):
        from .mailer import send_mail
        link = (request.host_url.rstrip("/") + tautan) if tautan else ""
        send_mail(u["email"], judul, f"Halo {u['nama']},\n\n{isi or judul}\n\n{link}\n\n— Portal POS IND")


# ---------------------------------------------------------------- sesi
def _sid(token):
    return hashlib.sha256(token.encode()).hexdigest()


def device_label(ua):
    ua = ua or ""
    os_ = ("Windows" if "Windows" in ua else "Android" if "Android" in ua else
           "iOS" if ("iPhone" in ua or "iPad" in ua) else "macOS" if "Mac OS" in ua else
           "Linux" if "Linux" in ua else "Perangkat tidak dikenal")
    br = ("Edge" if "Edg/" in ua else "Chrome" if "Chrome/" in ua else
          "Firefox" if "Firefox/" in ua else "Safari" if "Safari/" in ua else "Peramban")
    return f"{br} di {os_}"


def create_session(user_id):
    token = secrets.token_urlsafe(32)
    t = now()
    ex("INSERT INTO sessions(id,user_id,csrf,ip,user_agent,perangkat,created_at,last_seen,expires_at) "
       "VALUES(?,?,?,?,?,?,?,?,?)",
       (_sid(token), user_id, secrets.token_urlsafe(24), client_ip(),
        (request.headers.get("User-Agent") or "")[:300], device_label(request.headers.get("User-Agent")),
        iso(t), iso(t), iso(t + timedelta(hours=SESSION_HOURS))))
    return token


def set_cookie(resp, token):
    resp.set_cookie(COOKIE, token, max_age=SESSION_HOURS * 3600, httponly=True,
                    samesite="Lax", secure=bool(current_app.config.get("COOKIE_SECURE")))


def clear_cookie(resp):
    resp.delete_cookie(COOKIE)


def load_session():
    g.user = None
    g.sid = None
    g.csrf = None
    token = request.cookies.get(COOKIE)
    if not token:
        return
    row = q("SELECT s.*, u.id AS uid FROM sessions s JOIN users u ON u.id=s.user_id "
            "WHERE s.id=? AND s.revoked=0 AND u.status='aktif'", (_sid(token),), one=True)
    if not row or parse_iso(row["expires_at"]) < now():
        return
    g.user = q("SELECT * FROM users WHERE id=?", (row["uid"],), one=True)
    g.sid, g.csrf = row["id"], row["csrf"]
    if (now() - parse_iso(row["last_seen"])).total_seconds() > 60:   # sliding expiry
        ex("UPDATE sessions SET last_seen=?, expires_at=? WHERE id=?",
           (iso(), iso(now() + timedelta(hours=SESSION_HOURS)), row["id"]))


def revoke_session(sid):
    ex("UPDATE sessions SET revoked=1 WHERE id=?", (sid,))


def revoke_others(user_id, keep_sid):
    """Cabut semua sesi lain milik pengguna; kembalikan jumlah sesi yang dicabut."""
    from .db import get_db
    db = get_db()
    cur = db.execute("UPDATE sessions SET revoked=1 WHERE user_id=? AND id<>? AND revoked=0", (user_id, keep_sid))
    db.commit()
    return cur.rowcount


# ---------------------------------------------------------------- percobaan login
def recent_failures(identifier):
    since = iso(now() - timedelta(minutes=LOCK_MINUTES))
    return q("SELECT COUNT(*) c, MAX(waktu) last FROM login_attempts "
             "WHERE identifier=? AND berhasil=0 AND waktu>=?", (identifier, since), one=True)


def record_attempt(identifier, success):
    ex("INSERT INTO login_attempts(identifier,ip,berhasil,waktu) VALUES(?,?,?,?)",
       (identifier, client_ip(), 1 if success else 0, iso()))


def clear_failures(identifier):
    ex("DELETE FROM login_attempts WHERE identifier=? AND berhasil=0", (identifier,))


# ---------------------------------------------------------------- dekorator
# Hanya peran ini yang boleh melihat SEMUA laporan (uraian kronologis bisa memuat nama terlapor & detail sensitif).
# Registrasi karyawan/mitra bersifat swadaya, jadi peran "karyawan"/"mitra" tidak boleh membaca laporan orang lain.
ROLES_LIHAT_SEMUA = ("spi",)


def boleh_lihat_semua(user):
    return bool(user) and user["portal"] == "karyawan" and user["role"] in ROLES_LIHAT_SEMUA


def home_for(user):
    if user["portal"] == "pelapor":
        return "/pelapor/laporan-saya"
    return "/dashboard" if boleh_lihat_semua(user) else "/staf/pengaturan"


def login_url(portal="karyawan"):
    return "/pelapor/masuk" if portal == "pelapor" else "/masuk"


def api_auth(roles=None, portal=None):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            if not g.user:
                return fail("Sesi berakhir. Silakan masuk kembali.", 401)
            if request.method not in ("GET", "HEAD") and request.headers.get("X-CSRF-Token") != g.csrf:
                return fail("Token keamanan tidak valid. Muat ulang halaman.", 403)
            if roles and g.user["role"] not in roles:
                return fail("Anda tidak memiliki hak akses untuk tindakan ini.", 403)
            if portal and g.user["portal"] != portal:
                return fail("Fitur ini tidak tersedia untuk tipe akun Anda.", 403)
            return fn(*a, **kw)
        return wrapper
    return deco


def page_auth(roles=None, portal=None):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            if not g.user:
                nxt = request.full_path.rstrip("?")
                dest = login_url(portal or "karyawan")
                return redirect(f"{dest}?next={nxt}" if request.method == "GET" else dest)
            if (roles and g.user["role"] not in roles) or (portal and g.user["portal"] != portal):
                return redirect(home_for(g.user))
            return fn(*a, **kw)
        return wrapper
    return deco


def user_public(u):
    keys = ["id", "portal", "tipe", "role", "identifier", "nama", "email", "telepon", "jabatan",
            "unit_kerja", "hub", "tingkat_kantor", "tmt", "level_akses", "zona_penugasan",
            "email_verified", "hrms_terverifikasi", "password_changed_at", "last_login_at", "created_at"]
    d = {k: u[k] for k in keys}
    d["avatar"] = f"/avatar/{u['id']}" if u["avatar_path"] else None
    d["inisial"] = "".join(w[0] for w in re.findall(r"[A-Za-z]+", u["nama"])[:2]).upper() or "?"
    return d
