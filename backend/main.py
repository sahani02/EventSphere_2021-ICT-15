
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .models import *

# Import models before create_all so SQLAlchemy knows all tables.
#import models

# Import API routers.
from .routers import (
    auth,
    venues,
    events,
    bookings,
    tickets,
    hire,
    waitlist,
    dashboard,
)


# =========================================================
# APPLICATION LIFESPAN
# =========================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Create database tables when the application starts.

    For production deployments, use database migrations
    rather than relying on create_all for schema changes.
    """
    Base.metadata.create_all(bind=engine)

    yield


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title="EventSphere API",
    description=(
        "University event booking and digital ticketing platform "
        "powered by cooperating software agents."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# =========================================================
# CORS CONFIGURATION
# =========================================================

allowed_origins = os.getenv(
    "FRONTEND_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
)


# =========================================================
# API ROUTERS
# =========================================================

app.include_router(auth.router)
app.include_router(venues.router)
app.include_router(events.router)
app.include_router(bookings.router)
app.include_router(tickets.router)
app.include_router(hire.router)
app.include_router(waitlist.router)
app.include_router(dashboard.router)


# =========================================================
# ROOT ENDPOINT
# =========================================================

@app.get("/", tags=["General"])
def root():
    return {
        "message": "Welcome to EventSphere API",
        "version": "1.0.0",
        "documentation": "/docs",
        "status": "running"
    }


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health", tags=["General"])
def health_check():
    return {
        "status": "healthy",
        "application": "EventSphere"
    }
