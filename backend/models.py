from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, UniqueConstraint, Text
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
import uuid
import hashlib
import os


def hash_password(password: str) -> str:
    salt = hashlib.sha256(os.urandom(32)).hexdigest().encode()
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    return salt.hex() + ':' + pwd_hash.hex()


def verify_password(password: str, stored: str) -> bool:
    if ':' not in stored:
        return hashlib.sha256(password.encode()).hexdigest() == stored
    salt_hex, pwd_hash_hex = stored.split(':')
    salt = bytes.fromhex(salt_hex)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    return pwd_hash.hex() == pwd_hash_hex


class DBClient(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    company_name = Column(String, default="")
    contact_name = Column(String, default="")
    phone_number = Column(String, default="")
    logo_url = Column(String, default="")
    address = Column(String, default="")
    website = Column(String, default="")
    abn = Column(String, default="")
    industry = Column(String, default="")
    is_active = Column(Boolean, default=True)
    is_onboarded = Column(Boolean, default=False)
    currency = Column(String, default="GBP")
    last_login = Column(String, default="")
    login_count = Column(Integer, default=0)
    created_at = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    settings = relationship("DBSettings", back_populates="client")
    invoices = relationship("DBInvoice", back_populates="client")
    bills = relationship("DBBill", back_populates="client")
    contacts = relationship("DBContact", back_populates="client")
    departments = relationship("DBDepartment", back_populates="client")
    employees = relationship("DBEmployee", back_populates="client")
    attendance = relationship("DBAttendance")


class DBInvoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint('client_id', 'number', name='uq_client_invoice_number'),
    )

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    number = Column(String, index=True)
    ref = Column(String, default="")
    to_contact = Column(String)
    email = Column(String, default="")
    phone_number = Column(String, default="")
    issue_date = Column(String)
    due_date = Column(String)
    paid = Column(Float, default=0.0)
    due = Column(Float, default=0.0)
    status = Column(String, default="Draft", index=True)
    sent = Column(String, default="")
    tax_type = Column(String, default="exclusive")
    currency = Column(String, default="")
    bank_details = Column(String, default="")
    tracking_id = Column(String, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    open_count = Column(Integer, default=0)
    last_opened = Column(String, default="")

    line_items = relationship("DBLineItem", back_populates="invoice")
    client = relationship("DBClient", back_populates="invoices")


class DBLineItem(Base):
    __tablename__ = "line_items"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), index=True)
    name = Column(String, default="")
    description = Column(String)
    qty = Column(Float)
    price = Column(Float)
    disc = Column(Float, default=0.0)
    account = Column(String, default="200 - Sales")
    tax_rate = Column(String, default="20% (VAT on Income)")

    invoice = relationship("DBInvoice", back_populates="line_items")


class DBSettings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    key = Column(String, index=True)
    value = Column(String)
    description = Column(String, default="")

    client = relationship("DBClient", back_populates="settings")


class DBContact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    name = Column(String, index=True)
    email = Column(String)
    phone_number = Column(String)

    client = relationship("DBClient", back_populates="contacts")


class DBSuperAdmin(Base):
    __tablename__ = "super_admins"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    email = Column(String, default="")
    created_at = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class DBAdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)


class DBDepartment(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, default="")
    color = Column(String, default="#00f0ff")
    icon = Column(String, default="building")
    created_at = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    client = relationship("DBClient", back_populates="departments")
    employees = relationship("DBEmployee", back_populates="department")


class DBEmployee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    reports_to = Column(Integer, ForeignKey("employees.id"), nullable=True, index=True)

    employee_id = Column(String, default="")
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String, default="")
    address = Column(String, default="")

    job_title = Column(String, default="")
    role = Column(String, default="employee")
    employment_type = Column(String, default="full_time")
    pay_frequency = Column(String, default="monthly")

    salary = Column(Float, default=0.0)
    hourly_rate = Column(Float, default=0.0)
    tax_rate = Column(Float, default=0.0)
    deductions = Column(Float, default=0.0)
    allowances = Column(Float, default=0.0)
    bonus = Column(Float, default=0.0)

    bank_name = Column(String, default="")
    bank_account = Column(String, default="")
    tax_id = Column(String, default="")

    emergency_contact = Column(String, default="")
    emergency_phone = Column(String, default="")

    password_hash = Column(String, default="")
    work_location = Column(String, default="")
    latitude = Column(Float, default=0.0)
    longitude = Column(Float, default=0.0)

    start_date = Column(String, default="")
    end_date = Column(String, default="")
    status = Column(String, default="active", index=True)
    onboarding_complete = Column(Boolean, default=False)
    offboarding_complete = Column(Boolean, default=False)

    created_at = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    client = relationship("DBClient", back_populates="employees")
    department = relationship("DBDepartment", back_populates="employees")
    manager = relationship("DBEmployee", remote_side=[id], backref="direct_reports")
    payslips = relationship("DBPayslip", back_populates="employee")
    onboarding_items = relationship("DBOnboardingItem", back_populates="employee")
    attendance = relationship("DBAttendance")


class DBPayslip(Base):
    __tablename__ = "payslips"
    __table_args__ = (
        UniqueConstraint('client_id', 'number', name='uq_client_payslip_number'),
    )

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    number = Column(String, index=True)

    period_start = Column(String, default="")
    period_end = Column(String, default="")
    pay_date = Column(String, default="")

    hours_worked = Column(Float, default=0.0)
    overtime_hours = Column(Float, default=0.0)
    overtime_rate = Column(Float, default=0.0)

    basic_salary = Column(Float, default=0.0)
    overtime_pay = Column(Float, default=0.0)
    bonus = Column(Float, default=0.0)
    allowances = Column(Float, default=0.0)
    gross_pay = Column(Float, default=0.0)

    tax_amount = Column(Float, default=0.0)
    insurance = Column(Float, default=0.0)
    retirement = Column(Float, default=0.0)
    other_deductions = Column(Float, default=0.0)
    total_deductions = Column(Float, default=0.0)

    net_pay = Column(Float, default=0.0)

    status = Column(String, default="Draft", index=True)
    sent = Column(String, default="")
    notes = Column(String, default="")

    tracking_id = Column(String, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    open_count = Column(Integer, default=0)
    last_opened = Column(String, default="")
    created_at = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    employee = relationship("DBEmployee", back_populates="payslips")


class DBOnboardingItem(Base):
    __tablename__ = "onboarding_items"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)

    title = Column(String, nullable=False)
    description = Column(String, default="")
    category = Column(String, default="general")
    is_completed = Column(Boolean, default=False)
    completed_at = Column(String, default="")
    assigned_to = Column(String, default="")
    due_date = Column(String, default="")
    sort_order = Column(Integer, default=0)

    employee = relationship("DBEmployee", back_populates="onboarding_items")


class DBOnboardingTemplate(Base):
    __tablename__ = "onboarding_templates"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    name = Column(String, nullable=False)
    items_json = Column(Text, default="[]")
    created_at = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class DBAttendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    date = Column(String, nullable=False, index=True)
    clock_in = Column(String, default="")
    clock_out = Column(String, default="")
    total_hours = Column(Float, default=0.0)
    status = Column(String, default="present", index=True)
    check_type = Column(String, default="manual")
    ip_address = Column(String, default="")
    device_info = Column(String, default="")
    location_lat = Column(Float, default=0.0)
    location_lng = Column(Float, default=0.0)
    location_label = Column(String, default="")
    break_start = Column(String, default="")
    break_minutes = Column(Float, default=0.0)
    is_on_break = Column(Boolean, default=False)
    overtime_hours = Column(Float, default=0.0)
    overtime_announced = Column(Boolean, default=False)
    overtime_announced_by = Column(String, default="")
    notes = Column(String, default="")
    created_at = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class DBAttendanceSettings(Base):
    __tablename__ = "attendance_settings"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, unique=True)
    office_name = Column(String, default="Head Office")
    office_lat = Column(Float, default=0.0)
    office_lng = Column(Float, default=0.0)
    geofence_radius = Column(Float, default=200.0)
    work_start = Column(String, default="09:00")
    work_end = Column(String, default="17:30")
    grace_minutes = Column(Float, default=15.0)
    auto_clockout_hours = Column(Float, default=10.0)
    max_overtime_hours = Column(Float, default=4.0)
    allow_remote = Column(Boolean, default=True)
    require_location = Column(Boolean, default=True)
    created_at = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class DBClientLoginLog(Base):
    __tablename__ = "client_login_logs"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    email = Column(String, nullable=False)
    user_type = Column(String, default="client")
    login_type = Column(String, default="password")
    ip_address = Column(String, default="")
    device_info = Column(String, default="")
    location_label = Column(String, default="")
    status = Column(String, default="success")
    created_at = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class DBOvertimeLog(Base):
    __tablename__ = "overtime_logs"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    date = Column(String, nullable=False)
    hours = Column(Float, default=0.0)
    reason = Column(String, default="")
    announced_by = Column(String, default="")
    status = Column(String, default="announced")
    created_at = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class DBRecruitmentForm(Base):
    __tablename__ = "recruitment_forms"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, default="")
    fields = Column(Text, default="[]")
    is_active = Column(Boolean, default=True)
    form_token = Column(String, unique=True, index=True, default=lambda: str(__import__('uuid').uuid4()))
    pipeline_stages = Column(Text, default='["Applied","Screening","Interview","Offer","Hired"]')
    created_at = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class DBFormSubmission(Base):
    __tablename__ = "form_submissions"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    form_id = Column(Integer, ForeignKey("recruitment_forms.id"), nullable=False, index=True)
    answers = Column(Text, default="{}")
    file_name = Column(String, default="")
    file_type = Column(String, default="")
    file_data = Column(Text, default="")
    candidate_name = Column(String, default="")
    candidate_email = Column(String, default="")
    status = Column(String, default="new")
    current_stage = Column(String, default="Applied")
    stage_order = Column(Integer, default=0)
    notes = Column(String, default="")
    created_at = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    form = relationship("DBRecruitmentForm")


class DBEmployeeGoal(Base):
    __tablename__ = "employee_goals"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, default="")
    target_value = Column(Float, default=100.0)
    current_value = Column(Float, default=0.0)
    unit = Column(String, default="%")
    category = Column(String, default="performance")
    priority = Column(String, default="medium")
    start_date = Column(String, default="")
    due_date = Column(String, default="")
    status = Column(String, default="in_progress")
    created_by = Column(String, default="HR")
    created_at = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    employee = relationship("DBEmployee")
    department = relationship("DBDepartment")


class DBDepartmentGoal(Base):
    __tablename__ = "department_goals"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(String, default="")
    target_value = Column(Float, default=100.0)
    unit = Column(String, default="%")
    category = Column(String, default="performance")
    priority = Column(String, default="medium")
    start_date = Column(String, default="")
    due_date = Column(String, default="")
    created_by = Column(String, default="HR")
    is_assigned = Column(Boolean, default=False)
    created_at = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    department = relationship("DBDepartment")


class DBAuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    user_type = Column(String, default="client")
    user_name = Column(String, default="")
    action = Column(String, nullable=False)
    entity_type = Column(String, default="")
    entity_id = Column(Integer, nullable=True)
    entity_name = Column(String, default="")
    details = Column(Text, default="")
    ip_address = Column(String, default="")
    created_at = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class DBNotification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    message = Column(String, default="")
    type = Column(String, default="info")
    is_read = Column(Boolean, default=False)
    link = Column(String, default="")
    created_at = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class DBLeaveRequest(Base):
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    leave_type = Column(String, default="annual")
    start_date = Column(String, nullable=False)
    end_date = Column(String, nullable=False)
    days = Column(Float, default=0.0)
    reason = Column(String, default="")
    status = Column(String, default="pending")
    approved_by = Column(String, default="")
    created_at = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    employee = relationship("DBEmployee")


class DBDocument(Base):
    __tablename__ = "employee_documents"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    doc_type = Column(String, default="other")
    file_name = Column(String, default="")
    file_type = Column(String, default="")
    file_data = Column(Text, default="")
    uploaded_by = Column(String, default="HR")
    created_at = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class DBBill(Base):
    __tablename__ = "bills"
    __table_args__ = (
        UniqueConstraint('client_id', 'number', name='uq_client_bill_number'),
    )

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    number = Column(String, index=True)
    vendor_name = Column(String, default="")
    vendor_email = Column(String, default="")
    issue_date = Column(String)
    due_date = Column(String)
    amount = Column(Float, default=0.0)
    tax_amount = Column(Float, default=0.0)
    total = Column(Float, default=0.0)
    amount_paid = Column(Float, default=0.0)
    status = Column(String, default="Draft", index=True)
    category = Column(String, default="general")
    reference = Column(String, default="")
    notes = Column(String, default="")

    created_at = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    client = relationship("DBClient", back_populates="bills")

    line_items = relationship("DBBillLineItem", back_populates="bill")


class DBBillLineItem(Base):
    __tablename__ = "bill_line_items"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), index=True)
    description = Column(String, default="")
    qty = Column(Float, default=1.0)
    price = Column(Float, default=0.0)
    tax_rate = Column(String, default="20%")

    bill = relationship("DBBill", back_populates="line_items")
