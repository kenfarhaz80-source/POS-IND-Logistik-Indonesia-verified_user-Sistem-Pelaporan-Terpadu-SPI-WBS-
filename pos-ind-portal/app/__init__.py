import os
import secrets
from pathlib import Path

from flask import Flask, g, jsonify, request

from . import db as dbm
from . import security as sec

ROOT = Path(__file__).resolve().parent.parent


def _secret(data_dir):
    env = os.environ.get("SECRET_KEY")
    if env:
        return env
    f = Path(data_dir) / "secret.key"
    if not f.exists():
        f.write_text(secrets.token_hex(32))
        try:
            f.chmod(0o600)
        except OSError:
            pass
    return f.read_text().strip()


def create_app(config=None):
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    data_dir = Path(os.environ.get("DATA_DIR", ROOT / "data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    app.config.update(
        DATA_DIR=str(data_dir),
        DB_PATH=str(data_dir / "pos_ind.db"),
        UPLOAD_DIR=str(data_dir / "uploads"),
        HRMS_STRICT=os.environ.get("HRMS_STRICT", "0") == "1",   # 1 = NIPPOS wajib ada di hrms_master
        COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
        SMTP_HOST=os.environ.get("SMTP_HOST"), SMTP_PORT=int(os.environ.get("SMTP_PORT", 587)),
        SMTP_USER=os.environ.get("SMTP_USER"), SMTP_PASSWORD=os.environ.get("SMTP_PASSWORD"),
        SMTP_FROM=os.environ.get("SMTP_FROM", "no-reply@posindonesia.co.id"),
        MAX_CONTENT_LENGTH=60 * 1024 * 1024,
        SEED_DEMO=os.environ.get("SEED_DEMO", "1") == "1",
    )
    if config:
        app.config.update(config)
    Path(app.config["UPLOAD_DIR"]).mkdir(parents=True, exist_ok=True)
    app.secret_key = app.config.get("SECRET_KEY") or _secret(data_dir)

    dbm.init_db(app.config["DB_PATH"])
    app.teardown_appcontext(dbm.close_db)

    from . import akun_api, auth_api, laporan_api, pages, seed
    for m in (auth_api, akun_api, laporan_api, pages):
        app.register_blueprint(m.bp)

    with app.app_context():
        seed.ensure_reference(dbm.get_db())
        if app.config["SEED_DEMO"] and dbm.get_db().execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            seed.demo(dbm.get_db())

    with app.app_context():
        from . import purge_askug
        sisa = purge_askug.ringkas(dbm.get_db())
        if sisa["laporan"]:
            app.logger.warning("Masih ada %d laporan JASKUG/ASKUG lama di database (lingkup ini sudah dihapus dari portal). "
                               "Cadangkan data/ lalu jalankan: python manage.py hapus-askug --ya", sisa["laporan"])

    @app.before_request
    def _load():
        if request.endpoint == "static":
            g.user = None
            return
        sec.load_session()

    @app.after_request
    def _headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        if request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.errorhandler(413)
    def _big(_e):
        return jsonify(ok=False, error="Ukuran berkas melebihi batas 50 MB."), 413

    @app.errorhandler(404)
    def _nf(_e):
        if request.path.startswith("/api/"):
            return jsonify(ok=False, error="Endpoint tidak ditemukan."), 404
        return pages.render_info("tidak-ditemukan", 404)

    @app.errorhandler(500)
    def _err(_e):
        if request.path.startswith("/api/"):
            return jsonify(ok=False, error="Terjadi kesalahan pada server."), 500
        return "Terjadi kesalahan pada server.", 500

    return app
