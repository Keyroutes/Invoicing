import hashlib
import secrets
import uuid
import smtplib
import ssl
import json
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse, StreamingResponse, JSONResponse, Response, HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import os
import base64
import logging
from email.message import EmailMessage
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build
from dotenv import load_dotenv
from authlib.integrations.starlette_client import OAuth
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend

from sqlalchemy.orm import Session
from database import engine, get_db, SessionLocal, ensure_columns
import httpx
import models

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

def hash_password(password: str) -> str:
    salt = hashlib.sha256(os.urandom(32)).hexdigest().encode()
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    return salt.hex() + ':' + pwd_hash.hex()

def verify_password(password: str, stored: str) -> bool:
    salt_hex, pwd_hash_hex = stored.split(':')
    salt = bytes.fromhex(salt_hex)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    return pwd_hash.hex() == pwd_hash_hex

def log_login(db, client_id, email, user_type="client", login_type="password", request=None, status="success"):
    ip = ""
    device = ""
    if request and request.client:
        ip = request.client.host or ""
    if request:
        device = request.headers.get("user-agent", "")[:200]
    log = models.DBClientLoginLog(
        client_id=client_id, email=email, user_type=user_type,
        login_type=login_type, ip_address=ip, device_info=device,
        status=status,
    )
    db.add(log)
    if client_id:
        client = db.query(models.DBClient).filter(models.DBClient.id == client_id).first()
        if client:
            client.last_login = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            client.login_count = (client.login_count or 0) + 1
    db.commit()

def log_audit(db, client_id, action, entity_type="", entity_id=None, entity_name="", details="", request=None, user_type="client", user_name=""):
    ip = ""
    if request and request.client:
        ip = request.client.host or ""
    log = models.DBAuditLog(
        client_id=client_id, user_type=user_type, user_name=user_name,
        action=action, entity_type=entity_type, entity_id=entity_id,
        entity_name=entity_name, details=details, ip_address=ip,
    )
    db.add(log)

def generate_secret_key() -> str:
    return secrets.token_hex(32)

SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY or SECRET_KEY == "generate_a_random_secret_string":
    SECRET_KEY = generate_secret_key()
    logger.warning("Generated new SECRET_KEY - set it in .env for persistence")

def ensure_admin_user():
    try:
        with SessionLocal() as db:
            existing_admin = db.query(models.DBAdminUser).first()
            if not existing_admin:
                admin_pwd = os.getenv("ADMIN_PASSWORD", "admin")
                hashed = hash_password(admin_pwd)
                db.add(models.DBAdminUser(username="admin", password=hashed))
                db.commit()
                logger.info("Created default admin user (username=admin)")
            elif existing_admin.password and ':' not in existing_admin.password:
                existing_admin.password = hash_password(existing_admin.password)
                db.commit()
                logger.info("Upgraded admin password to hashed format")
    except Exception as e:
        logger.error(f"Admin user init failed: {e}")

from contextlib import asynccontextmanager

CURRENCY_SYMBOLS = {
    "AED": "د.إ", "AFN": "؋", "ALL": "L", "AMD": "֏", "ANG": "ƒ", "AOA": "Kz", "ARS": "$",
    "AUD": "A$", "AWG": "ƒ", "AZN": "₼", "BAM": "KM", "BBD": "$", "BDT": "৳", "BGN": "лв",
    "BHD": "ب.د", "BIF": "FBu", "BMD": "$", "BND": "$", "BOB": "Bs", "BRL": "R$", "BSD": "$",
    "BTN": "Nu.", "BWP": "P", "BYN": "Br", "BZD": "$", "CAD": "C$", "CDF": "FC", "CHF": "CHF",
    "CLP": "$", "CNY": "¥", "COP": "$", "CRC": "₡", "CUP": "$", "CVE": "Esc", "CZK": "Kč",
    "DJF": "Fdj", "DKK": "kr", "DOP": "RD$", "DZD": "دج", "EGP": "£", "ERN": "Nfk", "ETB": "Br",
    "EUR": "€", "FJD": "FJ$", "FKP": "£", "GBP": "£", "GEL": "₾", "GHS": "₵", "GIP": "£",
    "GMD": "D", "GNF": "FG", "GTQ": "Q", "GYD": "$", "HKD": "HK$", "HNL": "L", "HRK": "kn",
    "HTG": "G", "HUF": "Ft", "IDR": "Rp", "ILS": "₪", "INR": "₹", "IQD": "ع.د", "IRR": "﷼",
    "ISK": "kr", "JMD": "J$", "JOD": "د.ا", "JPY": "¥", "KES": "KSh", "KGS": "с", "KHR": "៛",
    "KMF": "CF", "KPW": "₩", "KRW": "₩", "KWD": "د.ك", "KYD": "CI$", "KZT": "₸", "LAK": "₭",
    "LBP": "ل.ل", "LKR": "₨", "LRD": "$", "LSL": "L", "LYD": "ل.د", "MAD": "د.م.", "MDL": "L",
    "MGA": "Ar", "MKD": "ден", "MMK": "K", "MNT": "₮", "MOP": "MOP$", "MRU": "UM", "MUR": "₨",
    "MVR": "Rf", "MWK": "MK", "MXN": "$", "MYR": "RM", "MZN": "MT", "NAD": "$", "NGN": "₦",
    "NIO": "C$", "NOK": "kr", "NPR": "₨", "NZD": "NZ$", "OMR": "ر.ع.", "PAB": "B/.", "PEN": "S/",
    "PGK": "K", "PHP": "₱", "PKR": "₨", "PLN": "zł", "PYG": "₲", "QAR": "ر.ق", "RON": "lei",
    "RSD": "дин", "RUB": "₽", "RWF": "FRw", "SAR": "﷼", "SBD": "SI$", "SCR": "₨", "SDG": "ج.س",
    "SEK": "kr", "SGD": "S$", "SHP": "£", "SLL": "Le", "SOS": "Sh", "SRD": "$", "SSP": "£",
    "STN": "Db", "SVC": "$", "SYP": "£", "SZL": "L", "THB": "฿", "TJS": "SM", "TMT": "m",
    "TND": "د.ت", "TOP": "T$", "TRY": "₺", "TTD": "TT$", "TWD": "NT$", "TZS": "Sh", "UAH": "₴",
    "UGX": "USh", "USD": "$", "UYU": "$U", "UZS": "so'm", "VES": "Bs", "VND": "₫", "VUV": "VT",
    "WST": "T", "XAF": "FCFA", "XCD": "EC$", "XOF": "CFA", "XPF": "₣", "YER": "﷼", "ZAR": "R",
    "ZMW": "ZK", "ZWL": "Z$",
}

def currency_symbol(code):
    code = (code or "").upper()
    return CURRENCY_SYMBOLS.get(code, code or "£")

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        models.Base.metadata.create_all(bind=engine)
        ensure_columns()
        ensure_admin_user()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
    ensure_super_admin()
    yield

app = FastAPI(title="Accounting Platform API", lifespan=lifespan)

class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username, password = form["username"], form["password"]
        with SessionLocal() as db:
            user = db.query(models.DBAdminUser).filter_by(username=username).first()
            if user and verify_password(password, user.password):
                request.session.update({"token": "admin_token"})
                return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return bool(request.session.get("token"))

authentication_backend = AdminAuth(secret_key=SECRET_KEY)
admin = Admin(app, engine, authentication_backend=authentication_backend)

class InvoiceAdmin(ModelView, model=models.DBInvoice):
    column_list = [models.DBInvoice.id, models.DBInvoice.number, models.DBInvoice.to_contact, models.DBInvoice.status]

class LineItemAdmin(ModelView, model=models.DBLineItem):
    column_list = [models.DBLineItem.id, models.DBLineItem.invoice_id, models.DBLineItem.description, models.DBLineItem.price]

class SettingsAdmin(ModelView, model=models.DBSettings):
    column_list = [models.DBSettings.id, models.DBSettings.key, models.DBSettings.value]

class ContactAdmin(ModelView, model=models.DBContact):
    column_list = [models.DBContact.id, models.DBContact.name, models.DBContact.email, models.DBContact.phone_number]

class AdminUserAdmin(ModelView, model=models.DBAdminUser):
    column_list = [models.DBAdminUser.id, models.DBAdminUser.username]

admin.add_view(InvoiceAdmin)
admin.add_view(LineItemAdmin)
admin.add_view(SettingsAdmin)
admin.add_view(ContactAdmin)
admin.add_view(AdminUserAdmin)

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, same_site="lax", https_only=True, max_age=86400)

oauth = OAuth()
oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile https://www.googleapis.com/auth/gmail.send'
    }
)

class LineItem(BaseModel):
    name: Optional[str] = ""
    description: str
    qty: float
    price: float
    disc: Optional[float] = 0.0
    account: Optional[str] = "200 - Sales"
    tax_rate: Optional[str] = "20% (VAT on Income)"

    class Config:
        from_attributes = True

class InvoiceCreate(BaseModel):
    contact: str
    email: Optional[str] = ""
    phone_number: Optional[str] = ""
    issue_date: str
    due_date: str
    invoice_number: Optional[str] = ""
    reference: Optional[str] = ""
    line_items: List[LineItem]
    tax_type: Optional[str] = "exclusive"
    status: Optional[str] = "Draft"
    currency: Optional[str] = ""

class SendInvoiceEmail(BaseModel):
    logo_data: Optional[str] = ""
    pdf_data: Optional[str] = ""

class TestEmail(BaseModel):
    to_email: str
    subject: str
    body: str

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def no_cache_html(request: Request, call_next):
    path = request.url.path
    if not (path.endswith(".html") or path == "/"):
        return await call_next(request)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response

# --- Client Registration & Auth ---

class ClientRegister(BaseModel):
    email: str
    password: str
    company_name: Optional[str] = ""
    contact_name: Optional[str] = ""

class ClientLogin(BaseModel):
    email: str
    password: str

class ClientOnboard(BaseModel):
    company_name: Optional[str] = ""
    contact_name: Optional[str] = ""
    phone_number: Optional[str] = ""
    address: Optional[str] = ""
    website: Optional[str] = ""
    abn: Optional[str] = ""
    industry: Optional[str] = ""
    logo_url: Optional[str] = ""

def get_client_user(request: Request, db: Session):
    client_id = request.session.get("client_id")
    if not client_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    client = db.query(models.DBClient).filter(models.DBClient.id == client_id).first()
    if not client or not client.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    return client

@app.post("/api/client/register")
def client_register(body: ClientRegister, db: Session = Depends(get_db)):
    existing = db.query(models.DBClient).filter(models.DBClient.email == body.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    client = models.DBClient(
        email=body.email,
        password_hash=hash_password(body.password),
        company_name=body.company_name,
        contact_name=body.contact_name,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return {"message": "Account created", "client_id": client.id}

@app.post("/api/client/login")
def client_login(body: ClientLogin, request: Request, db: Session = Depends(get_db)):
    client = db.query(models.DBClient).filter(models.DBClient.email == body.email).first()
    if not client or not verify_password(body.password, client.password_hash):
        log_login(db, None, body.email, "client", "password", request, "failed")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not client.is_active:
        log_login(db, client.id, body.email, "client", "password", request, "disabled")
        raise HTTPException(status_code=403, detail="Account disabled")
    request.session["client_id"] = client.id
    log_login(db, client.id, body.email, "client", "password", request, "success")
    return {"message": "Logged in", "is_onboarded": client.is_onboarded, "company_name": client.company_name}

@app.post("/api/client/logout")
def client_logout(request: Request):
    request.session.pop("client_id", None)
    return {"message": "Logged out"}

@app.get("/api/client/me")
def client_me(request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    return {
        "id": client.id,
        "email": client.email,
        "company_name": client.company_name,
        "contact_name": client.contact_name,
        "phone_number": client.phone_number,
        "logo_url": client.logo_url,
        "address": client.address,
        "website": client.website,
        "abn": client.abn,
        "industry": client.industry,
        "is_onboarded": client.is_onboarded,
        "created_at": client.created_at,
    }

@app.post("/api/client/onboard")
def client_onboard(body: ClientOnboard, request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    client.company_name = body.company_name or client.company_name
    client.contact_name = body.contact_name or client.contact_name
    client.phone_number = body.phone_number or client.phone_number
    client.address = body.address or client.address
    client.website = body.website or client.website
    client.abn = body.abn or client.abn
    client.industry = body.industry or client.industry
    if body.logo_url:
        client.logo_url = body.logo_url
    client.is_onboarded = True
    db.commit()
    return {"message": "Onboarding complete"}

@app.post("/api/client/logo")
def upload_logo(request: Request, db: Session = Depends(get_db)):
    import json
    client = get_client_user(request, db)
    return {"logo_url": client.logo_url or ""}

@app.get("/api/client/logo")
def get_logo(request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    return {"logo_url": client.logo_url or ""}

class LogoUpdate(BaseModel):
    logo_url: str = ""

@app.put("/api/client/logo")
def save_logo(body: LogoUpdate, request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    client.logo_url = body.logo_url
    db.commit()
    return {"message": "Logo saved"}

# --- Super Admin ---

def ensure_super_admin():
    with SessionLocal() as db:
        env_emails = [e.strip().lower() for e in os.getenv("SUPERADMIN_EMAILS", "hello@keyroutes.co").split(",") if e.strip()]
        existing_all = db.query(models.DBSuperAdmin).all()
        existing_emails = {e.email.strip().lower() for e in existing_all if e.email}
        for em in env_emails:
            if em not in existing_emails:
                db.add(models.DBSuperAdmin(username="superadmin", password_hash="", email=em))
                existing_emails.add(em)
        pwd = os.getenv("SUPERADMIN_PASSWORD", "")
        if pwd:
            for sa in db.query(models.DBSuperAdmin).all():
                sa.password_hash = hash_password(pwd)
        db.commit()
        logger.info("Super admin setup complete (%d admins)", len(env_emails))

@app.post("/api/superadmin/login")
def superadmin_login(request: Request, body: dict = None, db: Session = Depends(get_db)):
    body = body or {}
    identifier = (body.get("identifier") or body.get("username") or "").strip().lower()
    password = body.get("password", "")
    env_pwd = os.getenv("SUPERADMIN_PASSWORD", "")
    sa = None
    if identifier:
        sa = db.query(models.DBSuperAdmin).filter(
            (models.DBSuperAdmin.email == identifier) | (models.DBSuperAdmin.username == identifier)
        ).first()
    if sa:
        ok = False
        if sa.password_hash:
            ok = verify_password(password, sa.password_hash)
        elif env_pwd:
            ok = verify_password(password, hash_password(env_pwd))
        if ok:
            request.session['superadmin_id'] = sa.id
            log_login(db, None, identifier or sa.email, "superadmin", "password", request, "success")
            return {"ok": True, "username": sa.username, "email": sa.email}
    log_login(db, None, identifier or "superadmin", "superadmin", "password", request, "failed")
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.post("/api/superadmin/change-password")
def superadmin_change_password(request: Request, body: dict = None, db: Session = Depends(get_db)):
    sa_id = request.session.get("superadmin_id")
    if not sa_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    body = body or {}
    new_pwd = body.get("new_password", "")
    if len(new_pwd) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    admin = db.query(models.DBSuperAdmin).filter(models.DBSuperAdmin.id == sa_id).first()
    if not admin:
        raise HTTPException(status_code=401, detail="Not found")
    admin.password_hash = hash_password(new_pwd)
    db.commit()
    return {"message": "Password updated"}

@app.post("/api/superadmin/logout")
def superadmin_logout(request: Request):
    request.session.pop("superadmin_id", None)
    return {"message": "Logged out"}

@app.get("/api/superadmin/me")
def superadmin_me(request: Request, db: Session = Depends(get_db)):
    sa_id = request.session.get("superadmin_id")
    if not sa_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    admin = db.query(models.DBSuperAdmin).filter(models.DBSuperAdmin.id == sa_id).first()
    if not admin:
        raise HTTPException(status_code=401, detail="Not found")
    return {"username": admin.username, "email": admin.email}

from sqlalchemy import func

@app.get("/api/superadmin/clients")
def superadmin_clients(request: Request, db: Session = Depends(get_db)):
    sa_id = request.session.get("superadmin_id")
    if not sa_id:
        raise HTTPException(status_code=401, detail="Not authorized")
    results = (
        db.query(
            models.DBClient,
            func.count(models.DBInvoice.id).label('invoice_count'),
            func.count(func.nullif(models.DBInvoice.status, 'Paid')).label('unpaid_count'),
            func.coalesce(func.sum(func.nullif(models.DBInvoice.due, 0)), 0).label('outstanding')
        )
        .outerjoin(models.DBInvoice, models.DBInvoice.client_id == models.DBClient.id)
        .group_by(models.DBClient.id)
        .all()
    )
    return [{
        "id": c.id,
        "email": c.email,
        "company_name": c.company_name,
        "contact_name": c.contact_name,
        "phone_number": c.phone_number,
        "is_active": c.is_active,
        "is_onboarded": c.is_onboarded,
        "last_login": c.last_login or "",
        "login_count": c.login_count or 0,
        "created_at": c.created_at,
        "invoice_count": invoice_count,
        "paid_count": invoice_count - unpaid_count,
        "outstanding": round(float(outstanding), 2),
    } for c, invoice_count, unpaid_count, outstanding in results]

@app.get("/api/superadmin/insights")
def superadmin_insights(request: Request, db: Session = Depends(get_db)):
    sa_id = request.session.get("superadmin_id")
    if not sa_id:
        raise HTTPException(status_code=401, detail="Not authorized")
    total_clients = db.query(models.DBClient).count()
    active_clients = db.query(models.DBClient).filter(models.DBClient.is_active == True).count()
    onboarded = db.query(models.DBClient).filter(models.DBClient.is_onboarded == True).count()
    total_invoices = db.query(models.DBInvoice).count()
    total_revenue = db.query(func.coalesce(func.sum(models.DBInvoice.due), 0)).filter(models.DBInvoice.status == "Paid").scalar()
    total_outstanding = db.query(func.coalesce(func.sum(models.DBInvoice.due), 0)).filter(models.DBInvoice.status != "Paid").scalar()
    return {
        "total_clients": total_clients,
        "active_clients": active_clients,
        "onboarded_clients": onboarded,
        "total_invoices": total_invoices,
        "total_revenue": round(float(total_revenue), 2),
        "total_outstanding": round(float(total_outstanding), 2),
    }

@app.get("/api/superadmin/login-logs")
def superadmin_login_logs(request: Request, limit: int = 100, db: Session = Depends(get_db)):
    sa_id = request.session.get("superadmin_id")
    if not sa_id:
        raise HTTPException(status_code=401, detail="Not authorized")
    logs = db.query(models.DBClientLoginLog).order_by(models.DBClientLoginLog.created_at.desc()).limit(limit).all()
    return [{
        "id": l.id, "client_id": l.client_id, "email": l.email,
        "user_type": l.user_type, "login_type": l.login_type,
        "ip_address": l.ip_address, "device_info": l.device_info,
        "status": l.status, "created_at": l.created_at,
    } for l in logs]

@app.get("/api/superadmin/login-stats")
def superadmin_login_stats(request: Request, db: Session = Depends(get_db)):
    sa_id = request.session.get("superadmin_id")
    if not sa_id:
        raise HTTPException(status_code=401, detail="Not authorized")
    from datetime import timedelta
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    month_ago = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    total_logs = db.query(models.DBClientLoginLog).count()
    today_logs = db.query(models.DBClientLoginLog).filter(models.DBClientLoginLog.created_at.like(today + "%")).count()
    week_logs = db.query(models.DBClientLoginLog).filter(models.DBClientLoginLog.created_at >= week_ago).count()
    month_logs = db.query(models.DBClientLoginLog).filter(models.DBClientLoginLog.created_at >= month_ago).count()
    failed_logs = db.query(models.DBClientLoginLog).filter(models.DBClientLoginLog.status == "failed").count()
    google_logins = db.query(models.DBClientLoginLog).filter(models.DBClientLoginLog.login_type == "google").count()
    password_logins = db.query(models.DBClientLoginLog).filter(models.DBClientLoginLog.login_type == "password").count()
    clients_with_logins = db.query(models.DBClient).filter(models.DBClient.login_count > 0).count()
    never_logged_in = db.query(models.DBClient).filter(models.DBClient.login_count == 0).count()
    return {
        "total_logins": total_logs,
        "today_logins": today_logs,
        "week_logins": week_logs,
        "month_logins": month_logs,
        "failed_logins": failed_logs,
        "google_logins": google_logins,
        "password_logins": password_logins,
        "clients_with_logins": clients_with_logins,
        "clients_never_logged_in": never_logged_in,
    }

@app.put("/api/superadmin/clients/{client_id}/toggle")
def superadmin_toggle_client(client_id: int, request: Request, db: Session = Depends(get_db)):
    sa_id = request.session.get("superadmin_id")
    if not sa_id:
        raise HTTPException(status_code=401, detail="Not authorized")
    client = db.query(models.DBClient).filter(models.DBClient.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    client.is_active = not client.is_active
    log_audit(db, client.id, "client_" + ("enabled" if client.is_active else "disabled"), "client", client.id, client.company_name or client.email, "", request, user_type="superadmin", user_name="superadmin")
    db.commit()
    return {"message": "Client " + ("enabled" if client.is_active else "disabled"), "is_active": client.is_active}

@app.delete("/api/superadmin/clients/{client_id}")
def superadmin_delete_client(client_id: int, request: Request, db: Session = Depends(get_db)):
    sa_id = request.session.get("superadmin_id")
    if not sa_id:
        raise HTTPException(status_code=401, detail="Not authorized")
    client = db.query(models.DBClient).filter(models.DBClient.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    db.query(models.DBLineItem).filter(models.DBLineItem.invoice_id.in_(
        db.query(models.DBInvoice.id).filter(models.DBInvoice.client_id == client_id)
    )).delete(synchronize_session=False)
    db.query(models.DBInvoice).filter(models.DBInvoice.client_id == client_id).delete()
    db.query(models.DBContact).filter(models.DBContact.client_id == client_id).delete()
    db.query(models.DBSettings).filter(models.DBSettings.client_id == client_id).delete()
    db.delete(client)
    log_audit(db, client_id, "client_deleted", "client", client_id, "", "Client and all data deleted", request, user_type="superadmin", user_name="superadmin")
    db.commit()
    return {"message": "Client deleted"}

@app.post("/api/superadmin/impersonate/{client_id}")
def superadmin_impersonate(client_id: int, request: Request, db: Session = Depends(get_db)):
    sa_id = request.session.get("superadmin_id")
    if not sa_id:
        raise HTTPException(status_code=401, detail="Not authorized")
    client = db.query(models.DBClient).filter(models.DBClient.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if not client.is_active:
        raise HTTPException(status_code=400, detail="Client account is disabled")
    request.session['client_id'] = client.id
    log_audit(db, client.id, "impersonate", "client", client.id, client.company_name or client.email, "Super admin logged in as client", request, user_type="superadmin", user_name="superadmin")
    db.commit()
    return {"message": "Now acting as " + (client.company_name or client.email), "client_id": client.id}

@app.get("/api/superadmin/trends")
def superadmin_trends(request: Request, db: Session = Depends(get_db)):
    sa_id = request.session.get("superadmin_id")
    if not sa_id:
        raise HTTPException(status_code=401, detail="Not authorized")
    from datetime import timedelta
    from collections import defaultdict
    now = datetime.now()
    months = [(now - timedelta(days=30 * i)).strftime("%Y-%m") for i in range(5, -1, -1)]
    revenue_by_month = defaultdict(float)
    logins_by_month = defaultdict(int)
    for inv in db.query(models.DBInvoice).filter(models.DBInvoice.status == "Paid").all():
        m = inv.issue_date[:7] if inv.issue_date and len(inv.issue_date) >= 7 else None
        if m in months:
            revenue_by_month[m] += (inv.paid or 0)
    for l in db.query(models.DBClientLoginLog).filter(models.DBClientLoginLog.status == "success").all():
        m = l.created_at[:7] if l.created_at and len(l.created_at) >= 7 else None
        if m in months:
            logins_by_month[m] += 1
    return {
        "months": months,
        "revenue": [round(revenue_by_month.get(m, 0), 2) for m in months],
        "active_users": [logins_by_month.get(m, 0) for m in months],
        "total_revenue": round(sum(inv.paid or 0 for inv in db.query(models.DBInvoice).filter(models.DBInvoice.status == "Paid").all()), 2),
    }

@app.get("/api/superadmin/clients/{client_id}")
def superadmin_get_client(client_id: int, request: Request, db: Session = Depends(get_db)):
    sa_id = request.session.get("superadmin_id")
    if not sa_id:
        raise HTTPException(status_code=401, detail="Not authorized")
    client = db.query(models.DBClient).filter(models.DBClient.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    invoices = db.query(models.DBInvoice).filter(models.DBInvoice.client_id == client_id).all()
    return {
        "id": client.id,
        "email": client.email,
        "company_name": client.company_name,
        "contact_name": client.contact_name,
        "phone_number": client.phone_number,
        "address": client.address,
        "website": client.website,
        "abn": client.abn,
        "industry": client.industry,
        "is_active": client.is_active,
        "is_onboarded": client.is_onboarded,
        "created_at": client.created_at,
        "invoices": [{"number": i.number, "status": i.status, "due": i.due, "date": i.issue_date} for i in invoices],
    }

# --- Gmail API Helpers ---

def get_gmail_credentials(access_token: str = None, refresh_token: str = None):
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        logger.error("GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET not configured")
        return None
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret
    )
    try:
        if creds.expired or not creds.valid:
            creds.refresh(GoogleRequest())
    except Exception as e:
        logger.error(f"Failed to refresh Gmail credentials: {e}")
        return None
    return creds

def get_stored_refresh_token(db: Session, client_id: int = None):
    q = db.query(models.DBSettings).filter(models.DBSettings.key == "GOOGLE_REFRESH_TOKEN")
    if client_id:
        # Try client-specific token first
        setting = q.filter(models.DBSettings.client_id == client_id).first()
        if setting:
            return setting.value
    # Fallback to global token (no client_id) for backward compat
    setting = q.filter(models.DBSettings.client_id == None).first()
    if not setting:
        setting = q.first()
    return setting.value if setting else None

def validate_email_address(email: str) -> bool:
    import re as _re
    if not email or not isinstance(email, str):
        return False
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    return bool(_re.match(pattern, email.strip()))
def prepare_email_message(to_email, subject, body_text, html_body, from_email, logo_data="", pdf_bytes=None, pdf_filename="invoice.pdf"):
    """Build a properly structured MIME email with CID-embedded logo and PDF attachment."""
    import re as _re
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders as _encoders

    msg = MIMEMultipart('mixed')
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Reply-To'] = from_email
    msg['Date'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')
    msg['List-Unsubscribe'] = '<mailto:hello@keyroutes.co?subject=unsubscribe>'
    msg['List-Unsubscribe-Post'] = 'List-Unsubscribe=One-Click'

    alt_part = MIMEMultipart('alternative')
    alt_part.attach(MIMEText(body_text, 'plain', 'utf-8'))

    if html_body and logo_data:
        logo_cid = 'logo_' + uuid.uuid4().hex[:12]
        data_url_match = _re.match(r'^data:(image/\w+);base64,(.+)$', logo_data, _re.DOTALL)
        if data_url_match:
            img_mime = data_url_match.group(1)
            img_b64 = data_url_match.group(2)
            img_sub = img_mime.split('/')[1] if '/' in img_mime else 'png'
            if img_sub == 'jpeg':
                img_sub = 'jpg'
            img_bytes = base64.b64decode(img_b64)
            logo_part = MIMEBase('image', img_sub)
            logo_part.set_payload(img_bytes)
            _encoders.encode_base64(logo_part)
            logo_part.add_header('Content-ID', f'<{logo_cid}>')
            logo_part.add_header('Content-Disposition', 'inline', filename='logo.' + img_sub)
            msg.attach(logo_part)
            html_body = html_body.replace(logo_data, f'cid:{logo_cid}')
        elif logo_data.startswith('http'):
            pass
        else:
            pass

    alt_part.attach(MIMEText(html_body, 'html', 'utf-8'))
    msg.attach(alt_part)

    if pdf_bytes:
        pdf_part = MIMEBase('application', 'pdf')
        pdf_part.set_payload(pdf_bytes)
        _encoders.encode_base64(pdf_part)
        pdf_part.add_header('Content-Disposition', 'attachment', filename=pdf_filename)
        msg.attach(pdf_part)

    return msg.as_string()


def send_email_background(to_email: str, subject: str, body: str, from_email: str, html_body: str = None, pdf_b64: str = None, pdf_filename: str = "invoice.pdf", logo_data: str = "", client_id: int = None):
    pdf_bytes = None
    if pdf_b64:
        try:
            pdf_bytes = base64.b64decode(pdf_b64)
        except Exception as e:
            logger.error(f"Failed to decode PDF: {e}")

    raw_msg = prepare_email_message(to_email, subject, body, html_body or "", from_email, logo_data or "", pdf_bytes, pdf_filename)

    with SessionLocal() as db:
        refresh_token = get_stored_refresh_token(db, client_id=client_id)

    if not refresh_token:
        return False, "Gmail refresh token not configured"

    try:
        creds = get_gmail_credentials(access_token=None, refresh_token=refresh_token)
        service = build('gmail', 'v1', credentials=creds)
        encoded_message = base64.urlsafe_b64encode(raw_msg.encode('utf-8')).decode()
        send_result = service.users().messages().send(userId="me", body={'raw': encoded_message}).execute()
        logger.info(f"Email sent via Gmail API to {to_email} (ID: {send_result['id']})")
        return True, "Email sent via Gmail API"
    except Exception as e:
        logger.error(f"Gmail API failed: {e}")
        return False, f"Gmail API error: {str(e)}"


# --- API Endpoints ---

@app.get("/api/dashboard-summary")
def get_dashboard_summary(request: Request, db: Session = Depends(get_db)):
    from collections import defaultdict
    from datetime import datetime, timedelta

    client = get_client_user(request, db)
    all_invoices = db.query(models.DBInvoice).filter(models.DBInvoice.client_id == client.id).all()

    invoices_owed = sum(inv.due or 0 for inv in all_invoices if inv.status in ["Awaiting Payment", "Sent"])
    total_revenue = sum(inv.paid or 0 for inv in all_invoices)
    total_invoiced = sum((inv.paid or 0) + (inv.due or 0) for inv in all_invoices)
    paid_count = sum(1 for inv in all_invoices if inv.status == "Paid")
    pending_count = sum(1 for inv in all_invoices if inv.status in ["Awaiting Payment", "Sent"])
    draft_count = sum(1 for inv in all_invoices if inv.status == "Draft")

    months = []
    now = datetime.now()
    for i in range(5, -1, -1):
        d = now - timedelta(days=30 * i)
        months.append(d.strftime("%b %Y"))

    money_in = [0.0] * 6
    money_out = [0.0] * 6

    for inv in all_invoices:
        if not inv.issue_date:
            continue
        try:
            inv_date = datetime.strptime(inv.issue_date, "%Y-%m-%d")
        except (ValueError, TypeError):
            continue
        for i in range(6):
            d = now - timedelta(days=30 * (5 - i))
            month_start = d.replace(day=1)
            next_month = (month_start + timedelta(days=32)).replace(day=1)
            if month_start <= inv_date < next_month:
                if inv.status == "Paid":
                    money_in[i] += inv.paid or 0
                elif inv.status in ["Awaiting Payment", "Sent"]:
                    money_out[i] += inv.due or 0
                break

    short_months = [datetime.strptime(m, "%b %Y").strftime("%b") for m in months]

    return {
        "summary": {
            "total_invoiced": round(total_invoiced, 2),
            "total_revenue": round(total_revenue, 2),
            "invoices_owed": round(invoices_owed, 2),
            "paid_count": paid_count,
            "pending_count": pending_count,
            "draft_count": draft_count,
            "total_count": len(all_invoices)
        },
        "cash_flow": {
            "money_in": [round(x, 2) for x in money_in],
            "money_out": [round(x, 2) for x in money_out],
            "months": short_months
        }
    }

@app.get("/api/invoices")
def get_invoices(request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    invoices = db.query(models.DBInvoice).filter(models.DBInvoice.client_id == client.id).order_by(models.DBInvoice.id.desc()).all()
    return [{
        "number": inv.number,
        "ref": inv.ref,
        "to": inv.to_contact,
        "email": inv.email,
        "phone_number": inv.phone_number,
        "date": inv.issue_date,
        "due_date": inv.due_date,
        "paid": inv.paid,
        "due": inv.due,
        "status": inv.status,
        "sent": inv.sent,
        "tax_type": inv.tax_type,
        "currency": inv.currency or (client.currency if client else ""),
        "open_count": inv.open_count or 0,
        "last_opened": inv.last_opened or "",
    } for inv in invoices]

@app.get("/api/invoices/{number}")
def get_invoice(number: str, request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    inv = db.query(models.DBInvoice).filter(models.DBInvoice.number == number, models.DBInvoice.client_id == client.id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    settings_rows = db.query(models.DBSettings).filter(models.DBSettings.client_id == inv.client_id).all() if inv.client_id else []
    settings_map = {s.key: s.value for s in settings_rows}
    company = {
        "name": settings_map.get("company_name", "") or (client.company_name if client else ""),
        "email": settings_map.get("email", "") or (client.email if client else ""),
        "phone_number": settings_map.get("phone_number", "") or (client.phone_number if client else ""),
        "address": settings_map.get("company_address", "") or (client.address if client else ""),
        "website": settings_map.get("company_website", "") or (client.website if client else ""),
        "abn": settings_map.get("company_abn", "") or (client.abn if client else ""),
        "logo_url": client.logo_url if client else "",
    }
    return {
        "id": inv.id,
        "number": inv.number,
        "ref": inv.ref,
        "to": inv.to_contact,
        "email": inv.email,
        "phone_number": inv.phone_number,
        "date": inv.issue_date,
        "due_date": inv.due_date,
        "paid": inv.paid,
        "due": inv.due,
        "status": inv.status,
        "sent": inv.sent,
        "tax_type": inv.tax_type,
        "currency": inv.currency or (client.currency if client else ""),
        "tracking_id": inv.tracking_id,
        "open_count": inv.open_count or 0,
        "last_opened": inv.last_opened or "",
        "company": company,
        "line_items": [{
            "name": li.name or "",
            "description": li.description,
            "qty": li.qty,
            "price": li.price,
            "disc": li.disc,
            "account": li.account,
            "tax_rate": li.tax_rate
        } for li in inv.line_items]
    }

@app.get("/api/next-invoice-number")
def get_next_invoice_number(request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    invoices = db.query(models.DBInvoice.number).filter(models.DBInvoice.client_id == client.id).all()
    max_num = 0
    for inv in invoices:
        if inv.number and inv.number.startswith("INV-"):
            try:
                num = int(inv.number.split("-")[1])
                if num > max_num:
                    max_num = num
            except (IndexError, ValueError):
                pass
    return {"next_number": f"INV-{max_num + 1:04d}"}

@app.post("/api/invoices")
def create_invoice(invoice: InvoiceCreate, request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)

    subtotal = 0
    tax = 0
    for item in invoice.line_items:
        raw_amount = item.qty * item.price
        if item.disc and item.disc > 0:
            raw_amount = raw_amount * (1 - item.disc / 100)
        amount = raw_amount
        item_tax = 0
        if invoice.tax_type == 'exclusive':
            item_tax = amount * 0.20
            subtotal += amount
            tax += item_tax
        elif invoice.tax_type == 'inclusive':
            item_tax = amount - (amount / 1.20)
            subtotal_net = amount - item_tax
            subtotal += subtotal_net
            tax += item_tax
        else:
            subtotal += amount

    total = subtotal + tax

    # Auto-save contact (scoped to client)
    if invoice.contact and invoice.contact.strip():
        existing = db.query(models.DBContact).filter(models.DBContact.name == invoice.contact, models.DBContact.client_id == client.id).first()
        if existing:
            if invoice.email and not existing.email:
                existing.email = invoice.email
            if invoice.phone_number and not existing.phone_number:
                existing.phone_number = invoice.phone_number
        else:
            db.add(models.DBContact(name=invoice.contact, email=invoice.email or "", phone_number=invoice.phone_number or "", client_id=client.id))

    if invoice.invoice_number and invoice.invoice_number.strip() != "":
        number = invoice.invoice_number
    else:
        invoices = db.query(models.DBInvoice.number).filter(models.DBInvoice.client_id == client.id).all()
        max_num = 0
        for inv in invoices:
            if inv.number and inv.number.startswith("INV-"):
                try:
                    num = int(inv.number.split("-")[1])
                    if num > max_num:
                        max_num = num
                except (IndexError, ValueError):
                    pass
        number = f"INV-{max_num + 1:04d}"

    db_invoice = models.DBInvoice(
        client_id=client.id,
        number=number,
        ref=invoice.reference,
        to_contact=invoice.contact,
        email=invoice.email,
        phone_number=invoice.phone_number,
        issue_date=invoice.issue_date,
        due_date=invoice.due_date,
        paid=0.00,
        due=round(total, 2),
        status=invoice.status or "Draft",
        sent="",
        tax_type=invoice.tax_type,
        currency=(invoice.currency or "").upper() or (client.currency or "")
    )
    db.add(db_invoice)
    db.flush()

    for item in invoice.line_items:
        db_line_item = models.DBLineItem(
            invoice_id=db_invoice.id,
            name=item.name or "",
            description=item.description,
            qty=item.qty,
            price=item.price,
            disc=item.disc or 0.0,
            account=item.account,
            tax_rate=item.tax_rate
        )
        db.add(db_line_item)

    db.commit()
    db.refresh(db_invoice)
    log_audit(db, client.id, "invoice_created", "invoice", db_invoice.id, number, f"Total: {total:.2f}", request)
    db.commit()

    return get_invoice(number, request, db)

@app.post("/api/invoices/{number}/send")
def send_invoice_email(number: str, background_tasks: BackgroundTasks, request: Request, payload: Optional[SendInvoiceEmail] = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    if payload is None:
        payload = SendInvoiceEmail()
    inv = db.query(models.DBInvoice).filter(models.DBInvoice.number == number, models.DBInvoice.client_id == client.id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if not inv.email:
        raise HTTPException(status_code=400, detail="Invoice has no email address associated with it")
    if not validate_email_address(inv.email):
        raise HTTPException(status_code=400, detail=f"Invalid email address: {inv.email}")

    user = request.session.get('user', {})
    from_email = os.getenv("FROM_EMAIL", "hello@keyroutes.co")
    if not from_email:
        raise HTTPException(status_code=400, detail="No sender email configured.")

    settings_rows = db.query(models.DBSettings).filter(models.DBSettings.client_id == inv.client_id).all()
    settings_map = {s.key: s.value for s in settings_rows}
    inv_client = db.query(models.DBClient).filter(models.DBClient.id == inv.client_id).first() if inv.client_id else None
    company_name = settings_map.get("company_name", "") or (inv_client.company_name if inv_client else "") or "Accounting Platform"
    company_email = settings_map.get("email", "") or (inv_client.email if inv_client else "")
    company_phone = settings_map.get("phone_number", "") or (inv_client.phone_number if inv_client else "")
    company_address = settings_map.get("company_address", "") or (inv_client.address if inv_client else "")
    company_abn = settings_map.get("company_abn", "") or (inv_client.abn if inv_client else "")
    company_website = settings_map.get("company_website", "") or (inv_client.website if inv_client else "")

    cur = (inv.currency or settings_map.get("currency") or (inv_client.currency if inv_client else "") or "GBP").upper()
    cur_symbol = currency_symbol(cur)

    sender_name = os.getenv("FROM_NAME", "aniprotech")
    from_header = f"{sender_name} <{from_email}>"
    subject = f"Invoice {inv.number} from {sender_name}"

    logo_html = ""
    logo_data = payload.logo_data or ""
    if not logo_data and inv_client and inv_client.logo_url:
        logo_data = inv_client.logo_url
    if logo_data:
        logo_html = f'<div style="margin-bottom:24px;"><img src="{logo_data}" style="max-height:48px;max-width:200px;"></div>'

    line_items_html = ""
    if inv.line_items:
        rows = ""
        for li in inv.line_items:
            amount = li.qty * li.price
            disc_val = li.disc or 0
            if disc_val > 0:
                amount *= (1 - disc_val / 100)
            disc_html = f'<span style="display:inline-block;background:#fef3c7;color:#92400e;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:600;">{disc_val:g}% off</span>' if disc_val > 0 else ''
            rows += f'''
                <div style="padding:16px 20px;border-bottom:1px solid #f1f5f9;">
                  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px;">
                    <div style="font-size:15px;font-weight:700;color:#1e293b;">{li.name or 'Item'}</div>
                    <div style="font-size:16px;font-weight:800;color:#0f172a;">{cur_symbol}{amount:.2f}</div>
                  </div>
                  {f'<div style="font-size:13px;color:#64748b;margin-bottom:8px;word-wrap:break-word;">{li.description}</div>' if li.description else ''}
                  <div style="display:flex;gap:16px;flex-wrap:wrap;align-items:center;">
                    <span style="font-size:12px;color:#94a3b8;">Qty: <strong style="color:#475569;">{int(li.qty)}</strong></span>
                    <span style="font-size:12px;color:#94a3b8;">Price: <strong style="color:#475569;">{cur_symbol}{li.price:.2f}</strong></span>
                    {f'<span style="font-size:12px;color:#94a3b8;">Discount: {disc_html}</span>' if disc_val > 0 else ''}
                  </div>
                </div>'''

        line_items_html = f'''
            <div style="border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;margin-bottom:24px;">
              <div style="background-color:#f8fafc;padding:10px 20px;border-bottom:2px solid #e2e8f0;display:flex;justify-content:space-between;">
                <span style="font-size:11px;font-weight:700;text-transform:uppercase;color:#64748b;">Item</span>
                <span style="font-size:11px;font-weight:700;text-transform:uppercase;color:#64748b;">Amount</span>
              </div>
              {rows}
            </div>'''

    body = f"""Hello {inv.to_contact},

Please find the details of your invoice {inv.number} from {company_name or sender_name} below.

Invoice Number: {inv.number}
Issue Date: {inv.issue_date}
Due Date: {inv.due_date}

Line Items:
"""
    for li in inv.line_items:
        item_label = f"{li.name} - {li.description}" if li.name else li.description
        disc_text = f" (Disc: {li.disc}%)" if li.disc else ""
        body += f"  - {item_label} x{int(li.qty)} @ {cur_symbol}{li.price:.2f}{disc_text}\n"
    body += f"""
Total Amount Due: {cur_symbol}{inv.due:.2f}

Payment is due by {inv.due_date}. If you have any questions about this invoice, please reply to this email.

Thank you for your business!

Best regards,
{company_name or sender_name}
{company_address or ''}
{company_email or ''}
{company_phone or ''}

To unsubscribe from these emails, reply with 'unsubscribe' in the subject line."""

    html_body = f"""
    <!DOCTYPE html>
    <html>
      <body style="font-family: Arial, Helvetica, sans-serif; color: #1e293b; line-height: 1.6; margin: 0; padding: 0; background-color: #f1f5f9;">
        <div style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
          <div style="background: #ffffff; border-radius: 12px; overflow: hidden;">
            <!-- Header -->
            <div style="background-color: #0f172a; padding: 40px; text-align: center;">
              {logo_html}
              <h1 style="font-size: 32px; font-weight: 800; color: #ffffff; margin: 0 0 8px 0;">INVOICE</h1>
              <p style="font-size: 16px; color: #94a3b8; margin: 0; font-weight: 600;">{inv.number}</p>
              <div style="margin-top: 16px; display: inline-block; background-color: #0ea5e9; padding: 8px 20px; border-radius: 20px;">
                <span style="font-size: 14px; color: #ffffff; font-weight: 600;">Amount Due: {cur_symbol}{inv.due:.2f}</span>
              </div>
            </div>

            <!-- Company Details Bar -->
            {f'''
            <div style="background-color: #f8fafc; padding: 16px 40px; border-bottom: 1px solid #e2e8f0;">
              <div style="font-size: 13px; color: #475569;">
                <strong style="color: #1e293b;">{company_name}</strong>
                {f' &bull; {company_address}' if company_address else ''}
                {f' &bull; {company_email}' if company_email else ''}
                {f' &bull; {company_phone}' if company_phone else ''}
              </div>
            </div>
            ''' if company_name else ''}

            <!-- Body -->
            <div style="padding: 40px;">
              <p style="font-size: 16px; color: #1e293b; margin: 0 0 6px 0;">Hello <strong>{inv.to_contact}</strong>,</p>
              <p style="font-size: 14px; color: #64748b; margin: 0 0 32px 0;">Here's your invoice from <strong>{company_name or sender_name}</strong>. Please find the details below.</p>

              <!-- Invoice Details Cards -->
              <div style="margin-bottom: 32px;">
                <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse: collapse;">
                  <tr>
                    <td style="background-color: #f1f5f9; border-radius: 10px; padding: 16px; text-align: center; width: 33%;">
                      <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: #64748b; margin-bottom: 4px;">Issue Date</div>
                      <div style="font-size: 14px; font-weight: 600; color: #1e293b;">{inv.issue_date}</div>
                    </td>
                    <td style="width: 10px;"></td>
                    <td style="background-color: #f1f5f9; border-radius: 10px; padding: 16px; text-align: center; width: 33%;">
                      <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: #64748b; margin-bottom: 4px;">Due Date</div>
                      <div style="font-size: 14px; font-weight: 600; color: #1e293b;">{inv.due_date}</div>
                    </td>
                    <td style="width: 10px;"></td>
                    <td style="background-color: #f1f5f9; border-radius: 10px; padding: 16px; text-align: center; width: 33%;">
                      <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: #64748b; margin-bottom: 4px;">Invoice #</div>
                      <div style="font-size: 14px; font-weight: 600; color: #1e293b;">{inv.number}</div>
                    </td>
                  </tr>
                </table>
              </div>

              <!-- Line Items -->
              {line_items_html}

              <!-- Total -->
              <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse: collapse; margin-top: 24px;">
                <tr>
                  <td style="background-color: #0f172a; border-radius: 12px; padding: 24px; text-align: right;">
                    <div style="font-size: 13px; color: #94a3b8; margin-bottom: 4px;">TOTAL AMOUNT</div>
                    <div style="font-size: 32px; font-weight: 800; color: #ffffff;">{cur_symbol}{inv.due:.2f}</div>
                  </td>
                </tr>
              </table>

              <!-- Payment Note -->
              <div style="margin-top: 32px; padding: 20px; background-color: #fefce8; border-radius: 10px; border-left: 4px solid #fcd34d;">
                <p style="font-size: 13px; color: #854d0e; margin: 0;"><strong>Payment Terms:</strong> Please pay by {inv.due_date}. For any questions, reply to this email.</p>
              </div>

              <!-- View and Pay Online -->
              <p style="margin-top: 20px;"><a href="{request.base_url}login.html" style="color: #0ea5e9; font-size: 14px; font-weight: 600;">View and pay online &rarr;</a></p>
            </div>

            <!-- Footer -->
            <div style="padding: 24px 40px; background-color: #f8fafc; border-top: 1px solid #e2e8f0; text-align: center;">
              <p style="font-size: 13px; color: #94a3b8; margin: 0 0 4px 0;">Thank you for your business!</p>
              <p style="font-size: 12px; color: #64748b; margin: 0;">{sender_name}</p>
              {f'<p style="font-size:11px;color:#94a3b8;margin:4px 0 0 0;">{company_address}</p>' if company_address else ''}
              <p style="font-size: 11px; color: #94a3b8; margin: 12px 0 0 0;"><a href="mailto:hello@keyroutes.co?subject=unsubscribe" style="color: #94a3b8;">Unsubscribe</a> from these notifications</p>
            </div>
          </div>
        </div>
        <img src="{request.base_url}api/track/open/{inv.tracking_id}" width="1" height="1" style="display:none;" alt="">
      </body>
    </html>
    """

    pdf_b64 = payload.pdf_data if payload.pdf_data else None
    pdf_filename = f"{inv.number}.pdf" if pdf_b64 else "invoice.pdf"

    background_tasks.add_task(send_email_background, inv.email, subject, body, from_header, html_body, pdf_b64, pdf_filename, logo_data, client_id=client.id)

    inv.status = "Sent"
    inv.sent = datetime.now().strftime("%Y-%m-%d")
    log_audit(db, client.id, "invoice_sent", "invoice", inv.id, inv.number, f"Sent to {inv.email}", request)
    db.commit()

    return {"message": "Email sending initiated via Gmail API", "status": "Sent", "sent_date": inv.sent}

def send_whatsapp_background(phone_number: str, message: str):
    with SessionLocal() as db:
        setting_id = db.query(models.DBSettings).filter(models.DBSettings.key == "WHATSAPP_PHONE_NUMBER_ID").first()
        phone_number_id = setting_id.value if setting_id else os.getenv("WHATSAPP_PHONE_NUMBER_ID")
        setting_token = db.query(models.DBSettings).filter(models.DBSettings.key == "WHATSAPP_ACCESS_TOKEN").first()
        access_token = setting_token.value if setting_token else os.getenv("WHATSAPP_ACCESS_TOKEN")

    if not phone_number_id or not access_token:
        logger.warning("WhatsApp credentials missing")
        return

    url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": phone_number, "type": "text", "text": {"body": message}}

    try:
        response = httpx.post(url, headers=headers, json=payload)
        response.raise_for_status()
        logger.info(f"WhatsApp message sent to {phone_number}")
    except Exception as e:
        logger.error(f"Failed to send WhatsApp: {str(e)}")

@app.post("/api/invoices/{number}/send-whatsapp")
def send_invoice_whatsapp(number: str, background_tasks: BackgroundTasks, request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    inv = db.query(models.DBInvoice).filter(models.DBInvoice.number == number, models.DBInvoice.client_id == client.id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if not inv.phone_number:
        raise HTTPException(status_code=400, detail="Invoice has no phone number")

    inv_client = db.query(models.DBClient).filter(models.DBClient.id == inv.client_id).first() if inv.client_id else None
    ws_cur = (inv.currency or (inv_client.currency if inv_client else "") or "GBP").upper()
    ws_sym = currency_symbol(ws_cur)
    message = f"Hello {inv.to_contact},\n\nPlease find the details of your invoice {inv.number} below:\n\nTotal Due: {ws_sym}{inv.due:.2f}\nDue Date: {inv.due_date}\n\nThank you for your business!"
    background_tasks.add_task(send_whatsapp_background, inv.phone_number, message)

    if inv.status == "Draft":
        inv.status = "Sent"
        inv.sent = datetime.now().strftime("%Y-%m-%d")
        db.commit()

    return {"message": "WhatsApp sending initiated", "status": inv.status}

# --- Email Open Tracking ---

TRACKING_PIXEL = bytes([
    0x47, 0x49, 0x46, 0x38, 0x39, 0x61, 0x01, 0x00, 0x01, 0x00, 0x80, 0x00,
    0x00, 0xff, 0xff, 0xff, 0x00, 0x00, 0x00, 0x21, 0xf9, 0x04, 0x01, 0x00,
    0x00, 0x00, 0x00, 0x2c, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00,
    0x00, 0x02, 0x02, 0x44, 0x01, 0x00, 0x3b
])

@app.get("/api/track/open/{tracking_id}")
def track_email_open(tracking_id: str, db: Session = Depends(get_db)):
    inv = db.query(models.DBInvoice).filter(models.DBInvoice.tracking_id == tracking_id).first()
    if inv:
        inv.open_count = (inv.open_count or 0) + 1
        inv.last_opened = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.commit()
    return StreamingResponse(iter([TRACKING_PIXEL]), media_type="image/gif", headers={
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
    })

@app.get("/api/invoices/{number}/open-stats")
def get_open_stats(number: str, request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    inv = db.query(models.DBInvoice).filter(models.DBInvoice.number == number, models.DBInvoice.client_id == client.id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return {
        "number": inv.number,
        "tracking_id": inv.tracking_id,
        "open_count": inv.open_count or 0,
        "last_opened": inv.last_opened or "",
    }

# --- Contacts API ---

@app.get("/api/contacts/search")
def search_contacts(request: Request, q: str = "", db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    query = db.query(models.DBContact).filter(models.DBContact.client_id == client.id)
    if q:
        from sqlalchemy import or_
        query = query.filter(or_(
            models.DBContact.name.ilike(f"%{q}%"),
            models.DBContact.email.ilike(f"%{q}%")
        ))
    contacts = query.limit(10).all()
    return [{"id": c.id, "name": c.name, "email": c.email or "", "phone_number": c.phone_number or ""} for c in contacts]

@app.get("/api/contacts")
def list_contacts(request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    contacts = db.query(models.DBContact).filter(models.DBContact.client_id == client.id).all()
    return [{"id": c.id, "name": c.name, "email": c.email or "", "phone_number": c.phone_number or ""} for c in contacts]

@app.post("/api/contacts")
def create_contact(request: Request, body: dict = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    if not body or not body.get("name"):
        raise HTTPException(status_code=400, detail="Name required")
    existing = db.query(models.DBContact).filter(models.DBContact.name == body["name"], models.DBContact.client_id == client.id).first()
    if existing:
        if body.get("email") and not existing.email:
            existing.email = body["email"]
        if body.get("phone_number") and not existing.phone_number:
            existing.phone_number = body["phone_number"]
        db.commit()
        return {"id": existing.id, "name": existing.name, "email": existing.email or "", "phone_number": existing.phone_number or ""}
    contact = models.DBContact(name=body["name"], email=body.get("email", ""), phone_number=body.get("phone_number", ""), client_id=client.id)
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return {"id": contact.id, "name": contact.name, "email": contact.email or "", "phone_number": contact.phone_number or ""}


@app.put("/api/contacts/{contact_id}")
def update_contact(contact_id: int, request: Request, body: dict = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    contact = db.query(models.DBContact).filter(models.DBContact.id == contact_id, models.DBContact.client_id == client.id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    if body:
        if "name" in body: contact.name = body["name"]
        if "email" in body: contact.email = body["email"]
        if "phone_number" in body: contact.phone_number = body["phone_number"]
        db.commit()
        db.refresh(contact)
    return {"id": contact.id, "name": contact.name, "email": contact.email or "", "phone_number": contact.phone_number or ""}


@app.delete("/api/contacts/{contact_id}")
def delete_contact(contact_id: int, request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    contact = db.query(models.DBContact).filter(models.DBContact.id == contact_id, models.DBContact.client_id == client.id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    db.delete(contact)
    db.commit()
    return {"ok": True}


# --- Bills API ---

@app.get("/api/bills")
def list_bills(request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    bills = db.query(models.DBBill).filter(models.DBBill.client_id == client.id).order_by(models.DBBill.id.desc()).all()
    return [{"id": b.id, "number": b.number, "vendor_name": b.vendor_name, "vendor_email": b.vendor_email or "",
             "issue_date": b.issue_date or "", "due_date": b.due_date or "", "amount": b.amount or 0.0,
             "tax_amount": b.tax_amount or 0.0, "total": b.total or 0.0, "amount_paid": b.amount_paid or 0.0,
             "status": b.status or "Draft", "category": b.category or "general", "reference": b.reference or "",
             "notes": b.notes or ""} for b in bills]


@app.post("/api/bills")
def create_bill(request: Request, body: dict = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    if not body:
        raise HTTPException(status_code=400, detail="Bill data required")
    existing = db.query(models.DBBill).filter(models.DBBill.number == body.get("number", ""), models.DBBill.client_id == client.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Bill number already exists")
    bill = models.DBBill(
        client_id=client.id,
        number=body.get("number", ""),
        vendor_name=body.get("vendor_name", ""),
        vendor_email=body.get("vendor_email", ""),
        issue_date=body.get("issue_date", ""),
        due_date=body.get("due_date", ""),
        amount=body.get("amount", 0.0),
        tax_amount=body.get("tax_amount", 0.0),
        total=body.get("total", 0.0),
        status=body.get("status", "Draft"),
        category=body.get("category", "general"),
        reference=body.get("reference", ""),
        notes=body.get("notes", ""),
    )
    db.add(bill)
    db.commit()
    db.refresh(bill)
    log_audit(db, client.id, "bill_created", "bill", bill.id, bill.number, f"Vendor: {bill.vendor_name}, Total: {bill.total}", request)
    db.commit()
    return {"id": bill.id, "number": bill.number}


@app.get("/api/bills/{bill_id}")
def get_bill(bill_id: int, request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    bill = db.query(models.DBBill).filter(models.DBBill.id == bill_id, models.DBBill.client_id == client.id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    line_items = db.query(models.DBBillLineItem).filter(models.DBBillLineItem.bill_id == bill.id).all()
    return {
        "id": bill.id, "number": bill.number, "vendor_name": bill.vendor_name, "vendor_email": bill.vendor_email or "",
        "issue_date": bill.issue_date or "", "due_date": bill.due_date or "", "amount": bill.amount or 0.0,
        "tax_amount": bill.tax_amount or 0.0, "total": bill.total or 0.0, "amount_paid": bill.amount_paid or 0.0,
        "status": bill.status or "Draft", "category": bill.category or "general", "reference": bill.reference or "",
        "notes": bill.notes or "",
        "line_items": [{"id": li.id, "description": li.description or "", "qty": li.qty or 1, "price": li.price or 0, "tax_rate": li.tax_rate or "20%"} for li in line_items]
    }


@app.put("/api/bills/{bill_id}")
def update_bill(bill_id: int, request: Request, body: dict = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    bill = db.query(models.DBBill).filter(models.DBBill.id == bill_id, models.DBBill.client_id == client.id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    if body:
        for field in ["number", "vendor_name", "vendor_email", "issue_date", "due_date", "amount", "tax_amount", "total", "amount_paid", "status", "category", "reference", "notes"]:
            if field in body:
                setattr(bill, field, body[field])
        db.commit()
        db.refresh(bill)
    return {"id": bill.id, "number": bill.number}


@app.delete("/api/bills/{bill_id}")
def delete_bill(bill_id: int, request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    bill = db.query(models.DBBill).filter(models.DBBill.id == bill_id, models.DBBill.client_id == client.id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    db.query(models.DBBillLineItem).filter(models.DBBillLineItem.bill_id == bill.id).delete()
    log_audit(db, client.id, "bill_deleted", "bill", bill.id, bill.number, "", request)
    db.delete(bill)
    db.commit()
    return {"ok": True}


@app.post("/api/bills/{bill_id}/pay")
def mark_bill_paid(bill_id: int, request: Request, body: dict = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    bill = db.query(models.DBBill).filter(models.DBBill.id == bill_id, models.DBBill.client_id == client.id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    bill.amount_paid = bill.total or bill.amount or 0.0
    bill.status = "Paid"
    log_audit(db, client.id, "bill_paid", "bill", bill.id, bill.number, f"Amount: {bill.amount_paid}", request)
    db.commit()
    return {"ok": True, "status": "Paid"}


@app.get("/api/next-bill-number")
def next_bill_number(request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    last = db.query(models.DBBill).filter(models.DBBill.client_id == client.id).order_by(models.DBBill.id.desc()).first()
    if last and last.number:
        try:
            num = int(last.number.replace("BILL-", "").replace("BILL", ""))
            return {"number": f"BILL-{num + 1:04d}"}
        except (ValueError, TypeError):
            pass
    return {"number": "BILL-0001"}


@app.get("/api/reports/profit-loss")
def profit_loss_report(request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    invoices = db.query(models.DBInvoice).filter(models.DBInvoice.client_id == client.id).all()
    bills = db.query(models.DBBill).filter(models.DBBill.client_id == client.id).all()
    monthly_revenue = {}
    monthly_expenses = {}
    for inv in invoices:
        m = inv.issue_date[:7] if inv.issue_date and len(inv.issue_date) >= 7 else "Unknown"
        monthly_revenue[m] = monthly_revenue.get(m, 0) + (inv.paid or 0)
    for b in bills:
        m = b.issue_date[:7] if b.issue_date and len(b.issue_date) >= 7 else "Unknown"
        monthly_expenses[m] = monthly_expenses.get(m, 0) + (b.total or 0)
    all_months = sorted(set(list(monthly_revenue.keys()) + list(monthly_expenses.keys())))
    total_revenue = sum(monthly_revenue.values())
    total_expenses = sum(monthly_expenses.values())
    return {
        "months": all_months,
        "revenue": [monthly_revenue.get(m, 0) for m in all_months],
        "expenses": [monthly_expenses.get(m, 0) for m in all_months],
        "profit": [monthly_revenue.get(m, 0) - monthly_expenses.get(m, 0) for m in all_months],
        "total_revenue": total_revenue,
        "total_expenses": total_expenses,
        "net_profit": total_revenue - total_expenses,
    }


@app.get("/api/reports/balance-sheet")
def balance_sheet_report(request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    invoices = db.query(models.DBInvoice).filter(models.DBInvoice.client_id == client.id).all()
    bills = db.query(models.DBBill).filter(models.DBBill.client_id == client.id).all()
    total_invoiced = sum(inv.paid or 0 for inv in invoices)
    outstanding = sum(inv.due or 0 for inv in invoices if inv.status != "Paid")
    total_billed = sum(b.total or 0 for b in bills)
    bills_paid = sum(b.amount_paid or 0 for b in bills)
    bills_unpaid = sum((b.total or 0) - (b.amount_paid or 0) for b in bills)
    return {
        "assets": {"cash_collected": total_invoiced, "accounts_receivable": outstanding},
        "liabilities": {"accounts_payable": bills_unpaid},
        "equity": {"retained_earnings": total_invoiced - bills_paid},
        "total_assets": total_invoiced + outstanding,
        "total_liabilities": bills_unpaid,
        "total_equity": total_invoiced - bills_paid,
    }


@app.get("/api/reports/cash-summary")
def cash_summary_report(request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    invoices = db.query(models.DBInvoice).filter(models.DBInvoice.client_id == client.id).all()
    bills = db.query(models.DBBill).filter(models.DBBill.client_id == client.id).all()
    monthly_in = {}
    monthly_out = {}
    for inv in invoices:
        m = inv.issue_date[:7] if inv.issue_date and len(inv.issue_date) >= 7 else "Unknown"
        monthly_in[m] = monthly_in.get(m, 0) + (inv.paid or 0)
    for b in bills:
        m = b.issue_date[:7] if b.issue_date and len(b.issue_date) >= 7 else "Unknown"
        monthly_out[m] = monthly_out.get(m, 0) + (b.amount_paid or 0)
    all_months = sorted(set(list(monthly_in.keys()) + list(monthly_out.keys())))
    return {
        "months": all_months,
        "money_in": [monthly_in.get(m, 0) for m in all_months],
        "money_out": [monthly_out.get(m, 0) for m in all_months],
        "net_cash": [monthly_in.get(m, 0) - monthly_out.get(m, 0) for m in all_months],
    }
@app.get("/api/auth/login")
async def login(request: Request, role: str = "client"):
    request.session['oauth_role'] = role
    redirect_uri = str(request.url_for('auth_callback'))
    if redirect_uri.startswith('http://') and 'localhost' not in redirect_uri:
        redirect_uri = redirect_uri.replace('http://', 'https://', 1)
    return await oauth.google.authorize_redirect(request, redirect_uri, access_type='offline', prompt='consent')

@app.get("/api/auth/callback")
async def auth_callback(request: Request, db: Session = Depends(get_db)):
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        logger.error(f"Google token exchange failed: {e}")
        return RedirectResponse(url="/login.html?error=auth_failed")
    user = token.get('userinfo')
    access_token = token.get('access_token')
    refresh_token = token.get('refresh_token')
    oauth_role = request.session.pop('oauth_role', 'client')

    try:
        if user:
            request.session['user'] = dict(user)
            request.session['access_token'] = access_token
            if refresh_token:
                request.session['refresh_token'] = refresh_token

            google_email = user.get('email', '')

            if oauth_role == 'superadmin' and google_email:
                sa_user = db.query(models.DBSuperAdmin).filter(models.DBSuperAdmin.email == google_email).first()
                if sa_user:
                    request.session['superadmin_id'] = sa_user.id
                    log_login(db, None, google_email, "superadmin", "google", request, "success")
                    return RedirectResponse(url="/superadmin.html")
                else:
                    log_login(db, None, google_email, "superadmin", "google", request, "failed")
                    return RedirectResponse(url="/superadmin-login.html?error=not_admin")

            if google_email:
                sa_check = db.query(models.DBSuperAdmin).filter(models.DBSuperAdmin.email == google_email).first()
                if sa_check:
                    return RedirectResponse(url="/superadmin-login.html")
                existing_client = db.query(models.DBClient).filter(models.DBClient.email == google_email).first()
                if existing_client:
                    client_id = existing_client.id
                    request.session['client_id'] = client_id
                    log_login(db, client_id, google_email, "client", "google", request, "success")
                else:
                    new_client = models.DBClient(
                        email=google_email,
                        password_hash=hash_password(secrets.token_hex(16)),
                        company_name=user.get('name', ''),
                        contact_name=user.get('name', ''),
                        is_onboarded=False,
                    )
                    db.add(new_client)
                    db.flush()
                    client_id = new_client.id
                    request.session['client_id'] = client_id
                    log_login(db, client_id, google_email, "client", "google", request, "success")

                # Save refresh token per-client
                if refresh_token and client_id:
                    try:
                        setting = db.query(models.DBSettings).filter(
                            models.DBSettings.key == "GOOGLE_REFRESH_TOKEN",
                            models.DBSettings.client_id == client_id
                        ).first()
                        if not setting:
                            setting = models.DBSettings(key="GOOGLE_REFRESH_TOKEN", value=refresh_token, client_id=client_id)
                            db.add(setting)
                        else:
                            setting.value = refresh_token
                        db.commit()
                    except Exception as e:
                        logger.error(f"Failed to save refresh token: {e}")

                if existing_client:
                    if existing_client.is_onboarded:
                        return RedirectResponse(url="/app.html")
                    else:
                        return RedirectResponse(url="/onboard.html")
                else:
                    return RedirectResponse(url="/onboard.html")
    except Exception as e:
        logger.error(f"Callback processing failed: {e}")
        return RedirectResponse(url="/login.html?error=callback_failed")

    return RedirectResponse(url="/app.html")

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

@app.get("/api/auth/me")
def get_current_user(request: Request):
    user = request.session.get('user')
    if user:
        return {"user": user}
    return JSONResponse(status_code=401, content={"error": "Not authenticated"})

@app.get("/api/auth/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")

@app.get("/api/gmail/status")
def gmail_status(request: Request, db: Session = Depends(get_db)):
    user = request.session.get('user')
    client_id = request.session.get('client_id')
    refresh_token = get_stored_refresh_token(db, client_id=client_id)
    # Try to get the authorized Gmail email from the refresh token owner
    gmail_email = None
    if refresh_token:
        try:
            creds = get_gmail_credentials(access_token=None, refresh_token=refresh_token)
            if creds and creds.valid:
                service = build('gmail', 'v1', credentials=creds)
                profile = service.users().getProfile(userId="me").execute()
                gmail_email = profile.get("emailAddress")
        except Exception:
            pass
    return {
        "logged_in": bool(user),
        "user_email": user.get('email') if user else None,
        "user_name": user.get('name') if user else None,
        "refresh_token_stored": bool(refresh_token),
        "gmail_ready": bool(refresh_token),
        "gmail_authorized_email": gmail_email
    }

@app.post("/api/gmail/disconnect")
def disconnect_gmail(request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    setting = db.query(models.DBSettings).filter(
        models.DBSettings.key == "GOOGLE_REFRESH_TOKEN",
        models.DBSettings.client_id == client.id
    ).first()
    if setting:
        db.delete(setting)
        db.commit()
    return {"ok": True, "message": "Gmail disconnected. Re-authorize with your Google account."}

# --- Test Email Endpoint (for demos) ---

@app.post("/api/send-test-email")
def send_test_email(test: TestEmail, background_tasks: BackgroundTasks, request: Request, db: Session = Depends(get_db)):
    from_email = os.getenv("FROM_EMAIL", "hello@keyroutes.co")
    sender_name = os.getenv("FROM_NAME", "aniprotech")
    from_header = f"{sender_name} <{from_email}>"

    background_tasks.add_task(send_email_background, test.to_email, test.subject, test.body, from_header)
    return {"message": f"Email queued for delivery to {test.to_email}"}

# --- Invoice Management ---

@app.delete("/api/invoices/{number}")
def delete_invoice(number: str, request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    inv = db.query(models.DBInvoice).filter(models.DBInvoice.number == number, models.DBInvoice.client_id == client.id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    db.query(models.DBLineItem).filter(models.DBLineItem.invoice_id == inv.id).delete()
    log_audit(db, client.id, "invoice_deleted", "invoice", inv.id, inv.number, f"Contact: {inv.to_contact}", request)
    db.delete(inv)
    db.commit()
    return {"message": "Invoice deleted successfully"}

@app.post("/api/invoices/{number}/mark-paid")
def mark_invoice_paid(number: str, request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    inv = db.query(models.DBInvoice).filter(models.DBInvoice.number == number, models.DBInvoice.client_id == client.id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    inv.status = "Paid"
    inv.paid = inv.due
    inv.due = 0.0
    log_audit(db, client.id, "invoice_marked_paid", "invoice", inv.id, inv.number, f"Amount: {inv.paid}", request)
    db.commit()
    return {"message": "Invoice marked as paid", "status": "Paid"}

# --- Settings API ---

@app.get("/api/settings")
def get_settings(request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    settings = db.query(models.DBSettings).filter(models.DBSettings.client_id == client.id).all()
    return {s.key: s.value for s in settings}

@app.post("/api/settings")
def save_settings(request: Request, body: dict = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    if body:
        for key, val in body.items():
            setting = db.query(models.DBSettings).filter(models.DBSettings.key == key, models.DBSettings.client_id == client.id).first()
            if setting:
                setting.value = str(val)
            else:
                setting = models.DBSettings(key=key, value=str(val), client_id=client.id)
                db.add(setting)
    db.commit()
    return {"message": "Settings saved"}

@app.get("/api/audit-logs")
def get_audit_logs(request: Request, limit: int = 100, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    logs = db.query(models.DBAuditLog).filter(
        models.DBAuditLog.client_id == client.id
    ).order_by(models.DBAuditLog.created_at.desc()).limit(limit).all()
    return [{
        "id": l.id, "user_type": l.user_type, "user_name": l.user_name,
        "action": l.action, "entity_type": l.entity_type, "entity_id": l.entity_id,
        "entity_name": l.entity_name, "details": l.details, "ip_address": l.ip_address,
        "created_at": l.created_at,
    } for l in logs]

@app.get("/api/my/login-history")
def my_login_history(request: Request, limit: int = 50, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    logs = db.query(models.DBClientLoginLog).filter(
        models.DBClientLoginLog.client_id == client.id
    ).order_by(models.DBClientLoginLog.created_at.desc()).limit(limit).all()
    return [{
        "id": l.id, "email": l.email, "login_type": l.login_type,
        "ip_address": l.ip_address, "device_info": l.device_info,
        "status": l.status, "created_at": l.created_at,
    } for l in logs]

# ============================================================================
# HR MODULE - Departments, Employees, Payroll, Onboarding
# ============================================================================

from sqlalchemy import func as sqlfunc, or_

class DepartmentCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    color: Optional[str] = "#00f0ff"
    icon: Optional[str] = "building"

class EmployeeCreate(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = ""
    address: Optional[str] = ""
    department_id: Optional[int] = None
    reports_to: Optional[int] = None
    job_title: Optional[str] = ""
    role: Optional[str] = "employee"
    employment_type: Optional[str] = "full_time"
    pay_frequency: Optional[str] = "monthly"
    salary: Optional[float] = 0.0
    hourly_rate: Optional[float] = 0.0
    tax_rate: Optional[float] = 0.0
    deductions: Optional[float] = 0.0
    allowances: Optional[float] = 0.0
    bonus: Optional[float] = 0.0
    bank_name: Optional[str] = ""
    bank_account: Optional[str] = ""
    tax_id: Optional[str] = ""
    emergency_contact: Optional[str] = ""
    emergency_phone: Optional[str] = ""
    start_date: Optional[str] = ""
    employee_id: Optional[str] = ""
    password: Optional[str] = ""

class PayslipCreate(BaseModel):
    employee_id: int
    period_start: str
    period_end: str
    pay_date: str
    hours_worked: Optional[float] = 0.0
    overtime_hours: Optional[float] = 0.0
    overtime_rate: Optional[float] = 0.0
    basic_salary: Optional[float] = 0.0
    overtime_pay: Optional[float] = 0.0
    bonus: Optional[float] = 0.0
    allowances: Optional[float] = 0.0
    tax_amount: Optional[float] = 0.0
    insurance: Optional[float] = 0.0
    retirement: Optional[float] = 0.0
    other_deductions: Optional[float] = 0.0
    notes: Optional[str] = ""

# --- Departments API ---

@app.get("/api/departments")
def get_departments(request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    depts = db.query(models.DBDepartment).filter(models.DBDepartment.client_id == client.id).all()
    result = []
    for d in depts:
        employees = db.query(models.DBEmployee).filter(models.DBEmployee.department_id == d.id).all()
        emp_list = [{"id": e.id, "name": (e.first_name + " " + e.last_name).strip(), "job_title": e.job_title or "", "email": e.email or ""} for e in employees]
        result.append({
            "id": d.id, "name": d.name, "description": d.description,
            "color": d.color or "#00f0ff", "icon": d.icon or "building",
            "employee_count": len(employees), "employees": emp_list, "created_at": d.created_at,
        })
    return result

@app.get("/api/departments/{dept_id}")
def get_department(dept_id: int, request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    d = db.query(models.DBDepartment).filter(models.DBDepartment.id == dept_id, models.DBDepartment.client_id == client.id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Department not found")
    employees = db.query(models.DBEmployee).filter(models.DBEmployee.department_id == d.id).all()
    emp_list = [{"id": e.id, "name": (e.first_name + " " + e.last_name).strip(), "job_title": e.job_title or "", "email": e.email or "", "status": e.status or ""} for e in employees]
    return {
        "id": d.id, "name": d.name, "description": d.description,
        "color": d.color or "#00f0ff", "icon": d.icon or "building",
        "employee_count": len(employees), "employees": emp_list, "created_at": d.created_at,
    }

@app.post("/api/departments")
def create_department(request: Request, body: DepartmentCreate, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    existing = db.query(models.DBDepartment).filter(
        models.DBDepartment.name == body.name, models.DBDepartment.client_id == client.id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Department already exists")
    dept = models.DBDepartment(name=body.name, description=body.description, color=body.color, icon=body.icon, client_id=client.id)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return {"id": dept.id, "name": dept.name, "description": dept.description, "color": dept.color, "icon": dept.icon, "employee_count": 0}

@app.put("/api/departments/{dept_id}")
def update_department(dept_id: int, request: Request, body: DepartmentCreate, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    dept = db.query(models.DBDepartment).filter(models.DBDepartment.id == dept_id, models.DBDepartment.client_id == client.id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    dept.name = body.name
    dept.description = body.description
    dept.color = body.color
    dept.icon = body.icon
    db.commit()
    return {"id": dept.id, "name": dept.name, "description": dept.description, "color": dept.color, "icon": dept.icon}

@app.delete("/api/departments/{dept_id}")
def delete_department(dept_id: int, request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    dept = db.query(models.DBDepartment).filter(models.DBDepartment.id == dept_id, models.DBDepartment.client_id == client.id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    db.query(models.DBEmployee).filter(models.DBEmployee.department_id == dept_id).update({"department_id": None})
    db.delete(dept)
    db.commit()
    return {"message": "Department deleted"}

# --- Employees API ---

@app.get("/api/employees")
def get_employees(request: Request, q: str = "", status: str = "", db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    query = db.query(models.DBEmployee).filter(models.DBEmployee.client_id == client.id)
    if status:
        query = query.filter(models.DBEmployee.status == status)
    if q:
        query = query.filter(or_(
            models.DBEmployee.first_name.ilike(f"%{q}%"),
            models.DBEmployee.last_name.ilike(f"%{q}%"),
            models.DBEmployee.email.ilike(f"%{q}%"),
            models.DBEmployee.job_title.ilike(f"%{q}%"),
        ))
    employees = query.order_by(models.DBEmployee.created_at.desc()).all()
    result = []
    for e in employees:
        dept_name = ""
        if e.department_id:
            dept = db.query(models.DBDepartment).filter(models.DBDepartment.id == e.department_id).first()
            dept_name = dept.name if dept else ""
        manager_name = ""
        if e.reports_to:
            mgr = db.query(models.DBEmployee).filter(models.DBEmployee.id == e.reports_to).first()
            manager_name = f"{mgr.first_name} {mgr.last_name}" if mgr else ""
        result.append({
            "id": e.id, "employee_id": e.employee_id,
            "first_name": e.first_name, "last_name": e.last_name,
            "full_name": f"{e.first_name} {e.last_name}",
            "email": e.email, "phone": e.phone,
            "department_id": e.department_id, "department_name": dept_name,
            "reports_to": e.reports_to, "manager_name": manager_name,
            "job_title": e.job_title, "role": e.role,
            "employment_type": e.employment_type,
            "pay_frequency": e.pay_frequency,
            "salary": e.salary, "hourly_rate": e.hourly_rate,
            "tax_rate": e.tax_rate, "deductions": e.deductions,
            "allowances": e.allowances, "bonus": e.bonus,
            "bank_name": e.bank_name, "bank_account": e.bank_account, "tax_id": e.tax_id,
            "emergency_contact": e.emergency_contact, "emergency_phone": e.emergency_phone,
            "start_date": e.start_date, "end_date": e.end_date,
            "status": e.status, "onboarding_complete": e.onboarding_complete,
            "offboarding_complete": e.offboarding_complete,
            "created_at": e.created_at,
        })
    return result

@app.post("/api/employees")
def create_employee(request: Request, body: EmployeeCreate, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    existing = db.query(models.DBEmployee).filter(
        models.DBEmployee.email == body.email, models.DBEmployee.client_id == client.id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Employee with this email already exists")

    max_num = db.query(sqlfunc.coalesce(sqlfunc.max(models.DBEmployee.id), 0)).filter(models.DBEmployee.client_id == client.id).scalar()
    emp_number = f"EMP-{max_num + 1:04d}" if not body.employee_id else body.employee_id

    emp = models.DBEmployee(
        client_id=client.id, employee_id=emp_number,
        first_name=body.first_name, last_name=body.last_name,
        email=body.email, phone=body.phone, address=body.address,
        department_id=body.department_id, reports_to=body.reports_to,
        job_title=body.job_title, role=body.role,
        employment_type=body.employment_type, pay_frequency=body.pay_frequency,
        salary=body.salary, hourly_rate=body.hourly_rate,
        tax_rate=body.tax_rate, deductions=body.deductions,
        allowances=body.allowances, bonus=body.bonus,
        bank_name=body.bank_name, bank_account=body.bank_account,
        tax_id=body.tax_id,
        emergency_contact=body.emergency_contact, emergency_phone=body.emergency_phone,
        start_date=body.start_date, status="onboarding",
        password_hash=models.hash_password(body.password) if body.password else "",
    )
    db.add(emp)
    db.flush()

    # Create default onboarding checklist
    default_items = [
        ("Sign employment contract", "Legal", "HR"),
        ("Provide government-issued ID", "Legal", "HR"),
        ("Submit bank details for payroll", "Finance", "Finance"),
        ("Provide emergency contact information", "General", "HR"),
        ("Company policy acknowledgment", "Compliance", "HR"),
        ("IT equipment setup", "Technical", "IT"),
        ("Email and system access setup", "Technical", "IT"),
        ("Introduction to team members", "Social", "Manager"),
        ("Complete tax withholding forms (W-4)", "Finance", "Finance"),
        ("Review employee handbook", "Compliance", "HR"),
    ]
    for title, category, assignee in default_items:
        db.add(models.DBOnboardingItem(
            client_id=client.id, employee_id=emp.id,
            title=title, category=category, assigned_to=assignee,
        ))

    if body.department_id:
        pending_goals = db.query(models.DBDepartmentGoal).filter(
            models.DBDepartmentGoal.department_id == body.department_id,
            models.DBDepartmentGoal.client_id == client.id,
            models.DBDepartmentGoal.is_assigned == False,
        ).all()
        for dg in pending_goals:
            goal = models.DBEmployeeGoal(
                client_id=client.id, employee_id=emp.id, department_id=body.department_id,
                title=dg.title, description=dg.description,
                target_value=dg.target_value, current_value=0,
                unit=dg.unit, category=dg.category,
                priority=dg.priority, start_date=dg.start_date,
                due_date=dg.due_date, created_by="HR",
            )
            db.add(goal)
            note = models.DBNotification(
                client_id=client.id, employee_id=emp.id,
                title="New Goal Assigned", message=f"HR has assigned you a department goal: {dg.title}",
                type="info",
            )
            db.add(note)
            dg.is_assigned = True

    db.commit()
    db.refresh(emp)
    log_audit(db, client.id, "employee_created", "employee", emp.id, f"{emp.first_name} {emp.last_name}", f"Dept: {body.department_id or 'None'}", request)
    db.commit()
    return {
        "id": emp.id, "employee_id": emp.employee_id,
        "first_name": emp.first_name, "last_name": emp.last_name,
        "message": "Employee created. Onboarding checklist generated.",
    }

@app.get("/api/employees/{emp_id}")
def get_employee(emp_id: int, request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == emp_id, models.DBEmployee.client_id == client.id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    dept_name = ""
    if emp.department_id:
        dept = db.query(models.DBDepartment).filter(models.DBDepartment.id == emp.department_id).first()
        dept_name = dept.name if dept else ""
    manager_name = ""
    if emp.reports_to:
        mgr = db.query(models.DBEmployee).filter(models.DBEmployee.id == emp.reports_to).first()
        manager_name = f"{mgr.first_name} {mgr.last_name}" if mgr else ""
    payslips = db.query(models.DBPayslip).filter(models.DBPayslip.employee_id == emp.id).order_by(models.DBPayslip.created_at.desc()).limit(12).all()
    onboarding = db.query(models.DBOnboardingItem).filter(models.DBOnboardingItem.employee_id == emp.id).all()
    return {
        "id": emp.id, "employee_id": emp.employee_id,
        "first_name": emp.first_name, "last_name": emp.last_name,
        "full_name": f"{emp.first_name} {emp.last_name}",
        "email": emp.email, "phone": emp.phone, "address": emp.address,
        "department_id": emp.department_id, "department_name": dept_name,
        "reports_to": emp.reports_to, "manager_name": manager_name,
        "job_title": emp.job_title, "role": emp.role,
        "employment_type": emp.employment_type, "pay_frequency": emp.pay_frequency,
        "salary": emp.salary, "hourly_rate": emp.hourly_rate,
        "tax_rate": emp.tax_rate, "deductions": emp.deductions,
        "allowances": emp.allowances, "bonus": emp.bonus,
        "bank_name": emp.bank_name, "bank_account": emp.bank_account, "tax_id": emp.tax_id,
        "emergency_contact": emp.emergency_contact, "emergency_phone": emp.emergency_phone,
        "start_date": emp.start_date, "end_date": emp.end_date,
        "status": emp.status, "onboarding_complete": emp.onboarding_complete,
        "offboarding_complete": emp.offboarding_complete,
        "created_at": emp.created_at,
        "payslips": [{"id": p.id, "number": p.number, "period_start": p.period_start, "period_end": p.period_end,
                       "pay_date": p.pay_date, "gross_pay": p.gross_pay, "net_pay": p.net_pay,
                       "status": p.status, "sent": p.sent} for p in payslips],
        "onboarding_items": [{"id": o.id, "title": o.title, "description": o.description,
                               "category": o.category, "is_completed": o.is_completed,
                               "completed_at": o.completed_at, "assigned_to": o.assigned_to,
                               "due_date": o.due_date} for o in onboarding],
    }

@app.put("/api/employees/{emp_id}")
def update_employee(emp_id: int, request: Request, body: dict = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == emp_id, models.DBEmployee.client_id == client.id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    old_dept = emp.department_id
    if body:
        for key, val in body.items():
            if hasattr(emp, key) and key not in ("id", "client_id", "created_at", "password_hash"):
                setattr(emp, key, val)
    new_dept = emp.department_id
    if new_dept and new_dept != old_dept:
        pending_goals = db.query(models.DBDepartmentGoal).filter(
            models.DBDepartmentGoal.department_id == new_dept,
            models.DBDepartmentGoal.client_id == client.id,
            models.DBDepartmentGoal.is_assigned == False,
        ).all()
        for dg in pending_goals:
            goal = models.DBEmployeeGoal(
                client_id=client.id, employee_id=emp.id, department_id=new_dept,
                title=dg.title, description=dg.description,
                target_value=dg.target_value, current_value=0,
                unit=dg.unit, category=dg.category,
                priority=dg.priority, start_date=dg.start_date,
                due_date=dg.due_date, created_by="HR",
            )
            db.add(goal)
            note = models.DBNotification(
                client_id=client.id, employee_id=emp.id,
                title="New Goal Assigned", message=f"HR has assigned you a department goal: {dg.title}",
                type="info",
            )
            db.add(note)
            dg.is_assigned = True
    log_audit(db, client.id, "employee_updated", "employee", emp.id, f"{emp.first_name} {emp.last_name}", f"Fields: {', '.join(body.keys()) if body else 'none'}", request)
    db.commit()
    return {"message": "Employee updated"}

@app.delete("/api/employees/{emp_id}")
def delete_employee(emp_id: int, request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == emp_id, models.DBEmployee.client_id == client.id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    emp_name = f"{emp.first_name} {emp.last_name}"
    db.query(models.DBOnboardingItem).filter(models.DBOnboardingItem.employee_id == emp_id).delete()
    db.query(models.DBPayslip).filter(models.DBPayslip.employee_id == emp_id).delete()
    log_audit(db, client.id, "employee_deleted", "employee", emp.id, emp_name, "", request)
    db.delete(emp)
    db.commit()
    return {"message": "Employee deleted"}

@app.post("/api/employees/{emp_id}/reset-password")
def reset_employee_password(emp_id: int, body: dict, request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == emp_id, models.DBEmployee.client_id == client.id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    new_pass = body.get("password", "")
    if not new_pass or len(new_pass) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")
    emp.password_hash = models.hash_password(new_pass)
    db.commit()
    return {"message": "Password updated successfully"}

@app.post("/api/employees/{emp_id}/offboard")
def start_offboarding(emp_id: int, request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == emp_id, models.DBEmployee.client_id == client.id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    emp.status = "offboarding"
    db.commit()
    return {"message": "Offboarding started"}

@app.post("/api/employees/{emp_id}/complete-offboard")
def complete_offboarding(emp_id: int, request: Request, body: dict = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == emp_id, models.DBEmployee.client_id == client.id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    end_date = body.get("end_date", "") if body else ""
    emp.status = "terminated"
    emp.end_date = end_date
    emp.offboarding_complete = True
    db.commit()
    return {"message": "Employee offboarded"}

# --- Onboarding API ---

@app.get("/api/onboarding/hub")
def get_onboarding_hub(request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    employees = db.query(models.DBEmployee).filter(
        models.DBEmployee.client_id == client.id,
        models.DBEmployee.status.in_(["onboarding", "active"])
    ).all()
    result = []
    for emp in employees:
        items = db.query(models.DBOnboardingItem).filter(models.DBOnboardingItem.employee_id == emp.id).all()
        completed = sum(1 for i in items if i.is_completed)
        overdue = 0
        today = datetime.now().strftime("%Y-%m-%d")
        for i in items:
            if not i.is_completed and i.due_date and i.due_date < today:
                overdue += 1
        result.append({
            "id": emp.id, "name": (emp.first_name + " " + emp.last_name).strip(),
            "job_title": emp.job_title or "", "department": emp.department.name if emp.department else "",
            "status": emp.status or "", "start_date": emp.start_date or "",
            "total": len(items), "completed": completed,
            "progress": round((completed / len(items)) * 100) if items else 0,
            "overdue": overdue,
        })
    result.sort(key=lambda x: (-x["overdue"], x["progress"]))
    return result

@app.get("/api/employees/{emp_id}/onboarding")
def get_onboarding(emp_id: int, request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == emp_id, models.DBEmployee.client_id == client.id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    items = db.query(models.DBOnboardingItem).filter(models.DBOnboardingItem.employee_id == emp_id).order_by(models.DBOnboardingItem.sort_order).all()
    completed = sum(1 for i in items if i.is_completed)
    return {
        "total": len(items), "completed": completed,
        "progress": round((completed / len(items)) * 100) if items else 0,
        "items": [{"id": i.id, "title": i.title, "description": i.description,
                    "category": i.category, "is_completed": i.is_completed,
                    "completed_at": i.completed_at, "assigned_to": i.assigned_to,
                    "due_date": i.due_date, "sort_order": i.sort_order} for i in items],
    }

@app.put("/api/onboarding/{item_id}")
def update_onboarding_item(item_id: int, request: Request, body: dict = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    item = db.query(models.DBOnboardingItem).filter(models.DBOnboardingItem.id == item_id, models.DBOnboardingItem.client_id == client.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if body:
        if "is_completed" in body:
            item.is_completed = body["is_completed"]
            if body["is_completed"]:
                item.completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            else:
                item.completed_at = ""
        if "title" in body:
            item.title = body["title"]
        if "description" in body:
            item.description = body["description"]
        if "category" in body:
            item.category = body["category"]
        if "assigned_to" in body:
            item.assigned_to = body["assigned_to"]
        if "due_date" in body:
            item.due_date = body["due_date"]
    db.commit()
    emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == item.employee_id).first()
    if emp:
        all_items = db.query(models.DBOnboardingItem).filter(models.DBOnboardingItem.employee_id == emp.id).all()
        if all_items and all(i.is_completed for i in all_items):
            emp.onboarding_complete = True
            emp.status = "active"
            db.commit()
    return {"message": "Item updated"}

@app.delete("/api/onboarding/{item_id}")
def delete_onboarding_item(item_id: int, request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    item = db.query(models.DBOnboardingItem).filter(models.DBOnboardingItem.id == item_id, models.DBOnboardingItem.client_id == client.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()
    return {"message": "Item deleted"}

@app.post("/api/employees/{emp_id}/onboarding")
def add_onboarding_item(emp_id: int, request: Request, body: dict = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == emp_id, models.DBEmployee.client_id == client.id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    max_order = db.query(func.max(models.DBOnboardingItem.sort_order)).filter(models.DBOnboardingItem.employee_id == emp_id).scalar() or 0
    item = models.DBOnboardingItem(
        client_id=client.id, employee_id=emp_id,
        title=body.get("title", ""), description=body.get("description", ""),
        category=body.get("category", "general"), assigned_to=body.get("assigned_to", ""),
        due_date=body.get("due_date", ""), sort_order=max_order + 1,
    )
    db.add(item)
    db.commit()
    return {"id": item.id, "title": item.title, "message": "Item added"}

@app.post("/api/employees/{emp_id}/onboarding/bulk")
def bulk_add_onboarding(emp_id: int, request: Request, body: dict = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == emp_id, models.DBEmployee.client_id == client.id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    items = body.get("items", []) if body else []
    max_order = db.query(func.max(models.DBOnboardingItem.sort_order)).filter(models.DBOnboardingItem.employee_id == emp_id).scalar() or 0
    added = []
    for i, item_data in enumerate(items):
        oitem = models.DBOnboardingItem(
            client_id=client.id, employee_id=emp_id,
            title=item_data.get("title", ""), description=item_data.get("description", ""),
            category=item_data.get("category", "general"), assigned_to=item_data.get("assigned_to", ""),
            due_date=item_data.get("due_date", ""), sort_order=max_order + i + 1,
        )
        db.add(oitem)
        added.append(item_data.get("title", ""))
    db.commit()
    return {"added": len(added), "message": f"Added {len(added)} items"}

@app.post("/api/onboarding/apply-template")
def apply_onboarding_template(request: Request, body: dict = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    emp_ids = body.get("employee_ids", []) if body else []
    template_items = body.get("items", []) if body else []
    count = 0
    for emp_id in emp_ids:
        emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == emp_id, models.DBEmployee.client_id == client.id).first()
        if not emp:
            continue
        max_order = db.query(func.max(models.DBOnboardingItem.sort_order)).filter(models.DBOnboardingItem.employee_id == emp_id).scalar() or 0
        for i, item_data in enumerate(template_items):
            db.add(models.DBOnboardingItem(
                client_id=client.id, employee_id=emp_id,
                title=item_data.get("title", ""), description=item_data.get("description", ""),
                category=item_data.get("category", "general"), assigned_to=item_data.get("assigned_to", ""),
                due_date=item_data.get("due_date", ""), sort_order=max_order + i + 1,
            ))
            count += 1
    db.commit()
    return {"added": count, "message": f"Added {count} items to {len(emp_ids)} employees"}

@app.get("/api/onboarding/templates")
def get_onboarding_templates(request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    templates = db.query(models.DBOnboardingTemplate).filter(models.DBOnboardingTemplate.client_id == client.id).all()
    return [{"id": t.id, "name": t.name, "items": json.loads(t.items_json) if t.items_json else [], "created_at": t.created_at} for t in templates]

@app.post("/api/onboarding/templates")
def create_onboarding_template(request: Request, body: dict = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    if not body or not body.get("name"):
        raise HTTPException(status_code=400, detail="Name required")
    template = models.DBOnboardingTemplate(
        client_id=client.id, name=body["name"],
        items_json=json.dumps(body.get("items", [])),
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return {"id": template.id, "name": template.name, "message": "Template created"}

@app.delete("/api/onboarding/templates/{template_id}")
def delete_onboarding_template(template_id: int, request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    template = db.query(models.DBOnboardingTemplate).filter(models.DBOnboardingTemplate.id == template_id, models.DBOnboardingTemplate.client_id == client.id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(template)
    db.commit()
    return {"message": "Template deleted"}

# --- Payroll API ---

@app.get("/api/payslips")
def get_payslips(request: Request, status: str = "", db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    query = db.query(models.DBPayslip).filter(models.DBPayslip.client_id == client.id)
    if status:
        query = query.filter(models.DBPayslip.status == status)
    payslips = query.order_by(models.DBPayslip.created_at.desc()).all()
    result = []
    for p in payslips:
        emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == p.employee_id).first()
        result.append({
            "id": p.id, "number": p.number,
            "employee_id": p.employee_id,
            "employee_name": f"{emp.first_name} {emp.last_name}" if emp else "",
            "employee_email": emp.email if emp else "",
            "period_start": p.period_start, "period_end": p.period_end,
            "pay_date": p.pay_date, "gross_pay": p.gross_pay,
            "tax_amount": p.tax_amount, "total_deductions": p.total_deductions,
            "net_pay": p.net_pay, "status": p.status, "sent": p.sent,
            "created_at": p.created_at,
        })
    return result

@app.get("/api/employees/{emp_id}/pay-details")
def get_employee_pay_details(emp_id: int, request: Request, period_start: str = "", period_end: str = "", db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == emp_id, models.DBEmployee.client_id == client.id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    hours_worked = 0.0
    if period_start and period_end:
        records = db.query(models.DBAttendance).filter(
            models.DBAttendance.employee_id == emp_id,
            models.DBAttendance.client_id == client.id,
            models.DBAttendance.date >= period_start,
            models.DBAttendance.date <= period_end,
        ).all()
        for r in records:
            hours_worked += r.total_hours or 0
        hours_worked = round(hours_worked, 2)

    overtime_hours = 0.0
    if period_start and period_end:
        ot_logs = db.query(models.DBOvertimeLog).filter(
            models.DBOvertimeLog.employee_id == emp_id,
            models.DBOvertimeLog.client_id == client.id,
            models.DBOvertimeLog.date >= period_start,
            models.DBOvertimeLog.date <= period_end,
            models.DBOvertimeLog.status == "announced",
        ).all()
        for log in ot_logs:
            overtime_hours += log.hours or 0
        overtime_hours = round(overtime_hours, 2)

    ot_rate = emp.hourly_rate or 0.0
    if ot_rate == 0 and emp.salary > 0:
        ot_rate = round(emp.salary / 160 * 1.5, 2)

    basic = emp.salary or 0.0
    ot_pay = round(overtime_hours * ot_rate, 2) if overtime_hours > 0 else 0
    bonus = emp.bonus or 0.0
    allowances = emp.allowances or 0.0
    gross = basic + ot_pay + bonus + allowances
    tax_rate = emp.tax_rate or 0.0
    tax_amount = round(gross * (tax_rate / 100), 2) if tax_rate > 0 else 0
    deductions = emp.deductions or 0.0
    total_deductions = tax_amount + deductions
    net_pay = round(gross - total_deductions, 2)

    return {
        "employee_id": emp.id,
        "full_name": f"{emp.first_name} {emp.last_name}",
        "employee_id_code": emp.employee_id,
        "job_title": emp.job_title,
        "pay_frequency": emp.pay_frequency,
        "bank_name": emp.bank_name,
        "bank_account": emp.bank_account,
        "tax_id": emp.tax_id,
        "salary": basic,
        "hourly_rate": emp.hourly_rate or 0.0,
        "tax_rate": tax_rate,
        "deductions": deductions,
        "allowances": allowances,
        "bonus": bonus,
        "hours_worked": hours_worked,
        "overtime_hours": overtime_hours,
        "overtime_rate": ot_rate,
        "overtime_pay": ot_pay,
        "gross_pay": round(gross, 2),
        "tax_amount": tax_amount,
        "total_deductions": round(total_deductions, 2),
        "net_pay": net_pay,
    }

@app.post("/api/payslips")
def create_payslip(request: Request, body: PayslipCreate, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == body.employee_id, models.DBEmployee.client_id == client.id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    ps_count = db.query(models.DBPayslip).filter(models.DBPayslip.client_id == client.id).count()
    ps_number = f"PS-{ps_count + 1:04d}"

    basic = body.basic_salary if body.basic_salary > 0 else emp.salary
    ot_pay = body.overtime_hours * body.overtime_rate if body.overtime_hours > 0 else 0
    gross = basic + ot_pay + body.bonus + body.allowances
    tax = body.tax_amount if body.tax_amount > 0 else round(gross * (emp.tax_rate / 100), 2) if emp.tax_rate > 0 else 0
    total_deductions = tax + body.insurance + body.retirement + body.other_deductions + emp.deductions
    net = round(gross - total_deductions, 2)

    ps = models.DBPayslip(
        client_id=client.id, employee_id=body.employee_id, number=ps_number,
        period_start=body.period_start, period_end=body.period_end, pay_date=body.pay_date,
        hours_worked=body.hours_worked, overtime_hours=body.overtime_hours,
        overtime_rate=body.overtime_rate,
        basic_salary=basic, overtime_pay=ot_pay, bonus=body.bonus, allowances=body.allowances,
        gross_pay=round(gross, 2),
        tax_amount=round(tax, 2), insurance=body.insurance, retirement=body.retirement,
        other_deductions=body.other_deductions,
        total_deductions=round(total_deductions, 2), net_pay=net,
        status="Draft", notes=body.notes,
    )
    db.add(ps)
    db.commit()
    db.refresh(ps)
    return {"id": ps.id, "number": ps.number, "gross_pay": ps.gross_pay, "net_pay": ps.net_pay, "message": "Payslip created"}

@app.get("/api/payslips/{ps_id}")
def get_payslip(ps_id: int, request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    ps = db.query(models.DBPayslip).filter(models.DBPayslip.id == ps_id, models.DBPayslip.client_id == client.id).first()
    if not ps:
        raise HTTPException(status_code=404, detail="Payslip not found")
    emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == ps.employee_id).first()
    settings_rows = db.query(models.DBSettings).filter(models.DBSettings.client_id == client.id).all()
    settings_map = {s.key: s.value for s in settings_rows}
    return {
        "id": ps.id, "number": ps.number,
        "employee_id": ps.employee_id,
        "employee": {
            "full_name": f"{emp.first_name} {emp.last_name}" if emp else "",
            "employee_id": emp.employee_id if emp else "",
            "email": emp.email if emp else "",
            "job_title": emp.job_title if emp else "",
            "department_name": "", "bank_name": emp.bank_name if emp else "",
            "bank_account": emp.bank_account if emp else "", "tax_id": emp.tax_id if emp else "",
            "pay_frequency": emp.pay_frequency if emp else "",
        } if emp else {},
        "period_start": ps.period_start, "period_end": ps.period_end, "pay_date": ps.pay_date,
        "hours_worked": ps.hours_worked, "overtime_hours": ps.overtime_hours, "overtime_rate": ps.overtime_rate,
        "basic_salary": ps.basic_salary, "overtime_pay": ps.overtime_pay,
        "bonus": ps.bonus, "allowances": ps.allowances, "gross_pay": ps.gross_pay,
        "tax_amount": ps.tax_amount, "insurance": ps.insurance, "retirement": ps.retirement,
        "other_deductions": ps.other_deductions, "total_deductions": ps.total_deductions,
        "net_pay": ps.net_pay, "status": ps.status, "sent": ps.sent, "notes": ps.notes,
        "company": {
            "name": settings_map.get("company_name", "") or (client.company_name or ""),
            "address": settings_map.get("company_address", "") or (client.address or ""),
            "email": settings_map.get("email", "") or (client.email or ""),
            "phone": settings_map.get("phone_number", "") or (client.phone_number or ""),
            "abn": settings_map.get("company_abn", "") or (client.abn or ""),
            "logo_url": client.logo_url or "",
        },
    }

@app.put("/api/payslips/{ps_id}")
def update_payslip(ps_id: int, request: Request, body: dict = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    ps = db.query(models.DBPayslip).filter(models.DBPayslip.id == ps_id, models.DBPayslip.client_id == client.id).first()
    if not ps:
        raise HTTPException(status_code=404, detail="Payslip not found")
    if body:
        for key, val in body.items():
            if hasattr(ps, key) and key not in ("id", "client_id", "created_at", "tracking_id", "net_pay", "gross_pay", "employee_id", "number"):
                setattr(ps, key, val)
    db.commit()
    return {"message": "Payslip updated"}

@app.post("/api/payslips/{ps_id}/mark-paid")
def mark_payslip_paid(ps_id: int, request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    ps = db.query(models.DBPayslip).filter(models.DBPayslip.id == ps_id, models.DBPayslip.client_id == client.id).first()
    if not ps:
        raise HTTPException(status_code=404, detail="Payslip not found")
    ps.status = "Paid"
    ps.pay_date = ps.pay_date or datetime.now().strftime("%Y-%m-%d")
    log_audit(db, client.id, "payslip_marked_paid", "payslip", ps.id, ps.number, f"Net: {ps.net_pay}", request)
    db.commit()
    return {"message": "Payslip marked as paid"}

@app.delete("/api/payslips/{ps_id}")
def delete_payslip(ps_id: int, request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    ps = db.query(models.DBPayslip).filter(models.DBPayslip.id == ps_id, models.DBPayslip.client_id == client.id).first()
    if not ps:
        raise HTTPException(status_code=404, detail="Payslip not found")
    db.delete(ps)
    db.commit()
    return {"message": "Payslip deleted"}

@app.post("/api/payslips/{ps_id}/send")
def send_payslip_email(ps_id: int, request: Request, background_tasks: BackgroundTasks, payload: Optional[SendInvoiceEmail] = None, db: Session = Depends(get_db)):
    if payload is None:
        payload = SendInvoiceEmail()
    client = get_client_user(request, db)
    ps = db.query(models.DBPayslip).filter(models.DBPayslip.id == ps_id, models.DBPayslip.client_id == client.id).first()
    if not ps:
        raise HTTPException(status_code=404, detail="Payslip not found")
    emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == ps.employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    if not emp.email or not validate_email_address(emp.email):
        raise HTTPException(status_code=400, detail=f"Invalid employee email address")

    settings_rows = db.query(models.DBSettings).filter(models.DBSettings.client_id == client.id).all()
    settings_map = {s.key: s.value for s in settings_rows}
    company_name = settings_map.get("company_name", "") or client.company_name or "aniprotech"
    company_email = settings_map.get("email", "") or client.email or ""
    company_phone = settings_map.get("phone_number", "") or client.phone_number or ""
    company_address = settings_map.get("company_address", "") or client.address or ""

    from_email = os.getenv("FROM_EMAIL", "hello@keyroutes.co")
    sender_name = os.getenv("FROM_NAME", "aniprotech")
    from_header = f"{sender_name} <{from_email}>"
    subject = f"Payslip {ps.number} from {company_name}"

    logo_data = client.logo_url or ""
    logo_html = f'<div style="margin-bottom:24px;"><img src="{logo_data}" style="max-height:48px;max-width:200px;"></div>' if logo_data else ""

    body_text = f"""Hello {emp.first_name},

Please find your payslip {ps.number} for the period {ps.period_start} to {ps.period_end}.

Pay Date: {ps.pay_date}
Gross Pay: \u00a3{ps.gross_pay:.2f}
Tax: \u00a3{ps.tax_amount:.2f}
Total Deductions: \u00a3{ps.total_deductions:.2f}
Net Pay: \u00a3{ps.net_pay:.2f}

Best regards,
{company_name}
{company_address}
{company_email}
{company_phone}"""

    html_body = f"""<!DOCTYPE html>
<html><body style="font-family:Arial,Helvetica,sans-serif;color:#1e293b;margin:0;padding:0;background-color:#f1f5f9;">
<div style="max-width:600px;margin:0 auto;padding:40px 20px;">
<div style="background:#fff;border-radius:12px;overflow:hidden;">
<div style="background-color:#0f172a;padding:40px;text-align:center;">
{logo_html}
<h1 style="font-size:32px;font-weight:800;color:#fff;margin:0 0 8px 0;">PAYSLIP</h1>
<p style="font-size:16px;color:#94a3b8;margin:0;">{ps.number}</p>
<div style="margin-top:16px;display:inline-block;background-color:#0ea5e9;padding:8px 20px;border-radius:20px;">
<span style="font-size:14px;color:#fff;font-weight:600;">Net Pay: &pound;{ps.net_pay:.2f}</span>
</div>
</div>
<div style="background-color:#f8fafc;padding:16px 40px;border-bottom:1px solid #e2e8f0;">
<div style="font-size:13px;color:#475569;"><strong style="color:#1e293b;">{company_name}</strong>{f' &bull; {company_address}' if company_address else ''}{f' &bull; {company_email}' if company_email else ''}</div>
</div>
<div style="padding:40px;">
<p style="font-size:16px;color:#1e293b;margin:0 0 6px 0;">Hello <strong>{emp.first_name}</strong>,</p>
<p style="font-size:14px;color:#64748b;margin:0 0 24px 0;">Here's your payslip from <strong>{company_name}</strong> for the period {ps.period_start} to {ps.period_end}.</p>
<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin-bottom:24px;">
<tr>
<td style="background-color:#f1f5f9;border-radius:10px;padding:16px;text-align:center;width:33%;">
<div style="font-size:11px;font-weight:700;text-transform:uppercase;color:#64748b;margin-bottom:4px;">Period Start</div>
<div style="font-size:14px;font-weight:600;">{ps.period_start}</div>
</td>
<td style="width:10px;"></td>
<td style="background-color:#f1f5f9;border-radius:10px;padding:16px;text-align:center;width:33%;">
<div style="font-size:11px;font-weight:700;text-transform:uppercase;color:#64748b;margin-bottom:4px;">Period End</div>
<div style="font-size:14px;font-weight:600;">{ps.period_end}</div>
</td>
<td style="width:10px;"></td>
<td style="background-color:#f1f5f9;border-radius:10px;padding:16px;text-align:center;width:33%;">
<div style="font-size:11px;font-weight:700;text-transform:uppercase;color:#64748b;margin-bottom:4px;">Pay Date</div>
<div style="font-size:14px;font-weight:600;">{ps.pay_date}</div>
</td>
</tr>
</table>
<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin-bottom:24px;">
<tr style="background-color:#f8fafc;"><th style="padding:10px 16px;text-align:left;font-size:11px;font-weight:700;text-transform:uppercase;color:#64748b;border-bottom:2px solid #e2e8f0;">Description</th><th style="padding:10px 16px;text-align:right;font-size:11px;font-weight:700;text-transform:uppercase;color:#64748b;border-bottom:2px solid #e2e8f0;">Amount</th></tr>
<tr><td style="padding:10px 16px;border-bottom:1px solid #f1f5f9;font-size:14px;">Basic Salary</td><td style="padding:10px 16px;text-align:right;border-bottom:1px solid #f1f5f9;font-weight:600;font-size:14px;">&pound;{ps.basic_salary:.2f}</td></tr>
<tr><td style="padding:10px 16px;border-bottom:1px solid #f1f5f9;font-size:14px;">Overtime Pay</td><td style="padding:10px 16px;text-align:right;border-bottom:1px solid #f1f5f9;font-weight:600;font-size:14px;">&pound;{ps.overtime_pay:.2f}</td></tr>
<tr><td style="padding:10px 16px;border-bottom:1px solid #f1f5f9;font-size:14px;">Bonus</td><td style="padding:10px 16px;text-align:right;border-bottom:1px solid #f1f5f9;font-weight:600;font-size:14px;">&pound;{ps.bonus:.2f}</td></tr>
<tr><td style="padding:10px 16px;border-bottom:1px solid #f1f5f9;font-size:14px;">Allowances</td><td style="padding:10px 16px;text-align:right;border-bottom:1px solid #f1f5f9;font-weight:600;font-size:14px;">&pound;{ps.allowances:.2f}</td></tr>
<tr style="font-weight:700;background-color:#f0fdf4;"><td style="padding:12px 16px;font-size:14px;">Gross Pay</td><td style="padding:12px 16px;text-align:right;color:#16a34a;font-size:14px;">&pound;{ps.gross_pay:.2f}</td></tr>
<tr><td style="padding:10px 16px;border-bottom:1px solid #f1f5f9;color:#dc2626;font-size:14px;">Tax</td><td style="padding:10px 16px;text-align:right;border-bottom:1px solid #f1f5f9;color:#dc2626;font-size:14px;">-&pound;{ps.tax_amount:.2f}</td></tr>
<tr><td style="padding:10px 16px;border-bottom:1px solid #f1f5f9;color:#dc2626;font-size:14px;">Insurance</td><td style="padding:10px 16px;text-align:right;border-bottom:1px solid #f1f5f9;color:#dc2626;font-size:14px;">-&pound;{ps.insurance:.2f}</td></tr>
<tr><td style="padding:10px 16px;border-bottom:1px solid #f1f5f9;color:#dc2626;font-size:14px;">Retirement</td><td style="padding:10px 16px;text-align:right;border-bottom:1px solid #f1f5f9;color:#dc2626;font-size:14px;">-&pound;{ps.retirement:.2f}</td></tr>
<tr><td style="padding:10px 16px;border-bottom:1px solid #f1f5f9;color:#dc2626;font-size:14px;">Other Deductions</td><td style="padding:10px 16px;text-align:right;border-bottom:1px solid #f1f5f9;color:#dc2626;font-size:14px;">-&pound;{ps.other_deductions:.2f}</td></tr>
<tr style="font-weight:700;background-color:#fef2f2;"><td style="padding:12px 16px;font-size:14px;">Total Deductions</td><td style="padding:12px 16px;text-align:right;color:#dc2626;font-size:14px;">-&pound;{ps.total_deductions:.2f}</td></tr>
</table>
<div style="background-color:#0f172a;border-radius:12px;padding:24px;text-align:right;">
<div style="font-size:13px;color:#94a3b8;margin-bottom:4px;">NET PAY</div>
<div style="font-size:32px;font-weight:800;color:#10b981;">&pound;{ps.net_pay:.2f}</div>
</div>
</div>
<div style="padding:24px 40px;background-color:#f8fafc;border-top:1px solid #e2e8f0;text-align:center;">
<p style="font-size:13px;color:#94a3b8;margin:0;">Thank you for your hard work!</p>
<p style="font-size:12px;color:#64748b;margin:4px 0 0 0;">{company_name}</p>
<p style="font-size:11px;color:#94a3b8;margin:12px 0 0 0;"><a href="mailto:hello@keyroutes.co?subject=unsubscribe" style="color:#94a3b8;">Unsubscribe</a> from these notifications</p>
</div>
</div>
</div><img src="{request.base_url}api/payslip/track/open/{ps.tracking_id}" width="1" height="1" style="display:none;" alt="">
</body></html>
"""

    pdf_b64 = payload.pdf_data if payload.pdf_data else None
    pdf_filename = f"{ps.number}.pdf" if pdf_b64 else "payslip.pdf"

    background_tasks.add_task(send_email_background, emp.email, subject, body_text, from_header, html_body, pdf_b64, pdf_filename, logo_data, client_id=client.id)
    ps.status = "Sent" if ps.status == "Draft" else ps.status
    ps.sent = datetime.now().strftime("%Y-%m-%d")
    db.commit()
    return {"message": "Payslip email sent", "status": ps.status}

@app.get("/api/payslip/track/open/{tracking_id}")
def track_payslip_open(tracking_id: str, db: Session = Depends(get_db)):
    ps = db.query(models.DBPayslip).filter(models.DBPayslip.tracking_id == tracking_id).first()
    if ps:
        ps.open_count = (ps.open_count or 0) + 1
        ps.last_opened = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.commit()
    response = Response(content=TRACKING_PIXEL, media_type="image/gif")
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response

# --- Org Chart API ---

@app.get("/api/org-chart")
def get_org_chart(request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    employees = db.query(models.DBEmployee).filter(
        models.DBEmployee.client_id == client.id,
        models.DBEmployee.status.in_(["active", "onboarding"])
    ).all()
    departments = db.query(models.DBDepartment).filter(models.DBDepartment.client_id == client.id).all()

    emp_map = {}
    for e in employees:
        dept_name = ""
        if e.department_id:
            dept = db.query(models.DBDepartment).filter(models.DBDepartment.id == e.department_id).first()
            dept_name = dept.name if dept else ""
        emp_map[e.id] = {
            "id": e.id, "employee_id": e.employee_id,
            "name": f"{e.first_name} {e.last_name}",
            "job_title": e.job_title, "email": e.email,
            "department": dept_name, "reports_to": e.reports_to,
            "status": e.status,
        }

    roots = []
    for e_id, e_data in emp_map.items():
        if e_data["reports_to"] and e_data["reports_to"] in emp_map:
            parent = emp_map[e_data["reports_to"]]
            if "children" not in parent:
                parent["children"] = []
            parent["children"].append(e_data)
        else:
            roots.append(e_data)

    dept_groups = {}
    for d in departments:
        dept_employees = [e for e in emp_map.values() if e["department"] == d.name]
        if dept_employees:
            dept_groups[d.name] = dept_employees

    return {"roots": roots, "departments": dept_groups, "total_employees": len(employees)}

# --- HR Dashboard Stats ---

@app.get("/api/hr/stats")
def get_hr_stats(request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    total = db.query(models.DBEmployee).filter(models.DBEmployee.client_id == client.id).count()
    active = db.query(models.DBEmployee).filter(models.DBEmployee.client_id == client.id, models.DBEmployee.status == "active").count()
    onboarding = db.query(models.DBEmployee).filter(models.DBEmployee.client_id == client.id, models.DBEmployee.status == "onboarding").count()
    offboarding = db.query(models.DBEmployee).filter(models.DBEmployee.client_id == client.id, models.DBEmployee.status == "offboarding").count()
    terminated = db.query(models.DBEmployee).filter(models.DBEmployee.client_id == client.id, models.DBEmployee.status == "terminated").count()
    depts = db.query(models.DBDepartment).filter(models.DBDepartment.client_id == client.id).count()
    total_payroll = db.query(sqlfunc.coalesce(sqlfunc.sum(models.DBPayslip.net_pay), 0)).filter(models.DBPayslip.client_id == client.id, models.DBPayslip.status == "Paid").scalar()
    pending_payroll = db.query(sqlfunc.coalesce(sqlfunc.sum(models.DBPayslip.net_pay), 0)).filter(models.DBPayslip.client_id == client.id, models.DBPayslip.status != "Paid").scalar()
    return {
        "total_employees": total, "active": active, "onboarding": onboarding,
        "offboarding": offboarding, "terminated": terminated,
        "departments": depts,
        "total_payroll": round(float(total_payroll), 2),
        "pending_payroll": round(float(pending_payroll), 2),
    }

# --- Attendance API ---

@app.post("/api/attendance/clock-in")
def clock_in(request: Request, body: dict = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    if not body or not body.get("employee_id"):
        raise HTTPException(status_code=400, detail="employee_id required")
    emp_id = body["employee_id"]
    emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == emp_id, models.DBEmployee.client_id == client.id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    today = datetime.now().strftime("%Y-%m-%d")
    existing = db.query(models.DBAttendance).filter(
        models.DBAttendance.employee_id == emp_id,
        models.DBAttendance.date == today,
        models.DBAttendance.client_id == client.id,
    ).first()
    if existing:
        if existing.clock_in:
            raise HTTPException(status_code=400, detail="Already clocked in today")
        existing.clock_in = datetime.now().strftime("%H:%M:%S")
        existing.status = "present"
        db.commit()
        return {"message": "Clocked in", "clock_in": existing.clock_in}
    att = models.DBAttendance(
        client_id=client.id, employee_id=emp_id, date=today,
        clock_in=datetime.now().strftime("%H:%M:%S"), status="present",
    )
    db.add(att)
    db.commit()
    return {"message": "Clocked in", "clock_in": att.clock_in}

@app.post("/api/attendance/clock-out")
def clock_out(request: Request, body: dict = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    if not body or not body.get("employee_id"):
        raise HTTPException(status_code=400, detail="employee_id required")
    emp_id = body["employee_id"]
    today = datetime.now().strftime("%Y-%m-%d")
    att = db.query(models.DBAttendance).filter(
        models.DBAttendance.employee_id == emp_id,
        models.DBAttendance.date == today,
        models.DBAttendance.client_id == client.id,
    ).first()
    if not att or not att.clock_in:
        raise HTTPException(status_code=400, detail="Not clocked in today")
    if att.clock_out:
        raise HTTPException(status_code=400, detail="Already clocked out today")
    att.clock_out = datetime.now().strftime("%H:%M:%S")
    try:
        cin = datetime.strptime(att.clock_in, "%H:%M:%S")
        cout = datetime.strptime(att.clock_out, "%H:%M:%S")
        att.total_hours = round((cout - cin).total_seconds() / 3600, 2)
    except Exception:
        att.total_hours = 0.0
    att.status = "completed"
    db.commit()
    return {"message": "Clocked out", "clock_out": att.clock_out, "total_hours": att.total_hours}

@app.get("/api/attendance")
def get_attendance(request: Request, employee_id: int = 0, date: str = "", db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    query = db.query(models.DBAttendance).filter(models.DBAttendance.client_id == client.id)
    if employee_id:
        query = query.filter(models.DBAttendance.employee_id == employee_id)
    if date:
        query = query.filter(models.DBAttendance.date == date)
    records = query.order_by(models.DBAttendance.date.desc(), models.DBAttendance.clock_in.desc()).limit(200).all()
    result = []
    for a in records:
        emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == a.employee_id).first()
        result.append({
            "id": a.id, "employee_id": a.employee_id,
            "employee_name": f"{emp.first_name} {emp.last_name}" if emp else "",
            "employee_email": emp.email if emp else "",
            "date": a.date, "clock_in": a.clock_in, "clock_out": a.clock_out,
            "total_hours": a.total_hours, "status": a.status, "notes": a.notes,
            "created_at": a.created_at,
        })
    return result

@app.get("/api/attendance/today")
def get_today_attendance(request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    today = datetime.now().strftime("%Y-%m-%d")
    records = db.query(models.DBAttendance).filter(
        models.DBAttendance.client_id == client.id,
        models.DBAttendance.date == today,
    ).all()
    result = []
    for a in records:
        emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == a.employee_id).first()
        result.append({
            "id": a.id, "employee_id": a.employee_id,
            "employee_name": f"{emp.first_name} {emp.last_name}" if emp else "",
            "date": a.date, "clock_in": a.clock_in, "clock_out": a.clock_out,
            "total_hours": a.total_hours, "status": a.status,
        })
    return result

@app.get("/api/attendance/stats")
def get_attendance_stats(request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    today = datetime.now().strftime("%Y-%m-%d")
    total_employees = db.query(models.DBEmployee).filter(
        models.DBEmployee.client_id == client.id,
        models.DBEmployee.status.in_(["active", "onboarding"]),
    ).count()
    today_records = db.query(models.DBAttendance).filter(
        models.DBAttendance.client_id == client.id,
        models.DBAttendance.date == today,
    ).all()
    present = sum(1 for r in today_records if r.status in ("present", "completed"))
    absent = total_employees - present
    avg_hours = 0.0
    if today_records:
        avg_hours = round(sum(r.total_hours for r in today_records) / len(today_records), 2)
    return {
        "total_employees": total_employees,
        "present": present,
        "absent": max(0, absent),
        "avg_hours": avg_hours,
        "date": today,
    }

@app.get("/api/attendance/live")
def get_live_attendance(request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    today = datetime.now().strftime("%Y-%m-%d")
    all_active = db.query(models.DBEmployee).filter(
        models.DBEmployee.client_id == client.id,
        models.DBEmployee.status.in_(["active", "onboarding"]),
    ).all()
    today_records = db.query(models.DBAttendance).filter(
        models.DBAttendance.client_id == client.id,
        models.DBAttendance.date == today,
    ).all()
    record_map = {r.employee_id: r for r in today_records}
    result = []
    for emp in all_active:
        rec = record_map.get(emp.id)
        dept_name = ""
        if emp.department_id:
            dept = db.query(models.DBDepartment).filter(models.DBDepartment.id == emp.department_id).first()
            dept_name = dept.name if dept else ""
        result.append({
            "id": emp.id, "employee_id": emp.employee_id,
            "full_name": f"{emp.first_name} {emp.last_name}",
            "email": emp.email, "job_title": emp.job_title,
            "department": dept_name, "status": emp.status,
            "clock_in": rec.clock_in if rec else "",
            "clock_out": rec.clock_out if rec else "",
            "total_hours": rec.total_hours if rec else 0,
            "attendance_status": rec.status if rec else "absent",
            "location_label": rec.location_label if rec else "",
            "ip_address": rec.ip_address if rec else "",
            "check_type": rec.check_type if rec else "",
        })
    return result

@app.get("/api/attendance/analytics")
def get_attendance_analytics(request: Request, days: int = 30, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    from datetime import timedelta
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    records = db.query(models.DBAttendance).filter(
        models.DBAttendance.client_id == client.id,
        models.DBAttendance.date >= start_date,
    ).all()
    total_employees = db.query(models.DBEmployee).filter(
        models.DBEmployee.client_id == client.id,
        models.DBEmployee.status.in_(["active", "onboarding"]),
    ).count()
    daily_stats = {}
    late_count = 0
    overtime_count = 0
    total_hours_all = 0
    remote_count = 0
    for r in records:
        d = r.date
        if d not in daily_stats:
            daily_stats[d] = {"present": 0, "absent": 0, "hours": 0}
        daily_stats[d]["present"] += 1
        daily_stats[d]["hours"] += r.total_hours or 0
        total_hours_all += r.total_hours or 0
        if r.clock_in and r.clock_in > "09:15":
            late_count += 1
        if r.overtime_hours and r.overtime_hours > 0:
            overtime_count += 1
        if r.location_label and "remote" in r.location_label.lower():
            remote_count += 1
    days_with_data = max(len(daily_stats), 1)
    for d in daily_stats:
        daily_stats[d]["absent"] = total_employees - daily_stats[d]["present"]
    return {
        "period_days": days,
        "total_records": len(records),
        "avg_daily_hours": round(total_hours_all / max(len(records), 1), 2),
        "late_arrivals": late_count,
        "overtime_sessions": overtime_count,
        "remote_sessions": remote_count,
        "avg_attendance_rate": round(sum(d["present"] for d in daily_stats.values()) / (days_with_data * max(total_employees, 1)) * 100, 1),
        "daily": dict(sorted(daily_stats.items())),
    }

@app.get("/api/attendance/export")
def export_attendance(request: Request, start_date: str = "", end_date: str = "", db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    query = db.query(models.DBAttendance).filter(models.DBAttendance.client_id == client.id)
    if start_date:
        query = query.filter(models.DBAttendance.date >= start_date)
    if end_date:
        query = query.filter(models.DBAttendance.date <= end_date)
    records = query.order_by(models.DBAttendance.date.desc()).limit(1000).all()
    rows = []
    for r in records:
        emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == r.employee_id).first()
        rows.append({
            "Employee": f"{emp.first_name} {emp.last_name}" if emp else "",
            "Email": emp.email if emp else "",
            "Date": r.date, "Clock In": r.clock_in, "Clock Out": r.clock_out,
            "Hours": r.total_hours, "Status": r.status, "Type": r.check_type,
            "Location": r.location_label, "IP": r.ip_address,
            "Overtime": r.overtime_hours, "Notes": r.notes,
        })
    return rows

@app.post("/api/attendance/overtime/announce")
def announce_overtime(request: Request, body: dict = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    if not body or not body.get("employee_id") or not body.get("hours"):
        raise HTTPException(status_code=400, detail="employee_id and hours required")
    emp = db.query(models.DBEmployee).filter(
        models.DBEmployee.id == body["employee_id"],
        models.DBEmployee.client_id == client.id,
    ).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    date = body.get("date", datetime.now().strftime("%Y-%m-%d"))
    hours = float(body["hours"])
    reason = body.get("reason", "")
    att = db.query(models.DBAttendance).filter(
        models.DBAttendance.employee_id == emp.id,
        models.DBAttendance.date == date,
        models.DBAttendance.client_id == client.id,
    ).first()
    if att:
        att.overtime_hours = hours
        att.overtime_announced = True
        att.overtime_announced_by = client.company_name or client.contact_name or "HR"
    log = models.DBOvertimeLog(
        client_id=client.id, employee_id=emp.id, date=date,
        hours=hours, reason=reason,
        announced_by=client.company_name or client.contact_name or "HR",
        status="announced",
    )
    db.add(log)
    db.commit()
    return {"message": f"Overtime of {hours}h announced for {emp.first_name} {emp.last_name}"}

@app.get("/api/attendance/overtime/logs")
def get_overtime_logs(request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    logs = db.query(models.DBOvertimeLog).filter(
        models.DBOvertimeLog.client_id == client.id
    ).order_by(models.DBOvertimeLog.created_at.desc()).limit(100).all()
    result = []
    for l in logs:
        emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == l.employee_id).first()
        result.append({
            "id": l.id, "employee_id": l.employee_id,
            "employee_name": f"{emp.first_name} {emp.last_name}" if emp else "",
            "date": l.date, "hours": l.hours, "reason": l.reason,
            "announced_by": l.announced_by, "status": l.status,
            "created_at": l.created_at,
        })
    return result

@app.put("/api/attendance/settings")
def update_attendance_settings(request: Request, body: dict = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    settings = db.query(models.DBAttendanceSettings).filter(models.DBAttendanceSettings.client_id == client.id).first()
    if not settings:
        settings = models.DBAttendanceSettings(client_id=client.id)
        db.add(settings)
    if body:
        for key, val in body.items():
            if hasattr(settings, key) and key not in ("id", "client_id", "created_at"):
                setattr(settings, key, val)
    db.commit()
    return {"message": "Settings saved"}

@app.get("/api/attendance/settings")
def get_attendance_settings(request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    settings = db.query(models.DBAttendanceSettings).filter(models.DBAttendanceSettings.client_id == client.id).first()
    if not settings:
        return {
            "office_name": "Head Office", "office_lat": 0.0, "office_lng": 0.0,
            "geofence_radius": 200.0, "work_start": "09:00", "work_end": "17:30",
            "grace_minutes": 15.0, "auto_clockout_hours": 10.0, "max_overtime_hours": 4.0,
            "allow_remote": True, "require_location": True,
        }
    return {
        "office_name": settings.office_name, "office_lat": settings.office_lat,
        "office_lng": settings.office_lng, "geofence_radius": settings.geofence_radius,
        "work_start": settings.work_start, "work_end": settings.work_end,
        "grace_minutes": settings.grace_minutes,
        "auto_clockout_hours": settings.auto_clockout_hours,
        "max_overtime_hours": settings.max_overtime_hours,
        "allow_remote": settings.allow_remote, "require_location": settings.require_location,
    }

@app.put("/api/employees/{emp_id}/set-password")
def set_employee_password(emp_id: int, request: Request, body: dict = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == emp_id, models.DBEmployee.client_id == client.id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    if not body or not body.get("password"):
        raise HTTPException(status_code=400, detail="Password required")
    emp.password_hash = models.hash_password(body["password"])
    db.commit()
    return {"message": "Password set successfully"}

@app.post("/api/employee/auth/login")
def employee_login(request: Request, body: dict = None, db: Session = Depends(get_db)):
    if not body or not body.get("email") or not body.get("password"):
        raise HTTPException(status_code=400, detail="Email and password required")
    email = body["email"].strip().lower()
    emp = db.query(models.DBEmployee).filter(models.DBEmployee.email.ilike(email)).first()
    if not emp:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not emp.password_hash:
        raise HTTPException(status_code=401, detail="Password not set. Contact your administrator.")
    if not models.verify_password(body["password"], emp.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if emp.status in ("terminated",):
        raise HTTPException(status_code=403, detail="Account deactivated")
    request.session['employee_id'] = emp.id
    request.session['employee_client_id'] = emp.client_id
    today = datetime.now().strftime("%Y-%m-%d")
    now_str = datetime.now().strftime("%H:%M:%S")
    ip = request.client.host if request and request.client else ""
    device = body.get("device_info", "")
    lat = body.get("latitude", 0.0)
    lng = body.get("longitude", 0.0)
    loc_label = body.get("location_label", "")
    existing = db.query(models.DBAttendance).filter(
        models.DBAttendance.employee_id == emp.id,
        models.DBAttendance.date == today,
        models.DBAttendance.client_id == emp.client_id,
    ).first()
    if existing and existing.clock_in:
        return {"message": "Already clocked in today", "employee": {"id": emp.id, "name": f"{emp.first_name} {emp.last_name}", "email": emp.email}, "clock_in": existing.clock_in}
    check_type = "remote"
    if lat and lng:
        settings = db.query(models.DBAttendanceSettings).filter(models.DBAttendanceSettings.client_id == emp.client_id).first()
        if settings and settings.office_lat and settings.office_lng:
            from math import radians, cos, sin, asin, sqrt
            dlat = radians(lat - settings.office_lat)
            dlng = radians(lng - settings.office_lng)
            a = sin(dlat/2)**2 + cos(radians(settings.office_lat)) * cos(radians(lat)) * sin(dlng/2)**2
            dist = 2 * 6371000 * asin(sqrt(a))
            if dist <= settings.geofence_radius:
                check_type = "office"
            else:
                check_type = "field"
    att = models.DBAttendance(
        client_id=emp.client_id, employee_id=emp.id, date=today,
        clock_in=now_str, status="present", check_type=check_type,
        ip_address=ip, device_info=device,
        location_lat=lat, location_lng=lng, location_label=loc_label,
    )
    db.add(att)
    db.commit()
    return {
        "message": "Clocked in automatically",
        "employee": {"id": emp.id, "name": f"{emp.first_name} {emp.last_name}", "email": emp.email},
        "clock_in": now_str, "check_type": check_type,
    }

@app.post("/api/employee/auth/logout")
def employee_logout(request: Request, db: Session = Depends(get_db)):
    emp_id = request.session.get('employee_id')
    client_id = request.session.get('employee_client_id')
    if not emp_id:
        return {"message": "Not logged in"}
    today = datetime.now().strftime("%Y-%m-%d")
    now_str = datetime.now().strftime("%H:%M:%S")
    att = db.query(models.DBAttendance).filter(
        models.DBAttendance.employee_id == emp_id,
        models.DBAttendance.date == today,
        models.DBAttendance.client_id == client_id,
    ).first()
    hours = 0.0
    if att and att.clock_in and not att.clock_out:
        if att.is_on_break and att.break_start:
            try:
                now = datetime.now()
                today_str = now.strftime("%Y-%m-%d")
                bs = datetime.strptime(today_str + " " + att.break_start, "%Y-%m-%d %H:%M:%S")
                att.break_minutes = (att.break_minutes or 0) + round((now - bs).total_seconds() / 60, 1)
            except Exception:
                pass
            att.is_on_break = False
            att.break_start = ""
        att.clock_out = now_str
        try:
            cin = datetime.strptime(today + " " + att.clock_in, "%Y-%m-%d %H:%M:%S")
            cout = datetime.strptime(today + " " + now_str, "%Y-%m-%d %H:%M:%S")
            raw_hours = (cout - cin).total_seconds() / 3600
            break_hours = (att.break_minutes or 0) / 60
            att.total_hours = round(raw_hours - break_hours, 2)
            hours = att.total_hours
            att.status = "completed"
        except Exception:
            pass
        db.commit()
    request.session.pop('employee_id', None)
    request.session.pop('employee_client_id', None)
    return {"message": "Logged out", "total_hours": hours, "break_minutes": att.break_minutes if att else 0}

@app.get("/api/employee/auth/me")
def employee_me(request: Request, db: Session = Depends(get_db)):
    emp_id = request.session.get('employee_id')
    if not emp_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == emp_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    dept_name = ""
    if emp.department_id:
        dept = db.query(models.DBDepartment).filter(models.DBDepartment.id == emp.department_id).first()
        dept_name = dept.name if dept else ""
    today = datetime.now().strftime("%Y-%m-%d")
    att = db.query(models.DBAttendance).filter(
        models.DBAttendance.employee_id == emp.id,
        models.DBAttendance.date == today,
    ).first()
    return {
        "id": emp.id, "employee_id": emp.employee_id,
        "full_name": f"{emp.first_name} {emp.last_name}",
        "email": emp.email, "job_title": emp.job_title,
        "department": dept_name, "phone": emp.phone,
        "status": emp.status, "work_location": emp.work_location,
        "today_clock_in": att.clock_in if att else "",
        "today_clock_out": att.clock_out if att else "",
        "today_hours": att.total_hours if att else 0,
        "today_status": att.status if att else "absent",
        "today_is_on_break": att.is_on_break if att else False,
        "today_break_minutes": (att.break_minutes or 0) if att else 0,
    }

@app.post("/api/employee/attendance/clock-in")
def employee_clock_in(request: Request, body: dict = None, db: Session = Depends(get_db)):
    emp_id = request.session.get('employee_id')
    client_id = request.session.get('employee_client_id')
    if not emp_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    today = datetime.now().strftime("%Y-%m-%d")
    now_str = datetime.now().strftime("%H:%M:%S")
    existing = db.query(models.DBAttendance).filter(
        models.DBAttendance.employee_id == emp_id,
        models.DBAttendance.date == today,
        models.DBAttendance.client_id == client_id,
    ).first()
    if existing and existing.clock_in:
        raise HTTPException(status_code=400, detail="Already clocked in today")
    ip = request.client.host if request and request.client else ""
    device = ""
    lat = lng = 0.0
    loc_label = ""
    if body:
        ip = body.get("ip_address", ip)
        device = body.get("device_info", "")
        lat = body.get("latitude", 0.0)
        lng = body.get("longitude", 0.0)
        loc_label = body.get("location_label", "")
    check_type = "manual"
    if lat and lng:
        settings = db.query(models.DBAttendanceSettings).filter(models.DBAttendanceSettings.client_id == client_id).first()
        if settings and settings.office_lat and settings.office_lng:
            from math import radians, cos, sin, asin, sqrt
            dlat = radians(lat - settings.office_lat)
            dlng = radians(lng - settings.office_lng)
            a = sin(dlat/2)**2 + cos(radians(settings.office_lat)) * cos(radians(lat)) * sin(dlng/2)**2
            dist = 2 * 6371000 * asin(sqrt(a))
            if dist <= settings.geofence_radius:
                check_type = "office"
            else:
                check_type = "field"
    att = models.DBAttendance(
        client_id=client_id, employee_id=emp_id, date=today,
        clock_in=now_str, status="present", check_type=check_type,
        ip_address=ip, device_info=device,
        location_lat=lat, location_lng=lng, location_label=loc_label,
    )
    db.add(att)
    db.commit()
    return {"message": "Clocked in", "clock_in": now_str, "check_type": check_type}

@app.post("/api/employee/attendance/clock-out")
def employee_clock_out(request: Request, db: Session = Depends(get_db)):
    emp_id = request.session.get('employee_id')
    client_id = request.session.get('employee_client_id')
    if not emp_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    today = datetime.now().strftime("%Y-%m-%d")
    now_str = datetime.now().strftime("%H:%M:%S")
    att = db.query(models.DBAttendance).filter(
        models.DBAttendance.employee_id == emp_id,
        models.DBAttendance.date == today,
        models.DBAttendance.client_id == client_id,
    ).first()
    if not att or not att.clock_in:
        raise HTTPException(status_code=400, detail="No clock-in found for today")
    if att.clock_out:
        raise HTTPException(status_code=400, detail="Already clocked out")
    if att.is_on_break:
        try:
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            break_start = datetime.strptime(today_str + " " + att.break_start, "%Y-%m-%d %H:%M:%S")
            att.break_minutes += round((now - break_start).total_seconds() / 60, 1)
        except Exception:
            pass
        att.is_on_break = False
        att.break_start = ""
    att.clock_out = now_str
    try:
        cin = datetime.strptime(today + " " + att.clock_in, "%Y-%m-%d %H:%M:%S")
        cout = datetime.strptime(today + " " + now_str, "%Y-%m-%d %H:%M:%S")
        raw_hours = (cout - cin).total_seconds() / 3600
        break_hours = (att.break_minutes or 0) / 60
        att.total_hours = round(raw_hours - break_hours, 2)
        settings = db.query(models.DBAttendanceSettings).filter(models.DBAttendanceSettings.client_id == client_id).first()
        if settings:
            try:
                wh_start = datetime.strptime(settings.work_start, "%H:%M")
                wh_end = datetime.strptime(settings.work_end, "%H:%M")
                work_hours = (wh_end - wh_start).total_seconds() / 3600
            except Exception:
                work_hours = 8.0
            if att.total_hours > work_hours:
                att.overtime_hours = round(att.total_hours - work_hours, 2)
        att.status = "completed"
    except Exception:
        pass
    db.commit()
    return {"message": "Clocked out", "total_hours": att.total_hours, "overtime_hours": att.overtime_hours, "break_minutes": att.break_minutes}

@app.post("/api/employee/attendance/break-start")
def employee_break_start(request: Request, db: Session = Depends(get_db)):
    emp_id = request.session.get('employee_id')
    client_id = request.session.get('employee_client_id')
    if not emp_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    today = datetime.now().strftime("%Y-%m-%d")
    now_str = datetime.now().strftime("%H:%M:%S")
    att = db.query(models.DBAttendance).filter(
        models.DBAttendance.employee_id == emp_id,
        models.DBAttendance.date == today,
        models.DBAttendance.client_id == client_id,
    ).first()
    if not att or not att.clock_in:
        raise HTTPException(status_code=400, detail="Not clocked in")
    if att.clock_out:
        raise HTTPException(status_code=400, detail="Already clocked out")
    if att.is_on_break:
        raise HTTPException(status_code=400, detail="Already on break")
    att.is_on_break = True
    att.break_start = now_str
    db.commit()
    return {"message": "Break started", "break_start": now_str}

@app.post("/api/employee/attendance/break-stop")
def employee_break_stop(request: Request, db: Session = Depends(get_db)):
    emp_id = request.session.get('employee_id')
    client_id = request.session.get('employee_client_id')
    if not emp_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    today = datetime.now().strftime("%Y-%m-%d")
    att = db.query(models.DBAttendance).filter(
        models.DBAttendance.employee_id == emp_id,
        models.DBAttendance.date == today,
        models.DBAttendance.client_id == client_id,
    ).first()
    if not att or not att.is_on_break:
        raise HTTPException(status_code=400, detail="Not on break")
    try:
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        break_start = datetime.strptime(today_str + " " + att.break_start, "%Y-%m-%d %H:%M:%S")
        elapsed = round((now - break_start).total_seconds() / 60, 1)
        att.break_minutes = (att.break_minutes or 0) + elapsed
    except Exception:
        logger.error(f"Failed to calculate break duration for attendance {att.id}")
    att.is_on_break = False
    att.break_start = ""
    db.commit()
    return {"message": "Break ended", "break_minutes": att.break_minutes}

@app.get("/api/employee/attendance/today")
def employee_today_attendance(request: Request, db: Session = Depends(get_db)):
    emp_id = request.session.get('employee_id')
    client_id = request.session.get('employee_client_id')
    if not emp_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    today = datetime.now().strftime("%Y-%m-%d")
    att = db.query(models.DBAttendance).filter(
        models.DBAttendance.employee_id == emp_id,
        models.DBAttendance.date == today,
        models.DBAttendance.client_id == client_id,
    ).first()
    if not att:
        return {"clocked_in": False}
    now_str = datetime.now().strftime("%H:%M:%S")
    elapsed = 0
    if att.clock_in and not att.clock_out:
        try:
            cin = datetime.strptime(today + " " + att.clock_in, "%Y-%m-%d %H:%M:%S")
            now_t = datetime.strptime(today + " " + now_str, "%Y-%m-%d %H:%M:%S")
            elapsed = round((now_t - cin).total_seconds() / 3600, 2)
            if att.is_on_break and att.break_start:
                bs = datetime.strptime(today + " " + att.break_start, "%Y-%m-%d %H:%M:%S")
                elapsed -= round((now_t - bs).total_seconds() / 3600, 2)
            elapsed -= (att.break_minutes or 0) / 60
            elapsed = round(max(0, elapsed), 2)
        except Exception:
            pass
    return {
        "clocked_in": bool(att.clock_in),
        "clock_in": att.clock_in,
        "clock_out": att.clock_out,
        "total_hours": att.total_hours,
        "is_on_break": att.is_on_break,
        "break_start": att.break_start,
        "break_minutes": att.break_minutes or 0,
        "overtime_hours": att.overtime_hours,
        "elapsed_hours": elapsed,
        "status": att.status,
    }

@app.get("/api/employee/dashboard")
def employee_dashboard(request: Request, db: Session = Depends(get_db)):
    emp_id = request.session.get('employee_id')
    client_id = request.session.get('employee_client_id')
    if not emp_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == emp_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    from datetime import timedelta
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    records = db.query(models.DBAttendance).filter(
        models.DBAttendance.employee_id == emp_id,
        models.DBAttendance.date >= thirty_days_ago,
    ).order_by(models.DBAttendance.date.desc()).limit(30).all()
    attendance = [{
        "date": r.date, "clock_in": r.clock_in, "clock_out": r.clock_out,
        "total_hours": r.total_hours, "status": r.status, "check_type": r.check_type,
        "break_minutes": r.break_minutes or 0, "overtime_hours": r.overtime_hours or 0,
        "is_on_break": r.is_on_break,
    } for r in records]
    payslips = db.query(models.DBPayslip).filter(models.DBPayslip.employee_id == emp_id).order_by(models.DBPayslip.created_at.desc()).limit(6).all()
    payslip_list = [{
        "number": p.number, "period_start": p.period_start, "period_end": p.period_end,
        "pay_date": p.pay_date, "net_pay": p.net_pay, "status": p.status,
    } for p in payslips]
    onboarding = db.query(models.DBOnboardingItem).filter(models.DBOnboardingItem.employee_id == emp_id).all()
    onboarding_list = [{
        "id": o.id, "title": o.title, "is_completed": o.is_completed,
        "category": o.category, "assigned_to": o.assigned_to,
    } for o in onboarding]
    ot_logs = db.query(models.DBOvertimeLog).filter(
        models.DBOvertimeLog.employee_id == emp_id,
        models.DBOvertimeLog.client_id == client_id,
    ).order_by(models.DBOvertimeLog.created_at.desc()).limit(10).all()
    overtime_list = [{
        "date": l.date, "hours": l.hours, "reason": l.reason,
        "announced_by": l.announced_by, "status": l.status,
    } for l in ot_logs]
    days_present = sum(1 for r in records if r.status in ("present", "completed"))
    total_hours = sum(max(r.total_hours, 0) for r in records if r.total_hours)
    total_breaks = sum(r.break_minutes or 0 for r in records)
    avg_hours = round(total_hours / max(len(records), 1), 2)
    return {
        "employee": {
            "full_name": f"{emp.first_name} {emp.last_name}", "email": emp.email,
            "job_title": emp.job_title, "salary": emp.salary, "pay_frequency": emp.pay_frequency,
            "bank_name": emp.bank_name, "bank_account": emp.bank_account, "tax_id": emp.tax_id,
        },
        "attendance_summary": {
            "days_present": days_present, "total_hours": round(total_hours, 2),
            "avg_hours": avg_hours, "total_break_minutes": round(total_breaks, 1),
        },
        "attendance": attendance,
        "payslips": payslip_list,
        "onboarding": onboarding_list,
        "overtime": overtime_list,
    }

@app.post("/api/employee/heartbeat")
def employee_heartbeat(request: Request, db: Session = Depends(get_db)):
    emp_id = request.session.get('employee_id')
    if not emp_id:
        return {"status": "no_session"}
    today = datetime.now().strftime("%Y-%m-%d")
    att = db.query(models.DBAttendance).filter(
        models.DBAttendance.employee_id == emp_id,
        models.DBAttendance.date == today,
    ).first()
    if att and att.clock_in and not att.clock_out:
        try:
            cin = datetime.strptime(att.clock_in, "%H:%M:%S")
            now_time = datetime.strptime(datetime.now().strftime("%H:%M:%S"), "%H:%M:%S")
            elapsed = (now_time - cin).total_seconds() / 3600
            settings = db.query(models.DBAttendanceSettings).filter(models.DBAttendanceSettings.client_id == att.client_id).first()
            max_hours = settings.auto_clockout_hours if settings else 10.0
            if elapsed >= max_hours:
                att.clock_out = datetime.now().strftime("%H:%M:%S")
                att.total_hours = round(elapsed, 2)
                att.status = "completed"
                att.notes = "Auto clocked out"
                db.commit()
                return {"status": "auto_clocked_out", "total_hours": att.total_hours}
        except Exception:
            pass
    return {"status": "ok"}

# ============ RECRUITMENT ============

class RecruitmentFormCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    fields: Optional[str] = "[]"
    pipeline_stages: Optional[str] = '["Applied","Screening","Interview","Offer","Hired"]'

class FormSubmissionCreate(BaseModel):
    answers: Optional[str] = "{}"
    file_name: Optional[str] = ""
    file_type: Optional[str] = ""
    file_data: Optional[str] = ""
    candidate_name: Optional[str] = ""
    candidate_email: Optional[str] = ""

@app.get("/api/recruitment/forms")
def list_recruitment_forms(request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    forms = db.query(models.DBRecruitmentForm).filter(
        models.DBRecruitmentForm.client_id == client.id
    ).order_by(models.DBRecruitmentForm.created_at.desc()).all()
    result = []
    for f in forms:
        sub_count = db.query(models.DBFormSubmission).filter(models.DBFormSubmission.form_id == f.id).count()
        result.append({
            "id": f.id, "title": f.title, "description": f.description,
            "fields": f.fields, "is_active": f.is_active,
            "form_token": f.form_token, "pipeline_stages": f.pipeline_stages,
            "created_at": f.created_at, "submission_count": sub_count,
        })
    return result

@app.post("/api/recruitment/forms")
def create_recruitment_form(request: Request, body: RecruitmentFormCreate, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    form = models.DBRecruitmentForm(
        client_id=client.id, title=body.title, description=body.description, fields=body.fields,
        pipeline_stages=body.pipeline_stages,
    )
    db.add(form)
    db.commit()
    db.refresh(form)
    return {"id": form.id, "form_token": form.form_token, "message": "Form created"}

@app.put("/api/recruitment/forms/{form_id}")
def update_recruitment_form(form_id: int, request: Request, body: dict, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    form = db.query(models.DBRecruitmentForm).filter(
        models.DBRecruitmentForm.id == form_id, models.DBRecruitmentForm.client_id == client.id
    ).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    if "title" in body: form.title = body["title"]
    if "description" in body: form.description = body["description"]
    if "fields" in body: form.fields = body["fields"]
    if "is_active" in body: form.is_active = body["is_active"]
    if "pipeline_stages" in body: form.pipeline_stages = body["pipeline_stages"]
    db.commit()
    return {"message": "Form updated"}

@app.delete("/api/recruitment/forms/{form_id}")
def delete_recruitment_form(form_id: int, request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    form = db.query(models.DBRecruitmentForm).filter(
        models.DBRecruitmentForm.id == form_id, models.DBRecruitmentForm.client_id == client.id
    ).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    db.query(models.DBFormSubmission).filter(models.DBFormSubmission.form_id == form_id).delete()
    db.delete(form)
    db.commit()
    return {"message": "Form deleted"}

@app.get("/api/recruitment/forms/{form_id}/submissions")
def list_form_submissions(form_id: int, request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    form = db.query(models.DBRecruitmentForm).filter(
        models.DBRecruitmentForm.id == form_id, models.DBRecruitmentForm.client_id == client.id
    ).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    subs = db.query(models.DBFormSubmission).filter(
        models.DBFormSubmission.form_id == form_id
    ).order_by(models.DBFormSubmission.created_at.desc()).all()
    return [{
        "id": s.id, "answers": s.answers, "file_name": s.file_name,
        "file_type": s.file_type, "file_data": s.file_data,
        "candidate_name": s.candidate_name,
        "candidate_email": s.candidate_email, "status": s.status,
        "current_stage": getattr(s, 'current_stage', 'Applied'),
        "stage_order": getattr(s, 'stage_order', 0),
        "notes": s.notes, "created_at": s.created_at,
    } for s in subs]

@app.put("/api/recruitment/submissions/{sub_id}")
def update_submission(sub_id: int, request: Request, body: dict, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    sub = db.query(models.DBFormSubmission).join(models.DBRecruitmentForm).filter(
        models.DBFormSubmission.id == sub_id,
        models.DBRecruitmentForm.client_id == client.id,
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if "status" in body: sub.status = body["status"]
    if "notes" in body: sub.notes = body["notes"]
    db.commit()
    return {"message": "Submission updated"}

@app.get("/api/recruitment/forms/{form_id}/pipeline")
def get_form_pipeline(form_id: int, request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    form = db.query(models.DBRecruitmentForm).filter(
        models.DBRecruitmentForm.id == form_id, models.DBRecruitmentForm.client_id == client.id
    ).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    stages = form.pipeline_stages or '["Applied","Screening","Interview","Offer","Hired"]'
    subs = db.query(models.DBFormSubmission).filter(
        models.DBFormSubmission.form_id == form_id
    ).order_by(models.DBFormSubmission.stage_order.asc(), models.DBFormSubmission.created_at.desc()).all()
    pipeline = {}
    for s in subs:
        stage = getattr(s, 'current_stage', 'Applied') or 'Applied'
        if stage not in pipeline:
            pipeline[stage] = []
        pipeline[stage].append({
            "id": s.id, "answers": s.answers, "file_name": s.file_name,
            "file_type": s.file_type, "candidate_name": s.candidate_name,
            "candidate_email": s.candidate_email, "status": s.status,
            "current_stage": stage, "stage_order": getattr(s, 'stage_order', 0),
            "notes": s.notes, "created_at": s.created_at,
        })
    return {"stages": stages, "pipeline": pipeline}

@app.put("/api/recruitment/submissions/{sub_id}/stage")
def move_submission_stage(sub_id: int, request: Request, body: dict, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    sub = db.query(models.DBFormSubmission).join(models.DBRecruitmentForm).filter(
        models.DBFormSubmission.id == sub_id,
        models.DBRecruitmentForm.client_id == client.id,
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    new_stage = body.get("stage")
    stage_order = body.get("stage_order", 0)
    if not new_stage:
        raise HTTPException(status_code=400, detail="stage is required")
    sub.current_stage = new_stage
    sub.stage_order = stage_order
    db.commit()
    return {"message": f"Candidate moved to {new_stage}"}

@app.get("/api/recruitment/form/{token}")
def get_public_form(token: str, db: Session = Depends(get_db)):
    form = db.query(models.DBRecruitmentForm).filter(
        models.DBRecruitmentForm.form_token == token,
        models.DBRecruitmentForm.is_active == True,
    ).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found or inactive")
    return {"title": form.title, "description": form.description, "fields": form.fields}

@app.post("/api/recruitment/form/{token}/submit")
def submit_application(token: str, body: FormSubmissionCreate, db: Session = Depends(get_db)):
    form = db.query(models.DBRecruitmentForm).filter(
        models.DBRecruitmentForm.form_token == token,
        models.DBRecruitmentForm.is_active == True,
    ).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found or inactive")
    sub = models.DBFormSubmission(
        client_id=form.client_id, form_id=form.id,
        answers=body.answers, file_name=body.file_name,
        file_type=body.file_type, file_data=body.file_data,
        candidate_name=body.candidate_name, candidate_email=body.candidate_email,
    )
    db.add(sub)
    db.commit()
    return {"message": "Application submitted successfully"}


@app.get("/api/employee/goals")
def get_employee_goals(request: Request, db: Session = Depends(get_db)):
    emp_id = request.session.get('employee_id')
    if not emp_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    goals = db.query(models.DBEmployeeGoal).filter(models.DBEmployeeGoal.employee_id == emp_id).order_by(models.DBEmployeeGoal.created_at.desc()).all()
    return [{"id": g.id, "title": g.title, "description": g.description, "target_value": g.target_value, "current_value": g.current_value, "unit": g.unit, "category": g.category, "priority": g.priority, "start_date": g.start_date, "due_date": g.due_date, "status": g.status, "created_by": g.created_by} for g in goals]


@app.get("/api/employee/notifications")
def get_employee_notifications(request: Request, db: Session = Depends(get_db)):
    emp_id = request.session.get('employee_id')
    if not emp_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    notes = db.query(models.DBNotification).filter(models.DBNotification.employee_id == emp_id).order_by(models.DBNotification.created_at.desc()).limit(50).all()
    unread = db.query(models.DBNotification).filter(models.DBNotification.employee_id == emp_id, models.DBNotification.is_read == False).count()
    return {"notifications": [{"id": n.id, "title": n.title, "message": n.message, "type": n.type, "is_read": n.is_read, "link": n.link, "created_at": n.created_at} for n in notes], "unread_count": unread}


@app.patch("/api/employee/notifications/{note_id}/read")
def mark_notification_read(note_id: int, request: Request, db: Session = Depends(get_db)):
    emp_id = request.session.get('employee_id')
    if not emp_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    note = db.query(models.DBNotification).filter(models.DBNotification.id == note_id, models.DBNotification.employee_id == emp_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Not found")
    note.is_read = True
    db.commit()
    return {"message": "Marked as read"}


@app.post("/api/employee/notifications/read-all")
def mark_all_notifications_read(request: Request, db: Session = Depends(get_db)):
    emp_id = request.session.get('employee_id')
    if not emp_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    db.query(models.DBNotification).filter(models.DBNotification.employee_id == emp_id, models.DBNotification.is_read == False).update({"is_read": True})
    db.commit()
    return {"message": "All notifications marked as read"}


@app.get("/api/employee/leave")
def get_employee_leave(request: Request, db: Session = Depends(get_db)):
    emp_id = request.session.get('employee_id')
    if not emp_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    leaves = db.query(models.DBLeaveRequest).filter(models.DBLeaveRequest.employee_id == emp_id).order_by(models.DBLeaveRequest.created_at.desc()).all()
    approved = sum(l.days for l in leaves if l.status == "approved" and l.leave_type == "annual")
    sick_taken = sum(l.days for l in leaves if l.status == "approved" and l.leave_type == "sick")
    return {
        "requests": [{"id": l.id, "leave_type": l.leave_type, "start_date": l.start_date, "end_date": l.end_date, "days": l.days, "reason": l.reason, "status": l.status, "approved_by": l.approved_by, "created_at": l.created_at} for l in leaves],
        "balance": {"annual_total": 25, "annual_taken": approved, "sick_total": 10, "sick_taken": sick_taken}
    }


@app.post("/api/employee/leave")
def request_leave(request: Request, body: dict, db: Session = Depends(get_db)):
    emp_id = request.session.get('employee_id')
    if not emp_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == emp_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    leave = models.DBLeaveRequest(
        client_id=emp.client_id, employee_id=emp_id,
        leave_type=body.get("leave_type", "annual"),
        start_date=body.get("start_date", ""),
        end_date=body.get("end_date", ""),
        days=body.get("days", 0),
        reason=body.get("reason", ""),
    )
    db.add(leave)
    note = models.DBNotification(
        client_id=emp.client_id, employee_id=emp_id,
        title="Leave Request Submitted", message=f"Your {leave.leave_type} leave request for {leave.days} day(s) has been submitted.",
        type="info",
    )
    db.add(note)
    db.commit()
    return {"message": "Leave request submitted"}


@app.get("/api/employee/documents")
def get_employee_documents(request: Request, db: Session = Depends(get_db)):
    emp_id = request.session.get('employee_id')
    if not emp_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    docs = db.query(models.DBDocument).filter(models.DBDocument.employee_id == emp_id).order_by(models.DBDocument.created_at.desc()).all()
    return [{"id": d.id, "title": d.title, "doc_type": d.doc_type, "file_name": d.file_name, "uploaded_by": d.uploaded_by, "created_at": d.created_at} for d in docs]


@app.get("/api/employee/documents/{doc_id}/download")
def download_document(doc_id: int, request: Request, db: Session = Depends(get_db)):
    emp_id = request.session.get('employee_id')
    if not emp_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    doc = db.query(models.DBDocument).filter(models.DBDocument.id == doc_id, models.DBDocument.employee_id == emp_id).first()
    if not doc or not doc.file_data:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"file_name": doc.file_name, "file_type": doc.file_type, "file_data": doc.file_data}


@app.get("/api/employee/profile")
def get_employee_profile(request: Request, db: Session = Depends(get_db)):
    emp_id = request.session.get('employee_id')
    if not emp_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == emp_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    dept = db.query(models.DBDepartment).filter(models.DBDepartment.id == emp.department_id).first() if emp.department_id else None
    manager = db.query(models.DBEmployee).filter(models.DBEmployee.id == emp.reports_to).first() if emp.reports_to else None
    team = db.query(models.DBEmployee).filter(models.DBEmployee.department_id == emp.department_id, models.DBEmployee.status == "active", models.DBEmployee.id != emp_id).all() if emp.department_id else []
    goals = db.query(models.DBEmployeeGoal).filter(models.DBEmployeeGoal.employee_id == emp_id).all()
    goal_progress = 0
    if goals:
        goal_progress = round(sum(min(g.current_value / g.target_value * 100, 100) for g in goals) / len(goals), 1)
    return {
        "full_name": f"{emp.first_name} {emp.last_name}",
        "first_name": emp.first_name,
        "last_name": emp.last_name,
        "email": emp.email,
        "phone": emp.phone,
        "address": emp.address,
        "job_title": emp.job_title,
        "role": emp.role,
        "employment_type": emp.employment_type,
        "department": dept.name if dept else "",
        "department_id": emp.department_id,
        "manager": f"{manager.first_name} {manager.last_name}" if manager else "",
        "start_date": emp.start_date,
        "work_location": emp.work_location,
        "emergency_contact": emp.emergency_contact,
        "emergency_phone": emp.emergency_phone,
        "employee_id_code": emp.employee_id,
        "goals_count": len(goals),
        "goal_progress": goal_progress,
        "team": [{"id": t.id, "name": f"{t.first_name} {t.last_name}", "job_title": t.job_title, "email": t.email} for t in team],
    }


@app.get("/api/employee/analytics")
def get_employee_analytics(request: Request, days: int = 30, db: Session = Depends(get_db)):
    emp_id = request.session.get('employee_id')
    if not emp_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    from datetime import timedelta
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    records = db.query(models.DBAttendance).filter(
        models.DBAttendance.employee_id == emp_id,
        models.DBAttendance.date >= start,
    ).order_by(models.DBAttendance.date.asc()).all()
    daily = []
    for r in records:
        daily.append({"date": r.date, "hours": r.total_hours or 0, "break": r.break_minutes or 0, "status": r.status, "check_type": r.check_type})
    total_hours = sum(d["hours"] for d in daily)
    days_present = len([d for d in daily if d["hours"] > 0])
    avg_hours = round(total_hours / max(days_present, 1), 1)
    late_days = 0
    for r in records:
        if r.clock_in:
            try:
                ci = datetime.strptime(r.clock_in, "%H:%M:%S")
                if ci.hour > 9 or (ci.hour == 9 and ci.minute > 15):
                    late_days += 1
            except: pass
    return {"daily": daily, "total_hours": round(total_hours, 1), "days_present": days_present, "avg_hours": avg_hours, "late_days": late_days, "period_days": days}


@app.get("/api/employee/team-presence")
def get_team_presence(request: Request, db: Session = Depends(get_db)):
    emp_id = request.session.get('employee_id')
    if not emp_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == emp_id).first()
    if not emp or not emp.department_id:
        return []
    today = datetime.now().strftime("%Y-%m-%d")
    team = db.query(models.DBEmployee).filter(models.DBEmployee.department_id == emp.department_id, models.DBEmployee.status == "active").all()
    result = []
    for t in team:
        att = db.query(models.DBAttendance).filter(models.DBAttendance.employee_id == t.id, models.DBAttendance.date == today).first()
        is_online = att and att.clock_in and not att.clock_out
        result.append({
            "id": t.id, "name": f"{t.first_name} {t.last_name}", "job_title": t.job_title,
            "is_online": is_online, "clock_in": att.clock_in if att else "",
            "is_on_break": att.is_on_break if att else False,
        })
    return result


@app.get("/api/employee/weekly-chart")
def get_weekly_chart(request: Request, db: Session = Depends(get_db)):
    emp_id = request.session.get('employee_id')
    if not emp_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    from datetime import timedelta
    today = datetime.now()
    start = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
    week_days = []
    for i in range(7):
        d = (today - timedelta(days=today.weekday() - i)).strftime("%Y-%m-%d")
        att = db.query(models.DBAttendance).filter(models.DBAttendance.employee_id == emp_id, models.DBAttendance.date == d).first()
        week_days.append({"date": d, "day": ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][i], "hours": att.total_hours if att else 0, "is_today": d == today.strftime("%Y-%m-%d")})
    return week_days


@app.post("/api/employee/goals/{goal_id}/update")
def update_goal_progress(goal_id: int, request: Request, body: dict, db: Session = Depends(get_db)):
    emp_id = request.session.get('employee_id')
    if not emp_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    goal = db.query(models.DBEmployeeGoal).filter(models.DBEmployeeGoal.id == goal_id, models.DBEmployeeGoal.employee_id == emp_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    goal.current_value = body.get("current_value", goal.current_value)
    if goal.current_value >= goal.target_value:
        goal.status = "completed"
    db.commit()
    return {"message": "Goal updated"}


# HR-side: Create goal for employee
@app.post("/api/employees/{emp_id}/goals")
def create_employee_goal(emp_id: int, request: Request, body: dict = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    if not body: body = {}
    emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == emp_id, models.DBEmployee.client_id == client.id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    goal = models.DBEmployeeGoal(
        client_id=client.id, employee_id=emp_id,
        title=body.get("title", ""), description=body.get("description", ""),
        target_value=body.get("target_value", 100), current_value=body.get("current_value", 0),
        unit=body.get("unit", "%"), category=body.get("category", "performance"),
        priority=body.get("priority", "medium"), start_date=body.get("start_date", ""),
        due_date=body.get("due_date", ""), created_by="HR",
    )
    db.add(goal)
    note = models.DBNotification(
        client_id=client.id, employee_id=emp_id,
        title="New Goal Assigned", message=f"HR has assigned you a new goal: {goal.title}",
        type="info",
    )
    db.add(note)
    db.commit()
    return {"message": "Goal created", "id": goal.id}


@app.post("/api/goals/assign-department")
def assign_department_goal(request: Request, body: dict = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    if not body: body = {}
    dept_id = body.get("department_id")
    if not dept_id:
        raise HTTPException(status_code=400, detail="department_id required")
    dept = db.query(models.DBDepartment).filter(models.DBDepartment.id == dept_id, models.DBDepartment.client_id == client.id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    employees = db.query(models.DBEmployee).filter(models.DBEmployee.department_id == dept_id, models.DBEmployee.client_id == client.id, models.DBEmployee.status == "active").all()
    created = []
    for emp in employees:
        goal = models.DBEmployeeGoal(
            client_id=client.id, employee_id=emp.id, department_id=dept_id,
            title=body.get("title", ""), description=body.get("description", ""),
            target_value=body.get("target_value", 100), current_value=0,
            unit=body.get("unit", "%"), category=body.get("category", "performance"),
            priority=body.get("priority", "medium"), start_date=body.get("start_date", ""),
            due_date=body.get("due_date", ""), created_by="HR",
        )
        db.add(goal)
        note = models.DBNotification(
            client_id=client.id, employee_id=emp.id,
            title="New Goal Assigned", message=f"HR has assigned you a new goal: {goal.title}",
            type="info",
        )
        db.add(note)
        created.append(emp.id)
    if not employees:
        dept_goal = models.DBDepartmentGoal(
            client_id=client.id, department_id=dept_id,
            title=body.get("title", ""), description=body.get("description", ""),
            target_value=body.get("target_value", 100),
            unit=body.get("unit", "%"), category=body.get("category", "performance"),
            priority=body.get("priority", "medium"), start_date=body.get("start_date", ""),
            due_date=body.get("due_date", ""), created_by="HR",
        )
        db.add(dept_goal)
        log_audit(db, client.id, "goal_saved_for_dept", "goal", None, body.get("title", ""), f"Dept: {dept.name} (pending)", request)
        db.commit()
        return {"message": f"Goal saved for {dept.name}. It will be assigned to employees when they join.", "count": 0, "department": dept.name, "pending": True}
    log_audit(db, client.id, "goal_assigned_dept", "goal", None, body.get("title", ""), f"Dept: {dept.name}, {len(created)} employees", request)
    db.commit()
    return {"message": f"Goal assigned to {len(created)} employees in {dept.name}", "count": len(created), "department": dept.name}


@app.get("/api/goals/department-pending")
def get_pending_department_goals(request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    goals = db.query(models.DBDepartmentGoal).filter(
        models.DBDepartmentGoal.client_id == client.id,
        models.DBDepartmentGoal.is_assigned == False,
    ).all()
    result = []
    for g in goals:
        dept = db.query(models.DBDepartment).filter(models.DBDepartment.id == g.department_id).first()
        result.append({
            "id": g.id, "department_id": g.department_id, "department_name": dept.name if dept else "",
            "title": g.title, "description": g.description,
            "target_value": g.target_value, "unit": g.unit,
            "category": g.category, "priority": g.priority,
            "due_date": g.due_date, "created_at": g.created_at,
        })
    return result


@app.get("/api/leave/requests")
def get_all_leave_requests(request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    leaves = db.query(models.DBLeaveRequest).filter(models.DBLeaveRequest.client_id == client.id).order_by(models.DBLeaveRequest.created_at.desc()).all()
    result = []
    for l in leaves:
        emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == l.employee_id).first()
        result.append({
            "id": l.id, "employee_id": l.employee_id,
            "employee_name": f"{emp.first_name} {emp.last_name}" if emp else "",
            "leave_type": l.leave_type, "start_date": l.start_date, "end_date": l.end_date,
            "days": l.days, "reason": l.reason, "status": l.status,
            "approved_by": l.approved_by, "created_at": l.created_at,
        })
    return result


@app.post("/api/leave/requests/{leave_id}/action")
def action_leave_simple(leave_id: int, request: Request, body: dict = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    if not body: body = {}
    leave = db.query(models.DBLeaveRequest).filter(models.DBLeaveRequest.id == leave_id, models.DBLeaveRequest.client_id == client.id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    action = body.get("action", "")
    leave.status = "approved" if action == "approve" else "rejected"
    leave.approved_by = body.get("approved_by", "HR")
    note = models.DBNotification(
        client_id=client.id, employee_id=leave.employee_id,
        title=f"Leave Request {leave.status.title()}", message=f"Your {leave.leave_type} leave request has been {leave.status}.",
        type="success" if leave.status == "approved" else "warning",
    )
    db.add(note)
    log_audit(db, client.id, f"leave_{leave.status}", "leave", leave.id, f"{leave.leave_type} ({leave.days}d)", f"Employee ID: {leave.employee_id}", request)
    db.commit()
    return {"message": f"Leave {leave.status}"}


@app.get("/api/employees/{emp_id}/goals")
def get_goals_for_employee(emp_id: int, request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    goals = db.query(models.DBEmployeeGoal).filter(models.DBEmployeeGoal.employee_id == emp_id, models.DBEmployeeGoal.client_id == client.id).order_by(models.DBEmployeeGoal.created_at.desc()).all()
    return [{"id": g.id, "title": g.title, "description": g.description, "target_value": g.target_value, "current_value": g.current_value, "unit": g.unit, "category": g.category, "priority": g.priority, "start_date": g.start_date, "due_date": g.due_date, "status": g.status, "created_by": g.created_by, "department_id": g.department_id} for g in goals]


@app.get("/api/employees/{emp_id}/documents")
def get_documents_for_employee(emp_id: int, request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    docs = db.query(models.DBDocument).filter(models.DBDocument.employee_id == emp_id, models.DBDocument.client_id == client.id).order_by(models.DBDocument.created_at.desc()).all()
    return [{"id": d.id, "title": d.title, "doc_type": d.doc_type, "file_name": d.file_name, "uploaded_by": d.uploaded_by, "created_at": d.created_at} for d in docs]


@app.get("/api/employees/{emp_id}/leave")
def get_leave_for_employee(emp_id: int, request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    leaves = db.query(models.DBLeaveRequest).filter(models.DBLeaveRequest.employee_id == emp_id, models.DBLeaveRequest.client_id == client.id).order_by(models.DBLeaveRequest.created_at.desc()).all()
    return [{"id": l.id, "leave_type": l.leave_type, "start_date": l.start_date, "end_date": l.end_date, "days": l.days, "reason": l.reason, "status": l.status, "approved_by": l.approved_by, "created_at": l.created_at} for l in leaves]


@app.post("/api/employees/{emp_id}/documents")
def upload_document(emp_id: int, request: Request, body: dict = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    if not body: body = {}
    emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == emp_id, models.DBEmployee.client_id == client.id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    doc = models.DBDocument(
        client_id=client.id, employee_id=emp_id,
        title=body.get("title", ""), doc_type=body.get("doc_type", "other"),
        file_name=body.get("file_name", ""), file_type=body.get("file_type", ""),
        file_data=body.get("file_data", ""), uploaded_by="HR",
    )
    db.add(doc)
    note = models.DBNotification(
        client_id=client.id, employee_id=emp_id,
        title="New Document Uploaded", message=f"HR has uploaded a document: {doc.title}",
        type="info",
    )
    db.add(note)
    db.commit()
    return {"message": "Document uploaded", "id": doc.id}


# ============================================================================
# AI ENDPOINTS (Groq / Llama 3.3)
# ============================================================================

from llm import llm_chat, llm_json


@app.post("/api/ai/screen-resume")
def screen_resume(request: Request, body: dict = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    if not body or not body.get("job_title"):
        raise HTTPException(status_code=400, detail="job_title required")
    job_title = body["job_title"]
    job_description = body.get("job_description", "")
    resume_text = body.get("resume_text", "")
    candidate_name = body.get("candidate_name", "Candidate")
    if not resume_text:
        return {"score": 0, "summary": "No resume text provided to analyze.", "strengths": [], "weaknesses": [], "recommendation": "Cannot screen without resume content."}
    messages = [
        {"role": "system", "content": "You are an expert HR recruiter. Analyze the resume against the job requirements and return JSON with: score (0-100), summary (1 sentence), strengths (list of up to 5), weaknesses (list of up to 5), recommendation (Hire/Interview/Reject with 1 sentence reason). Return ONLY valid JSON."},
        {"role": "user", "content": f"Job Title: {job_title}\nJob Description: {job_description}\n\nCandidate: {candidate_name}\nResume:\n{resume_text[:4000]}"}
    ]
    result = llm_json(messages)
    if not result:
        return {"score": 0, "summary": "AI service unavailable.", "strengths": [], "weaknesses": [], "recommendation": "Unable to screen at this time."}
    return {
        "score": result.get("score", 0),
        "summary": result.get("summary", ""),
        "strengths": result.get("strengths", []),
        "weaknesses": result.get("weaknesses", []),
        "recommendation": result.get("recommendation", ""),
    }


@app.post("/api/ai/generate-onboarding")
def generate_onboarding_checklist(request: Request, body: dict = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    if not body or not body.get("job_title"):
        raise HTTPException(status_code=400, detail="job_title required")
    job_title = body["job_title"]
    department = body.get("department", "")
    seniority = body.get("seniority", "mid-level")
    messages = [
        {"role": "system", "content": "You are an HR onboarding specialist. Generate a custom onboarding checklist for a new hire. Return JSON with: items (list of objects with title, category, description, due_days from start). Categories: Legal, IT, HR, Social, Compliance, Training. Include 8-15 items. Return ONLY valid JSON."},
        {"role": "user", "content": f"Job Title: {job_title}\nDepartment: {department}\nSeniority: {seniority}"}
    ]
    result = llm_json(messages)
    if not result:
        return {"items": [
            {"title": "Sign employment contract", "category": "Legal", "description": "Review and sign employment agreement", "due_days": 1},
            {"title": "Provide government-issued ID", "category": "Legal", "description": "Submit ID for verification", "due_days": 1},
            {"title": "Submit bank details for payroll", "category": "Finance", "description": "Provide banking information", "due_days": 3},
            {"title": "IT equipment setup", "category": "IT", "description": "Laptop, email, system access", "due_days": 1},
            {"title": "Company policy acknowledgment", "category": "Compliance", "description": "Read and acknowledge policies", "due_days": 7},
        ]}
    return {"items": result.get("items", [])}


@app.post("/api/ai/personalize-email")
def personalize_invoice_email(request: Request, body: dict = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    if not body or not body.get("client_name"):
        raise HTTPException(status_code=400, detail="client_name required")
    client_name = body["client_name"]
    invoice_number = body.get("invoice_number", "")
    total = body.get("total", 0)
    due_date = body.get("due_date", "")
    is_first_time = body.get("is_first_time", False)
    tone = body.get("tone", "professional")
    messages = [
        {"role": "system", "content": f"You are a professional accounts receivable email writer. Write a short, {tone} invoice email. Include: greeting, invoice reference, amount, due date, payment link mention, and closing. Keep it under 100 words. Return ONLY the email body text, no subject line."},
        {"role": "user", "content": f"Client: {client_name}\nInvoice: {invoice_number}\nAmount: £{total}\nDue: {due_date}\nFirst time client: {is_first_time}"}
    ]
    result = llm_chat(messages)
    if not result:
        return {"subject": f"Invoice {invoice_number}", "body": f"Dear {client_name},\n\nPlease find invoice {invoice_number} for £{total}, due {due_date}.\n\nKind regards,\n{client.company_name or 'Accounts Team'}"}
    subject = f"Invoice {invoice_number}" if invoice_number else "Invoice"
    lines = result.strip().split("\n")
    for line in lines:
        if line.lower().startswith("subject:"):
            subject = line.split(":", 1)[1].strip()
            result = result.replace(line, "").strip()
            break
    return {"subject": subject, "body": result}


@app.post("/api/ai/generate-followup")
def generate_followup_email(request: Request, body: dict = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    if not body or not body.get("client_name"):
        raise HTTPException(status_code=400, detail="client_name required")
    client_name = body["client_name"]
    invoice_number = body.get("invoice_number", "")
    total = body.get("total", 0)
    days_overdue = body.get("days_overdue", 0)
    tone = body.get("tone", "polite")
    messages = [
        {"role": "system", "content": f"You are an accounts receivable specialist. Write a {tone} payment follow-up email for an overdue invoice. Be concise, professional, and clear about the amount owed and urgency. Keep under 80 words. Return ONLY the email body text."},
        {"role": "user", "content": f"Client: {client_name}\nInvoice: {invoice_number}\nAmount: £{total}\nDays overdue: {days_overdue}"}
    ]
    result = llm_chat(messages)
    if not result:
        return {"subject": f"Payment Reminder - {invoice_number}", "body": f"Dear {client_name},\n\nThis is a friendly reminder that invoice {invoice_number} for £{total} is now {days_overdue} days overdue.\n\nPlease arrange payment at your earliest convenience.\n\nKind regards,\n{client.company_name or 'Accounts Team'}"}
    subject = f"Payment Reminder - {invoice_number}" if invoice_number else "Payment Reminder"
    return {"subject": subject, "body": result}


@app.get("/api/ai/payroll-anomalies")
def detect_payroll_anomalies(request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    payslips = db.query(models.DBPayslip).filter(
        models.DBPayslip.client_id == client.id
    ).order_by(models.DBPayslip.employee_id, models.DBPayslip.period_start.desc()).all()
    by_emp = {}
    for p in payslips:
        if p.employee_id not in by_emp:
            by_emp[p.employee_id] = []
        by_emp[p.employee_id].append(p)
    anomalies = []
    for emp_id, ps_list in by_emp.items():
        if len(ps_list) < 2:
            continue
        latest = ps_list[0]
        prev = ps_list[1]
        if prev.net_pay and prev.net_pay > 0 and latest.net_pay:
            pct_change = abs(latest.net_pay - prev.net_pay) / prev.net_pay * 100
            if pct_change > 20:
                emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == emp_id).first()
                emp_name = f"{emp.first_name} {emp.last_name}" if emp else f"Employee #{emp_id}"
                direction = "increased" if latest.net_pay > prev.net_pay else "decreased"
                anomalies.append({
                    "employee_id": emp_id, "employee_name": emp_name,
                    "latest_net": round(float(latest.net_pay), 2),
                    "previous_net": round(float(prev.net_pay), 2),
                    "change_pct": round(pct_change, 1), "direction": direction,
                    "latest_period": latest.period_start or "",
                })
    anomalies.sort(key=lambda x: x["change_pct"], reverse=True)
    return {"anomalies": anomalies, "total_checked": len(by_emp)}


@app.get("/api/ai/attendance-alerts")
def detect_attendance_alerts(request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    from datetime import timedelta
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    records = db.query(models.DBAttendance).filter(
        models.DBAttendance.client_id == client.id,
        models.DBAttendance.date >= thirty_days_ago,
    ).all()
    by_emp = {}
    for r in records:
        if r.employee_id not in by_emp:
            by_emp[r.employee_id] = []
        by_emp[r.employee_id].append(r)
    alerts = []
    for emp_id, recs in by_emp.items():
        emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == emp_id).first()
        if not emp:
            continue
        emp_name = f"{emp.first_name} {emp.last_name}"
        late_count = 0
        absent_days = 0
        long_breaks = 0
        no_clockout = 0
        total_hours = 0
        for r in recs:
            if r.clock_in and r.clock_in > "09:15:00":
                late_count += 1
            if r.status == "absent" or (not r.clock_in and not r.clock_out):
                absent_days += 1
            if r.break_minutes and r.break_minutes > 90:
                long_breaks += 1
            if r.clock_in and not r.clock_out:
                no_clockout += 1
            if r.total_hours:
                total_hours += float(r.total_hours)
        emp_alerts = []
        if late_count >= 5:
            emp_alerts.append({"type": "late", "message": f"Late {late_count} times in 30 days", "severity": "warning"})
        if absent_days >= 5:
            emp_alerts.append({"type": "absent", "message": f"{absent_days} absent days in 30 days", "severity": "critical"})
        if long_breaks >= 3:
            emp_alerts.append({"type": "break", "message": f"{long_breaks} extended breaks (>90 min)", "severity": "warning"})
        if no_clockout >= 2:
            emp_alerts.append({"type": "clockout", "message": f"{no_clockout} missed clock-outs", "severity": "warning"})
        if recs and total_hours / len(recs) > 10:
            emp_alerts.append({"type": "overtime", "message": f"Avg {round(total_hours/len(recs), 1)}h/day — burnout risk", "severity": "critical"})
        if emp_alerts:
            alerts.append({"employee_id": emp_id, "employee_name": emp_name, "department": emp.department_id, "alerts": emp_alerts, "total_hours_30d": round(total_hours, 1)})
    alerts.sort(key=lambda x: len(x["alerts"]), reverse=True)
    return {"alerts": alerts, "period": "30 days", "employees_checked": len(by_emp)}


@app.post("/api/ai/summarize-attendance")
def summarize_attendance(request: Request, body: dict = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    from datetime import timedelta
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    records = db.query(models.DBAttendance).filter(
        models.DBAttendance.client_id == client.id,
        models.DBAttendance.date >= thirty_days_ago,
    ).all()
    total_employees = db.query(models.DBEmployee).filter(
        models.DBEmployee.client_id == client.id, models.DBEmployee.status == "active"
    ).count()
    total_records = len(records)
    present_days = sum(1 for r in records if r.status == "present")
    avg_hours = sum(float(r.total_hours or 0) for r in records) / max(total_records, 1)
    remote_count = sum(1 for r in records if r.check_type == "remote")
    office_count = sum(1 for r in records if r.check_type == "office")
    context = f"Period: last 30 days. Active employees: {total_employees}. Total attendance records: {total_records}. Present days: {present_days}. Avg hours/day: {round(avg_hours,1)}. Remote check-ins: {remote_count}. Office check-ins: {office_count}."
    messages = [
        {"role": "system", "content": "You are an HR analytics assistant. Summarize the attendance data in 2-3 bullet points. Be specific with numbers. Focus on actionable insights."},
        {"role": "user", "content": context}
    ]
    result = llm_chat(messages)
    if not result:
        result = f"• {present_days} present days recorded across {total_employees} employees.\n• Average daily hours: {round(avg_hours, 1)}h.\n• Remote: {remote_count}, Office: {office_count}."
    return {"summary": result, "stats": {"total_employees": total_employees, "total_records": total_records, "present_days": present_days, "avg_hours": round(avg_hours, 1), "remote": remote_count, "office": office_count}}


# ============================================================
# VIDEO MEETINGS - WebRTC Signaling Server
# ============================================================
import asyncio
from collections import defaultdict

meeting_rooms = defaultdict(lambda: {
    "participants": {},
    "host": None,
    "waiting": {},
    "locked": False,
    "created_at": datetime.utcnow().isoformat()
})

class MeetingSignaling:
    def __init__(self):
        self.connections = defaultdict(list)

    async def connect(self, websocket: WebSocket, room_id: str, user_id: str):
        await websocket.accept()
        self.connections[room_id].append({
            "ws": websocket,
            "user_id": user_id
        })

    def disconnect(self, room_id: str, user_id: str):
        self.connections[room_id] = [
            c for c in self.connections[room_id] if c["user_id"] != user_id
        ]
        if room_id in meeting_rooms:
            meeting_rooms[room_id]["participants"].pop(user_id, None)
            meeting_rooms[room_id]["waiting"].pop(user_id, None)
            if not meeting_rooms[room_id]["participants"]:
                del meeting_rooms[room_id]
            elif meeting_rooms[room_id]["host"] == user_id:
                # Reassign host to the next participant if possible
                new_host = next(iter(meeting_rooms[room_id]["participants"].keys()), None)
                meeting_rooms[room_id]["host"] = new_host
                
        if not self.connections[room_id]:
            if room_id in self.connections:
                del self.connections[room_id]

    async def broadcast(self, room_id: str, message: dict, exclude_user: str = None):
        dead = []
        for conn in self.connections.get(room_id, []):
            if conn["user_id"] == exclude_user:
                continue
            try:
                await conn["ws"].send_json(message)
            except Exception:
                dead.append(conn)
        for d in dead:
            if d in self.connections.get(room_id, []):
                self.connections[room_id].remove(d)

    async def send_to(self, room_id: str, user_id: str, message: dict):
        for conn in self.connections.get(room_id, []):
            if conn["user_id"] == user_id:
                try:
                    await conn["ws"].send_json(message)
                except Exception:
                    pass
                return

    def get_participants(self, room_id: str):
        return list(meeting_rooms.get(room_id, {}).get("participants", {}).keys())

signaling = MeetingSignaling()

@app.get("/meeting", response_class=HTMLResponse)
async def meeting_page():
    html_path = os.path.join(frontend_path, "meeting.html")
    if os.path.exists(html_path):
        with open(html_path, "r") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Meeting page not found</h1>", status_code=404)

@app.websocket("/ws/meeting/{room_id}")
async def meeting_websocket(websocket: WebSocket, room_id: str):
    user_id = websocket.query_params.get("user_id", str(uuid.uuid4())[:8])
    display_name = websocket.query_params.get("name", "Guest")

    await signaling.connect(websocket, room_id, user_id)
    room = meeting_rooms[room_id]

    # Host assignment logic
    if not room.get("host"):
        room["host"] = user_id
    
    is_host = room["host"] == user_id

    # Waiting room logic
    if room.get("locked") and not is_host:
        room["waiting"][user_id] = {"name": display_name, "ws": websocket}
        await signaling.send_to(room_id, user_id, {"type": "waiting"})
        await signaling.send_to(room_id, room["host"], {
            "type": "join-request",
            "user_id": user_id,
            "name": display_name
        })
        # Keep connection open but don't join yet
    else:
        # Join immediately
        room["participants"][user_id] = {"joined_at": datetime.utcnow().isoformat(), "name": display_name}
        participants = signaling.get_participants(room_id)
        
        await signaling.send_to(room_id, user_id, {
            "type": "welcome",
            "user_id": user_id,
            "is_host": is_host,
            "host_id": room["host"],
            "participants": [p for p in participants if p != user_id]
        })
        
        await signaling.broadcast(room_id, {
            "type": "user-joined",
            "user_id": user_id,
            "name": display_name,
            "participants": participants
        }, exclude_user=user_id)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            # Host controls
            if msg_type == "admit-user" and room["host"] == user_id:
                target_id = data.get("target")
                if target_id in room["waiting"]:
                    del room["waiting"][target_id]
                    room["participants"][target_id] = {"joined_at": datetime.utcnow().isoformat(), "name": data.get("name")}
                    await signaling.send_to(room_id, target_id, {
                        "type": "welcome",
                        "user_id": target_id,
                        "is_host": False,
                        "host_id": room["host"],
                        "participants": [p for p in signaling.get_participants(room_id) if p != target_id]
                    })
                    await signaling.broadcast(room_id, {
                        "type": "user-joined",
                        "user_id": target_id,
                        "name": data.get("name"),
                        "participants": signaling.get_participants(room_id)
                    }, exclude_user=target_id)
            
            elif msg_type == "deny-user" and room["host"] == user_id:
                target_id = data.get("target")
                if target_id in room["waiting"]:
                    del room["waiting"][target_id]
                    await signaling.send_to(room_id, target_id, {"type": "denied"})
            
            elif msg_type == "mute-all" and room["host"] == user_id:
                await signaling.broadcast(room_id, {"type": "force-mute"}, exclude_user=user_id)
                
            elif msg_type == "remove-user" and room["host"] == user_id:
                await signaling.send_to(room_id, data.get("target"), {"type": "removed"})
                
            elif msg_type == "toggle-lock" and room["host"] == user_id:
                room["locked"] = data.get("locked", False)
                await signaling.broadcast(room_id, {"type": "room-locked", "locked": room["locked"]})

            # Meeting Features
            elif msg_type == "raise-hand":
                await signaling.broadcast(room_id, {
                    "type": "raise-hand",
                    "user_id": user_id,
                    "name": display_name
                }, exclude_user=user_id)
                
            elif msg_type == "caption":
                await signaling.broadcast(room_id, {
                    "type": "caption",
                    "user_id": user_id,
                    "name": display_name,
                    "text": data.get("text", "")
                }, exclude_user=user_id)

            # Standard WebRTC Signaling
            elif msg_type == "offer":
                await signaling.send_to(room_id, data.get("target"), {
                    "type": "offer",
                    "offer": data.get("offer"),
                    "from": user_id,
                    "name": display_name
                })
            elif msg_type == "answer":
                await signaling.send_to(room_id, data.get("target"), {
                    "type": "answer",
                    "answer": data.get("answer"),
                    "from": user_id
                })
            elif msg_type == "ice-candidate":
                await signaling.send_to(room_id, data.get("target"), {
                    "type": "ice-candidate",
                    "candidate": data.get("candidate"),
                    "from": user_id
                })
            elif msg_type == "chat":
                await signaling.broadcast(room_id, {
                    "type": "chat",
                    "from": user_id,
                    "name": display_name,
                    "message": data.get("message", "")
                })
            elif msg_type == "toggle-media":
                await signaling.broadcast(room_id, {
                    "type": "toggle-media",
                    "user_id": user_id,
                    "kind": data.get("kind"),
                    "muted": data.get("muted")
                }, exclude_user=user_id)
            elif msg_type == "screen-share-started":
                await signaling.broadcast(room_id, {
                    "type": "screen-share-started",
                    "user_id": user_id,
                    "name": display_name
                }, exclude_user=user_id)
            elif msg_type == "screen-share-stopped":
                await signaling.broadcast(room_id, {
                    "type": "screen-share-stopped",
                    "user_id": user_id
                }, exclude_user=user_id)

    except WebSocketDisconnect:
        signaling.disconnect(room_id, user_id)
        if user_id in room.get("participants", {}):
            participants = signaling.get_participants(room_id)
            await signaling.broadcast(room_id, {
                "type": "user-left",
                "user_id": user_id,
                "name": display_name,
                "participants": participants,
                "new_host": room.get("host")
            })
    except Exception as e:
        logger.error(f"WebSocket Error: {e}")
        signaling.disconnect(room_id, user_id)
        participants = signaling.get_participants(room_id)
        await signaling.broadcast(room_id, {
            "type": "user-left",
            "user_id": user_id,
            "name": display_name,
            "participants": participants
        })

# Serve frontend
frontend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    logger.warning(f"Frontend directory not found at {frontend_path}")

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host=host, port=port, reload=False)
