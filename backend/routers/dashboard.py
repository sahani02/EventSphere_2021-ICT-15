from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.database import get_db
from backend import models
from backend.security import require_role

router=APIRouter(prefix="/dashboard",tags=["Admin Dashboard"])

@router.get("/",dependencies=[Depends(require_role("admin"))])
def dashboard(db:Session=Depends(get_db)):
    events=db.query(models.Event).all()
    rows=[]
    for e in events:
        sold=db.query(func.coalesce(func.sum(models.Booking.quantity),0)).filter_by(event_id=e.id,status="confirmed").scalar()
        revenue=db.query(func.coalesce(func.sum(models.Booking.total_amount),0)).filter_by(event_id=e.id,status="confirmed").scalar()
        checked=db.query(models.Ticket).filter_by(event_id=e.id,status="used").count()
        rows.append({"event_id":e.id,"title":e.title,"tickets_sold":sold,"revenue":str(revenue),"check_ins":checked})
    messages=db.query(models.AgentMessage).order_by(models.AgentMessage.id.desc()).limit(100).all()
    return {"events":rows,"agent_messages":messages}
