"""Pembersihan data JASKUG/ASKUG lama. Lingkup JASKUG (jasa keuangan & kas) sudah dihapus dari portal; database yang dibuat
sebelumnya mungkin masih menyimpan laporan ASKUG beserta bukti dan percakapannya. Dijalankan SENGAJA lewat
`python manage.py hapus-askug` (tidak otomatis, karena penghapusan tidak dapat dibatalkan)."""
import sqlite3
from pathlib import Path

POLA_TIKET = "%LAP-ASKUG-%"


def ringkas(conn):
    """Jumlah data ASKUG yang masih tersimpan."""
    n = lambda sql, *a: conn.execute(sql, a).fetchone()[0]
    return {
        "laporan": n("SELECT COUNT(*) FROM laporan WHERE klasifikasi='ASKUG'"),
        "lampiran": n("SELECT COUNT(*) FROM lampiran WHERE laporan_id IN (SELECT id FROM laporan WHERE klasifikasi='ASKUG')"),
        "pesan": n("SELECT COUNT(*) FROM pesan WHERE laporan_id IN (SELECT id FROM laporan WHERE klasifikasi='ASKUG')"),
        "notifikasi": n("SELECT COUNT(*) FROM notifikasi WHERE tautan LIKE ? OR judul LIKE ? OR isi LIKE ?", POLA_TIKET, POLA_TIKET, POLA_TIKET),
        "email": n("SELECT COUNT(*) FROM email_outbox WHERE subjek LIKE ? OR isi LIKE ?", POLA_TIKET, POLA_TIKET),
    }


def hapus(db_path, upload_dir):
    """Hapus semua laporan ASKUG + turunannya (disposisi, lampiran, pesan), berkas buktinya di disk, notifikasi & email
    outbox yang menyebut tiketnya, lalu VACUUM agar isi yang dihapus tidak tertinggal di file database."""
    conn = sqlite3.connect(db_path, timeout=15, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    hasil = ringkas(conn)
    ids = [r[0] for r in conn.execute("SELECT id FROM laporan WHERE klasifikasi='ASKUG'")]
    paths = [r[0] for i in ids for r in conn.execute("SELECT path FROM lampiran WHERE laporan_id=?", (i,))]
    conn.execute("BEGIN")
    try:
        conn.execute("DELETE FROM notifikasi WHERE tautan LIKE ? OR judul LIKE ? OR isi LIKE ?", (POLA_TIKET,) * 3)
        conn.execute("DELETE FROM email_outbox WHERE subjek LIKE ? OR isi LIKE ?", (POLA_TIKET,) * 2)
        conn.execute("DELETE FROM urutan WHERE kunci LIKE 'tiket:ASKUG:%'")
        conn.execute("DELETE FROM laporan WHERE klasifikasi='ASKUG'")          # disposisi, lampiran, pesan ikut terhapus (CASCADE)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    berkas = 0
    for p in paths:
        f = Path(upload_dir) / p
        if f.exists():
            f.unlink(); berkas += 1
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.execute("VACUUM")
    conn.close()
    hasil["berkas_dihapus"] = berkas
    return hasil
