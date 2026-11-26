"""Data referensi (HRMS, halaman informasi) dan data demo."""
from datetime import timedelta

from . import security as sec

DEMO_PASSWORD = "PosInd2025!"

HRMS = [
    # identifier, nama, jabatan, unit_kerja, hub, tingkat, tmt, level, zona
    ("987654321", "Budi Santoso, S.T.", "Petugas Pengawasan Operasional L1", "Sentral Pengolahan Pos Jakarta 10000",
     "SPP JKT-13400", "SPP", "2018-03-01", "Ops-L2", "WIB"),
    ("987654322", "Ahmad Pratama, S.T.", "Staf Operasional SPP Jakarta Timur", "Sentral Pengolahan Pos Jakarta Timur",
     "SPP JKT-13400", "SPP", "2018-03-01", "Ops-L2", "WIB"),
    ("100000001", "Dewi Anggraini, S.H.", "Auditor Utama SPI", "Satuan Pengawasan Intern - Kantor Pusat",
     "Graha Pos Bandung", "PUSAT", "2015-07-01", "SPI-L4", "WIB"),
    ("981120340", "Siti Nurhaliza", "Kepala Kasir KCP Lembang", "KCP Lembang 40391", "KC Cimahi", "KCP",
     "2019-01-15", "Ops-L1", "WIB"),
    ("990011223", "Yusuf Rahman", "Supervisor Hub Makassar", "SPP Makassar", "Regional IV Makassar", "SPP",
     "2020-06-01", "Ops-L2", "WITA"),
]

INFO = {
    "kebijakan-privasi": ("Kebijakan Privasi",
        "PT Pos Indonesia (Persero) memproses data pribadi pegawai dan mitra sesuai UU No. 27 Tahun 2022 tentang "
        "Pelindungan Data Pribadi.\n\nData yang dikumpulkan: identitas (NIPPOS/ID Mitra, nama, email, telepon), data "
        "penugasan, log akses, dan laporan yang Anda kirim.\n\nTujuan: autentikasi, operasional logistik, "
        "penanganan laporan oleh Satuan Pengawasan Intern (SPI), dan kepatuhan audit.\n\nIdentitas pelapor dijaga "
        "kerahasiaannya dan hanya dapat dilihat oleh tim SPI yang berwenang. Anda dapat meminta koreksi data melalui "
        "Helpdesk SDM (Ext. 14045)."),
    "syarat-ketentuan": ("Syarat & Ketentuan Layanan",
        "Dengan menggunakan portal ini Anda setuju untuk: menggunakan akun hanya untuk keperluan kedinasan; menjaga "
        "kerahasiaan kata sandi; menyampaikan laporan dengan iktikad baik dan sesuai fakta; tidak mengunggah berkas "
        "berbahaya. Penyalahgunaan dapat berakibat penonaktifan akun dan tindakan disipliner."),
    "pusat-bantuan": ("Pusat Bantuan",
        "Kendala login: hubungi Helpdesk IT POS IND ext. 1500161.\nNIPPOS tidak ditemukan: Helpdesk SDM ext. 14045.\n"
        "Hotline Siaga SPI: 0800-1-POSIND.\nEmail: helpdesk.it@posindonesia.co.id\n\nLupa kata sandi? Gunakan tautan "
        "'Lupa Kata Sandi?' pada halaman masuk."),
    "perlindungan-pelapor": ("Perlindungan Pelapor",
        "Berdasarkan Peraturan Direksi No. PER/09/DIRUT/2023 dan ISO 37001:2016, pelapor terlindungi dari tindakan "
        "pembalasan, intimidasi, maupun mutasi yang merugikan. Identitas pelapor hanya dapat dilihat oleh tim inti "
        "auditor SPI. Anda dapat melapor secara anonim melalui opsi pada formulir laporan."),
    "tidak-ditemukan": ("Halaman Tidak Ditemukan", "Halaman yang Anda cari tidak tersedia atau telah dipindahkan."),
}

# kunci: (no, klas, kategori, tipologi, judul, uraian, tingkat_pel, unit_pel, terl, terl_nippos, tingkat_t, unit_t,
#         hari_lalu_kejadian, lokasi, (kosong), awb, plat, rute, deviasi, prioritas, status, tahap, level)
LAPORAN = [
    ("WASUM", "deviasi", "Kerusakan / Kehilangan Koli & Pembobolan Segel Kantong Pos",
     "Kerusakan Segel Pengaman Koli & Deviasi Bobot Muatan Feeder BDG-04",
     "Ditemukan 3 koli kantong kiriman pos terbuka segel dan deviasi timbangan riil defisit -12.4 kg saat unloading feeder di "
     "Docking Pintu 4 Inbound. Pelapor menyaksikan langsung perbedaan nomor fisik seal dengan lembar manifest.",
     "SPP", "Sentral Pengolahan Pos Jakarta 10000", "Sdr. RH & Regu Muat MTR-BDG04", "MTR-FEEDER-BDG04", "MITRA",
     "Divisi Bongkar Muat SPP Bandung", 3, "Docking Pintu 4 Inbound, SPP Bandung", None, "POS99281746210ID",
     "D-8812-POS (Box Tronton 20ft)", "Hub Sentral Jakarta - Sentral Pengolahan Pos Bandung", "3 Koli / -12.4 Kg",
     "Mendesak", "Investigasi SPI Lapangan", 2, "REGIONAL", "Tim SPI Regional III Jawa Barat"),
    ("WASUM", "sop", "Keterlambatan Feeder & Deviasi Rute Armada Truk Pos Tanpa Otorisasi",
     "Deviasi Waktu Tempuh & Verifikasi Integritas Segel Jalur Pantura",
     "Keterlambatan feeder lintas Pantura diverifikasi akibat rob Sayung. Seluruh segel muatan diperiksa utuh bersama tim "
     "audit SPP Semarang dan ditutup dengan Berita Acara Rekonsiliasi Klir.",
     "SPP", "Sentral Pengolahan Pos Jakarta 10000", "Mitra Feeder Pantura", "MTR-JB-120", "MITRA",
     "Vendor Feeder Pantura", 25, "Jalur Pantura km 42", None, "POS77120934410ID", "H-4410-POS", "KCU Semarang - KCU Solo Gladag Feeder Malam",
     "0 Koli", "Normal", "Selesai", 4, "PUSAT", None),
]

LAPORAN_UMUM = [   # laporan dari pelapor lain (terlihat di dashboard karyawan/SPI)
    ("WASUM", "deviasi", "Kerusakan / Kehilangan Koli & Pembobolan Segel Kantong Pos",
     "Segel kantong Pos Kilat Khusus terbuka & selisih timbangan bruto -4.2 kg",
     "Ditemukan 2 koli kantong kiriman Pos Kilat Khusus segel terbuka dan terdapat selisih timbangan bruto -4.2 kg saat "
     "penerimaan dari armada feeder nopol D-8812-POS di dock KCP Lembang.",
     "KCP", "KCP Lembang 40391", "Rian Kurniawan (Driver Feeder)", "978451120", "KC", "KC Cimahi 40500",
     1, "Dock penerimaan KCP Lembang", None, "POS55102938475ID", "D-8812-POS", "Hub Sentral Jakarta - Sentral Pengolahan Pos Bandung",
     "2 Koli / -4.2 Kg", "Mendesak", "Investigasi SPI Lapangan", 2, "KC", "Tim SPI Regional III Jawa Barat"),
    ("WASUM", "sop", "Unmanifested Cargo & Skip Barcode SPP (Barang Gelap / Kargo Tak Teregistrasi)",
     "14 waybill dilewatkan tanpa re-weighing dan unmanifested",
     "Sebanyak 14 waybill kiriman kargo logistik dilewatkan tanpa proses re-weighing dan unmanifested saat dipindahkan ke "
     "truk konsolidasi jalur Pantura.",
     "KCU", "KCU Bandung 40000", "Tim Manifest Outbound Shift Malam", "", "KC", "KC Subang 41200",
     2, "Area konsolidasi KC Subang", None, "POS55102938999ID", "T-1190-POS", "KCU Semarang - KCU Solo Gladag Feeder Malam",
     "14 Waybill", "Normal", "Klarifikasi Satker", 3, "KC", None),
]


def ensure_reference(db):
    for h in HRMS:
        db.execute("INSERT OR IGNORE INTO hrms_master VALUES(?,?,?,?,?,?,?,?,?)", h)
    for slug, (judul, isi) in INFO.items():
        db.execute("INSERT OR IGNORE INTO halaman_info VALUES(?,?,?)", (slug, judul, isi))
    db.commit()


def _user(db, portal, tipe, role, ident, nama, email, tel, jab, unit, hub, tingkat, tmt, lvl, zona, verified=1):
    from werkzeug.security import generate_password_hash
    now = sec.iso()
    cur = db.execute(
        """INSERT INTO users(portal,tipe,role,identifier,nama,email,telepon,password_hash,jabatan,unit_kerja,hub,tingkat_kantor,
           tmt,level_akses,zona_penugasan,email_verified,hrms_terverifikasi,password_changed_at,created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (portal, tipe, role, ident, nama, email, tel, generate_password_hash(DEMO_PASSWORD), jab, unit, hub, tingkat, tmt,
         lvl, zona, verified, 1, sec.iso(sec.now() - timedelta(days=42)), now))
    db.execute("INSERT INTO preferensi(user_id,zona_waktu,updated_at) VALUES(?,?,?)", (cur.lastrowid, zona or "WIB", now))
    return cur.lastrowid


_SEQ = {}


def _insert_laporan(db, row, pelapor_id, seq):
    (klas, kat, tip, judul, uraian, tp, up, tn, tnp, tt, ut, hari, lokasi, _kosong, awb, plat, rute, dev,
     prio, status, tahap, level, invest) = row
    t_kej = sec.now() - timedelta(days=hari, hours=3)
    t_kirim = t_kej + timedelta(hours=11)
    yr = sec.now().year
    seq = _SEQ[klas] = _SEQ.get(klas, 0) + 1          # urutan per klasifikasi
    no = f"LAP-{klas}-{yr}-{seq:04d}"
    ba = f"BA-{klas}/{yr}/{sec.now().month:02d}/{seq:03d}" if status == "Selesai" else None
    cur = db.execute(
        """INSERT INTO laporan(no_tiket,klasifikasi,kategori_masalah,tipologi,judul,uraian,pelapor_id,pelapor_tingkat,pelapor_unit,
           terlapor_nama,terlapor_nippos,terlapor_tingkat,terlapor_unit,waktu_kejadian,lokasi,awb,plat_armada,rute,deviasi,
           prioritas,status,tahap,level_disposisi,investigator,tenggat,no_berita_acara,resolusi,pernyataan,dibuat_pada,
           diperbarui_pada,dikirim_pada,ditutup_pada) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?,?,?)""",
        (no, klas, kat, tip, judul, uraian, pelapor_id, tp, up, tn, tnp, tt, ut, sec.iso(t_kej), lokasi, awb, plat, rute,
         dev, prio, status, tahap, level, invest,
         (sec.now() + timedelta(days=2)).strftime("%Y-%m-%d") if status == "Klarifikasi Satker" else None, ba,
         "Selisih telah direkonsiliasi dan Berita Acara ditandatangani bersama." if status == "Selesai" else None,
         sec.iso(t_kirim), sec.iso(t_kirim), sec.iso(t_kirim),
         sec.iso(t_kirim + timedelta(days=3)) if status == "Selesai" else None))
    lid = cur.lastrowid
    db.execute("INSERT INTO disposisi(laporan_id,aksi,tahap,status,level,unit,catatan,oleh_id,waktu) VALUES(?,?,?,?,?,?,?,?,?)",
               (lid, "registrasi", 1, "Terdaftar", {"KCP": "KCP", "KCU": "KC", "SPP": "KC"}.get(tp, "KC"), up,
                "Laporan dibuat dan bukti digital diunggah ke sistem POS IND.", pelapor_id, sec.iso(t_kirim)))
    if tahap >= 2:
        db.execute("INSERT INTO disposisi(laporan_id,aksi,tahap,status,level,unit,catatan,waktu) VALUES(?,?,?,?,?,?,?,?)",
                   (lid, "ubah_status", 2, "Investigasi SPI Lapangan", "REGIONAL", "SPI Regional III Jawa Barat",
                    "Pemeriksaan rekaman CCTV dan permintaan keterangan kru.", sec.iso(t_kirim + timedelta(hours=20))))
    if tahap >= 3:
        db.execute("INSERT INTO disposisi(laporan_id,aksi,tahap,status,level,unit,catatan,waktu) VALUES(?,?,?,?,?,?,?,?)",
                   (lid, "ubah_status", 3, "Klarifikasi Satker", "KC", ut, "Panggilan klarifikasi kepada Kepala Kantor terkait.",
                    sec.iso(t_kirim + timedelta(days=1, hours=6))))
    if tahap >= 4:
        db.execute("INSERT INTO disposisi(laporan_id,aksi,tahap,status,level,unit,catatan,waktu) VALUES(?,?,?,?,?,?,?,?)",
                   (lid, "ubah_status", 4, "Selesai", "PUSAT", "Kantor Pusat (Graha Pos)",
                    "Laporan ditutup dengan Berita Acara Rekonsiliasi.", sec.iso(t_kirim + timedelta(days=3))))
    return lid


def demo(db):
    spi = _user(db, "karyawan", "karyawan", "spi", "100000001", "Dewi Anggraini, S.H.", "dewi.anggraini@posindonesia.co.id",
                "081200000001", "Auditor Utama SPI", "Satuan Pengawasan Intern - Kantor Pusat", "Graha Pos Bandung",
                "PUSAT", "2015-07-01", "SPI-L4", "WIB")
    _user(db, "karyawan", "karyawan", "karyawan", "987654322", "Ahmad Pratama, S.T.", "ahmad.pratama@posindonesia.co.id",
          "081234567890", "Staf Operasional SPP Jakarta Timur", "Sentral Pengolahan Pos Jakarta Timur", "SPP JKT-13400",
          "SPP", "2018-03-01", "Ops-L2", "WIB")
    _user(db, "karyawan", "mitra", "mitra", "AG-8829104", "Agen Pos Cimahi Mandiri", "agen.cimahi@mitra-pos.co.id",
          "081311112222", "Mitra Agen POS", "Agen POS Cimahi", "Regional III Jabar", "MITRA", "2022-01-10", "Mitra", "WIB")
    budi = _user(db, "pelapor", "pelapor", "pelapor", "987654321", "Budi Santoso, S.T.", "budi.santoso@posindonesia.co.id",
                 "081234567890", "Petugas Pengawasan Operasional L1", "Sentral Pengolahan Pos Jakarta 10000", "SPP JKT-13400",
                 "SPP", "2018-03-01", "Ops-L2", "WIB")
    siti = _user(db, "pelapor", "pelapor", "pelapor", "981120340", "Siti Nurhaliza", "siti.nurhaliza@posindonesia.co.id",
                 "081355550000", "Kepala Kasir", "KCP Lembang 40391", "KC Cimahi", "KCP", "2019-01-15", "Ops-L1", "WIB")
    _SEQ.clear()
    n = 0
    for row in LAPORAN:
        n += 1
        _insert_laporan(db, row, budi, n)
    for row in LAPORAN_UMUM:
        n += 1
        _insert_laporan(db, row, siti, n)
    for k, cnt in _SEQ.items():
        db.execute("INSERT OR REPLACE INTO urutan(kunci,nilai) VALUES(?,?)", (f"tiket:{k}:{sec.now().year}", cnt))
    db.execute("INSERT OR REPLACE INTO urutan(kunci,nilai) VALUES('ba',?)", (n,))
    sec_user = spi
    inv = db.execute("SELECT id FROM laporan WHERE pelapor_id=? AND status='Investigasi SPI Lapangan' ORDER BY id LIMIT 1", (budi,)).fetchone()
    if inv:   # contoh komunikasi: permintaan informasi ke pelapor + catatan internal yang TIDAK terlihat pelapor
        db.execute("INSERT INTO pesan(laporan_id,pengirim_id,peran,jenis,isi,waktu) VALUES(?,?,?,?,?,?)",
                   (inv[0], spi, "spi", "permintaan", "Mohon lampirkan foto segel kantong dan nomor seal yang tertera pada manifest.", sec.iso(sec.now() - timedelta(hours=5))))
        db.execute("INSERT INTO pesan(laporan_id,pengirim_id,peran,jenis,isi,waktu) VALUES(?,?,?,?,?,?)",
                   (inv[0], spi, "spi", "catatan", "Internal: cocokkan dengan rekaman CCTV dock 4 sebelum klarifikasi Satker.", sec.iso(sec.now() - timedelta(hours=4))))
    db.execute("INSERT INTO notifikasi(user_id,judul,isi,tautan,waktu) VALUES(?,?,?,?,?)",
               (budi, "Laporan dalam investigasi", "Tim SPI Regional III mulai memeriksa laporan Anda.", "/pelapor/laporan-saya", sec.iso()))
    db.commit()
