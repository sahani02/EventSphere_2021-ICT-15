from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend import models
from backend.security import require_role

router=APIRouter(prefix="/tickets",tags=["Tickets"])

@router.get("/validate/{code}")
def validate_ticket(code:str,event_id:int,db:Session=Depends(get_db),staff=Depends(require_role("staff","admin"))):
    ticket=db.query(models.Ticket).filter_by(ticket_code=code).first()
    if not ticket: raise HTTPException(404,"Ticket not found")
    if ticket.event_id != event_id: raise HTTPException(400,"Wrong event")
    if ticket.status=="cancelled": raise HTTPException(400,"Ticket cancelled")
    if ticket.status=="used": raise HTTPException(409,"Ticket already used")
    ticket.status="used"; ticket.checked_in_at=datetime.utcnow(); db.commit()
    return {"result":"ADMIT","message":"Ticket accepted"}
