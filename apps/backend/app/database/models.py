from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float, JSON
from sqlalchemy.sql import func
from .config import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, index=True)
    customer_code = Column(String, unique=True, index=True)
    name = Column(String)
    pan_encrypted = Column(String)
    portal_username_encrypted = Column(String)
    credential_reference = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Filing(Base):
    __tablename__ = "filings"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    filing_reference = Column(String, unique=True, index=True)
    amount = Column(Float)
    tds_amount = Column(Float)
    filing_date = Column(DateTime(timezone=True))
    status = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True))

class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True, index=True)
    job_reference = Column(String, unique=True, index=True)
    logical_filing_id = Column(String, index=True, nullable=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    filing_id = Column(Integer, ForeignKey("filings.id"))
    status = Column(String)
    current_step = Column(String)
    attempt_count = Column(Integer, default=0)
    worker_id = Column(String)
    error_code = Column(String)
    error_message = Column(Text)
    data_payload = Column(JSON)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    last_heartbeat = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    # Preview checkpoint fields (populated when PREVIEW_PENDING is reached)
    preview_metadata = Column(JSON, nullable=True)
    preview_reached_at = Column(DateTime(timezone=True), nullable=True)
    preview_screenshot_path = Column(String, nullable=True)

class JobEvent(Base):
    __tablename__ = "job_events"
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    event_type = Column(String)
    status = Column(String)
    message = Column(Text)
    metadata_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Worker(Base):
    __tablename__ = "workers"
    id = Column(Integer, primary_key=True, index=True)
    worker_id = Column(String, unique=True, index=True)
    hostname = Column(String)
    status = Column(String)
    current_job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)
    last_heartbeat = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String)
    entity_type = Column(String)
    entity_id = Column(String)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    metadata_json = Column(JSON)

class Form141Import(Base):
    __tablename__ = "form141_imports"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    total_customers = Column(Integer, default=0)
    status = Column(String, default="IMPORTED")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Form141LogicalFiling(Base):
    __tablename__ = "form141_logical_filings"
    id = Column(Integer, primary_key=True, index=True)
    import_id = Column(Integer, ForeignKey("form141_imports.id"), nullable=True)
    logical_filing_id = Column(String, unique=True, index=True)
    customer_label = Column(String)
    column_index = Column(Integer, default=1)
    deductor_pan = Column(String, nullable=True)
    deductee_pan = Column(String, nullable=True)
    amount = Column(Float, default=0.0)
    tds_amount = Column(Float, nullable=True)
    status = Column(String, default="READY")
    current_step = Column(String, default="READY")
    validation_errors = Column(JSON, nullable=True)
    validation_warnings = Column(JSON, nullable=True)
    field_values = Column(JSON, nullable=True)
    field_metadata = Column(JSON, nullable=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

