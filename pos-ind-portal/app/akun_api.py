import secrets
from datetime import timedelta
from pathlib import Path

from flask import Blueprint, current_app, g, request, send_file

from . import security as sec
from .db import ex, q
from .mailer import send_verification
from .security import api_auth, err_item, fail, ok

bp = Blueprint("akun_api", __name__, url_prefix="/api")

ZONA = ("WIB", "WITA", "WIT")
FORMAT_TGL = ("DD/MM/YYYY", "YYYY-MM-DD", "DD MMM YYYY")
BAHASA = ("id", "en")
PREF_BOOL = ("notif_sms_wa", "notif_email", "notif_push", "samarkan_nama", "consent_pemrosesan",
             "consent_manifest", "audit_trail_email", "notif_keamanan")


def _json():
    return request.get_json(silent=True) or {}


def get_pref(uid):
    r = q("SELECT * FROM preferensi WHERE user_id=?", (uid,), one=True)
    if not r:
        ex("INSERT INTO preferensi(user_id,updated_at) VALUES(?,?)", (uid, sec.iso()))
        r = q("SELECT * FROM preferensi WHERE user_id=?", (uid,), one=True)
    d = dict(r)
    for k in PREF_BOOL:
        d[k] = bool(d[k])
    return d


# ------------------------------------------------------------------ /api/me
def me_data():
    u = g.user
    if not u:
        return None
    prev = q("SELECT waktu FROM audit_log WHERE user_id=? AND aksi='login' ORDER BY id DESC LIMIT 1 OFFSET 1",
             (u["id"],), one=True)
    n = q("SELECT COUNT(*) c FROM laporan WHERE status NOT IN ('Draf','Selesai')"
          + ("" if u["portal"] == "karyawan" else " AND pelapor_id=?"),
          () if u["portal"] == "karyawan" else (u["id"],), one=True)["c"]
    return {
        "user": sec.user_public(u), "pref": get_pref(u["id"]), "csrf": g.csrf,
        "notif_unread": q("SELECT COUNT(*) c FROM notifikasi WHERE user_id=? AND dibaca=0", (u["id"],), one=True)["c"],
        "badge_laporan": n, "login_sebelumnya": prev["waktu"] if prev else u["last_login_at"],
        "home": sec.home_for(u),
    }


@bp.get("/me")
def me():
    d = me_data()
    return ok(d) if d else fail("Belum masuk.", 401)


# ------------------------------------------------------------------ profil
@bp.put("/akun/profil")
@api_auth()
def profil():
    d, u, errs = _json(), g.user, []
    nama = " ".join((d.get("nama", u["nama"]) or "").split())
    email = (d.get("email", u["email"]) or "").strip().lower()
    tel_raw = d.get("telepon", u["telepon"] or "")

    if "identifier" in d and str(d["identifier"]).strip() != u["identifier"]:
        errs.append(err_item("identifier", "NIPPOS Terkunci",
                    "Nomor induk pegawai tidak dapat diubah secara mandiri. Hubungi bagian SDM jika ada kekeliruan."))
    if nama != u["nama"]:
        if u["portal"] == "pelapor":
            errs.append(err_item("nama", "Nama Terkunci", "Nama pelapor mengikuti SK dan hanya dapat diubah oleh SDM."))
        elif len(nama) < 3 or len(nama) > 100:
            errs.append(err_item("nama", "Nama Lengkap", "Nama lengkap wajib diisi (3–100 karakter)."))
    tel = None
    if (tel_raw or "").strip():
        tel = sec.normalize_phone(tel_raw)
        if not tel:
            errs.append(err_item("telepon", "Format Nomor Telepon", "Nomor harus terdiri dari 10–13 digit angka valid."))
    email_changed = email != u["email"]
    if email_changed:
        if not sec.valid_email(email):
            errs.append(err_item("email", "Format Email", "Alamat email tidak valid."))
        elif u["tipe"] != "mitra" and not email.endswith("@" + sec.EMAIL_DOMAIN):
            errs.append(err_item("email", "Domain Email", f"Pegawai wajib memakai email resmi @{sec.EMAIL_DOMAIN}."))
        elif q("SELECT 1 FROM users WHERE portal=? AND email=? AND id<>?", (u["portal"], email, u["id"]), one=True):
            errs.append(err_item("email", "Email Sudah Dipakai", "Alamat email ini sudah terhubung dengan akun lain."))
    if errs:
        return fail("Identitas & kontak belum dapat disimpan.", 422, errs)

    ex("UPDATE users SET nama=?, email=?, telepon=?, email_verified=? WHERE id=?",
       (nama, email, tel, 0 if email_changed else u["email_verified"], u["id"]))
    g.user = q("SELECT * FROM users WHERE id=?", (u["id"],), one=True)
    if email_changed:
        send_verification(g.user)
    sec.audit(u["id"], "ubah_profil", "email" if email_changed else None)
    return ok({"user": sec.user_public(g.user), "ringkasan": [
        ["Nama Lengkap", nama], ["NIPPOS", u["identifier"]], ["No. Telepon", tel or "-"], ["Email", email]],
        "perlu_verifikasi_email": email_changed})


@bp.post("/akun/verifikasi-email")
@api_auth()
def kirim_ulang_verifikasi():
    u = g.user
    if u["email_verified"]:
        return fail("Email Anda sudah terverifikasi.", 409)
    dalam_jam = q("SELECT COUNT(*) c FROM audit_log WHERE user_id=? AND aksi='kirim_verifikasi' AND waktu>=?",
                  (u["id"], sec.iso(sec.now() - timedelta(hours=1))), one=True)["c"]
    if dalam_jam >= 3:
        return fail("Terlalu sering meminta tautan verifikasi. Coba lagi dalam 1 jam.", 429)
    send_verification(u)
    sec.audit(u["id"], "kirim_verifikasi", u["email"])
    return ok({"email": u["email"]})


@bp.post("/akun/avatar")
@api_auth()
def avatar():
    f = request.files.get("foto")
    if not f:
        return fail("Pilih berkas foto terlebih dahulu.")
    data = f.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        return fail("Ukuran foto maksimal 2 MB.", 413)
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        ext = "png"
    elif data[:3] == b"\xff\xd8\xff":
        ext = "jpg"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        ext = "webp"
    else:
        return fail("Format foto harus PNG, JPG, atau WEBP.", 415)
    folder = Path(current_app.config["UPLOAD_DIR"]) / "avatars"
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{g.user['id']}-{secrets.token_hex(6)}.{ext}"
    (folder / name).write_bytes(data)
    old = g.user["avatar_path"]
    ex("UPDATE users SET avatar_path=? WHERE id=?", (f"avatars/{name}", g.user["id"]))
    if old:
        (Path(current_app.config["UPLOAD_DIR"]) / old).unlink(missing_ok=True)
    return ok({"avatar": f"/avatar/{g.user['id']}?v={name[-10:]}"})


def avatar_response(uid):
    if not g.user:
        return fail("Belum masuk.", 401)
    if uid != g.user["id"] and not sec.boleh_lihat_semua(g.user):
        return fail("Tidak ada foto.", 404)
    row = q("SELECT avatar_path FROM users WHERE id=?", (uid,), one=True)
    if not row or not row["avatar_path"]:
        return fail("Tidak ada foto.", 404)
    p = Path(current_app.config["UPLOAD_DIR"]) / row["avatar_path"]
    if not p.exists():
        return fail("Tidak ada foto.", 404)
    resp = send_file(p)
    resp.headers["Cache-Control"] = "private, max-age=300"
    return resp


# ------------------------------------------------------------------ kata sandi
@bp.put("/akun/kata-sandi")
@api_auth()
def ganti_sandi():
    d, u = _json(), g.user
    cur, new, conf = d.get("saat_ini") or "", d.get("baru") or "", d.get("konfirmasi") or ""
    errs = []
    if not sec.verify_password(u["password_hash"], cur):
        errs.append(err_item("saat_ini", "Kata Sandi Saat Ini Salah", "Kata sandi lama yang Anda masukkan tidak sesuai."))
    pe = sec.password_errors(new)
    if pe:
        errs.append(err_item("baru", "Format Kata Sandi Baru", " ".join(pe)))
    elif cur and new == cur:
        errs.append(err_item("baru", "Kata Sandi Sama", "Kata sandi baru tidak boleh sama dengan yang lama."))
    if new != conf:
        errs.append(err_item("konfirmasi", "Konfirmasi Tidak Cocok", "Konfirmasi kata sandi baru harus sama persis."))
    if errs:
        sec.audit(u["id"], "ganti_sandi_gagal")
        return fail("Gagal memperbarui kata sandi.", 422, errs)
    ex("UPDATE users SET password_hash=?, password_changed_at=? WHERE id=?",
       (sec.hash_password(new), sec.iso(), u["id"]))
    n = sec.revoke_others(u["id"], g.sid)
    sec.audit(u["id"], "ganti_sandi", f"sesi_lain_dicabut={n}")
    sec.notify(u["id"], "Kata sandi diperbarui", "Kata sandi akun Anda berhasil diubah.")
    return ok({"sesi_dicabut": n})


# ------------------------------------------------------------------ preferensi
@bp.put("/akun/preferensi")
@api_auth()
def preferensi():
    d, u = _json(), g.user
    bagian = d.get("bagian")
    errs, sets = [], {}
    if bagian == "bahasa":
        bahasa, zona, fmt = d.get("bahasa", "id"), d.get("zona_waktu", "WIB"), d.get("format_tanggal", "DD/MM/YYYY")
        if bahasa not in BAHASA:
            errs.append(err_item("bahasa", "Bahasa Tidak Didukung", "Pilih Bahasa Indonesia atau English."))
        if zona not in ZONA:
            errs.append(err_item("zona_waktu", "Zona Waktu Tidak Valid", "Zona waktu harus WIB, WITA, atau WIT."))
        elif u["zona_penugasan"] and zona != u["zona_penugasan"] and u["role"] != "spi":
            errs.append(err_item("zona_waktu", "Zona Waktu Tidak Sesuai",
                        f"Zona waktu yang dipilih tidak cocok dengan wilayah kerja kantor Anda ({u['zona_penugasan']})."))
        if fmt not in FORMAT_TGL:
            errs.append(err_item("format_tanggal", "Format Tanggal Tidak Valid", "Format kustom yang dimasukkan tidak didukung sistem."))
        sets = {"bahasa": bahasa, "zona_waktu": zona, "format_tanggal": fmt}
    elif bagian == "notifikasi":
        sets = {k: 1 if d.get(k) else 0 for k in ("notif_sms_wa", "notif_email", "notif_push")}
        if "bahasa" in d:
            if d["bahasa"] not in BAHASA:
                errs.append(err_item("bahasa", "Bahasa Tidak Didukung", "Pilih Bahasa Indonesia atau English."))
            else:
                sets["bahasa"] = d["bahasa"]
    elif bagian == "privasi":
        if not d.get("consent_pemrosesan"):
            errs.append(err_item("consent_pemrosesan", "Persetujuan Wajib Belum Dicentang",
                        "Anda harus menyetujui pemrosesan data kepegawaian & logistik untuk melanjutkan."))
        sets = {k: 1 if d.get(k) else 0 for k in
                ("consent_pemrosesan", "consent_manifest", "audit_trail_email", "notif_keamanan", "samarkan_nama")
                if k in d or k == "consent_pemrosesan"}
    else:
        return fail("Bagian pengaturan tidak dikenal.")
    if errs:
        return fail("Preferensi belum dapat disimpan.", 422, errs)
    cols = ", ".join(f"{k}=?" for k in sets)
    get_pref(u["id"])
    ex(f"UPDATE preferensi SET {cols}, updated_at=? WHERE user_id=?", (*sets.values(), sec.iso(), u["id"]))
    sec.audit(u["id"], "ubah_preferensi", bagian)
    return ok({"pref": get_pref(u["id"])})


# ------------------------------------------------------------------ sesi perangkat
@bp.get("/akun/sesi")
@api_auth()
def daftar_sesi():
    rows = q("SELECT * FROM sessions WHERE user_id=? AND revoked=0 AND expires_at>? ORDER BY last_seen DESC",
             (g.user["id"], sec.iso()))
    return ok([{"id": r["id"][:12], "perangkat": r["perangkat"], "ip": r["ip"], "last_seen": r["last_seen"],
                "current": r["id"] == g.sid} for r in rows])


@bp.delete("/akun/sesi")
@api_auth()
def putus_sesi():
    n = sec.revoke_others(g.user["id"], g.sid)
    sec.audit(g.user["id"], "putus_sesi_lain", str(n))
    return ok({"dicabut": n})


# ------------------------------------------------------------------ ringkasan & skor keamanan
@bp.get("/akun/ringkasan")
@api_auth()
def ringkasan():
    u = g.user
    umur = max(0, (sec.now() - sec.parse_iso(u["password_changed_at"])).days)
    pref = get_pref(u["id"])
    lain = q("SELECT COUNT(*) c FROM sessions WHERE user_id=? AND revoked=0 AND expires_at>? AND id<>?",
             (u["id"], sec.iso(), g.sid), one=True)["c"]
    rows = [
        ("Usia Kata Sandi", f"{umur} / 90 Hari", umur <= 90, 30 if umur <= 90 else max(0, int(30 - (umur - 90) / 3))),
        ("Email Terverifikasi", "Valid" if u["email_verified"] else "Belum", bool(u["email_verified"]), 20),
        ("Sinkron HRMS (NIPPOS)", "Valid" if u["hrms_terverifikasi"] else "Belum", bool(u["hrms_terverifikasi"]), 20),
        ("Persetujuan & Peringatan Keamanan", "Aktif" if pref["consent_pemrosesan"] and pref["notif_keamanan"] else "Tidak",
         pref["consent_pemrosesan"] and pref["notif_keamanan"], 10),
        ("Sesi Perangkat Lain", f"{lain} aktif", lain <= 2, 10 if lain <= 2 else 0),
        ("Autentikasi 2 Faktor", "Belum tersedia", False, 0),
    ]
    skor = sum(r[3] for r in rows if r[2] or r[0] == "Usia Kata Sandi")
    skor = min(100, skor)
    label = "Sangat Baik" if skor >= 80 else "Baik" if skor >= 60 else "Perlu Ditingkatkan"
    out = {"skor": skor, "label": label, "umur_sandi": umur,
           "rows": [{"nama": r[0], "nilai": r[1], "ok": bool(r[2])} for r in rows]}
    if u["portal"] == "pelapor":
        c = lambda w, a=(): q(f"SELECT COUNT(*) c FROM laporan WHERE pelapor_id=? AND status<>'Draf' {w}", (u["id"], *a), one=True)["c"]
        out["aktivitas"] = {"total": c(""), "selesai": c("AND status='Selesai'"),
                            "investigasi": c("AND status IN ('Investigasi SPI Lapangan','Klarifikasi Satker')")}
    return ok(out)


# ------------------------------------------------------------------ notifikasi
@bp.get("/notifikasi")
@api_auth()
def notifikasi():
    rows = q("SELECT id,judul,isi,tautan,dibaca,waktu FROM notifikasi WHERE user_id=? ORDER BY id DESC LIMIT 20",
             (g.user["id"],))
    unread = q("SELECT COUNT(*) c FROM notifikasi WHERE user_id=? AND dibaca=0", (g.user["id"],), one=True)["c"]
    return ok({"items": [dict(r) for r in rows], "unread": unread})


@bp.post("/notifikasi/baca")
@api_auth()
def notifikasi_baca():
    d = _json()
    if str(d.get("id") or "").isdigit():
        ex("UPDATE notifikasi SET dibaca=1 WHERE id=? AND user_id=?", (int(d["id"]), g.user["id"]))
    else:
        ex("UPDATE notifikasi SET dibaca=1 WHERE user_id=?", (g.user["id"],))
    return ok()
