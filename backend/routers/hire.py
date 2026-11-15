from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend import models
from backend.schemas import HireCreate
from backend.security import get_current_user, require_role
from backend.agents.message_bus import MessageBus
from backend.agents.agents import VenueAgent

router=APIRouter(prefix="/hire",tags=["Private Venue Hire"])

@router.post("/",status_code=201)
def request_hire(data:HireCreate,db:Session=Depends(get_db),user=Depends(get_current_user)):
    venue=db.query(models.Venue).filter_by(id=data.venue_id).first()
    if not venue: raise HTTPException(404,"Venue not found")
    if data.end_time<=data.start_time: raise HTTPException(400,"End must be after start")
    if data.guest_count>venue.capacity: raise HTTPException(400,"Guest count exceeds venue capacity")
    if not venue.is_open_for_private_hire: raise HTTPException(400,"Venue is not open for private hire")
    bus=MessageBus(db); bus.register("VenueAgent",VenueAgent(db))
    decision=bus.send("HireRouter","VenueAgent","REQUEST",{"venue_id":venue.id,"start_time":data.start_time,"end_time":data.end_time})
    hours=(data.end_time-data.start_time).total_seconds()/3600
    price=float(venue.hourly_hire_rate)*hours
    request=models.VenueHireRequest(user_id=user.id,venue_id=venue.id,purpose=data.purpose,
        guest_count=data.guest_count,start_time=data.start_time,end_time=data.end_time,
        quoted_price=price,status="confirmed" if decision["performative"]=="AGREE" else "pending",
        decision_reason=decision.get("reason",""))
    db.add(request);db.commit();db.refresh(request)
    return {"request_id":request.id,"status":request.status,"quoted_price":price,"decision_reason":request.decision_reason}

@router.get("/requests",dependencies=[Depends(require_role("admin"))])
def all_requests(db:Session=Depends(get_db)):
    return db.query(models.VenueHireRequest).all()

@router.post("/requests/{request_id}/decision",dependencies=[Depends(require_role("admin"))])
def decide(request_id:int,approved:bool,db:Session=Depends(get_db)):
    req=db.query(models.VenueHireRequest).filter_by(id=request_id).first()
    if not req: raise HTTPException(404,"Request not found")
    req.status="approved" if approved else "rejected";db.commit()
    return {"status":req.status}
