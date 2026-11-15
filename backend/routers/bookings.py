import secrets
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import update
from backend.database import get_db
from backend import models
from backend.schemas import BookingCreate
from backend.security import get_current_user
from backend.agents.message_bus import MessageBus
from backend.agents.agents import BookingAgent, TicketAgent, NotificationAgent

router = APIRouter(prefix="/bookings", tags=["Bookings"])

@router.post("/", status_code=201)
def book(data: BookingCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    category = db.query(models.TicketCategory).filter_by(id=data.ticket_category_id, event_id=data.event_id).first()
    event = db.query(models.Event).filter_by(id=data.event_id, status="published").first()
    if not category or not event: raise HTTPException(404, "Event or ticket category not found")
    if data.quantity > 6: raise HTTPException(400, "Maximum 6 tickets per booking")
    # Atomic conditional update prevents allocating more than the remaining quantity.
    result = db.execute(update(models.TicketCategory).where(
        models.TicketCategory.id == category.id,
        models.TicketCategory.sold_quantity + data.quantity <= models.TicketCategory.total_quantity
    ).values(sold_quantity=models.TicketCategory.sold_quantity + data.quantity))
    if result.rowcount != 1:
        db.rollback(); raise HTTPException(409, "Not enough tickets available")
    total = Decimal(str(category.price)) * data.quantity
    booking = models.Booking(booking_reference="ES-"+secrets.token_hex(5).upper(),
        user_id=user.id,event_id=event.id,ticket_category_id=category.id,quantity=data.quantity,
        total_amount=total,payment_reference="SIM-"+secrets.token_hex(6).upper(),status="confirmed")
    db.add(booking); db.commit(); db.refresh(booking)
    bus=MessageBus(db)
    bus.register("BookingAgent",BookingAgent(db)); bus.register("TicketAgent",TicketAgent(db))
    bus.register("NotificationAgent",NotificationAgent(db))
    bus.send("BookingRouter","BookingAgent","REQUEST",{"booking_id":booking.id})
    codes=[]
    for _ in range(data.quantity):
        code=secrets.token_urlsafe(32)
        db.add(models.Ticket(ticket_code=code,booking_id=booking.id,event_id=event.id,ticket_category_id=category.id))
        codes.append(code)
    db.commit()
    bus.send("BookingRouter","NotificationAgent","INFORM",{"user_id":user.id,"title":"Booking confirmed","message":f"Your booking {booking.booking_reference} is confirmed."})
    return {"booking_reference":booking.booking_reference,"quantity":data.quantity,
            "total_amount":str(total),"payment_reference":booking.payment_reference,"ticket_codes":codes}

@router.get("/my")
def my_bookings(db: Session=Depends(get_db), user=Depends(get_current_user)):
    return db.query(models.Booking).filter_by(user_id=user.id).all()

@router.post("/{booking_id}/cancel")
def cancel_booking(booking_id:int, db:Session=Depends(get_db), user=Depends(get_current_user)):
    booking=db.query(models.Booking).filter_by(id=booking_id,user_id=user.id).first()
    if not booking: raise HTTPException(404,"Booking not found")
    if booking.status != "confirmed": raise HTTPException(400,"Booking cannot be cancelled")
    event=db.query(models.Event).filter_by(id=booking.event_id).first()
    from datetime import datetime
    hours=(event.start_time-datetime.utcnow()).total_seconds()/3600
    rate=Decimal("1.0") if hours>48 else Decimal("0.5") if hours>=24 else Decimal("0.0")
    refund=Decimal(str(booking.total_amount))*rate
    booking.status="cancelled"
    booking.cancelled_at=datetime.utcnow()
    category=db.query(models.TicketCategory).filter_by(id=booking.ticket_category_id).first()
    category.sold_quantity=max(0,category.sold_quantity-booking.quantity)
    for ticket in db.query(models.Ticket).filter_by(booking_id=booking.id).all(): ticket.status="cancelled"
    db.commit()
    return {"status":"cancelled","refund_amount":str(refund),"policy":"100% >48h; 50% 24-48h; 0% <24h"}
