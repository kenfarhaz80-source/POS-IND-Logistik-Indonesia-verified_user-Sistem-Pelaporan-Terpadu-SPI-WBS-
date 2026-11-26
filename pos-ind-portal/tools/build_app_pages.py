# PERINGATAN: skrip ini USANG. Jangan dijalankan ulang — akan menimpa HTML yang sudah diedit langsung (sidebar, shell pelapor)
# dan memunculkan kembali lingkup JASKUG/ASKUG yang sudah dihapus. Desain sumbernya juga tidak disertakan.
"""Halaman terautentikasi: dasbor, laporan saya, buat laporan, pengaturan (karyawan & pelapor)."""
import re

from bs4 import BeautifulSoup

from build_pages import (bind, bind_all, drop_scripts, find, find_all, finish, load, remove_remote_imgs, txt)


def H(html):
    return BeautifulSoup(html, "html.parser")


def must(x, what=""):
    if x is None:
        raise SystemExit(f"[build] elemen tidak ditemukan: {what}")
    return x


def common_shell(s):
    """Binding header/sidebar yang sama di semua halaman terautentikasi."""
    for el in s.find_all(string=re.compile(r"Hub Sentral Jkt")):
        if el.find_parent("aside"):
            el.replace_with(H('<span data-bind="hub">Hub Sentral</span>'))
    header = s.find("header")
    if header:
        bind_all(header, "987654321", "identifier")


def ensure_badge(s):
    nav = s.select_one("aside nav")
    a = nav.find("a", attrs={"data-path": "lihat-laporan"}) if nav else None
    if a and not a.find(attrs={"data-bind": "badge"}):
        a.append(H('<span data-bind="badge" class="px-2 py-0.5 rounded-full bg-secondary-container text-white text-[10px] font-bold ml-auto">0</span>'))
        a["class"] = list(dict.fromkeys((a.get("class") or []) + ["flex", "items-center"]))


def add_buat_link(s):
    """Dasbor & pengaturan karyawan: tambah tautan 'Buat Laporan Baru' (belum ada di desain asli)."""
    nav = s.select_one("aside nav")
    src = nav.find("a", attrs={"data-path": "pengaturan-akun"})
    if not src or nav.find("a", attrs={"data-path": "buat-laporan-baru"}):
        return
    new = H(str(src)).a
    new["data-path"] = "buat-laporan-baru"
    new.attrs.pop("aria-current", None)
    spans = new.find_all("span")
    spans[0].string = "post_add"
    spans[-1].string = "Buat Laporan Baru"
    src.insert_before(new)


# ============================================================ DASBOR
def build_dashboard():
    s = load("daftar_laporan_logistik_insiden_dashboard_pos_ind")
    remove_remote_imgs(s)
    drop_scripts(s)
    common_shell(s)
    nav = must(s.find("a", id="nav-item-laporan"))
    nav["data-path"] = "lihat-laporan"
    nav.find_all("span")[-1]["data-bind"] = "badge"
    add_buat_link(s)
    main = s.find("main")

    for needle, name, exact in [("128", "s_total", True), ("+14 mgg ini", "s_pekan", False), ("KCP: 52", "s_tingkat", False),
                                ("98% Terverifikasi", "s_verif", False), ("34", "s_invest", True), ("Prioritas Tinggi", "s_prio", False),
                                ("Durasi rata-rata", "s_durasi", False), ("SLA: 94.2%", "s_sla", False), ("18", "s_klar", True),
                                ("Disposisi aktif", "s_unit", False), ("76", "s_selesai", True), ("100% Closed", "s_persen", False)]:
        bind(main, needle, name, exact)

    must(find(main, "button", "Filter Satuan Kerja"))["data-action"] = "toggle-filter"
    must(find(main, "button", "Export Laporan"))["data-action"] = "export"

    must(main.find("input", placeholder=re.compile("Cari NIPPOS")))["id"] = "f-q"
    sels = main.find_all("select")
    sels[0]["id"], sels[1]["id"] = "f-tingkat", "f-kategori"
    cal = must(find(main, "span", "calendar_month")).parent
    cal.clear()
    cal.append(H('<span class="material-symbols-outlined text-outline">calendar_month</span>'))
    cal.append(H('<input id="f-dari" type="date" aria-label="Dari tanggal kejadian" class="bg-transparent text-body-sm w-full min-w-0 outline-none">'))
    cal.append(H('<span class="text-outline">–</span>'))
    cal.append(H('<input id="f-sampai" type="date" aria-label="Sampai tanggal kejadian" class="bg-transparent text-body-sm w-full min-w-0 outline-none">'))

    label = must(find(main, "span", "Filter Aktif:"))
    chips = label.parent
    for c in list(chips.children):
        if c is not label and getattr(c, "extract", None) and c != label:
            c.extract()
    chips["id"] = "chips"

    col = must(main.select_one("div.lg\\:col-span-8"))
    kids = [c for c in col.find_all("div", recursive=False)]
    head = kids[0]
    bind(head, "128 Laporan Terdata", "s_label")
    urut = must(find(head, "button", "Urutkan") or head.find("button"))
    urut.replace_with(H('<select id="f-urut" aria-label="Urutkan" class="bg-transparent font-label-md text-label-md font-bold text-primary outline-none cursor-pointer">'
                        '<option value="terbaru">Waktu Kejadian (Terbaru)</option><option value="terlama">Waktu Kejadian (Terlama)</option>'
                        '<option value="prioritas">Prioritas</option></select>'))
    for k in kids[1:]:
        k.decompose()
    col.append(H('<div id="report-list" class="space-y-space-md"></div>'))
    col.append(H('<div id="pager" class="bg-surface-container-lowest rounded-xl p-space-md shadow-sm flex flex-wrap items-center justify-between gap-3"></div>'))

    side = must(main.select_one("div.lg\\:col-span-4"))
    card = side.find("div", recursive=False)
    keep = card["class"]
    card.clear()
    card["id"] = "preview"
    card["class"] = keep
    must(find(side, "a", "Pelajari")) if find(side, "a", "Pelajari") else None
    finish(s, "dashboard", "dashboard")


# ============================================================ LAPORAN SAYA
def build_laporan_saya():
    s = load("daftar_laporan_saya_portal_pelapor_pos_ind")
    remove_remote_imgs(s)
    drop_scripts(s)
    common_shell(s)
    ensure_badge(s)
    main = s.find("main")
    root = main.find("div")
    kids = [c for c in root.children if getattr(c, "name", None)]
    hero, stats, ribbon, grid = kids

    for el in hero.find_all(string=re.compile("NIPPOS: 987654321")):
        el.replace_with(el.replace("987654321", "").replace("NIPPOS: ", "NIPPOS: ") if False else H(str(el).replace("987654321", '<span data-bind="identifier"></span>')))
    must(find(hero, "button", "Filter Unit Satker"))["data-action"] = "unit-filter"
    must(find(hero, "button", "Ekspor"))["data-action"] = "export"
    for sp in hero.find_all("span"):
        if "Ekspor" in sp.get_text() and not sp.find("span"):
            sp.string = "Ekspor (.CSV)"
    for el in hero.find_all("p"):
        if "dilaporkan oleh NIPPOS" in el.get_text():
            el.string = ""
            el.append(H("Monitoring status investigasi, disposisi audit satker SPI, dan progres tindak lanjut berkas laporan Anda "
                        '(WASUM &amp; ASKUG) — NIPPOS: <span data-bind="identifier" class="font-bold"></span>.'))

    cards = [c for c in stats.find_all("div", recursive=False)]
    names = ["s_total", "s_invest", "s_klar", "s_selesai"]
    for c, n in zip(cards, names):
        num = c.find("span", class_=lambda x: x and "text-headline-lg" in x)
        for t in list(num.find_all(string=True, recursive=False)):
            if t.strip():
                t.replace_with(H(f'<span data-bind="{n}">0</span>'))
    bind(stats, "Akumulasi akun NIPPOS", "s_note_total")
    bind(stats, "Kerusakan Segel Koli WASUM", "s_note_invest")
    bind(stats, "SLA 94.2%", "s_note_sla")
    bind(stats, "BAP Klarifikasi Disposisi", "s_note_klar")
    bind(stats, "Berita Acara Rekonsiliasi Sah", "s_note_selesai")

    must(ribbon.find("input"))["id"] = "f-q"
    sels = ribbon.find_all("select")
    sels[0]["id"], sels[1]["id"] = "f-klasifikasi", "f-status"
    sels[0].clear(); sels[1].clear()
    for v, t in [("", "Semua Kategori (WASUM & ASKUG)"), ("WASUM", "WASUM (Pengawasan Umum & Fisik Muatan)"), ("ASKUG", "ASKUG (Jasa Keuangan, Giro & Loket)")]:
        sels[0].append(H(f'<option value="{v}">{t}</option>'))
    for v, t in [("", "Semua Status Laporan"), ("Draf", "Draf (belum dikirim)"), ("Terdaftar", "Terdaftar / Menunggu Verifikasi"),
                 ("Investigasi SPI Lapangan", "Investigasi SPI Lapangan"), ("Klarifikasi Satker", "Klarifikasi Satker KCU"),
                 ("Selesai", "Selesai & Rekonsiliasi Klir")]:
        sels[1].append(H(f'<option value="{v}">{t}</option>'))
    cal = must(find(ribbon, "span", "calendar_month")).parent
    cal.clear()
    cal.append(H('<span class="material-symbols-outlined text-outline">calendar_month</span>'))
    cal.append(H('<input id="f-dari" type="date" aria-label="Dari tanggal" class="bg-transparent text-body-sm outline-none w-32">'))
    cal.append(H('<span class="text-outline">–</span>'))
    cal.append(H('<input id="f-sampai" type="date" aria-label="Sampai tanggal" class="bg-transparent text-body-sm outline-none w-32">'))
    ribbon.append(H('<div id="chips" class="flex flex-wrap items-center gap-2"></div>'))

    left, right = [c for c in grid.find_all("div", recursive=False)][:2]
    for c in list(left.find_all("div", recursive=False)):
        c.decompose()
    left.append(H('<div id="report-list" class="flex flex-col gap-space-md"></div>'))
    left.append(H('<div id="pager" class="bg-surface-container-lowest rounded-xl p-space-md shadow-sm flex flex-wrap items-center justify-between gap-3"></div>'))
    first = right.find("div", recursive=False)
    keep = first["class"]
    first.clear()
    first["id"], first["class"] = "preview", keep
    a = find(right, "a", "Pelajari Regulasi")
    if a:
        a["href"], a["target"] = "/info/perlindungan-pelapor", "_blank"
        a.attrs.pop("data-path", None)
    finish(s, "laporan_saya", "laporan_saya")


# ============================================================ BUAT LAPORAN
def build_laporan_baru():
    s = load("buat_laporan_insiden_wasum_pengawasan_umum_sop_pos_ind")
    ask = load("buat_laporan_insiden_askug_wasum_dashboard_pos_ind")
    remove_remote_imgs(s)
    drop_scripts(s)
    common_shell(s)
    add_buat_link(s)
    ensure_badge(s)
    main = s.find("main")
    form = must(main.find("form", id="whistleblower-form"))
    del form["onsubmit"]
    form["novalidate"] = "novalidate"

    # --- bidang khusus WASUM (di dalam seksi klasifikasi)
    tip_label = must(find(main, "label", "Tipologi Sub-Kasus"))
    wasum_block = tip_label.parent.parent
    wasum_block["id"] = "wasum-fields"
    sel_tip = wasum_block.find("select")
    sel_tip["id"] = "f-tipologi"
    opts = [re.sub(r"\s*\(Terpilih\)", "", o.get_text(strip=True)) for o in sel_tip.find_all("option")]
    sel_tip.clear()
    sel_tip.append(H('<option value="">Pilih tipologi sub-kasus...</option>'))
    for o in opts:
        sel_tip.append(H(f'<option value="{o}">{o}</option>'))
    for lab, id_ in [("Nomor Koli / Barcode", "f-awb"), ("Nomor Plat Armada", "f-plat"), ("Estimasi Deviasi", "f-deviasi")]:
        inp = must(find(wasum_block, "label", lab)).parent.find("input")
        inp["id"] = id_
        inp["value"] = ""
    rute = must(find(wasum_block, "label", "Jalur Logistik")).parent.find("select")
    rute["id"] = "f-rute"
    ropts = [o.get_text(strip=True) for o in rute.find_all("option")]
    rute.clear()
    rute.append(H('<option value="">Pilih jalur logistik / rute...</option>'))
    for o in ropts:
        rute.append(H(f'<option value="{o}">{o}</option>'))

    # --- seksi 2: pihak
    pel_t = must(find(form, "label", "Tingkat Kantor Pelapor")).parent.find("select")
    pel_t["id"] = "f-pel-tingkat"
    pel_t.insert(0, H('<option value="">Pilih tingkat kantor...</option>'))
    for o in pel_t.find_all("option"):
        o.attrs.pop("selected", None)
    pel_u = must(find(form, "label", "Nama Satuan / Unit Kerja Asal")).parent.find("input")
    pel_u["id"], pel_u["value"] = "f-pel-unit", ""
    for lab, id_ in [("Nama Lengkap / Inisial Terlapor", "f-terl-nama"), ("NIPPOS / ID Mitra (Bila Ada)", "f-terl-nippos")]:
        inp = must(find(form, "label", lab)).parent.find("input")
        inp["id"], inp["value"] = id_, ""
    terl_t = must(find(form, "label", "Tingkat / Hub Terlapor")).parent.find("select")
    terl_t["id"] = "f-terl-tingkat"
    terl_t.insert(0, H('<option value="">Pilih tingkat / hub terlapor...</option>'))
    for o in terl_t.find_all("option"):
        o.attrs.pop("selected", None)
        o.string = re.sub(r"\s*\(Sentral Pengolahan Pos Bandung\)", " (Sentral Pengolahan Pos)", o.get_text())
    terl_u = must(find(form, "label", "Satuan Kerja / Unit Penugasan Terlapor")).parent.find("input")
    terl_u["id"], terl_u["value"] = "f-terl-unit", ""
    for lab in ("Nama Lengkap / Inisial Terlapor",):
        pass
    must(form.find("input", id="anon-toggle")).attrs.pop("onchange", None)
    nama_el = must(form.find(id="pelapor-nama"))
    nama_el.clear()
    nama_el.append(H('<span data-bind="nama"></span> <span class="font-normal text-on-surface-variant" data-bind="jabatan"></span>'))
    nip_el = must(form.find(id="pelapor-nippos"))
    nip_el.clear()
    nip_el.append(H('<span data-bind="identifier"></span>'))

    # --- seksi 3: kronologi
    waktu = must(find(form, "label", "Waktu Kejadian")).parent.find("input")
    waktu["id"], waktu["type"], waktu["value"] = "f-waktu", "datetime-local", ""
    lok = must(find(form, "label", "Lokasi Spesifik")).parent.find("input")
    lok["id"], lok["value"] = "f-lokasi", ""
    ta = must(form.find("textarea", id="incident-text"))
    ta.attrs.pop("oninput", None)
    ta.string = ""
    ta["maxlength"] = "2000"
    must(form.find(id="char-counter")).string = "0 / 2000 karakter"
    nominal = must(ask.find(id="field-kerugian-container"))
    nominal_html = re.sub(r'value="[^"]*"', 'value=""', str(nominal))
    nom = H(nominal_html)
    nom_inp = nom.find("input", id="input-nominal")
    nom_inp["inputmode"] = "numeric"
    nom_inp["autocomplete"] = "off"
    must(ta.parent.parent).insert_before(nom)

    # --- seksi 4: bukti
    up = must(form.find("input", id="file-uploader"))
    up.attrs.pop("onchange", None)
    up["accept"] = ".mp4,.m4a,.pdf,.jpg,.jpeg,.png,.csv,.xlsx"
    dz = up.parent
    dz["id"] = "dropzone"
    cnt = must(find(form, "p", "Daftar Dokumen Pendukung"))
    cnt["id"] = "file-count"
    listing = cnt.find_next_sibling("div")
    listing.clear()
    listing["id"] = "file-list"

    # --- pernyataan & aksi
    chk = must(find(form, "span", "Saya menyatakan")).parent.find("input", type="checkbox")
    chk["id"] = "f-pernyataan"
    chk.attrs.pop("required", None)
    for inp in form.find_all(attrs={"required": True}):
        del inp["required"]
    draf = must(find(form, "button", "Simpan sebagai Draf"))
    draf.attrs.pop("onclick", None)
    draf["id"] = "btn-draf"
    kirim = must(form.find("button", type="submit"))
    kirim["id"] = "btn-kirim"
    kirim.find_all("span")[0]["id"] = "kirim-label"
    must(find(form, "a", "Batal"))["data-path"] = "lihat-laporan"
    m = s.find(id="success-modal")
    if m:
        m.decompose()
    finish(s, "laporan_baru", "laporan_baru")


# ============================================================ PENGATURAN KARYAWAN
def build_pengaturan_karyawan():
    s = load("pengaturan_akun_profil_dashboard_pos_ind")
    remove_remote_imgs(s)
    drop_scripts(s, keep=("switchSection", "evaluateStrength"))
    common_shell(s)
    add_buat_link(s)
    ensure_badge(s)
    for f in s.find_all("form"):
        f.attrs.pop("onsubmit", None)
        f["novalidate"] = "novalidate"
    for el in s.find_all(attrs={"required": True}):
        del el["required"]
    main = s.find("main")

    # profil
    avatar = must(next((d for d in main.find_all("div") if d.get_text(strip=True) == "AP" and not d.find("div")), None), "avatar AP")
    avatar["data-bind"] = "inisial"
    for t in main.find_all("h3"):
        if "Ahmad Pratama" in t.get_text():
            t.string = ""
            t.append(H('<span data-bind="nama"></span>'))
    bind(main, "Staf Operasional Sentral Pengolahan Pos", "jabatan_unit")
    bind(main, "Hub SPP JKT-13400", "chip_hub")
    bind(main, "TMT: 01 Maret 2018", "chip_tmt")
    bind(main, "Level Akses: Ops-L2", "chip_level")
    photo = must(main.find("button", title="Ubah Foto Profil"))
    photo["data-action"] = "avatar"
    photo["type"] = "button"
    must(main.find("input", id="fullName"))["value"] = ""
    for id_ in ("nippos", "companyEmail", "phoneNumber"):
        must(main.find("input", id=id_))["value"] = ""
    rst = must(find(main.find("form", id="profileForm"), "button", "Batal"))
    rst["type"] = "button"
    rst["data-action"] = "profil-reset"
    # keamanan
    bind(main, "Terakhir diubah: 42 hari lalu", "umur_sandi")
    for id_ in ("currentPassword", "newPassword", "confirmPassword"):
        must(main.find("input", id=id_))
    # bahasa
    # privasi
    for a in main.find_all("a"):
        if "Unduh Sertifikat" in a.get_text():
            a.decompose()
        elif "Unduh Salinan Kebijakan" in a.get_text():
            a["href"], a["target"] = "/info/kebijakan-privasi", "_blank"
            for sp in a.find_all("span"):
                if "Unduh" in sp.get_text():
                    sp.string = "Lihat Salinan Kebijakan Privasi PT Pos Indonesia"
        elif "Syarat & Ketentuan Layanan" in a.get_text():
            a["href"], a["target"] = "/info/syarat-ketentuan", "_blank"
    # kolom kanan
    side = must(main.select_one("div.lg\\:col-span-4") or main.select_one("div.xl\\:col-span-4"))
    cards = [c for c in side.find_all("div", recursive=False)]
    cards[0].clear(); cards[0]["id"] = "skor-card"
    cards[1].clear(); cards[1]["id"] = "sesi-card"
    s_btn = main.find("button", attrs={"onclick": re.compile("switchSection")})
    finish(s, "pengaturan_karyawan", "pengaturan_karyawan")


# ============================================================ PENGATURAN PELAPOR
def build_pengaturan_pelapor():
    s = load("pengaturan_akun_pelapor_pos_ind")
    remove_remote_imgs(s)
    drop_scripts(s, keep=("togglePasswordVisibility",))
    common_shell(s)
    ensure_badge(s)
    for f in s.find_all("form"):
        f.attrs.pop("onsubmit", None)
        f["novalidate"] = "novalidate"
    main = s.find("main")
    bind_all(main, "987654321", "identifier")
    bind_all(main, "Budi Santoso, S.T.", "nama")
    for sp in main.find_all(string=re.compile(r"^\s*BS\s*$")):
        sp.replace_with(H('<span data-bind="inisial">BS</span>'))
    # disabled inputs -> diisi JS
    for val, key in [("Budi Santoso, S.T.", "nama"), ("987654321", "identifier"), ("budi.santoso@posindonesia.co.id", "email"),
                     ("Sentral Pengolahan Pos Jakarta 10000 (SPP)", "unit_kerja")]:
        inp = must(main.find("input", value=val))
        inp["data-field"] = key
        inp["value"] = ""
    ph = must(main.find("input", id="operationalPhone"))
    ph["value"] = ""
    bind(main, "Petugas Pengawasan Operasional L1", "jabatan_unit")
    for t in main.find_all(string=re.compile(r"Sentral Pengolahan Pos Jakarta 10000 \(Hub")):
        pass
    # notifikasi & privasi
    sec_notif = must(find(main, "h2", "Preferensi Notifikasi")).find_parent("section")
    for cb, id_ in zip(sec_notif.find_all("input", type="checkbox"), ["n-sms", "n-email", "n-push"]):
        cb["id"] = id_
        cb.attrs.pop("checked", None)
    sec_priv = must(find(main, "h2", "Privasi & Perlindungan")).find_parent("section")
    anon = sec_priv.find("input", type="checkbox")
    anon["id"] = "n-anon"
    anon.attrs.pop("checked", None)
    lang_id = must(find(sec_notif, "button", "Bahasa Indonesia"))
    lang_en = must(find(sec_notif, "button", "English"))
    lang_id["id"], lang_en["id"] = "lang-id", "lang-en"
    apply_ = must(find(sec_notif, "button", "Terapkan Pengaturan"))
    apply_.attrs.pop("onclick", None)
    apply_["id"] = "btn-apply-notif"
    sec_priv_btn = None
    # tombol simpan privasi (belum ada di desain): tambahkan
    anon_row = anon.find_parent("div", class_=lambda c: c and "justify-between" in c)
    sec_priv.find_all("div", recursive=False)[-1].append(
        H('<div class="flex justify-end pt-2"><button id="btn-save-privacy" type="button" class="inline-flex items-center gap-2 px-4 py-2 rounded-lg '
          'bg-primary-container text-white font-label-md text-label-md font-bold hover:bg-primary transition-all"><span class="material-symbols-outlined text-lg">save</span>'
          '<span>Simpan Pengaturan Privasi</span></button></div>'))
    a = find(sec_priv, "a", "Unduh Salinan Pakta")
    if a:
        a["href"], a["target"] = "/info/perlindungan-pelapor", "_blank"
        for sp in a.find_all("span"):
            if "Unduh" in sp.get_text():
                sp.string = "Lihat Pakta Integritas & Perlindungan Pelapor"
    # pilihan zona/format untuk pelapor tidak ada di desain -> diatur lewat pengaturan notifikasi/bahasa saja
    # kolom kanan: skor & ringkasan
    bind(main, "94%", "skor")
    bind(main, "Tingkat Keamanan Tinggi", "skor_label")
    bind(main, "SSO, 2FA, & Enkripsi E2E Aktif pada Sesi Ini", "skor_note")
    bind(main, "Hari ini, 08:42 WIB", "login_terakhir")
    bind(main, "987654321 (Valid)", "bind_valid")
    bind(main, "Ops-L2 Whistleblower", "level_akses")
    for sp in main.find_all("span"):
        if sp.get_text(strip=True) == "SHA256-AES-GCM":
            sp.string = "Cookie HttpOnly + CSRF"
    h = must(next((e for e in main.find_all("span") if e.get_text(strip=True) == "Ringkasan Aktivitas Pelapor"), None), "judul aktivitas")
    widget = h.parent.parent.parent
    nums = widget.find_all("div", recursive=False)[1]
    for d, name in zip(nums.find_all("div", recursive=False), ["a_total", "a_selesai"]):
        n = d.find("div")
        n.clear()
        n.append(H(f'<span data-bind="{name}">0</span>'))
    bind(main, "2 Tiket", "a_wasum", exact=True)
    bind(main, "1 Tiket", "a_askug", exact=True)
    bind(main, "2 Proses", "a_proses", exact=True)
    toast = s.find(id="toastNotification")
    finish(s, "pengaturan_pelapor", "pengaturan_pelapor")


def build_all():
    build_dashboard()
    build_laporan_saya()
    build_laporan_baru()
    build_pengaturan_karyawan()
    build_pengaturan_pelapor()
