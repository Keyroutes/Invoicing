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
    response = await call_next(request)
    path = request.url.path
    if path.endswith(".html") or path == "/":
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
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not client.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    request.session["client_id"] = client.id
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

@app.get("/api/superadmin/clients")
def superadmin_clients(request: Request, db: Session = Depends(get_db)):
    sa_id = request.session.get("superadmin_id")
    if not sa_id:
        raise HTTPException(status_code=401, detail="Not authorized")
    clients = db.query(models.DBClient).all()
    result = []
    for c in clients:
        invoice_count = db.query(models.DBInvoice).filter(models.DBInvoice.client_id == c.id).count()
        total_revenue = db.query(models.DBInvoice).filter(models.DBInvoice.client_id == c.id, models.DBInvoice.status == "Paid").count()
        total_outstanding = sum(inv.due for inv in db.query(models.DBInvoice).filter(models.DBInvoice.client_id == c.id, models.DBInvoice.status != "Paid").all())
        result.append({
            "id": c.id,
            "email": c.email,
            "company_name": c.company_name,
            "contact_name": c.contact_name,
            "phone_number": c.phone_number,
            "is_active": c.is_active,
            "is_onboarded": c.is_onboarded,
            "created_at": c.created_at,
            "invoice_count": invoice_count,
            "paid_count": total_revenue,
            "outstanding": round(total_outstanding, 2),
        })
    return result

@app.get("/api/superadmin/insights")
def superadmin_insights(request: Request, db: Session = Depends(get_db)):
    sa_id = request.session.get("superadmin_id")
    if not sa_id:
        raise HTTPException(status_code=401, detail="Not authorized")
    total_clients = db.query(models.DBClient).count()
    active_clients = db.query(models.DBClient).filter(models.DBClient.is_active == True).count()
    onboarded = db.query(models.DBClient).filter(models.DBClient.is_onboarded == True).count()
    total_invoices = db.query(models.DBInvoice).count()
    total_revenue = sum(inv.due for inv in db.query(models.DBInvoice).filter(models.DBInvoice.status == "Paid").all())
    total_outstanding = sum(inv.due for inv in db.query(models.DBInvoice).filter(models.DBInvoice.status != "Paid").all())
    return {
        "total_clients": total_clients,
        "active_clients": active_clients,
        "onboarded_clients": onboarded,
        "total_invoices": total_invoices,
        "total_revenue": round(total_revenue, 2),
        "total_outstanding": round(total_outstanding, 2),
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
        msg['X-Mailer'] = 'All in One Invoicing Solutions'
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
            msg['X-Mailer'] = 'All in One Invoicing Solutions'
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
def get_invoice(number: str, db: Session = Depends(get_db)):
    inv = db.query(models.DBInvoice).filter(models.DBInvoice.number == number).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    client = db.query(models.DBClient).filter(models.DBClient.id == inv.client_id).first() if inv.client_id else None
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

    return get_invoice(number, db)

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
def get_open_stats(number: str, db: Session = Depends(get_db)):
    inv = db.query(models.DBInvoice).filter(models.DBInvoice.number == number).first()
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
    contacts = db.query(models.DBContact).filter(models.DBContact.client_id == client.id).all()
    if q:
        q_lower = q.lower()
        contacts = [c for c in contacts if q_lower in (c.name or "").lower() or q_lower in (c.email or "").lower()]
    return [{"id": c.id, "name": c.name, "email": c.email or "", "phone_number": c.phone_number or ""} for c in contacts[:10]]

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
    redirect_uri = request.url_for('auth_callback')
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
                    return RedirectResponse(url="/superadmin.html")
                else:
                    return RedirectResponse(url="/superadmin-login.html?error=not_admin")

            if google_email:
                sa_check = db.query(models.DBSuperAdmin).filter(models.DBSuperAdmin.email == google_email).first()
                if sa_check:
                    return RedirectResponse(url="/superadmin-login.html")
                existing_client = db.query(models.DBClient).filter(models.DBClient.email == google_email).first()
                if existing_client:
                    request.session['client_id'] = existing_client.id
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
    sender_name = os.getenv("FROM_NAME", "Accounting Platform")
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
