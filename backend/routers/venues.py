
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Venue, Event, VenueHireRequest
from ..schemas import VenueCreate, VenueUpdate, VenueResponse
from ..security import get_current_admin

router = APIRouter(prefix="/venues", tags=["Venues"])


@router.get("/", response_model=list[VenueResponse])
def get_venues(db: Session = Depends(get_db)):
    return db.query(Venue).order_by(Venue.name.asc()).all()


@router.get("/{venue_id}", response_model=VenueResponse)
def get_venue(
    venue_id: int,
    db: Session = Depends(get_db),
):
    venue = db.query(Venue).filter(Venue.id == venue_id).first()

    if not venue:
        raise HTTPException(404, "Venue not found.")

    return venue


@router.post(
    "/",
    response_model=VenueResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_venue(
    venue_data: VenueCreate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    venue = Venue(**venue_data.model_dump())

    try:
        db.add(venue)
        db.commit()
        db.refresh(venue)
        return venue
    except Exception:
        db.rollback()
        raise


@router.put("/{venue_id}", response_model=VenueResponse)
def update_venue(
    venue_id: int,
    venue_data: VenueUpdate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    venue = db.query(Venue).filter(Venue.id == venue_id).first()

    if not venue:
        raise HTTPException(404, "Venue not found.")

    updates = venue_data.model_dump(exclude_unset=True)

    for field, value in updates.items():
        setattr(venue, field, value)

    try:
        db.commit()
        db.refresh(venue)
        return venue
    except Exception:
        db.rollback()
        raise


@router.delete("/{venue_id}")
def delete_venue(
    venue_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    venue = db.query(Venue).filter(Venue.id == venue_id).first()

    if not venue:
        raise HTTPException(404, "Venue not found.")

    has_events = (
        db.query(Event.id)
        .filter(Event.venue_id == venue_id)
        .first()
    )

    has_hires = (
        db.query(VenueHireRequest.id)
        .filter(VenueHireRequest.venue_id == venue_id)
        .first()
    )

    if has_events or has_hires:
        raise HTTPException(
            409,
            "Cannot delete a venue that has event or hire records.",
        )

    try:
        db.delete(venue)
        db.commit()
        return {"message": "Venue deleted successfully."}
    except Exception:
        db.rollback()
        raise
