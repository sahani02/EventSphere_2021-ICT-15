from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend import models
from backend.schemas import VenueCreate
from backend.security import require_role

router = APIRouter(prefix="/venues", tags=["Venues"])

@router.get("/")
def list_venues(db: Session = Depends(get_db)):
    return db.query(models.Venue).all()

@router.post("/", dependencies=[Depends(require_role("admin"))], status_code=201)
def create_venue(data: VenueCreate, db: Session = Depends(get_db)):
    venue = models.Venue(**data.model_dump())
    db.add(venue); db.commit(); db.refresh(venue)
    return venue

@router.put("/{venue_id}", dependencies=[Depends(require_role("admin"))])
def update_venue(venue_id: int, data: VenueCreate, db: Session = Depends(get_db)):
    venue = db.query(models.Venue).filter_by(id=venue_id).first()
    if not venue: raise HTTPException(404, "Venue not found")
    for key, value in data.model_dump().items(): setattr(venue, key, value)
    db.commit(); db.refresh(venue)
    return venue
