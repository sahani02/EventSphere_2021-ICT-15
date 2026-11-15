from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from backend.database import engine, Base
from backend.routers import auth, venues, events, bookings, tickets, hire, dashboard

Base.metadata.create_all(bind=engine)
app=FastAPI(title="EventSphere",description="Venue Booking and Digital Ticketing Platform",version="1.0.0")
app.include_router(auth.router)
app.include_router(venues.router)
app.include_router(events.router)
app.include_router(bookings.router)
app.include_router(tickets.router)
app.include_router(hire.router)
app.include_router(dashboard.router)

@app.get("/")
def home():
    return {"message":"Welcome to EventSphere","status":"running","docs":"/docs"}

@app.get("/health")
def health():
    return {"status":"healthy"}

@app.get("/database-status")
def database_status():
    return {"database":"configured","tables":list(Base.metadata.tables.keys())}

@app.post("/setup/demo-accounts")
def setup_demo_accounts():
    # For local coursework demo only. Remove/disable this endpoint before public deployment.
    from backend.database import SessionLocal
    from backend import models
    from backend.security import hash_password
    db=SessionLocal()
    try:
        created=[]
        for name,email,password,role in [
            ("Demo Admin","admin@eventsphere.local","Admin12345","admin"),
            ("Demo Staff","staff@eventsphere.local","Staff12345","staff"),
            ("Demo Attendee","attendee@eventsphere.local","Attendee12345","attendee")]:
            if not db.query(models.User).filter_by(email=email).first():
                db.add(models.User(full_name=name,email=email,password_hash=hash_password(password),role=role))
                created.append(email)
        db.commit()
        return {"created":created,"note":"Demo-only endpoint; disable before deployment."}
    finally:
        db.close()
