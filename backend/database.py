import os
import uuid
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")

# SQLAlchemy 1.4+ requires postgresql:// instead of postgres://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if not DATABASE_URL:
    print("WARNING: No DATABASE_URL found in .env, falling back to SQLite")
    DATABASE_URL = "sqlite:///./invoicing.db"

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(
        DATABASE_URL,
        pool_size=2,
        max_overflow=3,
        pool_timeout=10,
        pool_recycle=1800,
        pool_pre_ping=True
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def ensure_columns():
    """Add missing columns to existing tables."""
    if DATABASE_URL.startswith("sqlite"):
        return
    try:
        with engine.connect() as conn:
            # line_items.name
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='line_items' AND column_name='name'"))
            if not result.fetchone():
                conn.execute(text("ALTER TABLE line_items ADD COLUMN name VARCHAR DEFAULT ''"))
                conn.commit()
                print("Added 'name' column to line_items table")

            # invoices.client_id
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='invoices' AND column_name='client_id'"))
            if not result.fetchone():
                conn.execute(text("ALTER TABLE invoices ADD COLUMN client_id INTEGER"))
                conn.commit()
                print("Added 'client_id' column to invoices table")

            # settings.client_id
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='settings' AND column_name='client_id'"))
            if not result.fetchone():
                conn.execute(text("ALTER TABLE settings ADD COLUMN client_id INTEGER"))
                conn.commit()
                print("Added 'client_id' column to settings table")

            # contacts.client_id
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='contacts' AND column_name='client_id'"))
            if not result.fetchone():
                conn.execute(text("ALTER TABLE contacts ADD COLUMN client_id INTEGER"))
                conn.commit()
                print("Added 'client_id' column to contacts table")

            # invoices.tracking_id
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='invoices' AND column_name='tracking_id'"))
            if not result.fetchone():
                conn.execute(text("ALTER TABLE invoices ADD COLUMN tracking_id VARCHAR"))
                conn.commit()
                print("Added 'tracking_id' column to invoices table")

            # invoices.open_count
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='invoices' AND column_name='open_count'"))
            if not result.fetchone():
                conn.execute(text("ALTER TABLE invoices ADD COLUMN open_count INTEGER DEFAULT 0"))
                conn.commit()
                print("Added 'open_count' column to invoices table")

            # invoices.last_opened
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='invoices' AND column_name='last_opened'"))
            if not result.fetchone():
                conn.execute(text("ALTER TABLE invoices ADD COLUMN last_opened VARCHAR DEFAULT ''"))
                conn.commit()
                print("Added 'last_opened' column to invoices table")

            # Backfill tracking_ids for existing invoices (single query, no SQL injection)
            try:
                conn.execute(text("UPDATE invoices SET tracking_id = gen_random_uuid()::text WHERE tracking_id IS NULL OR tracking_id = ''"))
                conn.commit()
            except Exception:
                pass

            # Make settings.key non-unique (now per-client)
            try:
                result = conn.execute(text("SELECT indexname FROM pg_indexes WHERE tablename = :tname AND indexdef LIKE '%UNIQUE%' AND indexdef LIKE '%key%'"), {"tname": "settings"})
                for row in result.fetchall():
                    conn.execute(text(f"DROP INDEX IF EXISTS {row[0]}"))
                    conn.commit()
                    print(f"Dropped unique index on settings.key: {row[0]}")
            except Exception:
                pass
            try:
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_settings_key ON settings (key)"))
                conn.commit()
                print("Created non-unique index ix_settings_key")
            except Exception:
                pass

            # Drop old global unique constraint on invoices.number (now per-client unique)
            try:
                result = conn.execute(text("SELECT indexname FROM pg_indexes WHERE tablename = :tname"), {"tname": "invoices"})
                for row in result.fetchall():
                    idx_name = row[0]
                    if "number" in idx_name and idx_name != "uq_client_invoice_number":
                        conn.execute(text(f"DROP INDEX IF EXISTS {idx_name}"))
                        conn.commit()
                        print(f"Dropped old index: {idx_name}")
            except Exception:
                pass

            # Add composite unique constraint (client_id, number) if not exists
            try:
                conn.execute(text("ALTER TABLE invoices ADD CONSTRAINT uq_client_invoice_number UNIQUE (client_id, number)"))
                conn.commit()
                print("Added composite unique constraint (client_id, number)")
            except Exception:
                pass

            # Create performance indexes on foreign keys (safe to run multiple times)
            idx_statements = [
                "CREATE INDEX IF NOT EXISTS ix_invoices_client_id ON invoices (client_id)",
                "CREATE INDEX IF NOT EXISTS ix_invoices_status ON invoices (status)",
                "CREATE INDEX IF NOT EXISTS ix_line_items_invoice_id ON line_items (invoice_id)",
                "CREATE INDEX IF NOT EXISTS ix_contacts_client_id ON contacts (client_id)",
                "CREATE INDEX IF NOT EXISTS ix_settings_client_id ON settings (client_id)",
            ]
            for stmt in idx_statements:
                try:
                    conn.execute(text(stmt))
                except Exception:
                    pass
            conn.commit()

            # Create HR tables if they don't exist
            hr_tables = [
                """CREATE TABLE IF NOT EXISTS departments (
                    id SERIAL PRIMARY KEY,
                    client_id INTEGER REFERENCES clients(id),
                    name VARCHAR NOT NULL,
                    description VARCHAR DEFAULT '',
                    created_at VARCHAR DEFAULT ''
                )""",
                """CREATE TABLE IF NOT EXISTS employees (
                    id SERIAL PRIMARY KEY,
                    client_id INTEGER REFERENCES clients(id),
                    department_id INTEGER REFERENCES departments(id),
                    reports_to INTEGER REFERENCES employees(id),
                    employee_id VARCHAR DEFAULT '',
                    first_name VARCHAR NOT NULL,
                    last_name VARCHAR NOT NULL,
                    email VARCHAR NOT NULL,
                    phone VARCHAR DEFAULT '',
                    address VARCHAR DEFAULT '',
                    job_title VARCHAR DEFAULT '',
                    role VARCHAR DEFAULT 'employee',
                    employment_type VARCHAR DEFAULT 'full_time',
                    pay_frequency VARCHAR DEFAULT 'monthly',
                    salary DOUBLE PRECISION DEFAULT 0,
                    hourly_rate DOUBLE PRECISION DEFAULT 0,
                    tax_rate DOUBLE PRECISION DEFAULT 0,
                    deductions DOUBLE PRECISION DEFAULT 0,
                    allowances DOUBLE PRECISION DEFAULT 0,
                    bonus DOUBLE PRECISION DEFAULT 0,
                    bank_name VARCHAR DEFAULT '',
                    bank_account VARCHAR DEFAULT '',
                    tax_id VARCHAR DEFAULT '',
                    emergency_contact VARCHAR DEFAULT '',
                    emergency_phone VARCHAR DEFAULT '',
                    start_date VARCHAR DEFAULT '',
                    end_date VARCHAR DEFAULT '',
                    status VARCHAR DEFAULT 'active',
                    onboarding_complete BOOLEAN DEFAULT FALSE,
                    offboarding_complete BOOLEAN DEFAULT FALSE,
                    created_at VARCHAR DEFAULT ''
                )""",
                """CREATE TABLE IF NOT EXISTS payslips (
                    id SERIAL PRIMARY KEY,
                    client_id INTEGER REFERENCES clients(id),
                    employee_id INTEGER REFERENCES employees(id) NOT NULL,
                    number VARCHAR,
                    period_start VARCHAR DEFAULT '',
                    period_end VARCHAR DEFAULT '',
                    pay_date VARCHAR DEFAULT '',
                    hours_worked DOUBLE PRECISION DEFAULT 0,
                    overtime_hours DOUBLE PRECISION DEFAULT 0,
                    overtime_rate DOUBLE PRECISION DEFAULT 0,
                    basic_salary DOUBLE PRECISION DEFAULT 0,
                    overtime_pay DOUBLE PRECISION DEFAULT 0,
                    bonus DOUBLE PRECISION DEFAULT 0,
                    allowances DOUBLE PRECISION DEFAULT 0,
                    gross_pay DOUBLE PRECISION DEFAULT 0,
                    tax_amount DOUBLE PRECISION DEFAULT 0,
                    insurance DOUBLE PRECISION DEFAULT 0,
                    retirement DOUBLE PRECISION DEFAULT 0,
                    other_deductions DOUBLE PRECISION DEFAULT 0,
                    total_deductions DOUBLE PRECISION DEFAULT 0,
                    net_pay DOUBLE PRECISION DEFAULT 0,
                    status VARCHAR DEFAULT 'Draft',
                    sent VARCHAR DEFAULT '',
                    notes VARCHAR DEFAULT '',
                    tracking_id VARCHAR,
                    open_count INTEGER DEFAULT 0,
                    last_opened VARCHAR DEFAULT '',
                    created_at VARCHAR DEFAULT '',
                    UNIQUE(client_id, number)
                )""",
                """CREATE TABLE IF NOT EXISTS onboarding_items (
                    id SERIAL PRIMARY KEY,
                    client_id INTEGER REFERENCES clients(id),
                    employee_id INTEGER REFERENCES employees(id) NOT NULL,
                    title VARCHAR NOT NULL,
                    description VARCHAR DEFAULT '',
                    category VARCHAR DEFAULT 'general',
                    is_completed BOOLEAN DEFAULT FALSE,
                    completed_at VARCHAR DEFAULT '',
                    assigned_to VARCHAR DEFAULT '',
                    due_date VARCHAR DEFAULT ''
                )""",
                """CREATE TABLE IF NOT EXISTS attendance (
                    id SERIAL PRIMARY KEY,
                    client_id INTEGER REFERENCES clients(id),
                    employee_id INTEGER REFERENCES employees(id) NOT NULL,
                    date VARCHAR NOT NULL,
                    clock_in VARCHAR DEFAULT '',
                    clock_out VARCHAR DEFAULT '',
                    total_hours FLOAT DEFAULT 0.0,
                    status VARCHAR DEFAULT 'present',
                    check_type VARCHAR DEFAULT 'manual',
                    ip_address VARCHAR DEFAULT '',
                    device_info VARCHAR DEFAULT '',
                    location_lat FLOAT DEFAULT 0.0,
                    location_lng FLOAT DEFAULT 0.0,
                    location_label VARCHAR DEFAULT '',
                    break_minutes FLOAT DEFAULT 0.0,
                    overtime_hours FLOAT DEFAULT 0.0,
                    notes VARCHAR DEFAULT '',
                    created_at VARCHAR DEFAULT ''
                )""",
                """CREATE TABLE IF NOT EXISTS attendance_settings (
                    id SERIAL PRIMARY KEY,
                    client_id INTEGER REFERENCES clients(id) UNIQUE,
                    office_name VARCHAR DEFAULT 'Head Office',
                    office_lat FLOAT DEFAULT 0.0,
                    office_lng FLOAT DEFAULT 0.0,
                    geofence_radius FLOAT DEFAULT 200.0,
                    work_start VARCHAR DEFAULT '09:00',
                    work_end VARCHAR DEFAULT '17:30',
                    grace_minutes FLOAT DEFAULT 15.0,
                    auto_clockout_hours FLOAT DEFAULT 10.0,
                    max_overtime_hours FLOAT DEFAULT 4.0,
                    allow_remote BOOLEAN DEFAULT TRUE,
                    require_location BOOLEAN DEFAULT TRUE,
                    created_at VARCHAR DEFAULT ''
                )""",
            ]
            for sql in hr_tables:
                try:
                    conn.execute(text(sql))
                except Exception:
                    pass
            conn.commit()

            # Create indexes for HR tables
            hr_indexes = [
                "CREATE INDEX IF NOT EXISTS ix_employees_client_id ON employees (client_id)",
                "CREATE INDEX IF NOT EXISTS ix_employees_department_id ON employees (department_id)",
                "CREATE INDEX IF NOT EXISTS ix_employees_reports_to ON employees (reports_to)",
                "CREATE INDEX IF NOT EXISTS ix_employees_status ON employees (status)",
                "CREATE INDEX IF NOT EXISTS ix_payslips_client_id ON payslips (client_id)",
                "CREATE INDEX IF NOT EXISTS ix_payslips_employee_id ON payslips (employee_id)",
                "CREATE INDEX IF NOT EXISTS ix_payslips_status ON payslips (status)",
                "CREATE INDEX IF NOT EXISTS ix_departments_client_id ON departments (client_id)",
                "CREATE INDEX IF NOT EXISTS ix_onboarding_items_client_id ON onboarding_items (client_id)",
                "CREATE INDEX IF NOT EXISTS ix_onboarding_items_employee_id ON onboarding_items (employee_id)",
                "CREATE INDEX IF NOT EXISTS ix_attendance_client_id ON attendance (client_id)",
                "CREATE INDEX IF NOT EXISTS ix_attendance_employee_id ON attendance (employee_id)",
                "CREATE INDEX IF NOT EXISTS ix_attendance_date ON attendance (date)",
                "CREATE INDEX IF NOT EXISTS ix_attendance_status ON attendance (status)",
                "CREATE INDEX IF NOT EXISTS ix_attendance_settings_client_id ON attendance_settings (client_id)",
            ]
            for stmt in hr_indexes:
                try:
                    conn.execute(text(stmt))
                except Exception:
                    pass
            conn.commit()

            # Add new columns to existing tables
            alter_statements = [
                "ALTER TABLE employees ADD COLUMN IF NOT EXISTS password_hash VARCHAR DEFAULT ''",
                "ALTER TABLE employees ADD COLUMN IF NOT EXISTS work_location VARCHAR DEFAULT ''",
                "ALTER TABLE employees ADD COLUMN IF NOT EXISTS latitude FLOAT DEFAULT 0.0",
                "ALTER TABLE employees ADD COLUMN IF NOT EXISTS longitude FLOAT DEFAULT 0.0",
                "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS check_type VARCHAR DEFAULT 'manual'",
                "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS ip_address VARCHAR DEFAULT ''",
                "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS device_info VARCHAR DEFAULT ''",
                "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS location_lat FLOAT DEFAULT 0.0",
                "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS location_lng FLOAT DEFAULT 0.0",
                "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS location_label VARCHAR DEFAULT ''",
                "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS break_minutes FLOAT DEFAULT 0.0",
                "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS overtime_hours FLOAT DEFAULT 0.0",
            ]
            for stmt in alter_statements:
                try:
                    conn.execute(text(stmt))
                except Exception:
                    pass
            conn.commit()

    except Exception as e:
        print(f"Column check skipped: {e}")
