
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Event
from backend.security import get_current_user

router = APIRouter(
    prefix="/events",
    tags=["Events"]
)


@router.get("/")
def get_events(db: Session = Depends(get_db)):
    return db.query(Event).all()


@router.get("/{event_id}")
def get_event(
    event_id: int,
    db: Session = Depends(get_db)
):
    event = db.query(Event).filter(
        Event.id == event_id
    ).first()

    if not event:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    return event


@router.post("/")
def create_event(
    event_data: dict,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    event = Event(**event_data)

    db.add(event)
    db.commit()
    db.refresh(event)

    return event
