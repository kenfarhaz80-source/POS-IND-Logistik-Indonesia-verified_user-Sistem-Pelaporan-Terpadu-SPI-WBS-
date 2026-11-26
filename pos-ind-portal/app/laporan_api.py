import csv
import io
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Blueprint, Response, current_app, g, jsonify, request, send_file

from . import security as sec
from .db import get_db, next_seq, q
from .security import api_auth, err_item, fail, ok

bp = Blueprint("laporan_api", __name__, url_prefix="/api")

TINGKAT = ("KCP", "KC", "KCU", "SPP", "REGIONAL", "PUSAT", "MITRA")
TINGKAT_NAMA = {"KCP": "Kantor Cabang Pembantu", "KC": "Kantor Cabang", "KCU": "Kantor Cabang Utama",
                "SPP": "Sentral Pengolahan Pos", "REGIONAL": "Kantor Regional", "PUSAT": "Kantor Pusat",
                "MITRA": "Mitra Eksternal / Vendor"}
STATUS = ("Terdaftar", "Investigasi SPI Lapangan", "Klarifikasi Satker", "Selesai")
STATUS_TAHAP = {"Draf": 0, "Terdaftar": 1, "Investigasi SPI Lapangan": 2, "Klarifikasi Satker": 3, "Selesai": 4}
STATUS_LABEL = {"Draf": "Draf", "Terdaftar": "Menunggu Verifikasi Satker",
                "Investigasi SPI Lapangan": "Investigasi SPI Lapangan",
                "Klarifikasi Satker": "Klarifikasi Satker KC/KCU", "Selesai": "Selesai / Rekonsiliasi Klir"}
TAHAP_NAMA = {1: ("Laporan Terdaftar & Valid", "Laporan diregistrasi dan menunggu verifikasi kelayakan Satker."),
              2: ("Investigasi SPI Lapangan", "Pemeriksaan bukti, rekaman, dan permintaan keterangan di lapangan."),
              3: ("Penyusunan BAP & Klarifikasi Satker", "Klarifikasi unit terkait dan penyusunan Berita Acara Pemeriksaan."),
              4: ("Rekomendasi & Penutupan", "Rekomendasi Direksi, pemulihan kerugian, dan penutupan tiket.")}
LEVELS = ("KCP", "KC", "REGIONAL", "PUSAT")
LEVEL_OF = {"KCP": "KCP", "KC": "KC", "KCU": "KC", "SPP": "KC", "MITRA": "KC", "REGIONAL": "REGIONAL", "PUSAT": "PUSAT"}
KATEGORI = {"deviasi": "Deviasi Muatan Koli", "sop": "Pelanggaran SOP Manifest", "disiplin": "Disiplin Kerja & Fraud"}
KLASIFIKASI = "WASUM"       # satu-satunya lingkup pengawasan yang dilayani portal ini
PRIORITAS_ORDER = {"Mendesak": 0, "Tinggi": 1, "Normal": 2}
ZONA_OFFSET = {"WIB": 7, "WITA": 8, "WIT": 9}
SLA_HARI_KERJA = 5          # batas penyelesaian sejak laporan dikirim (hari kerja) — dipakai di semua layar & statistik
MAX_TOTAL_LAMPIRAN = 20

ALLOWED_FILES = {"mp4": "video/mp4", "m4a": "audio/mp4", "pdf": "application/pdf", "jpg": "image/jpeg",
                 "jpeg": "image/jpeg", "png": "image/png", "csv": "text/csv",
                 "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
INLINE_OK = {"mp4", "m4a", "pdf", "jpg", "jpeg", "png"}
MAX_FILE = 50 * 1024 * 1024
MAX_FILES_PER_REPORT = 10


def _json():
    return request.get_json(silent=True) or {}


def _spi():
    return g.user["role"] == "spi"


# ------------------------------------------------------------------ util
def kategori_dari_tipologi(tip):
    t = (tip or "").lower()
    if "disiplin" in t:
        return "disiplin"
    if "koli" in t or "segel" in t or "timbang" in t:
        return "deviasi"
    return "sop"


def hitung_prioritas(kategori):
    return "Tinggi" if kategori in ("deviasi", "disiplin") else "Normal"


def parse_waktu(raw, zona="WIB"):
    """Terima ISO (dengan/ tanpa offset). Kembalikan string UTC atau None."""
    try:
        dt = datetime.fromisoformat((raw or "").strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone(timedelta(hours=ZONA_OFFSET.get(zona, 7))))
    return sec.iso(dt.astimezone(timezone.utc))


def tambah_hari_kerja(dt, n):
    while n > 0:
        dt += timedelta(days=1)
        if dt.weekday() < 5:
            n -= 1
    return dt


def batas_sla(dikirim_iso):
    return tambah_hari_kerja(sec.parse_iso(dikirim_iso), SLA_HARI_KERJA).replace(hour=23, minute=59, second=59)


def selisih_hari_kerja(dari, ke):
    """Jumlah hari kerja dari tanggal `dari` ke `ke` (positif bila ke > dari, negatif bila sebaliknya)."""
    a, b, tanda = dari.date(), ke.date(), 1
    if b < a:
        a, b, tanda = b, a, -1
    n, cur = 0, a
    while cur < b:
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            n += 1
    return tanda * n


def lewat_sla(r):
    """True bila laporan melewati batas SLA (belum selesai & sudah lewat, atau selesai tetapi terlambat)."""
    if not r["dikirim_pada"]:
        return False
    akhir = sec.parse_iso(r["ditutup_pada"]) if r["ditutup_pada"] else sec.now()
    return akhir > batas_sla(r["dikirim_pada"])


def mask_name(n):
    """Pihak terlapor belum tentu bersalah: nama hanya terlihat oleh pelapor & SPI."""
    parts = re.findall(r"[A-Za-z]+", n or "")
    return (" ".join(p[0].upper() + "." for p in parts[:3]) + " (disamarkan)") if parts else "-"


def clip(v, n):
    v = (v or "").strip() if isinstance(v, str) else ""
    return v[:n]


def tiket_untuk(klas):
    """Nomor tiket unik per klasifikasi & tahun; melewati nomor yang sudah terpakai."""
    yr = sec.now().year
    while True:
        no = f"LAP-{klas}-{yr}-{next_seq(f'tiket:{klas}:{yr}'):04d}"
        if not q("SELECT 1 FROM laporan WHERE no_tiket=?", (no,), one=True):
            return no


# ------------------------------------------------------------------ pemetaan & serialisasi
def get_row(ref):
    return q("SELECT * FROM laporan WHERE no_tiket=? OR kode_draf=?", (ref, ref), one=True)


def can_view(r, viewer):
    if r["status"] == "Draf":
        return r["pelapor_id"] == viewer["id"]
    if r["pelapor_id"] == viewer["id"]:
        return True
    return sec.boleh_lihat_semua(viewer)


def lampiran_list(lid):
    return [{"id": a["id"], "nama": a["nama_asli"], "ukuran": a["ukuran"], "ekstensi": a["ekstensi"],
             "mime": a["mime"], "terverifikasi": bool(a["terverifikasi"]), "susulan": bool(a["susulan"]),
             "dibuat": a["dibuat"], "url": f"/berkas/{a['id']}"}
            for a in q("SELECT * FROM lampiran WHERE laporan_id=? ORDER BY id", (lid,))]


def hierarki(r, disp):
    cur = LEVELS.index(r["level_disposisi"])
    selesai = r["status"] == "Selesai"
    awal = LEVEL_OF.get(r["pelapor_tingkat"], "KCP")
    terl = LEVEL_OF.get(r["terlapor_tingkat"], "KC")
    out = []
    for i, lv in enumerate(LEVELS):
        e = next((x for x in disp if x["level"] == lv and x["aksi"] != "registrasi"), None) or \
            next((x for x in disp if x["level"] == lv), None)
        unit = e["unit"] if e and e["unit"] else None
        if not unit:
            unit = (r["pelapor_unit"] if lv == awal else r["terlapor_unit"] if lv == terl
                    else {"REGIONAL": "SPI Regional", "PUSAT": "Kantor Pusat (Graha Pos)"}.get(lv, TINGKAT_NAMA.get(lv)))
        peran = " (Pelapor Awal)" if lv == awal else " (Unit Terlapor)" if lv == terl else ""
        out.append({"level": lv, "unit": (unit or lv) + peran,
                    "state": "done" if (i < cur or selesai) else "aktif" if i == cur else "menunggu",
                    "catatan": e["catatan"] if e else None, "waktu": e["waktu"] if e else None})
    return out


GENERIK = {"registrasi": "Laporan diregistrasi.", "verifikasi_bukti": "Bukti laporan diverifikasi SPI.",
           "ubah_status": "Status penanganan laporan diperbarui.", "teruskan": "Disposisi laporan diteruskan ke level berikutnya.",
           "bukti_susulan": "Bukti tambahan diunggah pelapor."}
LANGKAH_BERIKUT = {1: "SPI memverifikasi kelayakan laporan dan bukti yang dilampirkan.",
                   2: "SPI memeriksa bukti, rekaman, dan meminta keterangan di lapangan.",
                   3: "Satker terkait memberi klarifikasi; SPI menyusun Berita Acara Pemeriksaan (BAP).",
                   4: "Laporan telah ditutup dan berkasnya diarsipkan."}


def daftar_pesan(r, viewer):
    staf = sec.boleh_lihat_semua(viewer)
    rows = q("SELECT p.*, u.nama FROM pesan p JOIN users u ON u.id=p.pengirim_id WHERE laporan_id=? ORDER BY p.waktu, p.id", (r["id"],))
    out = []
    for p in rows:
        if p["jenis"] == "catatan" and not staf:
            continue                                   # catatan internal tidak pernah sampai ke pelapor
        out.append({"id": p["id"], "peran": p["peran"], "jenis": p["jenis"], "isi": p["isi"], "waktu": p["waktu"],
                    "nama": (p["nama"] if staf or p["peran"] == "pelapor" else "Tim SPI"),
                    "saya": p["pengirim_id"] == viewer["id"]})
    return out


def hitung_progres(r, disp, pesan):
    """Ringkasan proses & progres sebuah laporan (dipakai panel 'Cuplikan Tiket Aktif' pelapor maupun SPI)."""
    tahap = r["tahap"]
    out = {"persen": tahap * 25, "tahap": tahap, "total_tahap": 4, "status": r["status"], "status_label": STATUS_LABEL[r["status"]],
           "tahap_nama": TAHAP_NAMA.get(tahap, ("Draf", ""))[0], "selesai": r["status"] == "Selesai"}
    if r["status"] == "Draf":
        return out
    batas = batas_sla(r["dikirim_pada"])
    akhir = sec.parse_iso(r["ditutup_pada"]) if r["ditutup_pada"] else sec.now()
    sisa = selisih_hari_kerja(akhir, batas)          # sisa HARI KERJA sampai batas SLA (negatif = terlambat)
    terlambat = akhir > batas
    out.update({
        "umur_hari": (akhir.date() - sec.parse_iso(r["dikirim_pada"]).date()).days,   # hari kalender sejak dikirim
        "batas_sla": batas.strftime("%Y-%m-%d"), "sisa_hari": sisa, "terlambat": terlambat,
        "sla": ("selesai_terlambat" if terlambat else "selesai_tepat") if out["selesai"]
               else "terlambat" if terlambat else "mendekati" if sisa <= 1 else "aman",
        "langkah_berikut": LANGKAH_BERIKUT[tahap],
        "penanggung_jawab": r["investigator"] or ("Belum ditugaskan" if not out["selesai"] else "-"),
        "tenggat_klarifikasi": r["tenggat"], "diperbarui_pada": r["diperbarui_pada"], "level": r["level_disposisi"],
    })
    terakhir_req = max((p["id"] for p in pesan if p["jenis"] == "permintaan"), default=0)
    terakhir_bal = max((p["id"] for p in pesan if p["jenis"] == "balasan"), default=0)
    out["permintaan_terbuka"] = terakhir_req > terakhir_bal and not out["selesai"]
    out["menunggu"] = (None if out["selesai"] else "Pelapor" if out["permintaan_terbuka"] else
                       {1: "SPI (verifikasi awal)", 2: "SPI (pemeriksaan lapangan)", 3: "Satker terkait (klarifikasi)"}.get(tahap))
    out["aktivitas"] = [{"aksi": x["aksi"], "catatan": x["catatan"], "waktu": x["waktu"], "internal": x["internal"]}
                        for x in disp[-3:]][::-1]
    return out


def serialize(r, viewer, detail=False):
    own = r["pelapor_id"] == viewer["id"]
    show = own or sec.boleh_lihat_semua(viewer)
    pel = q("SELECT nama, identifier FROM users WHERE id=?", (r["pelapor_id"],), one=True)
    inis = lambda n: "".join(w[0] for w in re.findall(r"[A-Za-z]+", n)[:2]).upper() or "?"
    d = {
        "id": r["id"], "ref": r["no_tiket"] or r["kode_draf"], "no_tiket": r["no_tiket"], "kode_draf": r["kode_draf"],
        "klasifikasi": r["klasifikasi"], "kategori_masalah": r["kategori_masalah"],
        "kategori_label": KATEGORI.get(r["kategori_masalah"]), "tipologi": r["tipologi"],
        "judul": r["judul"], "uraian": r["uraian"], "prioritas": r["prioritas"],
        "status": r["status"], "status_label": STATUS_LABEL[r["status"]], "tahap": r["tahap"],
        "level_disposisi": r["level_disposisi"], "investigator": r["investigator"], "tenggat": r["tenggat"],
        "anonim": bool(r["anonim"]), "milik_saya": own,
        "pelapor": {"nama": pel["nama"] if show else "Pelapor Terlindungi",
                    "nippos": pel["identifier"] if show else "••••••••",
                    "inisial": inis(pel["nama"]) if show else "••", "terlihat": show,
                    "tingkat": r["pelapor_tingkat"], "tingkat_nama": TINGKAT_NAMA.get(r["pelapor_tingkat"]),
                    "unit": r["pelapor_unit"]},
        "terlapor": {"nama": r["terlapor_nama"] if show else mask_name(r["terlapor_nama"]),
                     "nippos": r["terlapor_nippos"] if show else None, "tingkat": r["terlapor_tingkat"],
                     "tingkat_nama": TINGKAT_NAMA.get(r["terlapor_tingkat"]), "unit": r["terlapor_unit"],
                     "inisial": inis(r["terlapor_nama"] or "") if show else "••"},
        "waktu_kejadian": r["waktu_kejadian"], "lokasi": r["lokasi"],
        "awb": r["awb"], "plat_armada": r["plat_armada"], "rute": r["rute"], "deviasi": r["deviasi"],
        "dikirim_pada": r["dikirim_pada"], "dibuat_pada": r["dibuat_pada"], "ditutup_pada": r["ditutup_pada"],
        "no_berita_acara": r["no_berita_acara"], "resolusi": r["resolusi"],
        "jumlah_lampiran": q("SELECT COUNT(*) c FROM lampiran WHERE laporan_id=?", (r["id"],), one=True)["c"],
        "bukti_boleh_dilihat": show,
    }
    atts = lampiran_list(r["id"])
    d["lampiran"] = atts if show else []
    if detail:
        disp = [dict(x) for x in q("SELECT d.*, u.nama AS oleh FROM disposisi d LEFT JOIN users u ON u.id=d.oleh_id "
                                   "WHERE laporan_id=? ORDER BY d.waktu, d.id", (r["id"],))]
        staf = sec.boleh_lihat_semua(viewer)
        for x in disp:
            if not staf:                       # pelapor/lainnya: tanpa nama petugas, catatan internal disembunyikan
                x["oleh"] = None
                if not x["publik"]:
                    x["catatan"] = GENERIK.get(x["aksi"], "Laporan diperbarui oleh SPI.")
            x["internal"] = not x["publik"]
        pesan = daftar_pesan(r, viewer)
        d["pesan"] = pesan
        d["progres"] = hitung_progres(r, disp, pesan)
        d["disposisi"] = disp
        d["hierarki"] = hierarki(r, disp)
        d["langkah"] = []
        for n in (1, 2, 3, 4):
            t = next((x["waktu"] for x in disp if (x["tahap"] or 0) >= n), None) if r["tahap"] >= n else None
            state = "done" if (r["tahap"] > n or (r["tahap"] == n and r["status"] == "Selesai")) \
                else "aktif" if r["tahap"] == n else "menunggu"
            d["langkah"].append({"tahap": n, "judul": TAHAP_NAMA[n][0], "deskripsi": TAHAP_NAMA[n][1],
                                 "state": state, "waktu": t})
        if r["dikirim_pada"]:
            d["estimasi_selesai"] = tambah_hari_kerja(sec.parse_iso(r["dikirim_pada"]), 5).strftime("%Y-%m-%d")
        d["boleh_disposisi"] = sec.boleh_lihat_semua(viewer) and r["status"] not in ("Draf", "Selesai")
        d["boleh_ubah"] = own and r["status"] == "Draf"
        d["boleh_pesan"] = r["status"] not in ("Draf", "Selesai") and (own or staf)
        d["boleh_susulan"] = own and r["status"] not in ("Draf", "Selesai")
        d["peran_lihat"] = "spi" if staf else "pelapor"
        nxt = next((lv for lv in LEVELS if LEVELS.index(lv) > LEVELS.index(r["level_disposisi"])), None)
        d["level_berikut"] = nxt
    return d


# ------------------------------------------------------------------ lampiran
def _sig_ok(ext, head):
    if ext == "pdf":
        return head.startswith(b"%PDF")
    if ext == "png":
        return head.startswith(b"\x89PNG")
    if ext in ("jpg", "jpeg"):
        return head.startswith(b"\xff\xd8\xff")
    if ext in ("mp4", "m4a"):
        return head[4:8] == b"ftyp"
    if ext == "xlsx":
        return head.startswith(b"PK")
    if ext == "csv":
        return b"\x00" not in head
    return False


def _terima_berkas(f, laporan_id=None, susulan=0):
    """Validasi (ekstensi, ukuran, tanda tangan isi) lalu simpan. Mengembalikan (info, None) atau (None, respons_galat)."""
    if not f or not f.filename:
        return None, fail("Pilih berkas bukti terlebih dahulu.")
    nama = Path(f.filename).name[:150]
    ext = nama.rsplit(".", 1)[-1].lower() if "." in nama else ""
    if ext not in ALLOWED_FILES:
        return None, fail(f"{nama}: format tidak didukung. Gunakan mp4, m4a, pdf, jpg, png, csv, atau xlsx.", 415)
    folder = Path(current_app.config["UPLOAD_DIR"]) / "lampiran" / str(g.user["id"])
    folder.mkdir(parents=True, exist_ok=True)
    stored = f"{secrets.token_hex(12)}.{ext}"
    path = folder / stored
    size, head = 0, b""
    try:
        with open(path, "wb") as out:
            while chunk := f.stream.read(1024 * 1024):
                if not head:
                    head = chunk[:16]
                size += len(chunk)
                if size > MAX_FILE:
                    raise ValueError("terlalu besar")
                out.write(chunk)
    except ValueError:
        path.unlink(missing_ok=True)
        return None, fail(f"{nama}: ukuran melebihi batas 50 MB.", 413)
    if size == 0 or not _sig_ok(ext, head):
        path.unlink(missing_ok=True)
        return None, fail(f"{nama}: isi berkas tidak sesuai dengan ekstensinya atau kosong.", 415)
    db = get_db()
    cur = db.execute("INSERT INTO lampiran(laporan_id,pemilik_id,nama_asli,path,ukuran,ekstensi,mime,dibuat,susulan) VALUES(?,?,?,?,?,?,?,?,?)",
                     (laporan_id, g.user["id"], nama, f"lampiran/{g.user['id']}/{stored}", size, ext, ALLOWED_FILES[ext], sec.iso(), susulan))
    db.commit()
    return {"id": cur.lastrowid, "nama": nama, "ukuran": size, "ekstensi": ext, "url": f"/berkas/{cur.lastrowid}"}, None


@bp.post("/lampiran")
@api_auth(portal="pelapor")
def unggah():
    """Unggah bukti untuk laporan yang SEDANG DISUSUN (belum dikirim). Berkas menunggu sampai dilekatkan saat simpan/kirim."""
    pending = q("SELECT COUNT(*) c FROM lampiran WHERE pemilik_id=? AND laporan_id IS NULL", (g.user["id"],), one=True)["c"]
    if pending >= MAX_FILES_PER_REPORT * 2:
        return fail("Terlalu banyak berkas belum terkirim. Hapus beberapa terlebih dahulu.", 429)
    info, err = _terima_berkas(request.files.get("berkas"))
    return err if err else (ok(info), 201)


@bp.post("/laporan/<ref>/lampiran")
@api_auth(portal="pelapor")
def bukti_susulan(ref):
    """Bukti TAMBAHAN pada laporan yang sudah terkirim (mis. menjawab permintaan SPI). Bukti awal tetap tidak dapat dihapus."""
    r = get_row(ref)
    if not r or r["pelapor_id"] != g.user["id"] or r["status"] == "Draf":
        return fail("Laporan tidak ditemukan.", 404)
    if r["status"] == "Selesai":
        return fail("Laporan sudah ditutup; bukti tambahan tidak dapat ditambahkan.", 409)
    files = request.files.getlist("berkas")
    if not files:
        return fail("Pilih berkas bukti terlebih dahulu.")
    ada = q("SELECT COUNT(*) c FROM lampiran WHERE laporan_id=?", (r["id"],), one=True)["c"]
    if ada + len(files) > MAX_TOTAL_LAMPIRAN:
        return fail(f"Satu laporan maksimal {MAX_TOTAL_LAMPIRAN} berkas (sudah ada {ada}).", 409)
    nama = []
    for f in files:
        info, err = _terima_berkas(f, r["id"], 1)
        if err:
            if nama:   # sebagian sudah tersimpan: beri tahu agar pelapor tidak mengunggah ulang
                body = err[0].get_json(); body["error"] += f" (berkas sebelumnya yang sudah tersimpan: {', '.join(nama)})"
                return jsonify(body), err[1]
            return err
        nama.append(info["nama"])
    now = sec.iso()
    db = get_db()
    db.execute("INSERT INTO disposisi(laporan_id,aksi,tahap,status,level,catatan,oleh_id,waktu,publik) VALUES(?,?,?,?,?,?,?,?,1)",
               (r["id"], "bukti_susulan", r["tahap"], r["status"], r["level_disposisi"],
                f"Pelapor mengunggah {len(nama)} bukti tambahan: {', '.join(nama)}.", g.user["id"], now))
    db.execute("UPDATE laporan SET diperbarui_pada=? WHERE id=?", (now, r["id"]))
    db.commit()
    sec.audit(g.user["id"], "bukti_susulan", f"{r['no_tiket']} +{len(nama)}")
    for sp in q("SELECT id FROM users WHERE role='spi' AND status='aktif'"):
        sec.notify(sp["id"], f"Bukti tambahan pada {r['no_tiket']}", f"Pelapor mengunggah {len(nama)} berkas baru.", f"/dashboard?tiket={r['no_tiket']}")
    return ok(serialize(get_row(r["no_tiket"]), g.user, True)), 201


@bp.delete("/lampiran/<int:aid>")
@api_auth(portal="pelapor")
def hapus_lampiran(aid):
    a = q("SELECT l.*, r.status AS rstatus FROM lampiran l LEFT JOIN laporan r ON r.id=l.laporan_id WHERE l.id=?",
          (aid,), one=True)
    if not a or a["pemilik_id"] != g.user["id"]:
        return fail("Berkas tidak ditemukan.", 404)
    if a["laporan_id"] is not None and a["rstatus"] != "Draf":
        return fail("Bukti pada laporan yang sudah terkirim tidak dapat dihapus.", 409)
    (Path(current_app.config["UPLOAD_DIR"]) / a["path"]).unlink(missing_ok=True)
    db = get_db()
    db.execute("DELETE FROM lampiran WHERE id=?", (aid,))
    db.commit()
    return ok()


def kirim_berkas(aid):
    """Dipanggil dari route /berkas/<id> (halaman)."""
    a = q("SELECT l.*, r.pelapor_id AS rp, r.status AS rstatus FROM lampiran l LEFT JOIN laporan r ON r.id=l.laporan_id WHERE l.id=?",
          (aid,), one=True)
    if not a or not g.user:
        return fail("Berkas tidak ditemukan.", 404)
    spi_ok = sec.boleh_lihat_semua(g.user) and a["laporan_id"] is not None and a["rstatus"] != "Draf"
    if not (a["pemilik_id"] == g.user["id"] or spi_ok):
        return fail("Anda tidak berhak mengakses bukti ini.", 403)
    p = Path(current_app.config["UPLOAD_DIR"]) / a["path"]
    if not p.exists():
        return fail("Berkas tidak ditemukan di penyimpanan.", 404)
    inline = a["ekstensi"] in INLINE_OK and not request.args.get("unduh")
    resp = send_file(p, mimetype=a["mime"], as_attachment=not inline, download_name=a["nama_asli"], conditional=True)
    resp.headers["Content-Security-Policy"] = "sandbox; default-src 'none'; img-src 'self'; media-src 'self'"
    resp.headers["Cache-Control"] = "private, no-store"
    return resp


# ------------------------------------------------------------------ pengisian & validasi
def kumpulkan_field(d):
    zona = q("SELECT zona_waktu FROM preferensi WHERE user_id=?", (g.user["id"],), one=True)
    zona = zona["zona_waktu"] if zona else "WIB"
    f = {
        "klasifikasi": KLASIFIKASI,
        "tipologi": clip(d.get("tipologi"), 200),
        "uraian": clip(d.get("uraian"), 2000),
        "anonim": 1 if d.get("anonim") else 0,
        "pelapor_tingkat": d.get("pelapor_tingkat") if d.get("pelapor_tingkat") in TINGKAT else None,
        "pelapor_unit": clip(d.get("pelapor_unit"), 150),
        "terlapor_nama": clip(d.get("terlapor_nama"), 150),
        "terlapor_nippos": clip(d.get("terlapor_nippos"), 40),
        "terlapor_tingkat": d.get("terlapor_tingkat") if d.get("terlapor_tingkat") in TINGKAT else None,
        "terlapor_unit": clip(d.get("terlapor_unit"), 200),
        "waktu_kejadian": parse_waktu(d.get("waktu_kejadian"), zona),
        "lokasi": clip(d.get("lokasi"), 200),
        "awb": clip(d.get("awb"), 120).upper(), "plat_armada": clip(d.get("plat_armada"), 80),
        "rute": clip(d.get("rute"), 200), "deviasi": clip(d.get("deviasi"), 150),
        "pernyataan": 1 if d.get("pernyataan") else 0,
    }
    return f


def validasi_final(f):
    e = []
    if not f["pelapor_tingkat"] or not f["pelapor_unit"]:
        e.append(err_item("pelapor_unit", "Satuan Kerja Pelapor", "Tingkat kantor dan nama unit kerja pelapor wajib diisi."))
    if not f["terlapor_nama"]:
        e.append(err_item("terlapor_nama", "Pihak Terlapor", "Nama lengkap / inisial pihak terlapor wajib diisi."))
    if not f["terlapor_tingkat"]:
        e.append(err_item("terlapor_tingkat", "Tingkat Terlapor", "Tingkat / hub pihak terlapor wajib dipilih."))
    if not f["waktu_kejadian"]:
        e.append(err_item("waktu_kejadian", "Waktu Kejadian", "Waktu kejadian wajib diisi dengan tanggal & jam yang valid."))
    else:
        t = sec.parse_iso(f["waktu_kejadian"])
        if t > sec.now() + timedelta(minutes=10):
            e.append(err_item("waktu_kejadian", "Waktu Kejadian", "Waktu kejadian tidak boleh di masa depan."))
        elif t < sec.now() - timedelta(days=365 * 5):
            e.append(err_item("waktu_kejadian", "Waktu Kejadian", "Waktu kejadian terlalu lama (maksimal 5 tahun)."))
    if not f["lokasi"]:
        e.append(err_item("lokasi", "Lokasi Kejadian", "Lokasi spesifik kejadian wajib diisi."))
    if len(f["uraian"]) < 30:
        e.append(err_item("uraian", "Kronologi Kejadian", "Uraikan kronologi minimal 30 karakter agar dapat ditindaklanjuti."))
    if not f["tipologi"]:
        e.append(err_item("tipologi", "Tipologi Sub-Kasus", "Pilih tipologi sub-kasus WASUM."))
    toks = [t.strip() for t in f["awb"].split(",") if t.strip()]
    if not toks or any(not re.fullmatch(r"[A-Z0-9][A-Z0-9\- ]{4,24}", t) for t in toks):
        e.append(err_item("awb", "Nomor Koli / Barcode Connote (AWB)",
                          "Wajib diisi dengan kode connote yang valid (pisahkan dengan koma bila lebih dari satu)."))
    if not f["plat_armada"]:
        e.append(err_item("plat_armada", "Nomor Plat Armada / ID Feeder Truk", "Dibutuhkan untuk penelusuran GPS fleet & manifest docking."))
    if not f["rute"]:
        e.append(err_item("rute", "Jalur Logistik / Rute", "Pilih jalur logistik / rute trayek."))
    if not f["deviasi"]:
        e.append(err_item("deviasi", "Estimasi Deviasi", "Isi estimasi deviasi bobot / jumlah koli terdampak."))
    if not f["pernyataan"]:
        e.append(err_item("pernyataan", "Pernyataan Integritas & Kebenaran Data",
                          "Kotak centang konfirmasi pertanggungjawaban hukum belum dicentang."))
    return e


def buat_judul(f):
    base = f["tipologi"] or f["uraian"]
    base = re.sub(r"\s+", " ", base or "").strip()
    return (base[:117] + "…") if len(base) > 120 else (base or "Laporan tanpa judul")


def _simpan(f, draf_id, final):
    """Insert/update laporan, kembalikan (row, dibuat_baru)."""
    db = get_db()
    now = sec.iso()
    kat = kategori_dari_tipologi(f["tipologi"])
    cols = dict(f, kategori_masalah=kat, judul=buat_judul(f) if f["uraian"] or f["tipologi"] else "Draf laporan",
                prioritas=hitung_prioritas(kat), diperbarui_pada=now,
                level_disposisi=LEVEL_OF.get(f["pelapor_tingkat"], "KCP"))
    if draf_id:
        r = q("SELECT * FROM laporan WHERE id=? AND pelapor_id=? AND status='Draf'", (draf_id, g.user["id"]), one=True)
        if not r:
            return None, False
        sets = ", ".join(f"{k}=?" for k in cols)
        db.execute(f"UPDATE laporan SET {sets} WHERE id=?", (*cols.values(), draf_id))
        lid = draf_id
    else:
        cols.update(pelapor_id=g.user["id"], dibuat_pada=now,
                    kode_draf=f"DRF-{sec.now().year}-{next_seq('draf'):04d}")
        names = ", ".join(cols)
        cur = db.execute(f"INSERT INTO laporan({names}) VALUES({','.join('?' * len(cols))})", tuple(cols.values()))
        lid = cur.lastrowid
    db.commit()
    return q("SELECT * FROM laporan WHERE id=?", (lid,), one=True), not draf_id


def _lekatkan(lid, ids):
    db = get_db()
    ids = [int(i) for i in ids if str(i).isdigit()][:MAX_FILES_PER_REPORT]
    for i in ids:
        db.execute("UPDATE lampiran SET laporan_id=? WHERE id=? AND pemilik_id=? "
                   "AND (laporan_id IS NULL OR laporan_id=?)", (lid, i, g.user["id"], lid))
    db.commit()


@bp.post("/laporan/draf")
@api_auth(portal="pelapor")
def simpan_draf():
    d = _json()
    f = kumpulkan_field(d)
    r, _ = _simpan(f, d.get("draf_id"), False)
    if not r:
        return fail("Draf tidak ditemukan.", 404)
    _lekatkan(r["id"], d.get("lampiran_ids") or [])
    sec.audit(g.user["id"], "simpan_draf", r["kode_draf"])
    return ok({"id": r["id"], "kode_draf": r["kode_draf"], "disimpan": sec.iso()})


@bp.get("/laporan/draf/<int:lid>")
@api_auth(portal="pelapor")
def ambil_draf(lid):
    r = q("SELECT * FROM laporan WHERE id=? AND pelapor_id=? AND status='Draf'", (lid, g.user["id"]), one=True)
    if not r:
        return fail("Draf tidak ditemukan.", 404)
    return ok(serialize(r, g.user, True))


@bp.delete("/laporan/draf/<int:lid>")
@api_auth(portal="pelapor")
def hapus_draf(lid):
    r = q("SELECT * FROM laporan WHERE id=? AND pelapor_id=? AND status='Draf'", (lid, g.user["id"]), one=True)
    if not r:
        return fail("Draf tidak ditemukan.", 404)
    for a in q("SELECT path FROM lampiran WHERE laporan_id=?", (lid,)):
        (Path(current_app.config["UPLOAD_DIR"]) / a["path"]).unlink(missing_ok=True)
    db = get_db()
    db.execute("DELETE FROM laporan WHERE id=?", (lid,))
    db.commit()
    return ok()


@bp.post("/laporan")
@api_auth(portal="pelapor")
def kirim_laporan():
    d = _json()
    f = kumpulkan_field(d)
    errs = validasi_final(f)
    if errs:
        return fail("Formulir laporan belum dapat diproses.", 422, errs,
                    kelengkapan=_kelengkapan(f))
    r, _ = _simpan(f, d.get("draf_id"), True)
    if not r:
        return fail("Draf tidak ditemukan.", 404)
    db, now = get_db(), sec.iso()
    tiket = tiket_untuk(f["klasifikasi"])
    db.execute("UPDATE laporan SET no_tiket=?, kode_draf=NULL, status='Terdaftar', tahap=1, dikirim_pada=?, "
               "tenggat=? WHERE id=?", (tiket, now, (sec.now() + timedelta(days=1)).strftime("%Y-%m-%d"), r["id"]))
    db.execute("INSERT INTO disposisi(laporan_id,aksi,tahap,status,level,unit,catatan,oleh_id,waktu) "
               "VALUES(?,?,?,?,?,?,?,?,?)", (r["id"], "registrasi", 1, "Terdaftar", LEVEL_OF.get(f["pelapor_tingkat"], "KCP"),
               f["pelapor_unit"], "Laporan dibuat dan bukti digital diunggah ke sistem POS IND.", g.user["id"], now))
    db.commit()
    _lekatkan(r["id"], d.get("lampiran_ids") or [])
    sec.audit(g.user["id"], "kirim_laporan", tiket)
    sec.notify_user(g.user["id"], f"Laporan {tiket} terkirim", "Laporan Anda sudah diterima SPI dan menunggu verifikasi (maks. 1x24 jam).",
               f"/pelapor/laporan-saya?tiket={tiket}")
    for s in q("SELECT id FROM users WHERE role='spi' AND status='aktif'"):
        sec.notify(s["id"], f"Laporan baru {tiket}", f"{f['klasifikasi']} • prioritas {r['prioritas']}", f"/dashboard?tiket={tiket}")
    r = get_row(tiket)
    nama = g.user["nama"]
    return ok({"tiket": tiket, "klasifikasi": f["klasifikasi"], "kategori_label": KATEGORI.get(r["kategori_masalah"], "Lainnya"),
               "tipologi": r["tipologi"], "awb": r["awb"], "plat_armada": r["plat_armada"], "waktu": now,
               "pelapor": "Pelapor Anonim Terverifikasi (identitas dikelola SPI)" if f["anonim"] else f"{nama} (NIPPOS: {g.user['identifier']})",
               "status_label": STATUS_LABEL["Terdaftar"], "prioritas": r["prioritas"]}), 201


def _kelengkapan(f):
    wajib = ["pelapor_unit", "terlapor_nama", "waktu_kejadian", "lokasi", "uraian", "pernyataan"]
    wajib += ["tipologi", "awb", "plat_armada", "rute", "deviasi"]
    isi = sum(1 for k in wajib if f.get(k))
    return {"persen": round(100 * isi / len(wajib)), "kurang": len(wajib) - isi}


# ------------------------------------------------------------------ daftar & statistik
def _like(s):
    return "%" + s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def build_filter(args, scope):
    """scope: 'saya' (milik pengguna, termasuk draf) atau 'semua' (tidak termasuk draf)."""
    w, p = [], []
    if scope == "saya":
        w.append("l.pelapor_id=?")
        p.append(g.user["id"])
    else:
        w.append("l.status<>'Draf'")
        if args.get("milik") == "1":
            w.append("l.pelapor_id=?")
            p.append(g.user["id"])
    if args.get("q"):
        s = _like(args["q"].strip()[:80])
        cond = ["l.no_tiket LIKE ? ESCAPE '\\'", "l.kode_draf LIKE ? ESCAPE '\\'", "l.judul LIKE ? ESCAPE '\\'",
                "l.uraian LIKE ? ESCAPE '\\'", "l.awb LIKE ? ESCAPE '\\'", "l.plat_armada LIKE ? ESCAPE '\\'",
                "l.pelapor_unit LIKE ? ESCAPE '\\'", "l.terlapor_unit LIKE ? ESCAPE '\\'"]
        p += [s] * len(cond)
        if scope == "saya" or _spi():       # identitas pelapor & terlapor hanya dapat dicari bila memang terlihat
            cond += ["u.nama LIKE ? ESCAPE '\\'", "u.identifier LIKE ? ESCAPE '\\'",
                     "l.terlapor_nama LIKE ? ESCAPE '\\'", "l.terlapor_nippos LIKE ? ESCAPE '\\'"]
            p += [s] * 4
        w.append("(" + " OR ".join(cond) + ")")
    if args.get("status") in STATUS + ("Draf",):
        w.append("l.status=?"); p.append(args["status"])
    if args.get("kategori") in KATEGORI:
        w.append("l.kategori_masalah=?"); p.append(args["kategori"])
    tl = [t for t in (args.get("tingkat") or "").upper().split(",") if t in TINGKAT]
    if tl:
        ph = ",".join("?" * len(tl))
        w.append(f"(l.pelapor_tingkat IN ({ph}) OR l.terlapor_tingkat IN ({ph}))"); p += tl + tl
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.get("dari") or ""):
        w.append("l.waktu_kejadian>=?"); p.append(args["dari"] + "T00:00:00Z")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.get("sampai") or ""):
        w.append("l.waktu_kejadian<=?"); p.append(args["sampai"] + "T23:59:59Z")
    return " AND ".join(w), p


def _order(urut):
    return {"terlama": "l.waktu_kejadian ASC",
            "prioritas": "CASE l.prioritas WHEN 'Mendesak' THEN 0 WHEN 'Tinggi' THEN 1 ELSE 2 END, l.waktu_kejadian DESC",
            }.get(urut, "COALESCE(l.waktu_kejadian,l.dibuat_pada) DESC")


def _daftar(scope):
    a = request.args
    where, params = build_filter(a, scope)
    page = max(1, int(a.get("page", 1) or 1)) if str(a.get("page", "1")).isdigit() else 1
    per = min(50, max(1, int(a.get("per_page", 10)))) if str(a.get("per_page", "10")).isdigit() else 10
    base = f"FROM laporan l JOIN users u ON u.id=l.pelapor_id WHERE {where}"
    total = q(f"SELECT COUNT(*) c {base}", params, one=True)["c"]
    rows = q(f"SELECT l.* {base} ORDER BY {_order(a.get('urut'))} LIMIT ? OFFSET ?", (*params, per, (page - 1) * per))
    return ok({"items": [serialize(r, g.user) for r in rows], "total": total, "page": page, "per_page": per,
               "halaman": max(1, -(-total // per))})


@bp.get("/laporan/saya")
@api_auth(portal="pelapor")
def laporan_saya():
    return _daftar("saya")


@bp.get("/laporan")
@api_auth(portal="karyawan", roles=list(sec.ROLES_LIHAT_SEMUA))
def laporan_semua():
    return _daftar("semua")


def stat_saya(uid):
    c = lambda w, a=(): q(f"SELECT COUNT(*) c FROM laporan WHERE pelapor_id=? {w}", (uid, *a), one=True)["c"]
    return {"total": c("AND status<>'Draf'"), "draf": c("AND status='Draf'"),
            "berjalan": c("AND status NOT IN ('Draf','Selesai')"),
            "investigasi": c("AND status='Investigasi SPI Lapangan'"),
            "klarifikasi": c("AND status='Klarifikasi Satker'"), "selesai": c("AND status='Selesai'"),
            "terdekat_tenggat": (q("SELECT no_tiket, tenggat FROM laporan WHERE pelapor_id=? AND status='Klarifikasi Satker' "
                                   "AND tenggat IS NOT NULL ORDER BY tenggat LIMIT 1", (uid,), one=True) or None)}


@bp.get("/statistik")
@api_auth()
def statistik():
    if not sec.boleh_lihat_semua(g.user):
        if g.user["portal"] != "pelapor":
            return fail("Statistik laporan hanya tersedia untuk SPI dan pelapor.", 403)
        s = stat_saya(g.user["id"])
        if s["terdekat_tenggat"]:
            s["terdekat_tenggat"] = dict(s["terdekat_tenggat"])
        return ok(s)
    c = lambda w="", a=(): q(f"SELECT COUNT(*) c FROM laporan WHERE status<>'Draf' {w}", a, one=True)["c"]
    total = c()
    pekan = c("AND dikirim_pada>=?", (sec.iso(sec.now() - timedelta(days=7)),))
    per_t = {t: c("AND pelapor_tingkat=?", (t,)) for t in ("KCP", "KC", "KCU")}
    per_t["LAINNYA"] = total - sum(per_t.values())          # SPP, Regional, Pusat, Mitra, dst.
    terverif = c("AND (status<>'Terdaftar' OR id IN (SELECT laporan_id FROM lampiran WHERE terverifikasi=1))")
    invest = c("AND status='Investigasi SPI Lapangan'")
    tinggi = c("AND status='Investigasi SPI Lapangan' AND prioritas IN ('Tinggi','Mendesak')")
    avg = q("SELECT AVG(julianday(t.w)-julianday(l.dikirim_pada)) a FROM laporan l JOIN "
            "(SELECT laporan_id, MIN(waktu) w FROM disposisi WHERE aksi<>'registrasi' GROUP BY laporan_id) t "
            "ON t.laporan_id=l.id", one=True)["a"]
    semua = q("SELECT dikirim_pada, ditutup_pada FROM laporan WHERE status<>'Draf'")
    lewat = sum(1 for x in semua if lewat_sla(x))                 # aturan SLA yang sama dengan panel progres
    lewat_tenggat = c("AND status='Klarifikasi Satker' AND tenggat IS NOT NULL AND tenggat<?", (sec.now().strftime("%Y-%m-%d"),))
    menunggu_pelapor = q("SELECT COUNT(*) c FROM laporan l WHERE l.status NOT IN ('Draf','Selesai') AND "
                         "COALESCE((SELECT MAX(id) FROM pesan WHERE laporan_id=l.id AND jenis='permintaan'),0) > "
                         "COALESCE((SELECT MAX(id) FROM pesan WHERE laporan_id=l.id AND jenis='balasan'),0)", one=True)["c"]
    klar = c("AND status='Klarifikasi Satker'")
    unit_aktif = q("SELECT COUNT(DISTINCT terlapor_unit) c FROM laporan WHERE status='Klarifikasi Satker'", one=True)["c"]
    return ok({"total": total, "berjalan": total - c("AND status='Selesai'"), "pekan_ini": pekan, "per_tingkat": per_t,
               "persen_terverifikasi": round(100 * terverif / total) if total else 0,
               "investigasi": invest, "investigasi_prioritas_tinggi": tinggi,
               "durasi_rata": round(avg, 1) if avg is not None else None,
               "sla": round(100 * (total - lewat) / total, 1) if total else 100.0,
               "klarifikasi": klar, "unit_aktif": unit_aktif, "lewat_tenggat": lewat_tenggat, "menunggu_pelapor": menunggu_pelapor,
               "selesai": c("AND status='Selesai'"), "persen_selesai": round(100 * c("AND status='Selesai'") / total) if total else 0})


@bp.get("/laporan/<ref>")
@api_auth()
def detail(ref):
    r = get_row(ref)
    if not r or not can_view(r, g.user):
        return fail("Laporan tidak ditemukan.", 404)
    return ok(serialize(r, g.user, True))


# ------------------------------------------------------------------ disposisi (SPI)
@bp.post("/laporan/<ref>/disposisi")
@api_auth(roles=["spi"])
def disposisi(ref):
    r = get_row(ref)
    if not r or r["status"] == "Draf":
        return fail("Laporan tidak ditemukan.", 404)
    if r["status"] == "Selesai":
        return fail("Laporan sudah ditutup (Selesai) dan tidak dapat diubah lagi.", 409)
    d = _json()
    aksi = d.get("aksi")
    catatan = clip(d.get("catatan"), 1000)
    unit = clip(d.get("unit"), 150)
    db, now = get_db(), sec.iso()
    upd, entry = {}, {"tahap": r["tahap"], "status": r["status"], "level": r["level_disposisi"]}

    if d.get("investigator"):
        upd["investigator"] = clip(d["investigator"], 120)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d.get("tenggat") or ""):
        upd["tenggat"] = d["tenggat"]
    if d.get("prioritas") in PRIORITAS_ORDER:
        upd["prioritas"] = d["prioritas"]

    if aksi == "verifikasi_bukti":
        n = db.execute("UPDATE lampiran SET terverifikasi=1 WHERE laporan_id=?", (r["id"],)).rowcount
        if n == 0:
            return fail("Laporan ini tidak memiliki bukti digital untuk diverifikasi.", 409)
        catatan = catatan or f"{n} berkas bukti lapangan diverifikasi oleh SPI."
        if r["status"] == "Terdaftar":
            entry.update(status="Investigasi SPI Lapangan", tahap=2)
            upd.update(status="Investigasi SPI Lapangan", tahap=2)
    elif aksi == "ubah_status":
        st = d.get("status")
        if st not in STATUS:
            return fail("Status tujuan tidak valid.", 422)
        if STATUS_TAHAP[st] < r["tahap"]:
            return fail("Status tidak dapat dikembalikan ke tahap sebelumnya.", 409)
        if st == "Selesai" and r["tahap"] < 2:
            return fail("Laporan harus melalui verifikasi dan investigasi SPI sebelum ditutup.", 409)
        if st == "Selesai":
            if len(catatan) < 10:
                return fail("Keterangan resolusi wajib diisi (minimal 10 karakter) untuk menutup laporan.", 422,
                            [err_item("catatan", "Keterangan Resolusi", "Jelaskan hasil penyelesaian / rekonsiliasi.")])
            if not r["no_berita_acara"]:
                upd["no_berita_acara"] = f"BA-{r['klasifikasi']}/{sec.now().year}/{sec.now().month:02d}/{next_seq('ba'):03d}"
            upd.update(resolusi=catatan, ditutup_pada=now)
        if st == "Klarifikasi Satker" and "tenggat" not in upd and not r["tenggat"]:
            upd["tenggat"] = (sec.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        entry.update(status=st, tahap=STATUS_TAHAP[st])
        upd.update(status=st, tahap=STATUS_TAHAP[st])
        catatan = catatan or (f"Status diubah menjadi {STATUS_LABEL[st]}." if st != r["status"] else "Data penanganan diperbarui.")
    elif aksi == "teruskan":
        lv = d.get("level") if d.get("level") in LEVELS else None
        cur = LEVELS.index(r["level_disposisi"])
        lv = lv or (LEVELS[cur + 1] if cur + 1 < len(LEVELS) else None)
        if not lv or LEVELS.index(lv) <= cur:
            return fail("Disposisi sudah berada pada level tertinggi / level tujuan tidak valid.", 409)
        entry["level"] = lv
        upd["level_disposisi"] = lv
        catatan = catatan or f"Disposisi diteruskan ke level {lv}."
    else:
        return fail("Aksi disposisi tidak dikenal.", 422)

    if upd:
        sets = ", ".join(f"{k}=?" for k in upd)
        db.execute(f"UPDATE laporan SET {sets}, diperbarui_pada=? WHERE id=?", (*upd.values(), now, r["id"]))
    publik = 0 if d.get("tampilkan_pelapor") is False else 1
    if aksi == "ubah_status" and upd.get("status") == "Selesai":
        publik = 1                       # resolusi akhir selalu diberitahukan kepada pelapor
    db.execute("INSERT INTO disposisi(laporan_id,aksi,tahap,status,level,unit,catatan,oleh_id,waktu,publik) VALUES(?,?,?,?,?,?,?,?,?,?)",
               (r["id"], aksi, entry["tahap"], entry["status"], entry["level"], unit or None, catatan, g.user["id"], now, publik))
    db.commit()
    sec.audit(g.user["id"], f"disposisi_{aksi}", r["no_tiket"])
    sec.notify_user(r["pelapor_id"], f"Pembaruan laporan {r['no_tiket']}", catatan if publik else GENERIK.get(aksi, "Laporan Anda diperbarui."),
                    f"/pelapor/laporan-saya?tiket={r['no_tiket']}")
    return ok(serialize(get_row(r["no_tiket"]), g.user, True))


# ------------------------------------------------------------------ pesan pelapor <-> SPI
@bp.post("/laporan/<ref>/pesan")
@api_auth()
def kirim_pesan(ref):
    """Pelapor membalas/menambah keterangan; SPI meminta informasi tambahan ke pelapor atau menulis catatan INTERNAL."""
    r = get_row(ref)
    if not r or not can_view(r, g.user) or r["status"] == "Draf":
        return fail("Laporan tidak ditemukan.", 404)
    if r["status"] == "Selesai":
        return fail("Laporan sudah ditutup; tidak dapat menerima pesan baru.", 409)
    d = _json()
    isi = (d.get("isi") or "").strip()
    if len(isi) < 3 or len(isi) > 2000:
        return fail("Isi pesan wajib 3–2000 karakter.", 422, [err_item("isi", "Isi Pesan", "Tuliskan pesan minimal 3 karakter (maks. 2000).")])
    staf = sec.boleh_lihat_semua(g.user)
    if staf:
        jenis = "catatan" if d.get("jenis") == "catatan" else "permintaan"
        peran = "spi"
    elif r["pelapor_id"] == g.user["id"]:
        jenis, peran = "balasan", "pelapor"
    else:
        return fail("Anda tidak memiliki hak akses untuk tindakan ini.", 403)
    now = sec.iso()
    db = get_db()
    cur = db.execute("INSERT INTO pesan(laporan_id,pengirim_id,peran,jenis,isi,waktu) VALUES(?,?,?,?,?,?)",
                     (r["id"], g.user["id"], peran, jenis, isi, now))
    if jenis != "catatan":
        db.execute("UPDATE laporan SET diperbarui_pada=? WHERE id=?", (now, r["id"]))
    db.commit()
    sec.audit(g.user["id"], f"pesan_{jenis}", f"{r['no_tiket']}#{cur.lastrowid}")
    if jenis == "permintaan":
        sec.notify_user(r["pelapor_id"], f"SPI meminta informasi tambahan — {r['no_tiket']}", isi[:200],
                        f"/pelapor/laporan-saya?tiket={r['no_tiket']}")
    elif jenis == "balasan":
        for sp in q("SELECT id FROM users WHERE role='spi' AND status='aktif'"):
            sec.notify(sp["id"], f"Balasan pelapor — {r['no_tiket']}", isi[:200], f"/dashboard?tiket={r['no_tiket']}")
    return ok(serialize(get_row(r["no_tiket"]), g.user, True)), 201


# ------------------------------------------------------------------ ekspor CSV
def _csv_safe(v):
    v = "" if v is None else str(v)
    return "'" + v if v[:1] in ("=", "+", "-", "@", "\t", "\r") else v


@bp.get("/laporan-ekspor.csv")
@api_auth()
def ekspor():
    if g.user["portal"] != "pelapor" and not sec.boleh_lihat_semua(g.user):
        return fail("Anda tidak memiliki hak akses untuk tindakan ini.", 403)
    scope = "saya" if (g.user["portal"] == "pelapor" or request.args.get("lingkup") == "saya") else "semua"
    where, params = build_filter(request.args, scope)
    rows = q(f"SELECT l.* FROM laporan l JOIN users u ON u.id=l.pelapor_id WHERE {where} "
             f"ORDER BY {_order(request.args.get('urut'))} LIMIT 5000", params)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["No Tiket", "Klasifikasi", "Kategori", "Status", "Prioritas", "Waktu Kejadian (UTC)", "Waktu Lapor (UTC)",
                "Pelapor", "NIPPOS Pelapor", "Tingkat Pelapor", "Unit Pelapor", "Terlapor", "Tingkat Terlapor",
                "Unit Terlapor", "AWB", "Plat Armada", "Lokasi", "Uraian"])
    for r in rows:
        s = serialize(r, g.user)
        w.writerow([_csv_safe(x) for x in [
            r["no_tiket"] or r["kode_draf"], r["klasifikasi"], s["kategori_label"], r["status"], r["prioritas"],
            r["waktu_kejadian"], r["dikirim_pada"], s["pelapor"]["nama"], s["pelapor"]["nippos"], r["pelapor_tingkat"],
            r["pelapor_unit"], s["terlapor"]["nama"], r["terlapor_tingkat"], r["terlapor_unit"],
            r["awb"], r["plat_armada"], r["lokasi"], r["uraian"]]])
    sec.audit(g.user["id"], "ekspor_csv", f"{len(rows)} baris")
    fn = f"laporan-pos-ind-{sec.now().strftime('%Y%m%d-%H%M')}.csv"
    return Response("\ufeff" + buf.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{fn}"'})


# ------------------------------------------------------------------ pelacakan publik
@bp.get("/lacak/<ref>")
def lacak(ref):
    r = q("SELECT * FROM laporan WHERE no_tiket=?", (ref.strip().upper().lstrip("#"),), one=True)
    if not r:
        return fail("Nomor tiket tidak ditemukan. Periksa kembali penulisan nomor tiket Anda.", 404)
    disp = [dict(x) for x in q("SELECT * FROM disposisi WHERE laporan_id=? ORDER BY waktu,id", (r["id"],))]
    langkah = []
    for n in (1, 2, 3, 4):
        state = "done" if (r["tahap"] > n or (r["tahap"] == n and r["status"] == "Selesai")) else "aktif" if r["tahap"] == n else "menunggu"
        t = next((x["waktu"] for x in disp if (x["tahap"] or 0) >= n), None) if r["tahap"] >= n else None
        langkah.append({"tahap": n, "judul": TAHAP_NAMA[n][0], "state": state, "waktu": t})
    return ok({"no_tiket": r["no_tiket"], "klasifikasi": r["klasifikasi"], "status": r["status"],
               "status_label": STATUS_LABEL[r["status"]], "dikirim_pada": r["dikirim_pada"],
               "diperbarui_pada": r["diperbarui_pada"], "langkah": langkah})
