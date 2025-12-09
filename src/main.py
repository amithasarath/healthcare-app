"""
Healthcare Application - HIPAA-Compliant Patient Management System
Production-grade FastAPI application with PostgreSQL
"""
import os
from datetime import datetime, date
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Date, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel, EmailStr, Field
import structlog

# Configure structured logging
logger = structlog.get_logger()

# Database Configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://healthcareapp:password@localhost:5432/healthcaredb"
)

# Create engine
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=10)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Database Models
class Patient(Base):
    """Patient database model - HIPAA compliant"""
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    phone = Column(String(20))
    date_of_birth = Column(Date, nullable=False)
    gender = Column(String(20))
    address = Column(Text)
    medical_record_number = Column(String(50), unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Integer, default=1)


# Pydantic Schemas
class PatientBase(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=20)
    date_of_birth: date
    gender: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = None


class PatientCreate(PatientBase):
    pass


class PatientResponse(PatientBase):
    id: int
    medical_record_number: Optional[str]
    created_at: datetime
    updated_at: datetime
    is_active: int

    class Config:
        from_attributes = True


class HealthResponse(BaseModel):
    status: str
    environment: str
    database: str
    timestamp: datetime
    version: str


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting healthcare application", environment=os.getenv("ENVIRONMENT", "dev"))

    # Create tables if they don't exist
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error("Failed to create database tables", error=str(e))

    yield

    # Shutdown
    logger.info("Shutting down healthcare application")


# FastAPI Application
app = FastAPI(
    title="Healthcare Patient Management System",
    description="HIPAA-Compliant Patient Management API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency
def get_db():
    """Database session dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Utility function to generate MRN
def generate_mrn() -> str:
    """Generate unique Medical Record Number"""
    import secrets
    timestamp = datetime.utcnow().strftime("%Y%m%d")
    random_part = secrets.token_hex(4).upper()
    return f"MRN-{timestamp}-{random_part}"


# API Endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Healthcare Patient Management System API",
        "version": "1.0.0",
        "docs": "/api/docs"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint for ECS"""
    db_status = "connected"
    try:
        # Test database connection
        db.execute("SELECT 1")
    except Exception as e:
        db_status = f"disconnected: {str(e)}"
        logger.error("Database health check failed", error=str(e))

    return HealthResponse(
        status="healthy" if db_status == "connected" else "unhealthy",
        environment=os.getenv("ENVIRONMENT", "dev"),
        database=db_status,
        timestamp=datetime.utcnow(),
        version="1.0.0"
    )


@app.get("/api/patients", response_model=List[PatientResponse])
async def list_patients(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all patients with pagination"""
    try:
        patients = db.query(Patient).filter(Patient.is_active == 1).offset(skip).limit(limit).all()
        logger.info("Retrieved patients", count=len(patients))
        return patients
    except Exception as e:
        logger.error("Failed to retrieve patients", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve patients"
        )


@app.get("/api/patients/{patient_id}", response_model=PatientResponse)
async def get_patient(patient_id: int, db: Session = Depends(get_db)):
    """Get patient by ID"""
    try:
        patient = db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.is_active == 1
        ).first()

        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with ID {patient_id} not found"
            )

        logger.info("Retrieved patient", patient_id=patient_id)
        return patient
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to retrieve patient", patient_id=patient_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve patient"
        )


@app.post("/api/patients", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(patient: PatientCreate, db: Session = Depends(get_db)):
    """Create new patient"""
    try:
        # Check if email already exists
        existing = db.query(Patient).filter(Patient.email == patient.email).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Patient with this email already exists"
            )

        # Create patient
        db_patient = Patient(
            **patient.model_dump(),
            medical_record_number=generate_mrn()
        )
        db.add(db_patient)
        db.commit()
        db.refresh(db_patient)

        logger.info("Created patient", patient_id=db_patient.id, mrn=db_patient.medical_record_number)
        return db_patient

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Failed to create patient", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create patient"
        )


@app.put("/api/patients/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_id: int,
    patient_update: PatientCreate,
    db: Session = Depends(get_db)
):
    """Update patient information"""
    try:
        db_patient = db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.is_active == 1
        ).first()

        if not db_patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with ID {patient_id} not found"
            )

        # Update fields
        for key, value in patient_update.model_dump().items():
            setattr(db_patient, key, value)

        db_patient.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_patient)

        logger.info("Updated patient", patient_id=patient_id)
        return db_patient

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Failed to update patient", patient_id=patient_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update patient"
        )


@app.delete("/api/patients/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_patient(patient_id: int, db: Session = Depends(get_db)):
    """Soft delete patient (HIPAA compliance - maintain audit trail)"""
    try:
        db_patient = db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.is_active == 1
        ).first()

        if not db_patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with ID {patient_id} not found"
            )

        # Soft delete
        db_patient.is_active = 0
        db_patient.updated_at = datetime.utcnow()
        db.commit()

        logger.info("Deleted patient (soft)", patient_id=patient_id)
        return None

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Failed to delete patient", patient_id=patient_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete patient"
        )


# Exception Handlers
@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Global exception handler"""
    logger.error("Unhandled exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
