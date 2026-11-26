"""Pembersihan data JASKUG/ASKUG lama pada database yang dibuat sebelum lingkup itu dihapus."""
import os, sqlite3, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAHASIA = "SALDO-KAS-RAHASIA-4.500.000"


def _db_lama(d):
    """Bangun database ber-skema LAMA (CHECK masih mengizinkan ASKUG/cod + kolom nominal), lalu isi data uji."""
    sql = (ROOT / "app" / "schema.sql").read_text(encoding="utf-8")
    sql = sql.replace("CHECK (klasifikasi IN ('WASUM'))", "CHECK (klasifikasi IN ('ASKUG','WASUM'))")
    sql = sql.replace("CHECK (kategori_masalah IN ('deviasi','sop','disiplin'))", "CHECK (kategori_masalah IN ('deviasi','sop','cod','disiplin'))")
    sql = sql.replace("  waktu_kejadian TEXT, lokasi TEXT,\n", "  waktu_kejadian TEXT, lokasi TEXT,\n  nominal INTEGER,\n")
    assert "nominal INTEGER" in sql
    f = Path(d) / "pos_ind.db"
    c = sqlite3.connect(f); c.execute("PRAGMA foreign_keys=ON"); c.executescript(sql)
    now = "2026-10-01T00:00:00Z"
    c.execute("INSERT INTO users(id,portal,tipe,role,identifier,nama,email,password_hash,password_changed_at,created_at) "
              "VALUES(1,'pelapor','pelapor','pelapor','987654321','Budi','budi@posindonesia.co.id','x',?,?)", (now, now))
    for i, (klas, kat, no) in enumerate([("ASKUG", "cod", "LAP-ASKUG-2026-0001"), ("WASUM", "sop", "LAP-WASUM-2026-0001")], 1):
        c.execute("INSERT INTO laporan(id,no_tiket,klasifikasi,kategori_masalah,judul,uraian,pelapor_id,nominal,status,tahap,dibuat_pada,diperbarui_pada) "
                  "VALUES(?,?,?,?,?,?,1,?,'Terdaftar',1,?,?)", (i, no, klas, kat, "J" + no, RAHASIA if klas == "ASKUG" else "uraian wasum", 4500000 if klas == "ASKUG" else None, now, now))
        rel = f"lampiran/1/{klas}.pdf"
        (Path(d) / "uploads" / "lampiran" / "1").mkdir(parents=True, exist_ok=True)
        (Path(d) / "uploads" / rel).write_bytes(b"%PDF-1.4 " + klas.encode())
        c.execute("INSERT INTO lampiran(laporan_id,pemilik_id,nama_asli,path,ukuran,ekstensi,mime,dibuat) VALUES(?,1,'a.pdf',?,10,'pdf','application/pdf',?)", (i, rel, now))
        c.execute("INSERT INTO disposisi(laporan_id,aksi,tahap,status,catatan,waktu) VALUES(?,'registrasi',1,'Terdaftar',?,?)", (i, RAHASIA if klas == "ASKUG" else "ok", now))
        c.execute("INSERT INTO pesan(laporan_id,pengirim_id,peran,jenis,isi,waktu) VALUES(?,1,'pelapor','balasan',?,?)", (i, RAHASIA if klas == "ASKUG" else "ok", now))
        c.execute("INSERT INTO notifikasi(user_id,judul,isi,tautan,waktu) VALUES(1,?,?,?,?)", (f"Laporan {no} terkirim", "x", f"/pelapor/laporan-saya?tiket={no}", now))
        c.execute("INSERT INTO email_outbox(tujuan,subjek,isi,dibuat) VALUES('budi@posindonesia.co.id',?,?,?)", (f"Konfirmasi {no}", RAHASIA if klas == "ASKUG" else "ok", now))
    c.execute("INSERT INTO urutan(kunci,nilai) VALUES('tiket:ASKUG:2026',1),('tiket:WASUM:2026',1)")
    c.commit(); c.close()
    return f


def _manage(d, *args):
    env = {**os.environ, "DATA_DIR": d, "SEED_DEMO": "0"}
    return subprocess.run([sys.executable, "manage.py", *args], cwd=ROOT, env=env, capture_output=True, text=True)


def test_hapus_askug_lama():
    d = tempfile.mkdtemp(); f = _db_lama(d)
    # tanpa --ya: hanya melaporkan jumlahnya, tidak ada yang terhapus
    r = _manage(d, "hapus-askug"); assert r.returncode == 0, r.stderr
    assert "laporan=1" in r.stdout and "--ya" in r.stdout
    c = sqlite3.connect(f); assert c.execute("SELECT COUNT(*) FROM laporan WHERE klasifikasi='ASKUG'").fetchone()[0] == 1; c.close()
    # dengan --ya: seluruh data ASKUG hilang, data WASUM utuh
    r = _manage(d, "hapus-askug", "--ya"); assert r.returncode == 0, r.stderr
    c = sqlite3.connect(f)
    n = lambda s: c.execute(s).fetchone()[0]
    assert n("SELECT COUNT(*) FROM laporan WHERE klasifikasi='ASKUG'") == 0
    assert n("SELECT COUNT(*) FROM laporan") == 1 and n("SELECT COUNT(*) FROM lampiran") == 1       # WASUM utuh
    assert n("SELECT COUNT(*) FROM disposisi WHERE laporan_id=1") == 0 and n("SELECT COUNT(*) FROM pesan WHERE laporan_id=1") == 0
    assert n("SELECT COUNT(*) FROM notifikasi") == 1 and n("SELECT COUNT(*) FROM email_outbox") == 1
    assert n("SELECT COUNT(*) FROM urutan WHERE kunci LIKE 'tiket:ASKUG:%'") == 0
    assert n("SELECT COUNT(*) FROM audit_log WHERE aksi='admin_hapus_askug'") == 1                    # tercatat di audit
    c.close()
    up = Path(d) / "uploads" / "lampiran" / "1"
    assert not (up / "ASKUG.pdf").exists() and (up / "WASUM.pdf").exists()                            # berkas bukti ikut terhapus
    # isi yang dihapus tidak tertinggal secara fisik di file database
    for berkas in Path(d).glob("pos_ind.db*"):
        assert RAHASIA.encode() not in berkas.read_bytes(), berkas.name
    # idempoten
    assert "Tidak ada data JASKUG/ASKUG" in _manage(d, "hapus-askug", "--ya").stdout


def test_aplikasi_tetap_jalan_bila_data_lama_masih_ada():
    d = tempfile.mkdtemp(); _db_lama(d)
    lama = {k: os.environ.get(k) for k in ("DATA_DIR", "SEED_DEMO")}
    os.environ["DATA_DIR"], os.environ["SEED_DEMO"] = d, "0"
    try:
        from app import create_app
        app = create_app({"TESTING": True})
        from app import purge_askug
        from app.db import connect
        assert purge_askug.ringkas(connect(str(Path(d) / "pos_ind.db")))["laporan"] == 1
        # aplikasi tetap bisa jalan & tidak error bila data lama masih ada (halaman login/health)
        assert app.test_client().get("/health").status_code == 200
    finally:
        for k, v in lama.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
