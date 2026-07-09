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
    engine = create_engine(DATABASE_URL)

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

            # Backfill tracking_ids for existing invoices
            result = conn.execute(text("SELECT id FROM invoices WHERE tracking_id IS NULL OR tracking_id = ''"))
            rows = result.fetchall()
            if rows:
                for row in rows:
                    conn.execute(text(f"UPDATE invoices SET tracking_id = '{uuid.uuid4()}' WHERE id = {row[0]}"))
                conn.commit()
                print(f"Backfilled tracking_id for {len(rows)} invoices")

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

    except Exception as e:
        print(f"Column check skipped: {e}")
