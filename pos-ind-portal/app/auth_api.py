import hashlib
import secrets
import sqlite3
from datetime import timedelta
from urllib.parse import quote

from flask import Blueprint, current_app, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from . import security as sec
from .db import ex, q
from .mailer import send_mail, send_verification
from .security import err_item, fail, ok

bp = Blueprint("auth_api", __name__, url_prefix="/api/auth")


def _json():
    return request.get_json(silent=True) or {}


def _safe_next(n, user):
    if n and n.startswith("/") and not n.startswith("//") and "\\" not in n:
        return n
    return sec.home_for(user)


def _serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt="registrasi-berhasil")


# ------------------------------------------------------------------ registrasi
@bp.post("/daftar")
def daftar():
    d = _json()
    portal = d.get("portal")
    if portal not in ("karyawan", "pelapor"):
        return fail("Portal tidak dikenal.")
    nama = " ".join((d.get("nama") or "").split())
    email = (d.get("email") or "").strip().lower()
    pw, pw2 = d.get("password") or "", d.get("konfirmasi") or ""
    ident, tipe = sec.normalize_identifier(d.get("identifier"))
    errs = []

    if not ident or (portal == "pelapor" and tipe != "karyawan"):
        msg = ("NIPPOS harus berupa 9 digit angka." if portal == "pelapor" else
               "Gunakan NIPPOS 9 digit atau ID Mitra (contoh: AG-8829104).")
        errs.append(err_item("identifier", "Identitas Tidak Valid", msg))
    if len(nama) < 3 or len(nama) > 100:
        errs.append(err_item("nama", "Nama Lengkap", "Nama lengkap wajib diisi (3–100 karakter)."))
    if not sec.valid_email(email):
        errs.append(err_item("email", "Format Email", "Alamat email tidak valid."))
    elif (portal == "pelapor" or tipe == "karyawan") and not email.endswith("@" + sec.EMAIL_DOMAIN):
        errs.append(err_item("email", "Domain Email", f"Pegawai wajib memakai email resmi @{sec.EMAIL_DOMAIN}."))
    for m in sec.password_errors(pw):
        errs.append(err_item("password", "Kata Sandi", m))
    if pw != pw2:
        errs.append(err_item("konfirmasi", "Konfirmasi Kata Sandi", "Konfirmasi kata sandi tidak cocok."))
    if not d.get("setuju"):
        errs.append(err_item("setuju", "Persetujuan Wajib",
                             "Anda harus menyetujui pakta integritas / ketentuan layanan." if portal == "pelapor"
                             else "Anda harus menyetujui ketentuan layanan dan kebijakan privasi."))
    hrms = q("SELECT * FROM hrms_master WHERE identifier=?", (ident,), one=True) if ident else None
    if ident and tipe == "karyawan" and not hrms and current_app.config["HRMS_STRICT"]:
        errs.append(err_item("identifier", "NIPPOS Tidak Ditemukan",
                             "NIPPOS belum terdaftar di data kepegawaian. Hubungi Helpdesk SDM (Ext. 14045)."))
    if errs:
        return fail("Data registrasi belum valid.", 422, errs)

    if q("SELECT 1 FROM users WHERE portal=? AND identifier=?", (portal, ident), one=True):
        return fail("Identitas sudah terdaftar.", 409, [err_item("identifier", "Sudah Terdaftar",
                    "NIPPOS / ID Mitra ini sudah memiliki akun. Silakan masuk atau gunakan Lupa Kata Sandi.")])
    if q("SELECT 1 FROM users WHERE portal=? AND email=?", (portal, email), one=True):
        return fail("Email sudah dipakai.", 409, [err_item("email", "Email Sudah Dipakai",
                    "Alamat email ini sudah terhubung dengan akun lain.")])

    now = sec.iso()
    role = "pelapor" if portal == "pelapor" else tipe
    h = dict(hrms) if hrms else {}
    try:
        uid = ex("""INSERT INTO users(portal,tipe,role,identifier,nama,email,password_hash,jabatan,unit_kerja,hub,
                    tingkat_kantor,tmt,level_akses,zona_penugasan,hrms_terverifikasi,email_verified,
                    password_changed_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                 (portal, "pelapor" if portal == "pelapor" else tipe, role, ident, nama, email,
                  sec.hash_password(pw), h.get("jabatan"), h.get("unit_kerja"), h.get("hub"),
                  h.get("tingkat_kantor"), h.get("tmt"), h.get("level_akses"), h.get("zona_penugasan"),
                  1 if hrms else 0, 0, now, now))
    except sqlite3.IntegrityError:
        return fail("Identitas atau email sudah terdaftar.", 409)
    ex("INSERT INTO preferensi(user_id,zona_waktu,updated_at) VALUES(?,?,?)",
       (uid, h.get("zona_penugasan") or "WIB", now))
    g.user = None
    sec.audit(uid, "registrasi", f"{portal}:{ident}")
    sec.notify(uid, "Selamat datang di Portal POS IND",
               "Akun Anda berhasil dibuat. Lengkapi profil di menu Pengaturan Akun.", "/staf/pengaturan" if portal == "karyawan" else "/pelapor/pengaturan")
    send_verification(q("SELECT * FROM users WHERE id=?", (uid,), one=True))
    token = _serializer().dumps({"u": uid})
    return ok({"redirect": f"/registrasi-berhasil?t={token}"}), 201


@bp.get("/registrasi-ringkasan")
def registrasi_ringkasan():
    try:
        data = _serializer().loads(request.args.get("t", ""), max_age=1800)
    except (BadSignature, SignatureExpired):
        return fail("Tautan ringkasan registrasi sudah kedaluwarsa.", 410)
    u = q("SELECT portal,tipe,identifier,nama,email FROM users WHERE id=?", (data["u"],), one=True)
    if not u:
        return fail("Akun tidak ditemukan.", 404)
    return ok(dict(u))


@bp.get("/cek-id")
def cek_id():
    ident, tipe = sec.normalize_identifier(request.args.get("identifier"))
    hrms = bool(ident and q("SELECT 1 FROM hrms_master WHERE identifier=?", (ident,), one=True))
    return ok({"format_valid": bool(ident), "tipe": tipe, "hrms": hrms})


# ------------------------------------------------------------------ login / logout
@bp.post("/masuk")
def masuk():
    d = _json()
    portal = d.get("portal")
    if portal not in ("karyawan", "pelapor"):
        return fail("Portal tidak dikenal.")
    raw = (d.get("identifier") or "").strip()
    pw = d.get("password") or ""
    tab = d.get("tipe") if d.get("tipe") in ("karyawan", "mitra") else "karyawan"
    ident, tipe = sec.normalize_identifier(raw)
    key = f"{portal}:{ident or raw.upper()[:40]}"

    f = sec.recent_failures(key)
    if f["c"] >= sec.MAX_FAILED:
        wait = max(1, sec.LOCK_MINUTES - int((sec.now() - sec.parse_iso(f["last"])).total_seconds() // 60))
        return fail(f"Terlalu banyak percobaan gagal. Akun dikunci sementara, coba lagi dalam {wait} menit.", 429)

    user = q("SELECT * FROM users WHERE portal=? AND identifier=?", (portal, ident), one=True) if ident else None
    match = bool(user) and (portal == "pelapor" or user["tipe"] == tab)
    valid = sec.verify_password(user["password_hash"] if user else sec.DUMMY_HASH, pw) and match
    if not valid:
        sec.record_attempt(key, False)
        left = sec.MAX_FAILED - (f["c"] + 1)
        hint = f" Sisa percobaan: {left}." if left > 0 else ""
        return fail("NIPPOS / ID atau kata sandi salah." + hint, 401,
                    [err_item("password", "Autentikasi Gagal", "NIPPOS / ID atau kata sandi tidak sesuai.")])
    if user["status"] != "aktif":
        return fail("Akun Anda dinonaktifkan. Hubungi Helpdesk SDM.", 403)

    sec.clear_failures(key)
    sec.record_attempt(key, True)
    token = sec.create_session(user["id"])
    ex("UPDATE users SET last_login_at=? WHERE id=?", (sec.iso(), user["id"]))
    g.user = user
    sec.audit(user["id"], "login", user["identifier"])
    nxt = _safe_next(d.get("next"), user)
    resp = jsonify({"ok": True, "data": {"redirect": "/login-berhasil?next=" + quote(nxt, safe="/")}})
    sec.set_cookie(resp, token)
    return resp


@bp.post("/keluar")
def keluar():
    portal = g.user["portal"] if g.user else "karyawan"
    if g.user and request.headers.get("X-CSRF-Token") != g.csrf:
        return fail("Token keamanan tidak valid.", 403)
    if g.sid:
        sec.audit(g.user["id"], "logout")
        sec.revoke_session(g.sid)
    resp = jsonify({"ok": True, "data": {"redirect": sec.login_url(portal)}})
    sec.clear_cookie(resp)
    return resp


# ------------------------------------------------------------------ lupa / reset sandi
@bp.post("/lupa-sandi")
def lupa_sandi():
    d = _json()
    portal = d.get("portal") if d.get("portal") in ("karyawan", "pelapor") else "karyawan"
    ident, _ = sec.normalize_identifier(d.get("identifier"))
    generic = ok({"pesan": "Jika identitas terdaftar, tautan pemulihan telah dikirim ke email terdaftar."})
    if not ident:
        return generic
    # batasi permintaan: maks 3 per jam per identitas
    recent = q("SELECT COUNT(*) c FROM audit_log WHERE aksi='minta_reset' AND detail=? AND waktu>=?",
               (f"{portal}:{ident}", sec.iso(sec.now() - timedelta(hours=1))), one=True)["c"]
    user = q("SELECT * FROM users WHERE portal=? AND identifier=? AND status='aktif'", (portal, ident), one=True)
    if user and recent < 3:
        token = secrets.token_urlsafe(32)
        ex("INSERT INTO reset_tokens(user_id,token_hash,expires_at) VALUES(?,?,?)",
           (user["id"], hashlib.sha256(token.encode()).hexdigest(), sec.iso(sec.now() + timedelta(minutes=30))))
        link = f"{request.host_url.rstrip('/')}/reset-sandi?token={token}"
        send_mail(user["email"], "Pemulihan kata sandi POS IND",
                  f"Halo {user['nama']},\n\nGunakan tautan berikut (berlaku 30 menit) untuk membuat kata sandi baru:\n{link}\n\n"
                  "Abaikan email ini jika Anda tidak memintanya.")
    sec.audit(user["id"] if user else None, "minta_reset", f"{portal}:{ident}")
    return generic


@bp.post("/reset-sandi")
def reset_sandi():
    d = _json()
    th = hashlib.sha256((d.get("token") or "").encode()).hexdigest()
    row = q("SELECT * FROM reset_tokens WHERE token_hash=? AND used=0", (th,), one=True)
    if not row or sec.parse_iso(row["expires_at"]) < sec.now():
        return fail("Tautan pemulihan tidak valid atau sudah kedaluwarsa.", 410)
    errs = [err_item("password", "Kata Sandi", m) for m in sec.password_errors(d.get("password") or "")]
    if d.get("password") != d.get("konfirmasi"):
        errs.append(err_item("konfirmasi", "Konfirmasi", "Konfirmasi kata sandi tidak cocok."))
    if errs:
        return fail("Kata sandi baru belum memenuhi syarat.", 422, errs)
    now = sec.iso()
    ex("UPDATE users SET password_hash=?, password_changed_at=? WHERE id=?",
       (sec.hash_password(d["password"]), now, row["user_id"]))
    ex("UPDATE reset_tokens SET used=1 WHERE user_id=?", (row["user_id"],))
    ex("UPDATE sessions SET revoked=1 WHERE user_id=?", (row["user_id"],))
    g.user = None
    sec.audit(row["user_id"], "reset_sandi")
    sec.notify(row["user_id"], "Kata sandi diperbarui", "Kata sandi akun Anda baru saja direset.")
    portal = q("SELECT portal FROM users WHERE id=?", (row["user_id"],), one=True)["portal"]
    return ok({"redirect": sec.login_url(portal)})
