PRAGMA foreign_keys = ON;

-- ============ AKUN ============
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  portal TEXT NOT NULL CHECK (portal IN ('karyawan','pelapor')),
  tipe TEXT NOT NULL CHECK (tipe IN ('karyawan','mitra','pelapor')),
  role TEXT NOT NULL DEFAULT 'karyawan' CHECK (role IN ('karyawan','mitra','pelapor','spi')),
  identifier TEXT NOT NULL,              -- NIPPOS (9 digit) atau ID Mitra
  nama TEXT NOT NULL,
  email TEXT NOT NULL,
  telepon TEXT,
  password_hash TEXT NOT NULL,
  jabatan TEXT, unit_kerja TEXT, hub TEXT, tingkat_kantor TEXT,
  tmt TEXT,                              -- tanggal mulai tugas
  level_akses TEXT,
  zona_penugasan TEXT,                   -- WIB/WITA/WIT dari HRMS (NULL = bebas)
  avatar_path TEXT,
  status TEXT NOT NULL DEFAULT 'aktif' CHECK (status IN ('aktif','nonaktif')),
  email_verified INTEGER NOT NULL DEFAULT 0,
  hrms_terverifikasi INTEGER NOT NULL DEFAULT 0,
  password_changed_at TEXT NOT NULL,
  last_login_at TEXT,
  created_at TEXT NOT NULL,
  UNIQUE (portal, identifier),
  UNIQUE (portal, email)
);

CREATE TABLE IF NOT EXISTS preferensi (
  user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  bahasa TEXT NOT NULL DEFAULT 'id',
  zona_waktu TEXT NOT NULL DEFAULT 'WIB',
  format_tanggal TEXT NOT NULL DEFAULT 'DD/MM/YYYY',
  notif_sms_wa INTEGER NOT NULL DEFAULT 1,
  notif_email INTEGER NOT NULL DEFAULT 1,
  notif_push INTEGER NOT NULL DEFAULT 1,
  samarkan_nama INTEGER NOT NULL DEFAULT 0,
  consent_pemrosesan INTEGER NOT NULL DEFAULT 1,
  consent_manifest INTEGER NOT NULL DEFAULT 1,
  audit_trail_email INTEGER NOT NULL DEFAULT 1,
  notif_keamanan INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,                   -- sha256 dari token cookie
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  csrf TEXT NOT NULL,
  ip TEXT, user_agent TEXT, perangkat TEXT,
  created_at TEXT NOT NULL, last_seen TEXT NOT NULL, expires_at TEXT NOT NULL,
  revoked INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

CREATE TABLE IF NOT EXISTS login_attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  identifier TEXT NOT NULL, ip TEXT, berhasil INTEGER NOT NULL, waktu TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attempts ON login_attempts(identifier, waktu);

CREATE TABLE IF NOT EXISTS reset_tokens (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE, expires_at TEXT NOT NULL, used INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS email_outbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tujuan TEXT NOT NULL, subjek TEXT NOT NULL, isi TEXT NOT NULL,
  terkirim INTEGER NOT NULL DEFAULT 0, dibuat TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER, aksi TEXT NOT NULL, detail TEXT, ip TEXT, waktu TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notifikasi (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  judul TEXT NOT NULL, isi TEXT, tautan TEXT,
  dibaca INTEGER NOT NULL DEFAULT 0, waktu TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notif_user ON notifikasi(user_id, dibaca);

-- Data master kepegawaian (simulasi HRMS). Melengkapi profil saat registrasi.
CREATE TABLE IF NOT EXISTS hrms_master (
  identifier TEXT PRIMARY KEY, nama TEXT, jabatan TEXT, unit_kerja TEXT, hub TEXT,
  tingkat_kantor TEXT, tmt TEXT, level_akses TEXT, zona_penugasan TEXT
);

-- ============ LAPORAN ============
CREATE TABLE IF NOT EXISTS laporan (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  no_tiket TEXT UNIQUE,                  -- NULL selama masih draf
  kode_draf TEXT UNIQUE,
  klasifikasi TEXT NOT NULL CHECK (klasifikasi IN ('WASUM')),     -- satu-satunya lingkup pengawasan yang dilayani
  kategori_masalah TEXT NOT NULL DEFAULT 'sop' CHECK (kategori_masalah IN ('deviasi','sop','disiplin')),
  tipologi TEXT,
  judul TEXT,
  uraian TEXT,
  pelapor_id INTEGER NOT NULL REFERENCES users(id),
  anonim INTEGER NOT NULL DEFAULT 0,
  pelapor_tingkat TEXT, pelapor_unit TEXT,
  terlapor_nama TEXT, terlapor_nippos TEXT, terlapor_tingkat TEXT, terlapor_unit TEXT,
  waktu_kejadian TEXT, lokasi TEXT,
  awb TEXT, plat_armada TEXT, rute TEXT, deviasi TEXT,
  prioritas TEXT NOT NULL DEFAULT 'Normal' CHECK (prioritas IN ('Normal','Tinggi','Mendesak')),
  status TEXT NOT NULL DEFAULT 'Draf' CHECK (status IN ('Draf','Terdaftar','Investigasi SPI Lapangan','Klarifikasi Satker','Selesai')),
  tahap INTEGER NOT NULL DEFAULT 0,      -- 0 draf, 1..4 sesuai alur
  level_disposisi TEXT NOT NULL DEFAULT 'KCP' CHECK (level_disposisi IN ('KCP','KC','REGIONAL','PUSAT')),
  investigator TEXT, tenggat TEXT,
  no_berita_acara TEXT, resolusi TEXT,
  pernyataan INTEGER NOT NULL DEFAULT 0,
  dibuat_pada TEXT NOT NULL, diperbarui_pada TEXT NOT NULL,
  dikirim_pada TEXT, ditutup_pada TEXT
);
CREATE INDEX IF NOT EXISTS idx_laporan_pelapor ON laporan(pelapor_id);
CREATE INDEX IF NOT EXISTS idx_laporan_status ON laporan(status);
CREATE INDEX IF NOT EXISTS idx_laporan_waktu ON laporan(waktu_kejadian);

CREATE TABLE IF NOT EXISTS lampiran (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  laporan_id INTEGER REFERENCES laporan(id) ON DELETE CASCADE,   -- NULL = baru diunggah, belum dilekatkan
  pemilik_id INTEGER NOT NULL REFERENCES users(id),
  nama_asli TEXT NOT NULL, path TEXT NOT NULL, ukuran INTEGER NOT NULL,
  ekstensi TEXT NOT NULL, mime TEXT NOT NULL,
  terverifikasi INTEGER NOT NULL DEFAULT 0, dibuat TEXT NOT NULL,
  susulan INTEGER NOT NULL DEFAULT 0           -- 1 = bukti tambahan setelah laporan terkirim
);

CREATE TABLE IF NOT EXISTS disposisi (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  laporan_id INTEGER NOT NULL REFERENCES laporan(id) ON DELETE CASCADE,
  aksi TEXT NOT NULL,                    -- registrasi | verifikasi_bukti | ubah_status | teruskan
  tahap INTEGER, status TEXT, level TEXT, unit TEXT, catatan TEXT,
  oleh_id INTEGER REFERENCES users(id), waktu TEXT NOT NULL,
  publik INTEGER NOT NULL DEFAULT 1            -- 0 = catatan internal SPI (pelapor hanya melihat peristiwanya)
);
CREATE INDEX IF NOT EXISTS idx_disposisi_laporan ON disposisi(laporan_id, waktu);

CREATE TABLE IF NOT EXISTS urutan (
  kunci TEXT PRIMARY KEY, nilai INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS halaman_info (
  slug TEXT PRIMARY KEY, judul TEXT NOT NULL, isi TEXT NOT NULL
);

-- Komunikasi dua arah pelapor <-> SPI pada sebuah laporan (+ catatan internal SPI)
CREATE TABLE IF NOT EXISTS pesan (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  laporan_id INTEGER NOT NULL REFERENCES laporan(id) ON DELETE CASCADE,
  pengirim_id INTEGER NOT NULL REFERENCES users(id),
  peran TEXT NOT NULL CHECK (peran IN ('pelapor','spi')),
  jenis TEXT NOT NULL CHECK (jenis IN ('permintaan','balasan','catatan')),   -- catatan = internal SPI
  isi TEXT NOT NULL, waktu TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pesan_laporan ON pesan(laporan_id, waktu);
