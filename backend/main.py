import hashlib
import secrets
import uuid
import smtplib
import ssl
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Request
from fastapi.responses import RedirectResponse, StreamingResponse, JSONResponse
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

models.Base.metadata.create_all(bind=engine)
ensure_columns()

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

def generate_secret_key() -> str:
    return secrets.token_hex(32)

SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY or SECRET_KEY == "generate_a_random_secret_string":
    SECRET_KEY = generate_secret_key()
    logger.warning("Generated new SECRET_KEY - set it in .env for persistence")

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

app = FastAPI(title="Accounting Platform API")

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

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

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

@app.on_event("startup")
def ensure_super_admin():
    with SessionLocal() as db:
        existing = db.query(models.DBSuperAdmin).first()
        if not existing:
            db.add(models.DBSuperAdmin(username="superadmin", password_hash="", email="hello@keyroutes.co"))
            db.commit()
            logger.info("Created default super admin (Google OAuth: hello@keyroutes.co)")
        elif existing.email != "hello@keyroutes.co":
            existing.email = "hello@keyroutes.co"
            db.commit()
            logger.info("Updated super admin email to hello@keyroutes.co")

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
    db.commit()
    return {"message": "Client deleted"}

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
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret
    )
    if creds.expired or not creds.valid:
        creds.refresh(GoogleRequest())
    return creds

def get_stored_refresh_token(db: Session):
    setting = db.query(models.DBSettings).filter(models.DBSettings.key == "GOOGLE_REFRESH_TOKEN").first()
    return setting.value if setting else None

def send_email_smtp(to_email, subject, body, from_email, html_body=None, pdf_bytes=None, pdf_filename="invoice.pdf"):
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASSWORD", "")
    if not all([smtp_host, smtp_user, smtp_pass]):
        return False, "SMTP not configured"
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Reply-To'] = from_email
        msg['Precedence'] = 'bulk'
        msg['X-Mailer'] = 'aniprotech'
        msg['List-Unsubscribe'] = f'<mailto:{from_email}?subject=unsubscribe>'
        msg.set_content(body)
        if html_body:
            msg.add_alternative(html_body, subtype='html')
        if pdf_bytes:
            msg.add_attachment(pdf_bytes, maintype='application', subtype='pdf', filename=pdf_filename)
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls(context=context)
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        logger.info(f"Email sent via SMTP to {to_email}")
        return True, "Email sent via SMTP"
    except Exception as e:
        logger.error(f"SMTP failed: {e}")
        return False, f"SMTP error: {str(e)}"

def send_email_background(to_email: str, subject: str, body: str, from_email: str, html_body: str = None, pdf_b64: str = None, pdf_filename: str = "invoice.pdf"):
    pdf_bytes = None
    if pdf_b64:
        try:
            pdf_bytes = base64.b64decode(pdf_b64)
        except Exception as e:
            logger.error(f"Failed to decode PDF: {e}")

    with SessionLocal() as db:
        refresh_token = get_stored_refresh_token(db)

    if refresh_token:
        try:
            creds = get_gmail_credentials(access_token=None, refresh_token=refresh_token)
            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = from_email
            msg['To'] = to_email
            msg['Reply-To'] = from_email
            msg['Precedence'] = 'bulk'
            msg['X-Mailer'] = 'aniprotech'
            msg['List-Unsubscribe'] = f'<mailto:{from_email}?subject=unsubscribe>'
            msg.set_content(body)
            if html_body:
                msg.add_alternative(html_body, subtype='html')
            if pdf_bytes:
                msg.add_attachment(pdf_bytes, maintype='application', subtype='pdf', filename=pdf_filename)
            service = build('gmail', 'v1', credentials=creds)
            encoded_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            send_result = service.users().messages().send(userId="me", body={'raw': encoded_message}).execute()
            logger.info(f"Email sent via Gmail API to {to_email} (ID: {send_result['id']})")
            return True, "Email sent via Gmail API"
        except Exception as e:
            logger.warning(f"Gmail API failed, trying SMTP fallback: {e}")

    return send_email_smtp(to_email, subject, body, from_email, html_body, pdf_bytes, pdf_filename)

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
        except:
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
        tax_type=invoice.tax_type
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

    sender_name = company_name
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
            if li.disc and li.disc > 0:
                amount *= (1 - li.disc / 100)
            item_label = f"{li.name} - {li.description}" if li.name else li.description
            rows += f'''
                <tr>
                    <td style="padding:12px 16px;border-bottom:1px solid #f1f5f9;font-size:14px;color:#333;">{item_label}</td>
                    <td style="padding:12px 16px;border-bottom:1px solid #f1f5f9;font-size:14px;color:#333;text-align:right;">{int(li.qty)}</td>
                    <td style="padding:12px 16px;border-bottom:1px solid #f1f5f9;font-size:14px;color:#333;text-align:right;">${li.price:.2f}</td>
                    <td style="padding:12px 16px;border-bottom:1px solid #f1f5f9;font-size:14px;color:#333;text-align:right;font-weight:600;">${amount:.2f}</td>
                </tr>'''

        line_items_html = f'''
            <table style="width:100%;border-collapse:collapse;margin-bottom:24px;">
                <thead>
                    <tr style="background:#f8fafc;">
                        <th style="padding:10px 16px;text-align:left;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;color:#64748b;border-bottom:2px solid #e2e8f0;">Description</th>
                        <th style="padding:10px 16px;text-align:right;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;color:#64748b;border-bottom:2px solid #e2e8f0;">Qty</th>
                        <th style="padding:10px 16px;text-align:right;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;color:#64748b;border-bottom:2px solid #e2e8f0;">Price</th>
                        <th style="padding:10px 16px;text-align:right;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;color:#64748b;border-bottom:2px solid #e2e8f0;">Amount</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>'''

    body = f"""Hello {inv.to_contact},

Please find the details of your invoice {inv.number} from {company_name or sender_name} below.

Invoice Number: {inv.number}
Issue Date: {inv.issue_date}
Due Date: {inv.due_date}

Line Items:
"""
    for li in inv.line_items:
        item_label = f"{li.name} - {li.description}" if li.name else li.description
        body += f"  - {item_label} x{int(li.qty)} @ ${li.price:.2f}\n"
    body += f"""
Total Amount Due: ${inv.due:.2f}

Payment is due by {inv.due_date}. If you have any questions about this invoice, please reply to this email.

Thank you for your business!

Best regards,
{company_name or sender_name}
{company_address or ''}
{company_email or ''}
{company_phone or ''}

To unsubscribe from these emails, reply with 'unsubscribe' in the subject line."""

    html_body = f"""
    <html>
      <body style="font-family: 'Helvetica Neue', Arial, sans-serif; color: #1e293b; line-height: 1.6; margin: 0; padding: 0; background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);">
        <div style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
          <div style="background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 25px 60px rgba(0,0,0,0.3);">
            <!-- Gradient Header -->
            <div style="background: linear-gradient(135deg, #0ea5e9 0%, #7877c6 50%, #00f0ff 100%); padding: 40px; text-align: center; position: relative;">
              {logo_html}
              <h1 style="font-size: 32px; font-weight: 800; color: #ffffff; margin: 0 0 8px 0; text-shadow: 0 2px 4px rgba(0,0,0,0.2);">INVOICE</h1>
              <p style="font-size: 16px; color: rgba(255,255,255,0.9); margin: 0; font-weight: 600;">{inv.number}</p>
              <div style="margin-top: 16px; display: inline-block; background: rgba(255,255,255,0.2); padding: 6px 16px; border-radius: 20px;">
                <span style="font-size: 13px; color: #ffffff; font-weight: 600;">Amount Due: ${inv.due:.2f}</span>
              </div>
            </div>

            <!-- Company Details Bar -->
            {f'''
            <div style="background: #f8fafc; padding: 16px 40px; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
              <div style="font-size: 13px; color: #475569;">
                <strong style="color: #1e293b;">{company_name}</strong>
                {f' &bull; {company_address}' if company_address else ''}
              </div>
              <div style="font-size: 13px; color: #475569;">
                {f'{company_email}' if company_email else ''}
                {f' &bull; {company_phone}' if company_phone else ''}
              </div>
            </div>
            ''' if company_name else ''}

            <!-- Body -->
            <div style="padding: 40px;">
              <p style="font-size: 16px; color: #1e293b; margin: 0 0 6px 0;">Hello <strong>{inv.to_contact}</strong>,</p>
              <p style="font-size: 14px; color: #64748b; margin: 0 0 32px 0;">Here's your invoice from <strong>{company_name or sender_name}</strong>. Please find the details below.</p>

              <!-- Invoice Details Cards -->
              <div style="display: flex; gap: 16px; margin-bottom: 32px;">
                <div style="flex: 1; background: #f1f5f9; border-radius: 10px; padding: 16px; text-align: center;">
                  <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: #64748b; margin-bottom: 4px;">Issue Date</div>
                  <div style="font-size: 14px; font-weight: 600; color: #1e293b;">{inv.issue_date}</div>
                </div>
                <div style="flex: 1; background: #f1f5f9; border-radius: 10px; padding: 16px; text-align: center;">
                  <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: #64748b; margin-bottom: 4px;">Due Date</div>
                  <div style="font-size: 14px; font-weight: 600; color: #1e293b;">{inv.due_date}</div>
                </div>
                <div style="flex: 1; background: #f1f5f9; border-radius: 10px; padding: 16px; text-align: center;">
                  <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: #64748b; margin-bottom: 4px;">Invoice #</div>
                  <div style="font-size: 14px; font-weight: 600; color: #1e293b;">{inv.number}</div>
                </div>
              </div>

              <!-- Line Items -->
              {line_items_html}

              <!-- Total -->
              <div style="background: linear-gradient(135deg, #0ea5e9, #7877c6); border-radius: 12px; padding: 24px; text-align: right; margin-top: 24px;">
                <div style="font-size: 13px; color: rgba(255,255,255,0.8); margin-bottom: 4px;">TOTAL AMOUNT</div>
                <div style="font-size: 32px; font-weight: 800; color: #ffffff;">${inv.due:.2f}</div>
              </div>

              <!-- Payment Note -->
              <div style="margin-top: 32px; padding: 20px; background: #fefce8; border-radius: 10px; border-left: 4px solid #fcd34d;">
                <p style="font-size: 13px; color: #854d0e; margin: 0;"><strong>Payment Terms:</strong> Please pay by {inv.due_date}. For any questions, reply to this email.</p>
              </div>
            </div>

            <!-- Footer -->
            <div style="padding: 24px 40px; background: #f8fafc; border-top: 1px solid #e2e8f0; text-align: center;">
              <p style="font-size: 13px; color: #94a3b8; margin: 0 0 4px 0;">Thank you for your business!</p>
              <p style="font-size: 12px; color: #cbd5e1; margin: 0;">{sender_name}</p>
              {f'<p style="font-size:11px;color:#94a3b8;margin:4px 0 0 0;">{company_address}</p>' if company_address else ''}
              {f'<p style="font-size:11px;color:#94a3b8;margin:4px 0 0 0;">{company_email}</p>' if company_email else ''}
              {f'<p style="font-size:11px;color:#94a3b8;margin:4px 0 0 0;">{company_website}</p>' if company_website else ''}
              <p style="font-size:10px; color:#cbd5e1; margin:12px 0 0 0;"><a href="mailto:{company_email}?subject=unsubscribe" style="color:#94a3b8;">Unsubscribe</a> from these notifications</p>
            </div>
          </div>
        </div>
        <img src="{request.base_url}api/track/open/{inv.tracking_id}" width="1" height="1" style="display:none;" alt="">
      </body>
    </html>
    """

    pdf_b64 = payload.pdf_data if payload.pdf_data else None
    pdf_filename = f"{inv.number}.pdf" if pdf_b64 else "invoice.pdf"

    background_tasks.add_task(send_email_background, inv.email, subject, body, from_header, html_body, pdf_b64, pdf_filename)

    inv.status = "Sent"
    inv.sent = datetime.now().strftime("%Y-%m-%d")
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

    message = f"Hello {inv.to_contact},\n\nPlease find the details of your invoice {inv.number} below:\n\nTotal Due: ${inv.due:.2f}\nDue Date: {inv.due_date}\n\nThank you for your business!"
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

@app.post("/api/contacts")
def create_contact(request: Request, body: dict = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    if not body or not body.get("name"):
        return {"error": "Name required"}
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

# --- Google OAuth ---

@app.get("/api/auth/login")
async def login(request: Request, role: str = "client"):
    request.session['oauth_role'] = role
    redirect_uri = str(request.url_for('auth_callback'))
    if redirect_uri.startswith('http://'):
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
                try:
                    setting = db.query(models.DBSettings).filter(
                        models.DBSettings.key == "GOOGLE_REFRESH_TOKEN"
                    ).first()
                    if not setting:
                        setting = models.DBSettings(key="GOOGLE_REFRESH_TOKEN", value=refresh_token)
                        db.add(setting)
                    else:
                        setting.value = refresh_token
                    db.commit()
                except Exception as e:
                    logger.error(f"Failed to save refresh token: {e}")

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
                    request.session['client_id'] = existing_client.id
                    log_login(db, existing_client.id, google_email, "client", "google", request, "success")
                    if existing_client.is_onboarded:
                        return RedirectResponse(url="/app.html")
                    else:
                        return RedirectResponse(url="/onboard.html")
                else:
                    new_client = models.DBClient(
                        email=google_email,
                        password_hash=hash_password(secrets.token_hex(16)),
                        company_name=user.get('name', ''),
                        contact_name=user.get('name', ''),
                        is_onboarded=False,
                    )
                    db.add(new_client)
                    db.commit()
                    db.refresh(new_client)
                    request.session['client_id'] = new_client.id
                    log_login(db, new_client.id, google_email, "client", "google", request, "success")
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
    return JSONResponse(status_code=200, content={"error": "Not authenticated"})

@app.get("/api/auth/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")

@app.get("/api/gmail/status")
def gmail_status(request: Request, db: Session = Depends(get_db)):
    user = request.session.get('user')
    refresh_token = get_stored_refresh_token(db)
    return {
        "logged_in": bool(user),
        "user_email": user.get('email') if user else None,
        "user_name": user.get('name') if user else None,
        "refresh_token_stored": bool(refresh_token),
        "gmail_ready": bool(refresh_token)
    }

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
        emp_count = db.query(models.DBEmployee).filter(models.DBEmployee.department_id == d.id).count()
        result.append({
            "id": d.id, "name": d.name, "description": d.description,
            "employee_count": emp_count, "created_at": d.created_at,
        })
    return result

@app.post("/api/departments")
def create_department(request: Request, body: DepartmentCreate, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    existing = db.query(models.DBDepartment).filter(
        models.DBDepartment.name == body.name, models.DBDepartment.client_id == client.id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Department already exists")
    dept = models.DBDepartment(name=body.name, description=body.description, client_id=client.id)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return {"id": dept.id, "name": dept.name, "description": dept.description, "employee_count": 0}

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

    emp_count = db.query(models.DBEmployee).filter(models.DBEmployee.client_id == client.id).count()
    emp_number = f"EMP-{emp_count + 1:04d}" if not body.employee_id else body.employee_id

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

    db.commit()
    db.refresh(emp)
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
    if body:
        for key, val in body.items():
            if hasattr(emp, key) and key not in ("id", "client_id", "created_at"):
                setattr(emp, key, val)
    db.commit()
    return {"message": "Employee updated"}

@app.delete("/api/employees/{emp_id}")
def delete_employee(emp_id: int, request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == emp_id, models.DBEmployee.client_id == client.id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    db.query(models.DBOnboardingItem).filter(models.DBOnboardingItem.employee_id == emp_id).delete()
    db.query(models.DBPayslip).filter(models.DBPayslip.employee_id == emp_id).delete()
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

@app.get("/api/employees/{emp_id}/onboarding")
def get_onboarding(emp_id: int, request: Request, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == emp_id, models.DBEmployee.client_id == client.id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    items = db.query(models.DBOnboardingItem).filter(models.DBOnboardingItem.employee_id == emp_id).all()
    completed = sum(1 for i in items if i.is_completed)
    return {
        "total": len(items), "completed": completed,
        "progress": round((completed / len(items)) * 100) if items else 0,
        "items": [{"id": i.id, "title": i.title, "description": i.description,
                    "category": i.category, "is_completed": i.is_completed,
                    "completed_at": i.completed_at, "assigned_to": i.assigned_to,
                    "due_date": i.due_date} for i in items],
    }

@app.put("/api/onboarding/{item_id}")
def update_onboarding_item(item_id: int, request: Request, body: dict = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    item = db.query(models.DBOnboardingItem).filter(models.DBOnboardingItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if body:
        if "is_completed" in body:
            item.is_completed = body["is_completed"]
            if body["is_completed"]:
                item.completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if "title" in body:
            item.title = body["title"]
        if "assigned_to" in body:
            item.assigned_to = body["assigned_to"]
        if "due_date" in body:
            item.due_date = body["due_date"]
    db.commit()
    # Check if all items completed
    emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == item.employee_id).first()
    if emp:
        all_items = db.query(models.DBOnboardingItem).filter(models.DBOnboardingItem.employee_id == emp.id).all()
        if all_items and all(i.is_completed for i in all_items):
            emp.onboarding_complete = True
            emp.status = "active"
            db.commit()
    return {"message": "Item updated"}

@app.post("/api/employees/{emp_id}/onboarding")
def add_onboarding_item(emp_id: int, request: Request, body: dict = None, db: Session = Depends(get_db)):
    client = get_client_user(request, db)
    emp = db.query(models.DBEmployee).filter(models.DBEmployee.id == emp_id, models.DBEmployee.client_id == client.id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    item = models.DBOnboardingItem(
        client_id=client.id, employee_id=emp_id,
        title=body.get("title", ""), description=body.get("description", ""),
        category=body.get("category", "general"), assigned_to=body.get("assigned_to", ""),
        due_date=body.get("due_date", ""),
    )
    db.add(item)
    db.commit()
    return {"id": item.id, "title": item.title, "message": "Item added"}

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
            if hasattr(ps, key) and key not in ("id", "client_id", "created_at", "tracking_id"):
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
Gross Pay: ${ps.gross_pay:.2f}
Tax: ${ps.tax_amount:.2f}
Total Deductions: ${ps.total_deductions:.2f}
Net Pay: ${ps.net_pay:.2f}

Best regards,
{company_name}
{company_address}
{company_email}
{company_phone}"""

    html_body = f"""<html><body style="font-family:'Helvetica Neue',Arial,sans-serif;color:#1e293b;margin:0;padding:0;background:linear-gradient(135deg,#0f172a 0%,#1e1b4b 50%,#0f172a 100%);">
<div style="max-width:600px;margin:0 auto;padding:40px 20px;">
<div style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 25px 60px rgba(0,0,0,0.3);">
<div style="background:linear-gradient(135deg,#0ea5e9 0%,#7877c6 50%,#00f0ff 100%);padding:40px;text-align:center;">
{logo_html}
<h1 style="font-size:32px;font-weight:800;color:#fff;margin:0 0 8px 0;">PAYSLIP</h1>
<p style="font-size:16px;color:rgba(255,255,255,0.9);margin:0;">{ps.number}</p>
<div style="margin-top:16px;display:inline-block;background:rgba(255,255,255,0.2);padding:6px 16px;border-radius:20px;">
<span style="font-size:13px;color:#fff;font-weight:600;">Net Pay: ${ps.net_pay:.2f}</span>
</div>
</div>
<div style="background:#f8fafc;padding:16px 40px;border-bottom:1px solid #e2e8f0;display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;">
<div style="font-size:13px;color:#475569;"><strong style="color:#1e293b;">{company_name}</strong>{f' &bull; {company_address}' if company_address else ''}</div>
<div style="font-size:13px;color:#475569;">{f'{company_email}' if company_email else ''}{f' &bull; {company_phone}' if company_phone else ''}</div>
</div>
<div style="padding:40px;">
<p style="font-size:16px;color:#1e293b;margin:0 0 6px 0;">Hello <strong>{emp.first_name}</strong>,</p>
<p style="font-size:14px;color:#64748b;margin:0 0 24px 0;">Here's your payslip from <strong>{company_name}</strong> for the period {ps.period_start} to {ps.period_end}.</p>
<div style="display:flex;gap:16px;margin-bottom:24px;">
<div style="flex:1;background:#f1f5f9;border-radius:10px;padding:16px;text-align:center;">
<div style="font-size:11px;font-weight:700;text-transform:uppercase;color:#64748b;margin-bottom:4px;">Period Start</div>
<div style="font-size:14px;font-weight:600;">{ps.period_start}</div>
</div>
<div style="flex:1;background:#f1f5f9;border-radius:10px;padding:16px;text-align:center;">
<div style="font-size:11px;font-weight:700;text-transform:uppercase;color:#64748b;margin-bottom:4px;">Period End</div>
<div style="font-size:14px;font-weight:600;">{ps.period_end}</div>
</div>
<div style="flex:1;background:#f1f5f9;border-radius:10px;padding:16px;text-align:center;">
<div style="font-size:11px;font-weight:700;text-transform:uppercase;color:#64748b;margin-bottom:4px;">Pay Date</div>
<div style="font-size:14px;font-weight:600;">{ps.pay_date}</div>
</div>
</div>
<table style="width:100%;border-collapse:collapse;margin-bottom:24px;">
<tr style="background:#f8fafc;"><th style="padding:10px 16px;text-align:left;font-size:11px;font-weight:700;text-transform:uppercase;color:#64748b;">Description</th><th style="padding:10px 16px;text-align:right;font-size:11px;font-weight:700;text-transform:uppercase;color:#64748b;">Amount</th></tr>
<tr><td style="padding:10px 16px;border-bottom:1px solid #f1f5f9;">Basic Salary</td><td style="padding:10px 16px;text-align:right;border-bottom:1px solid #f1f5f9;font-weight:600;">${ps.basic_salary:.2f}</td></tr>
<tr><td style="padding:10px 16px;border-bottom:1px solid #f1f5f9;">Overtime Pay</td><td style="padding:10px 16px;text-align:right;border-bottom:1px solid #f1f5f9;font-weight:600;">${ps.overtime_pay:.2f}</td></tr>
<tr><td style="padding:10px 16px;border-bottom:1px solid #f1f5f9;">Bonus</td><td style="padding:10px 16px;text-align:right;border-bottom:1px solid #f1f5f9;font-weight:600;">${ps.bonus:.2f}</td></tr>
<tr><td style="padding:10px 16px;border-bottom:1px solid #f1f5f9;">Allowances</td><td style="padding:10px 16px;text-align:right;border-bottom:1px solid #f1f5f9;font-weight:600;">${ps.allowances:.2f}</td></tr>
<tr style="font-weight:700;background:#f0fdf4;"><td style="padding:12px 16px;">Gross Pay</td><td style="padding:12px 16px;text-align:right;color:#16a34a;">${ps.gross_pay:.2f}</td></tr>
<tr><td style="padding:10px 16px;border-bottom:1px solid #f1f5f9;color:#dc2626;">Tax</td><td style="padding:10px 16px;text-align:right;border-bottom:1px solid #f1f5f9;color:#dc2626;">-${ps.tax_amount:.2f}</td></tr>
<tr><td style="padding:10px 16px;border-bottom:1px solid #f1f5f9;color:#dc2626;">Insurance</td><td style="padding:10px 16px;text-align:right;border-bottom:1px solid #f1f5f9;color:#dc2626;">-${ps.insurance:.2f}</td></tr>
<tr><td style="padding:10px 16px;border-bottom:1px solid #f1f5f9;color:#dc2626;">Retirement</td><td style="padding:10px 16px;text-align:right;border-bottom:1px solid #f1f5f9;color:#dc2626;">-${ps.retirement:.2f}</td></tr>
<tr><td style="padding:10px 16px;border-bottom:1px solid #f1f5f9;color:#dc2626;">Other Deductions</td><td style="padding:10px 16px;text-align:right;border-bottom:1px solid #f1f5f9;color:#dc2626;">-${ps.other_deductions:.2f}</td></tr>
<tr style="font-weight:700;background:#fef2f2;"><td style="padding:12px 16px;">Total Deductions</td><td style="padding:12px 16px;text-align:right;color:#dc2626;">-${ps.total_deductions:.2f}</td></tr>
</table>
<div style="background:linear-gradient(135deg,#0ea5e9,#7877c6);border-radius:12px;padding:24px;text-align:right;">
<div style="font-size:13px;color:rgba(255,255,255,0.8);margin-bottom:4px;">NET PAY</div>
<div style="font-size:32px;font-weight:800;color:#fff;">${ps.net_pay:.2f}</div>
</div>
</div>
<div style="padding:24px 40px;background:#f8fafc;border-top:1px solid #e2e8f0;text-align:center;">
<p style="font-size:13px;color:#94a3b8;margin:0;">Thank you for your hard work!</p>
<p style="font-size:12px;color:#cbd5e1;margin:4px 0 0 0;">{company_name}</p>
</div>
</div>
</div></body></html>
<img src="{request.base_url}api/payslip/track/open/{ps.tracking_id}" width="1" height="1" style="display:none;" alt="">
"""

    pdf_b64 = payload.pdf_data if payload.pdf_data else None
    pdf_filename = f"{ps.number}.pdf" if pdf_b64 else "payslip.pdf"

    background_tasks.add_task(send_email_background, emp.email, subject, body_text, from_header, html_body, pdf_b64, pdf_filename)
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
def employee_login(body: dict = None, request: Request = None, db: Session = Depends(get_db)):
    if not body or not body.get("email") or not body.get("password"):
        raise HTTPException(status_code=400, detail="Email and password required")
    email = body["email"].strip().lower()
    emp = db.query(models.DBEmployee).filter(models.DBEmployee.email.ilike(email)).first()
    if not emp:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not emp.password_hash:
        raise HTTPException(status_code=401, detail="Password not set. Contact your administrator.")
    if models.hash_password(body["password"]) != emp.password_hash:
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
        break_stop = datetime.strptime(today_str + " " + att.break_start, "%Y-%m-%d %H:%M:%S")
        break_start = datetime.strptime(today_str + " " + att.break_start, "%Y-%m-%d %H:%M:%S")
        elapsed = round((now - break_start).total_seconds() / 60, 1)
        att.break_minutes = (att.break_minutes or 0) + elapsed
    except Exception:
        pass
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
    total_hours = sum(r.total_hours for r in records if r.total_hours)
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
