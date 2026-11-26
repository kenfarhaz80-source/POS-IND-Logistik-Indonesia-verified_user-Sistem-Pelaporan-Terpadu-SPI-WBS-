# Portal POS IND — Pengawasan & Laporan Insiden (Flask + SQLite)

Aplikasi pelaporan penyimpangan operasional **WASUM (Pengawasan Umum & SOP)** dengan dua area terpisah: **Pelapor** (membuat & memantau
laporan) dan **Staf/SPI** (melihat semua laporan, verifikasi, disposisi, penutupan). Database **SQLite** (`data/pos_ind.db`, dibuat otomatis).

## Menjalankan
```bash
pip install -r requirements.txt        # hanya Flask
python run.py                          # http://127.0.0.1:5000  (halaman awal "/" memuat dua pintu masuk)
```
Tampilan memakai Tailwind via CDN (sama seperti desain asli) — browser perlu internet.
Windows/PowerShell, jika `venv\Scripts\activate` ditolak: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

## Mana pintu untuk siapa
| Anda | Buka | Login (kata sandi demo `PosInd2025!`) | Setelah masuk |
|---|---|---|---|
| **Pelapor** (membuat laporan) | `/` → *Masuk sebagai Pelapor* (`/pelapor/masuk`) | `987654321` atau `981120340` | `/pelapor/laporan-saya`, `/pelapor/laporan-baru`, `/pelapor/pengaturan` |
| **Petugas SPI** (melihat **semua** laporan) | `/` → *Masuk Staf / SPI* (`/masuk`, tab Karyawan) | `100000001` | `/dashboard`, `/staf/pengaturan` |
| Karyawan / Mitra biasa | `/masuk` | `987654322` / `AG-8829104` (tab Mitra) | hanya `/staf/pengaturan` (tidak boleh membaca laporan orang lain) |

Halaman masuk/daftar kedua portal memiliki pemilih **Pelapor | Staf/SPI** di bagian atas kartu. URL lama (`/laporan-saya`, `/laporan/baru`, `/pengaturan`) dialihkan otomatis.
Siapa yang boleh melihat semua laporan: satu konstanta, `security.ROLES_LIHAT_SEMUA = ("spi",)`.

## Lingkup pengawasan: hanya WASUM (JASKUG/ASKUG sudah dihapus)
Lingkup JASKUG (jasa keuangan & kas: remittance, giropos, saldo kas loket, selisih COD) dihapus karena datanya sensitif.
- **Form**: tanpa kartu pilihan klasifikasi dan tanpa kolom *Estimasi Nilai Kerugian / Nominal* (kolom `nominal` juga dihapus dari skema baru & ekspor CSV).
- **Server**: klasifikasi selalu `WASUM`; kiriman klien yang masih memakai `ASKUG`/`nominal` diabaikan. Kategori *Kendala Kas / COD* dan filter klasifikasi dihapus.
- **Database lama** yang masih menyimpan laporan ASKUG: saat start muncul peringatan di log. Hapus dengan (cadangkan `data/` dulu, tidak bisa dibatalkan):
  ```bash
  python manage.py hapus-askug          # hanya menampilkan jumlah data ASKUG yang tersisa
  python manage.py hapus-askug --ya     # menghapus laporan + disposisi + pesan + berkas bukti + notifikasi/email terkait, lalu VACUUM
  ```
  `VACUUM` memastikan isi yang dihapus tidak tertinggal di file database. Catatan `audit_log` (hanya nomor tiket, tanpa isi) tidak dihapus; penghapusan dicatat sebagai `admin_hapus_askug`.
- Data demo (`SEED_DEMO=1`) tidak lagi berisi laporan ASKUG. Database demo lama: hapus `data/pos_ind.db` agar dibuat ulang, atau jalankan `hapus-askug --ya`.

## Alur proses laporan (kini ditegakkan oleh server)
1. **Pelapor** menyusun laporan (draf tersimpan di server), mengunggah bukti, mengirim → nomor tiket `LAP-WASUM-2026-0001`, tahap 1 **Terdaftar** (25%).
2. **SPI** memverifikasi bukti → tahap 2 **Investigasi SPI Lapangan** (50%). SPI dapat *meminta informasi tambahan*; pelapor membalas dan/atau menambah **bukti susulan**.
3. Tahap 3 **Klarifikasi Satker** (75%, tenggat otomatis 7 hari bila belum diisi) lalu tahap 4 **Selesai** (100%) — wajib keterangan resolusi, nomor Berita Acara otomatis.
4. Status **hanya maju** dan tidak boleh melompat: tidak bisa menutup laporan sebelum investigasi, tidak bisa mundur, laporan Selesai terkunci.
5. **SLA seragam: 5 hari kerja sejak dikirim** (panel progres, statistik dasbor, dan label layar memakai aturan yang sama).
6. Catatan SPI bisa **internal** (pelapor hanya melihat bahwa ada pembaruan, tanpa isi & tanpa nama petugas); resolusi akhir selalu terlihat pelapor.

## Yang ditambahkan pada pembaruan ini (bertahap)
**Tahap 1 — perbaikan yang dilaporkan**
- **Upload berkas**: area unggah kini bisa diklik ("Pilih dari Komputer"), keyboard (Enter/Spasi), dan drag-and-drop; validasi di browser *dan* server (ekstensi, ukuran 50 MB, isi berkas, duplikat, maks. 10), progres per berkas, batal, pratinjau, hapus.
  *Penyebabnya:* desain asli hanya menampilkan kotak "bisa diklik" tanpa handler; handler klik tidak pernah ada.
- **Bukti susulan** setelah laporan terkirim (dari detail laporan), tercatat di riwayat dan memberi notifikasi ke SPI.
- **Cuplikan Tiket Aktif** (pelapor & SPI): persen progres + bar 4 tahap, tahap berjalan, *siapa yang ditunggu*, penanggung jawab, batas & sisa SLA (hari kerja), langkah berikutnya, aktivitas terakhir, jumlah bukti terverifikasi, peringatan bila ada permintaan informasi terbuka.
- **Halaman awal `/`** + pemilih portal di halaman masuk/daftar agar jelas mana pintu Pelapor dan mana Staf/SPI.
- Kolom kanan (pratinjau) bisa di-scroll sendiri sehingga tidak terpotong.

**Tahap 2 — celah alur yang ditemukan saat audit kode**
- **Pesan dua arah** pelapor ↔ SPI (permintaan informasi, balasan) + **catatan internal SPI**.
- **Aturan status** (maju saja, tak boleh lompat) dan SLA yang konsisten (sebelumnya statistik memakai 7 hari kalender, layar menulis 5 hari kerja).
- **Email mengikuti preferensi** `notif_email` (konfirmasi laporan, pembaruan, permintaan informasi). Tanpa SMTP, email masuk tabel `email_outbox` + log.
- **Kirim ulang verifikasi email** (tombol di Pengaturan; sebelumnya halaman galat menyuruh "minta tautan baru" padahal tidak ada fitur itu).
- **`manage.py`** — tanpa ini tidak ada cara membuat akun SPI di produksi (akun SPI hanya ada pada data demo).
- Label yang menyesatkan diperbaiki: "Export (Excel/PDF)" → CSV; "SSO Terverifikasi" → "Sesi Aktif"; "Karyawan Tetap" untuk mitra; klaim HRMS/TLS kini mengikuti kondisi nyata; titik notifikasi ganda; tautan logo/Helpdesk yang mati.
- Migrasi otomatis untuk database lama (kolom `disposisi.publik`, `lampiran.susulan`, tabel `pesan`) — data lama tidak berubah.

## Administrasi (`manage.py`)
```bash
python manage.py buat-spi 123456789 "Nama Lengkap" nama@posindonesia.co.id      # akun SPI baru (sandi ditanya)
python manage.py jadikan-spi 987654322                                          # naikkan akun karyawan yang ada
python manage.py daftar-pengguna [--portal pelapor|karyawan]
python manage.py nonaktifkan pelapor 987654321   |   aktifkan karyawan 987654322    # sesi aktif langsung dicabut
python manage.py atur-sandi karyawan 100000001
python manage.py impor-hrms data_pegawai.csv                                    # lalu HRMS_STRICT=1 untuk mewajibkan NIPPOS terdaftar
python manage.py hapus-askug [--ya]                                             # buang sisa data JASKUG/ASKUG lama (lihat bagian di atas)
```

## Produksi
`SEED_DEMO=0` (tanpa akun demo), `COOKIE_SECURE=1` (HTTPS), `SECRET_KEY=...`, SMTP (`SMTP_HOST/PORT/USER/PASSWORD/FROM`), jalankan dengan
gunicorn/waitress (bukan `run.py`), dan buat akun SPI dengan `manage.py buat-spi`.

## Keputusan privasi
- Identitas pelapor & daftar bukti hanya terlihat oleh pemilik laporan dan SPI; pelapor anonim tetap dikelola SPI.
- Karyawan/mitra non-SPI tidak dapat membaca laporan orang lain sama sekali (uraian bisa memuat nama terlapor).
- Nama petugas SPI tidak diperlihatkan kepada pelapor ("Tim SPI").

## Struktur & tes
```
app/            Flask: auth_api, akun_api, laporan_api, pages, security, db (+migrasi), seed, mailer, schema.sql
app/pages_html  HTML halaman. CATATAN: sebagian besar sudah diedit langsung; tools/build_pages.py & build_app_pages.py
                akan MENIMPA perubahan itu (sidebar server-side, shell pelapor, penghapusan JASKUG — `build_app_pages.py` masih memuat teks ASKUG). Hanya tools/build_beranda.py yang aman dijalankan ulang.
app/static/js   core.js (API, modal, unggah XHR, pemilih portal), auth.js, settings.js, laporan.js
tests/          run.py (runner tanpa pytest) · test_api · test_laporan · test_pemisahan · test_tahap · test_hapus_askug · e2e.py · e2e2.py · e2e3.py (Playwright)
```
```bash
python tests/run.py test_api test_laporan test_pemisahan test_tahap test_hapus_askug     # 44 tes
python tests/e2e3.py                                                    # browser: upload klik/drag, progres, pesan, susulan
```

## Belum ada / batasan (jujur)
| Belum ada | Catatan |
|---|---|
| Terjemahan English | Tombol ID/EN hanya menyimpan preferensi; teks tetap Indonesia. |
| 2FA, SSO, integrasi HRMS/GPS/CCTV nyata | `hrms_master` hanya tabel simulasi/impor CSV. Skor keamanan menampilkan 2FA "Belum tersedia". |
| SMS / WhatsApp / push | Hanya preferensi tersimpan. Yang terkirim nyata: notifikasi dalam aplikasi + email (jika SMTP diisi). |
| Satker (KC/KCU) tidak punya login | Tahap "Klarifikasi Satker" dicatat oleh SPI; unit terkait belum bisa menjawab di sistem. |
| Antarmuka web untuk kelola akun & peran | Hanya lewat `manage.py`. |
| Halaman Audit Log untuk SPI | Tabel `audit_log` terisi, belum ada layar untuk membacanya. |
| Penarikan/pembatalan laporan oleh pelapor | Belum ada (pelapor dapat menambah keterangan & bukti). |
| Penetapan investigator per akun | Kolom investigator berupa teks bebas. |
| Pemindaian antivirus berkas | Yang ada: cek ekstensi, ukuran, dan tanda tangan isi berkas. |
| Ekspor XLSX/PDF tabel | Ekspor CSV; PDF lewat cetak browser (tanda terima/berita acara). |
