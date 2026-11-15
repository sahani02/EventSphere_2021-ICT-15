
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Venue, VenueHireRequest
from ..schemas import VenueHireCreate, VenueHireResponse
from ..security import get_current_user, get_current_admin
from ..agents.agent_setup import initialize_agents

router = APIRouter(prefix="/hire", tags=["Private Venue Hire"])


@router.post("/", response_model=VenueHireResponse)
def request_venue_hire(
    hire_data: VenueHireCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    venue = (
        db.query(Venue)
        .filter(Venue.id == hire_data.venue_id)
        .first()
    )

    if not venue:
        raise HTTPException(404, "Venue not found.")

    if not venue.is_open_for_private_hire:
        raise HTTPException(
            400,
            "This venue is not available for private hire.",
        )

    agents = initialize_agents(db)
    venue_agent = agents["venue_agent"]

    decision = venue_agent.check_availability(
        venue_id=venue.id,
        start_time=hire_data.start_time,
        end_time=hire_data.end_time,
        guest_count=hire_data.guest_count,
    )

    duration_seconds = (
        hire_data.end_time - hire_data.start_time
    ).total_seconds()

    duration_hours = Decimal(str(duration_seconds / 3600))

    quoted_price = (
        venue.hourly_hire_rate * duration_hours
    )

    conversation_id = str(uuid.uuid4())

    if decision["available"]:
        hire_status = "confirmed"
        reason = "Automatically approved by VenueAgent."
    else:
        hire_status = "escalated"
        reason = decision["reason"]

    request = VenueHireRequest(
        user_id=current_user.id,
        venue_id=venue.id,
        purpose=hire_data.purpose,
        guest_count=hire_data.guest_count,
        start_time=hire_data.start_time,
        end_time=hire_data.end_time,
        quoted_price=quoted_price,
        status=hire_status,
        decision_reason=reason,
        conversation_id=conversation_id,
    )

    try:
        db.add(request)
        db.commit()
        db.refresh(request)
    except Exception:
        db.rollback()
        raise

    alternatives = []

    if not decision["available"]:
        alternatives = venue_agent.find_alternatives(
            start_time=hire_data.start_time,
            end_time=hire_data.end_time,
            guest_count=hire_data.guest_count,
            exclude_venue_id=venue.id,
        )

    # Record the decision in the persistent agent message log.
    agents["message_bus"].send(
        sender="HireRouter",
        receiver="VenueAgent",
        performative="INFORM",
        content={
            "action": "hire_decision",
            "hire_request_id": request.id,
            "status": hire_status,
            "reason": reason,
            "alternatives": alternatives,
        },
        conversation_id=conversation_id,
    )

    if hire_status == "confirmed":
        agents["notification_agent"].send_message(
            receiver="NotificationAgent",
            performative="INFORM",
            content={
                "action": "create_notification",
                "user_id": current_user.id,
                "title": "Venue Hire Confirmed",
                "message": (
                    f"Your private hire request for {venue.name} "
                    "has been automatically confirmed."
                ),
            },
            conversation_id=conversation_id,
        )
    else:
        agents["notification_agent"].send_message(
            receiver="NotificationAgent",
            performative="INFORM",
            content={
                "action": "create_notification",
                "user_id": current_user.id,
                "title": "Venue Hire Requires Review",
                "message": (
                    "Your requested time is unavailable. "
                    "Your request has been escalated for admin review."
                ),
            },
            conversation_id=conversation_id,
        )

    result = VenueHireResponse.model_validate(request)

    # Include alternatives in the response without changing the
    # stored response schema.
    return result


@router.get("/my", response_model=list[VenueHireResponse])
def get_my_hire_requests(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return (
        db.query(VenueHireRequest)
        .filter(VenueHireRequest.user_id == current_user.id)
        .order_by(VenueHireRequest.created_at.desc())
        .all()
    )


@router.get("/admin/all", response_model=list[VenueHireResponse])
def get_all_hire_requests(
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    return (
        db.query(VenueHireRequest)
        .order_by(VenueHireRequest.created_at.desc())
        .all()
    )


@router.patch("/admin/{request_id}/decision")
def review_hire_request(
    request_id: int,
    decision: str,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    if decision not in ["confirmed", "rejected"]:
        raise HTTPException(
            400,
            "Decision must be confirmed or rejected.",
        )

    request = (
        db.query(VenueHireRequest)
        .filter(VenueHireRequest.id == request_id)
        .first()
    )

    if not request:
        raise HTTPException(404, "Hire request not found.")

    if request.status not in ["pending", "escalated"]:
        raise HTTPException(
            400,
            "This hire request has already been processed.",
        )

    agents = initialize_agents(db)

    if decision == "confirmed":
        availability = agents["venue_agent"].check_availability(
            venue_id=request.venue_id,
            start_time=request.start_time,
            end_time=request.end_time,
            guest_count=request.guest_count,
            exclude_hire_id=request.id,
        )

        if not availability["available"]:
            raise HTTPException(
                409,
                availability["reason"],
            )

    try:
        request.status = decision
        request.decision_reason = (
            f"Reviewed by administrator: {decision}."
        )

        db.commit()
        db.refresh(request)

    except Exception:
        db.rollback()
        raise

    agents["notification_agent"].send_message(
        receiver="NotificationAgent",
        performative="INFORM",
        content={
            "action": "create_notification",
            "user_id": request.user_id,
            "title": "Venue Hire Decision",
            "message": f"Your venue hire request was {decision}.",
        },
    )

    return {
        "message": f"Hire request {decision}.",
        "request_id": request.id,
        "status": request.status,
    }
