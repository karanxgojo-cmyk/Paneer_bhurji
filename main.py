from fastapi import FastAPI, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from ml_model import classify_complaint
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import threading

_id_lock = threading.Lock()
_id_counter = 0

def generate_id():
    global _id_counter
    with _id_lock:
        _id_counter += 1
        return f"CMP{datetime.now().year}{_id_counter:04d}"

app = FastAPI()

# 🔁 Category → Department Mapping
category_to_department = {
    "Bathroom & Hygiene": "Maintenance",
    "Mess & Food Quality": "Food Department",
    "Academic Issues": "Academic Office",
    "Infrastructure/Maintenance": "Maintenance",
    "Anti-Ragging & Safety": "Security",
    "Other": "General Admin"
}

def keyword_fallback(text):
    text = text.lower()

    if "food" in text or "mess" in text or "canteen" in text:
        return "Mess & Food Quality"
    if "bathroom" in text or "toilet" in text or "washroom" in text:
        return "Bathroom & Hygiene"
    if "fan" in text or "light" in text or "ac" in text:
        return "Infrastructure/Maintenance"
    if "ragging" in text or "unsafe" in text:
        return "Anti-Ragging & Safety"

    return None

# DATABASE SETUP
DATABASE_URL = "sqlite:///./complaints.db"

def send_email(to_email, subject, body):
    sender_email = "karanxgojo@gmail.com"
    app_password = "qwms fylp wteb myxd"

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = to_email

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, app_password)
            server.send_message(msg)
            print("Email sent successfully")
    except Exception as e:
        print("Email failed:", e)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()

# DATABASE MODEL
class ComplaintDB(Base):
    __tablename__ = "complaints"

    id = Column(String, primary_key=True, index=True)
    student_name = Column(String)
    description = Column(String)
    category = Column(String, default="Other")
    status = Column(String, default="Submitted")
    department = Column(String)
    resolution = Column(String, default="")

def keyword_fallback(text):
    text = text.lower()

    if "food" in text or "mess" in text or "canteen" in text:
        return "Mess & Food Quality"
    if "bathroom" in text or "toilet" in text or "washroom" in text:
        return "Bathroom & Hygiene"
    if "fan" in text or "light" in text or "ac" in text:
        return "Infrastructure/Maintenance"
    if "ragging" in text or "unsafe" in text:
        return "Anti-Ragging & Safety"

    return None

# CREATE TABLE
Base.metadata.create_all(bind=engine)

# Pydantic Model
class Complaint(BaseModel):
    student_name: str
    description: str
    category: Optional[str] = "Other"
    status: Optional[str] = "Submitted"
    department: Optional[str] = None

class ComplaintOut(BaseModel):
    id: str
    student_name: str
    description: str
    category: str
    department: str
    status: str
    resolution: str

class StatusUpdate(BaseModel):
    status: str
    resolution: Optional[str] = ""

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# CREATE Complaint
@app.post("/complaints")
def submit_complaint(complaint: Complaint, db: Session = Depends(get_db)):
    print("Incoming complaint:", complaint)
    print("Category:", category)
    print("Department:", department)
    
    # 🧠 AI Classification
    try:
        category, confidence = classify_complaint(complaint.description)
        confidence = float(confidence)
    except Exception as e:
        print("ML Error:", e)
        category = "Other"
        confidence = 0.5

    # 🔁 Keyword fallback
    fallback = keyword_fallback(complaint.description)
    if confidence < 0.6 and fallback:
        category = fallback

    # 🔁 Routing Logic
    department = category_to_department.get(category, "General Admin")

    new_id = generate_id()

    db_complaint = ComplaintDB(
        id=new_id,
        student_name=complaint.student_name,
        description=complaint.description,
        category=category,
        status=complaint.status,
        department=department
    )

    db.add(db_complaint)
    db.commit()
    db.refresh(db_complaint)

    subject = "New Complaint 🚨"

    body = f"""
    New Complaint Submitted:

    Name: {db_complaint.student_name}
    Issue: {db_complaint.description}
    Category: {db_complaint.category}
    Department: {db_complaint.department}
    Status: {db_complaint.status}
    """

    import threading

    try:
        threading.Thread(
        target=send_email,
        args=("karanxgojo@gmail.com", subject, body),
        daemon=True
        ).start()
    except Exception as e:
        print("Thread error:", e)

    return {
        "id": db_complaint.id,
        "student_name": db_complaint.student_name,
        "description": db_complaint.description,
        "category": db_complaint.category,
        "department": db_complaint.department,
        "status": db_complaint.status,
        "resolution": db_complaint.resolution,
        "confidence": float(confidence)
    }

# GET Complaints
@app.get("/complaints", response_model=List[ComplaintOut])
def get_complaints(db: Session = Depends(get_db)):
    complaints = db.query(ComplaintDB).all()

    return [
        {
            "id": c.id,
            "student_name": c.student_name,
                "description": c.description,
            "category": c.category,
            "department": c.department,
            "status": c.status,
            "resolution": c.resolution,
        }
        for c in complaints
    ]

# UPDATE Status
@app.put("/complaints/{complaint_id}/status")
def update_status(complaint_id: str, status_update: StatusUpdate, db: Session = Depends(get_db)):
    complaint = db.query(ComplaintDB).filter(ComplaintDB.id == complaint_id).first()

    if complaint:
        complaint.status = status_update.status
        complaint.resolution = status_update.resolution or ""
        db.commit()
        db.refresh(complaint)
        return complaint

    return {"message": "Complaint not found"}