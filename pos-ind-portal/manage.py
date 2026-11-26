"""Perintah administrasi (tanpa antarmuka web). Contoh:

  python manage.py buat-spi 123456789 "Nama Lengkap" nama@posindonesia.co.id     # akun petugas SPI baru
  python manage.py jadikan-spi 987654322                                        # naikkan akun karyawan yang sudah ada
  python manage.py daftar-pengguna [--portal pelapor|karyawan]
  python manage.py nonaktifkan pelapor 987654321      |  aktifkan karyawan 987654322
  python manage.py atur-sandi karyawan 100000001
  python manage.py hapus-askug [--ya]                 # buang data JASKUG/ASKUG lama (tanpa --ya: hanya menampilkan jumlahnya)
  python manage.py impor-hrms data_pegawai.csv        # kolom: identifier,nama,jabatan,unit_kerja,hub,tingkat_kantor,tmt,level_akses,zona_penugasan
"""
import argparse
import csv
import getpass
import sys

from app import create_app
from app import security as sec
from app.db import get_db


def _sandi(args):
    pw = args.sandi or getpass.getpass("Kata sandi (min. 8, huruf besar+kecil+angka): ")
    salah = sec.password_errors(pw)
    if salah:
        sys.exit("Kata sandi tidak memenuhi syarat: " + " ".join(salah))
    return pw


def _cari(db, portal, ident):
    u = db.execute("SELECT * FROM users WHERE portal=? AND identifier=?", (portal, ident.upper())).fetchone()
    if not u:
        sys.exit(f"Akun {portal}/{ident} tidak ditemukan.")
    return u


def buat_spi(db, a):
    ident, tipe = sec.normalize_identifier(a.nippos)
    if tipe != "karyawan":
        sys.exit("NIPPOS harus 9 digit angka.")
    if not sec.valid_email(a.email.lower()):
        sys.exit("Email tidak valid.")
    if db.execute("SELECT 1 FROM users WHERE portal='karyawan' AND (identifier=? OR email=?)", (ident, a.email.lower())).fetchone():
        sys.exit("NIPPOS atau email sudah terdaftar.")
    now = sec.iso()
    cur = db.execute("""INSERT INTO users(portal,tipe,role,identifier,nama,email,password_hash,jabatan,hrms_terverifikasi,email_verified,
                        password_changed_at,created_at) VALUES('karyawan','karyawan','spi',?,?,?,?,?,0,1,?,?)""",
                     (ident, a.nama, a.email.lower(), sec.hash_password(_sandi(a)), a.jabatan, now, now))
    db.execute("INSERT INTO preferensi(user_id,updated_at) VALUES(?,?)", (cur.lastrowid, now))
    db.commit()
    print(f"Akun SPI dibuat: {ident} ({a.nama}). Masuk lewat /masuk.")


def jadikan_spi(db, a):
    u = _cari(db, "karyawan", a.nippos)
    if u["tipe"] != "karyawan":
        sys.exit("Hanya akun pegawai (bukan mitra) yang dapat dijadikan SPI.")
    db.execute("UPDATE users SET role='spi' WHERE id=?", (u["id"],)); db.commit()
    print(f"{u['nama']} kini berperan SPI.")


def daftar(db, a):
    q, p = "SELECT portal,role,identifier,nama,email,status,last_login_at FROM users", ()
    if a.portal:
        q, p = q + " WHERE portal=?", (a.portal,)
    for r in db.execute(q + " ORDER BY portal, role, identifier", p):
        print(f"{r['portal']:9} {r['role']:9} {r['identifier']:12} {r['status']:9} {r['nama']} <{r['email']}> masuk terakhir: {r['last_login_at'] or '-'}")


def status(db, a, nilai):
    u = _cari(db, a.portal, a.identifier)
    db.execute("UPDATE users SET status=? WHERE id=?", (nilai, u["id"]))
    if nilai == "nonaktif":
        db.execute("UPDATE sessions SET revoked=1 WHERE user_id=?", (u["id"],))
    db.commit()
    print(f"{u['nama']}: {nilai}.")


def atur_sandi(db, a):
    u = _cari(db, a.portal, a.identifier)
    db.execute("UPDATE users SET password_hash=?, password_changed_at=? WHERE id=?", (sec.hash_password(_sandi(a)), sec.iso(), u["id"]))
    db.execute("UPDATE sessions SET revoked=1 WHERE user_id=?", (u["id"],)); db.commit()
    print(f"Kata sandi {u['nama']} diganti; seluruh sesinya diakhiri.")


def impor_hrms(db, a):
    kolom = ["identifier", "nama", "jabatan", "unit_kerja", "hub", "tingkat_kantor", "tmt", "level_akses", "zona_penugasan"]
    n = 0
    with open(a.berkas, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if not sec.RE_NIPPOS.match((row.get("identifier") or "").strip()):
                print("Lewati baris (NIPPOS tidak valid):", row.get("identifier")); continue
            db.execute(f"INSERT OR REPLACE INTO hrms_master({','.join(kolom)}) VALUES({','.join('?' * len(kolom))})",
                       [(row.get(k) or "").strip() or None for k in kolom]); n += 1
    db.commit()
    print(f"{n} baris data kepegawaian diimpor. Aktifkan wajib-terdaftar dengan HRMS_STRICT=1.")


def hapus_askug(db, a):
    from app import purge_askug
    from flask import current_app
    ada = purge_askug.ringkas(db)
    print("Data JASKUG/ASKUG yang masih tersimpan:", ", ".join(f"{k}={v}" for k, v in ada.items()))
    if not any(ada.values()):
        print("Tidak ada data JASKUG/ASKUG. Tidak ada yang perlu dihapus."); return
    if not a.ya:
        print("Belum ada yang dihapus. Penghapusan TIDAK DAPAT dibatalkan (cadangkan folder data/ lebih dulu), lalu jalankan:\n"
              "  python manage.py hapus-askug --ya"); return
    from flask import g
    db.close(); g.pop("db", None)               # sambungan lama ditutup; audit di bawah membuka sambungan baru
    hasil = purge_askug.hapus(current_app.config["DB_PATH"], current_app.config["UPLOAD_DIR"])
    print("Selesai dihapus:", ", ".join(f"{k}={v}" for k, v in hasil.items()))
    sec.audit(None, "admin_hapus_askug", f"{hasil['laporan']} laporan, {hasil['berkas_dihapus']} berkas")


def main():
    ap = argparse.ArgumentParser(description="Administrasi Portal POS IND")
    sp = ap.add_subparsers(dest="cmd", required=True)
    c = sp.add_parser("buat-spi"); c.add_argument("nippos"); c.add_argument("nama"); c.add_argument("email")
    c.add_argument("--jabatan", default="Petugas SPI"); c.add_argument("--sandi")
    c = sp.add_parser("jadikan-spi"); c.add_argument("nippos")
    c = sp.add_parser("daftar-pengguna"); c.add_argument("--portal", choices=["karyawan", "pelapor"])
    for nm in ("nonaktifkan", "aktifkan"):
        c = sp.add_parser(nm); c.add_argument("portal", choices=["karyawan", "pelapor"]); c.add_argument("identifier")
    c = sp.add_parser("atur-sandi"); c.add_argument("portal", choices=["karyawan", "pelapor"]); c.add_argument("identifier"); c.add_argument("--sandi")
    c = sp.add_parser("impor-hrms"); c.add_argument("berkas")
    c = sp.add_parser("hapus-askug"); c.add_argument("--ya", action="store_true", help="benar-benar menghapus (tanpa ini hanya menampilkan jumlah)")
    a = ap.parse_args()
    app = create_app()
    with app.app_context():
        db = get_db()
        {"buat-spi": buat_spi, "jadikan-spi": jadikan_spi, "daftar-pengguna": daftar, "atur-sandi": atur_sandi,
         "impor-hrms": impor_hrms, "hapus-askug": hapus_askug, "nonaktifkan": lambda d, x: status(d, x, "nonaktif"),
         "aktifkan": lambda d, x: status(d, x, "aktif")}[a.cmd](db, a)


if __name__ == "__main__":
    main()
