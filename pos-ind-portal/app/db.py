import sqlite3
from pathlib import Path
from flask import g, current_app

SCHEMA = Path(__file__).with_name("schema.sql")


def connect(path):
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["DB_PATH"])
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# Kolom yang ditambahkan setelah rilis awal: (tabel, kolom, definisi). Dijalankan otomatis pada database lama.
MIGRASI = [
    ("disposisi", "publik", "INTEGER NOT NULL DEFAULT 1"),
    ("lampiran", "susulan", "INTEGER NOT NULL DEFAULT 0"),
]


def migrate(conn):
    for tabel, kolom, ddl in MIGRASI:
        ada = {r[1] for r in conn.execute(f"PRAGMA table_info({tabel})")}
        if kolom not in ada:
            conn.execute(f"ALTER TABLE {tabel} ADD COLUMN {kolom} {ddl}")


def init_db(path):
    conn = connect(path)
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    migrate(conn)
    conn.commit()
    conn.close()


def q(sql, args=(), one=False):
    rows = get_db().execute(sql, args).fetchall()
    return (rows[0] if rows else None) if one else rows


def ex(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid


def next_seq(key):
    """Nomor urut atomik (nomor tiket, draf, berita acara)."""
    db = get_db()
    db.execute("BEGIN IMMEDIATE")
    try:
        row = db.execute("SELECT nilai FROM urutan WHERE kunci=?", (key,)).fetchone()
        n = (row["nilai"] if row else 0) + 1
        db.execute("INSERT INTO urutan(kunci,nilai) VALUES(?,?) "
                   "ON CONFLICT(kunci) DO UPDATE SET nilai=excluded.nilai", (key, n))
        db.commit()
        return n
    except Exception:
        db.rollback()
        raise
