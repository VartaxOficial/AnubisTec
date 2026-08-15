import hashlib
import json
import os
import random
import re
import secrets
import smtplib
import string
import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

import bcrypt
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HOST = "127.0.0.1"
PORT = 8000

MONGO_URI = os.getenv("MONGO_URI", "")
DB_NAME = os.getenv("DB_NAME", "auth")
COLLECTION = os.getenv("COLLECTION", "users")
GMAIL_EMAIL = os.getenv("GMAIL_EMAIL", "")
GMAIL_APP_PASSWORD = (os.getenv("GMAIL_APP_PASSWORD") or "").replace(" ", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

OTP_EXPIRY_MINUTES = 10
MIN_PASSWORD_LENGTH = 6
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
OTP_RE = re.compile(r"^\d{6}$")

MAX_BODY_SIZE = 64 * 1024
SESSION_COOKIE = "session"
SESSION_MAX_AGE = 60 * 60 * 12
RATE_LIMIT_MAX = 20
RATE_LIMIT_WINDOW = 10 * 60

TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Acceso Denegado</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #667eea, #764ba2);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }}
        .card {{
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            text-align: center;
        }}
        .card h1 {{ color: #e74c3c; margin-bottom: 12px; }}
        .card a {{ color: #667eea; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>{status}</h1>
        <p>{mensaje}</p>
        <p><a href="/">Volver al login</a></p>
    </div>
</body>
</html>
"""

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client[DB_NAME]
users = db[COLLECTION]
users.create_index("email", unique=True)

_sessions = {}
_sessions_lock = threading.Lock()
_attempts = defaultdict(list)
_attempts_lock = threading.Lock()


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def generate_otp(length=6):
    return "".join(random.choices(string.digits, k=length))


def send_otp_email(to_email, otp):
    html = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;font-family:Arial,sans-serif;background:#f4f4f5;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5;padding:32px 16px;">
        <tr>
            <td align="center">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:420px;background:#ffffff;border-radius:16px;padding:32px;box-shadow:0 10px 30px rgba(0,0,0,0.08);">
                    <tr>
                        <td align="center" style="padding-bottom:16px;">
                            <div style="width:48px;height:48px;border-radius:12px;background:linear-gradient(135deg,#6366f1,#4f46e5);margin:0 auto;"></div>
                        </td>
                    </tr>
                    <tr>
                        <td align="center" style="padding-bottom:8px;">
                            <h1 style="margin:0;font-size:20px;color:#1a1a2e;">Código de verificación</h1>
                        </td>
                    </tr>
                    <tr>
                        <td align="center" style="padding-bottom:24px;">
                            <p style="margin:0;font-size:14px;color:#8a8a9e;">Usá este código para completar tu verificación.</p>
                        </td>
                    </tr>
                    <tr>
                        <td align="center" style="padding-bottom:24px;">
                            <div style="display:inline-block;background:#eef2ff;border-radius:12px;padding:16px 32px;font-size:32px;font-weight:700;letter-spacing:8px;color:#4f46e5;">{otp}</div>
                        </td>
                    </tr>
                    <tr>
                        <td align="center">
                            <p style="margin:0;font-size:12px;color:#b3b3c2;">El código expira en {OTP_EXPIRY_MINUTES} minutos. Si no lo pediste, ignorá este correo.</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Tu código de verificación"
    msg["From"] = GMAIL_EMAIL
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.starttls()
        server.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_EMAIL, [to_email], msg.as_string())


def send_otp_email_async(to_email, otp):
    def _send():
        try:
            send_otp_email(to_email, otp)
            print(f"[SMTP] Código enviado a {to_email}")
        except Exception as e:
            print(f"[SMTP ERROR] {e}")

    threading.Thread(target=_send, daemon=True).start()


def set_otp(email):
    otp = generate_otp()
    otp_hash = bcrypt.hashpw(otp.encode("utf-8"), bcrypt.gensalt())
    otp_expiry = utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES)
    users.update_one(
        {"email": email},
        {"$set": {"otp_hash": otp_hash, "otp_expiry": otp_expiry}},
    )
    return otp


def _hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _create_session(email):
    token = secrets.token_urlsafe(32)
    with _sessions_lock:
        _sessions[_hash_token(token)] = {
            "email": email,
            "expires": utcnow() + timedelta(seconds=SESSION_MAX_AGE),
        }
    return token


def _get_session(token):
    if not token:
        return None
    with _sessions_lock:
        session = _sessions.get(_hash_token(token))
        if not session:
            return None
        if utcnow() > session["expires"]:
            del _sessions[_hash_token(token)]
            return None
        return session["email"]


def _delete_session(token):
    if not token:
        return
    with _sessions_lock:
        _sessions.pop(_hash_token(token), None)


def _is_rate_limited(ip):
    now = utcnow()
    with _attempts_lock:
        bucket = [t for t in _attempts[ip] if now - t < timedelta(seconds=RATE_LIMIT_WINDOW)]
        if len(bucket) >= RATE_LIMIT_MAX:
            return True
        bucket.append(now)
        _attempts[ip] = bucket
        return False


def _read_cookie(header):
    if not header:
        return {}
    cookies = {}
    for part in header.split(";"):
        part = part.strip()
        if "=" in part:
            name, value = part.split("=", 1)
            cookies[name.strip()] = value.strip()
    return cookies


class LoginHandler(BaseHTTPRequestHandler):
    def _send_html(self, content, code=200, headers=None):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("X-Content-Type-Options", "nosniff")
        if headers:
            for name, value in headers.items():
                self.send_header(name, value)
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))

    def _send_json(self, data, code=200, headers=None):
        body = json.dumps(data)
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        if headers:
            for name, value in headers.items():
                self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def _load(self, filename):
        with open(os.path.join(BASE_DIR, filename), "r", encoding="utf-8") as f:
            return f.read()

    def _read_json(self):
        raw_length = self.headers.get("Content-Length", "0")
        if not raw_length.isdigit():
            raise ValueError("Content-Length inválido")
        length = int(raw_length)
        if length <= 0 or length > MAX_BODY_SIZE:
            raise ValueError("Cuerpo demasiado grande")
        body = self.rfile.read(length).decode("utf-8")
        data = json.loads(body)
        if not isinstance(data, dict):
            raise ValueError("Cuerpo inválido")
        return data

    def _session_email(self):
        cookies = _read_cookie(self.headers.get("Cookie", ""))
        return _get_session(cookies.get(SESSION_COOKIE))

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            self._send_html(self._load("login.html"))
        elif path == "/register":
            self._send_html(self._load("register.html"))
        elif path == "/verify":
            self._send_html(self._load("verify.html"))
        elif path == "/dashboard":
            if not self._session_email():
                self.send_response(302)
                self.send_header("Location", "/")
                self.end_headers()
                return
            self._send_html(self._load("dashboard.html"))
        else:
            self._send_html(
                TEMPLATE.format(status="404", mensaje="Página no encontrada"),
                code=404,
            )

    def do_POST(self):
        path = urlparse(self.path).path
        ip = self.client_address[0]

        if path == "/logout":
            cookies = _read_cookie(self.headers.get("Cookie", ""))
            _delete_session(cookies.get(SESSION_COOKIE))
            self._send_json(
                {"success": True, "message": "Sesión cerrada"},
                headers={
                    "Set-Cookie": f"{SESSION_COOKIE}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"
                },
            )
            return

        if _is_rate_limited(ip):
            self._send_json(
                {"success": False, "message": "Demasiados intentos. Esperá unos minutos."},
                code=429,
            )
            return

        try:
            data = self._read_json()
        except ValueError:
            self._send_json({"success": False, "message": "Solicitud inválida o demasiado grande"}, 400)
            return

        try:
            if path == "/register":
                self._handle_register(data)
            elif path == "/verify":
                self._handle_verify(data)
            elif path == "/login":
                self._handle_login(data)
            else:
                self._send_json({"success": False, "message": "Ruta no válida"}, 404)
        except Exception:
            import traceback

            traceback.print_exc()
            self._send_json({"success": False, "message": f"Error interno del servidor"})

    def _handle_register(self, data):
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))

        if not EMAIL_RE.match(email):
            self._send_json({"success": False, "message": "Correo electrónico inválido"})
            return
        if len(password) < MIN_PASSWORD_LENGTH:
            self._send_json(
                {"success": False, "message": "La contraseña debe tener al menos 6 caracteres"}
            )
            return

        if users.find_one({"email": email}):
            self._send_json({"success": False, "message": "Ese correo ya está registrado"})
            return

        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        otp = generate_otp()
        otp_hash = bcrypt.hashpw(otp.encode("utf-8"), bcrypt.gensalt())
        otp_expiry = utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES)

        user = {
            "email": email,
            "password_hash": password_hash,
            "verified": False,
            "otp_hash": otp_hash,
            "otp_expiry": otp_expiry,
            "created_at": utcnow(),
        }

        users.insert_one(user)
        send_otp_email_async(email, otp)
        self._send_json(
            {
                "success": True,
                "message": "Registro exitoso. Revisá tu correo para el código.",
                "redirect": f"/verify?email={quote(email, safe='@')}",
            }
        )

    def _handle_verify(self, data):
        email = str(data.get("email", "")).strip().lower()
        otp = str(data.get("otp", "")).strip()

        if not EMAIL_RE.match(email) or not OTP_RE.match(otp):
            self._send_json({"success": False, "message": "Datos de verificación inválidos"})
            return

        user = users.find_one({"email": email})
        if not user:
            self._send_json({"success": False, "message": "Usuario no encontrado"})
            return

        if user.get("verified"):
            self._send_json(
                {"success": True, "message": "Cuenta ya verificada", "redirect": "/"}
            )
            return

        otp_hash = user.get("otp_hash")
        otp_expiry = user.get("otp_expiry")

        if not otp_hash or not otp_expiry or utcnow() > otp_expiry:
            self._send_json({"success": False, "message": "El código ha expirado. Pedí uno nuevo."})
            return

        if not bcrypt.checkpw(otp.encode("utf-8"), otp_hash):
            self._send_json({"success": False, "message": "Código incorrecto"})
            return

        users.update_one(
            {"email": email},
            {"$set": {"verified": True}, "$unset": {"otp_hash": "", "otp_expiry": ""}},
        )
        self._send_json(
            {"success": True, "message": "Cuenta verificada. Ya podés iniciar sesión.", "redirect": "/"}
        )

    def _handle_login(self, data):
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))

        if not EMAIL_RE.match(email):
            self._send_json({"success": False, "message": "Correo electrónico inválido"})
            return
        if len(password) < MIN_PASSWORD_LENGTH:
            self._send_json(
                {"success": False, "message": "La contraseña debe tener al menos 6 caracteres"}
            )
            return

        user = users.find_one({"email": email})
        if not user or not bcrypt.checkpw(password.encode("utf-8"), user.get("password_hash", b"")):
            self._send_json({"success": False, "message": "Correo o contraseña incorrectos"})
            return

        if not user.get("verified"):
            otp = set_otp(email)
            send_otp_email_async(email, otp)
            self._send_json(
                {
                    "success": False,
                    "verified": False,
                    "message": "Cuenta no verificada. Te enviamos un nuevo código a tu correo.",
                    "redirect": f"/verify?email={quote(email, safe='@')}",
                }
            )
            return

        token = _create_session(email)
        self._send_json(
            {
                "success": True,
                "message": "Login exitoso",
                "redirect": "/dashboard",
            },
            headers={
                "Set-Cookie": f"{SESSION_COOKIE}={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_MAX_AGE}"
            },
        )

    def log_message(self, format, *args):
        print(f"[{self.address_string()}] {format % args}")


if __name__ == "__main__":
    try:
        client.admin.command("ping")
        print(f"Conectado a MongoDB Atlas (db: {DB_NAME}, colección: {COLLECTION})")
    except Exception as e:
        print(f"[ERROR] No se pudo conectar a MongoDB: {e}")
        raise SystemExit(1)

    server = ThreadingHTTPServer((HOST, PORT), LoginHandler)
    print(f"Servidor corriendo en http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido")
        server.server_close()
