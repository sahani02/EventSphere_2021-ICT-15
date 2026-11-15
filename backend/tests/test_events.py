
from datetime import datetime, timedelta, timezone

from ..models import Event


def test_get_published_events(client, sample_event):
    response = client.get("/events/")

    assert response.status_code == 200

    events = response.json()

    assert len(events) == 1
    assert events[0]["title"] == sample_event.title
    assert events[0]["status"] == "published"


def test_get_single_published_event(client, sample_event):
    response = client.get(f"/events/{sample_event.id}")

    assert response.status_code == 200
    assert response.json()["title"] == sample_event.title


def test_draft_event_not_publicly_visible(
    client,
    db_session,
    sample_venue,
):
    now = datetime.now(timezone.utc)

    draft = Event(
        title="Draft Workshop",
        description="Not published yet.",
        category="Workshop",
        venue_id=sample_venue.id,
        start_time=now + timedelta(days=10),
        end_time=now + timedelta(days=10, hours=2),
        status="draft",
    )

    db_session.add(draft)
    db_session.commit()
    db_session.refresh(draft)

    response = client.get("/events/")

    assert response.status_code == 200

    titles = [event["title"] for event in response.json()]

    assert "Draft Workshop" not in titles


def test_get_draft_event_returns_404(
    client,
    db_session,
    sample_venue,
):
    now = datetime.now(timezone.utc)

    draft = Event(
        title="Private Draft",
        description="Private event",
        category="Seminar",
        venue_id=sample_venue.id,
        start_time=now + timedelta(days=12),
        end_time=now + timedelta(days=12, hours=2),
        status="draft",
    )

    db_session.add(draft)
    db_session.commit()
    db_session.refresh(draft)

    response = client.get(f"/events/{draft.id}")

    assert response.status_code == 404


def test_get_missing_event(client):
    response = client.get("/events/99999")

    assert response.status_code == 404
