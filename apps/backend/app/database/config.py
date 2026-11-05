import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

# Use DATABASE_URL if set and not pointing to missing postgres, else fallback to sqlite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///form141.db")
ENV = os.getenv("ENV", "development").lower()

if "postgresql" in DATABASE_URL and ENV != "production":
    # In development mode only, check connectivity and fallback to SQLite if postgres is not reachable
    import socket
    from urllib.parse import urlparse
    try:
        parsed = urlparse(DATABASE_URL)
        pg_host = parsed.hostname or "localhost"
        pg_port = parsed.port or 5432
        sock = socket.create_connection((pg_host, pg_port), timeout=0.8)
        sock.close()
    except Exception:
        DATABASE_URL = "sqlite:///form141.db"


engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_pre_ping"] = True

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Ensure all database tables exist."""
    from apps.backend.app.database import models  # noqa: F401
    Base.metadata.create_all(bind=engine)


