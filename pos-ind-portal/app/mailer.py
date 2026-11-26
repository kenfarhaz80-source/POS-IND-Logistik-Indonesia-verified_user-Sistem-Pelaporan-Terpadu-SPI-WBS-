"""Pengiriman email. Tanpa konfigurasi SMTP, email disimpan di tabel email_outbox dan dicatat di log
(berguna untuk pengembangan: tautan reset sandi dapat dibaca dari log server)."""
import smtplib
from email.message import EmailMessage

from flask import current_app, request
from itsdangerous import URLSafeTimedSerializer

from .db import ex
from .security import iso


def send_mail(to, subject, body):
    mail_id = ex("INSERT INTO email_outbox(tujuan,subjek,isi,dibuat) VALUES(?,?,?,?)", (to, subject, body, iso()))
    cfg = current_app.config
    if not cfg.get("SMTP_HOST"):
        current_app.logger.info("EMAIL (outbox #%s) ke %s | %s\n%s", mail_id, to, subject, body)
        return False
    try:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = cfg["SMTP_FROM"], to, subject
        msg.set_content(body)
        with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=10) as s:
            if cfg.get("SMTP_USER"):
                s.starttls()
                s.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
            s.send_message(msg)
        ex("UPDATE email_outbox SET terkirim=1 WHERE id=?", (mail_id,))
        return True
    except Exception as exc:  # jangan gagalkan permintaan pengguna karena SMTP
        current_app.logger.error("Gagal kirim email #%s: %s", mail_id, exc)
        return False


def verification_serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt="verifikasi-email")


def send_verification(user):
    token = verification_serializer().dumps({"u": user["id"], "e": user["email"]})
    send_mail(user["email"], "Verifikasi email POS IND",
              f"Halo {user['nama']},\n\nVerifikasi alamat email Anda melalui tautan berikut (berlaku 3 hari):\n"
              f"{request.host_url.rstrip('/')}/verifikasi-email?token={token}\n")
