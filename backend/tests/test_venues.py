
def test_get_venues(client, sample_venue):
    response = client.get("/venues/")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == sample_venue.name


def test_get_single_venue(client, sample_venue):
    response = client.get(f"/venues/{sample_venue.id}")

    assert response.status_code == 200
    assert response.json()["id"] == sample_venue.id
    assert response.json()["capacity"] == 500


def test_create_venue(client):
    response = client.post(
        "/venues/",
        json={
            "name": "Conference Hall",
            "location": "Building A",
            "capacity": 300,
            "description": "A large conference hall",
            "hourly_hire_rate": 3000,
            "is_open_for_private_hire": True,
            "turnaround_minutes": 30,
        },
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Conference Hall"
    assert response.json()["capacity"] == 300


def test_attendee_cannot_create_venue(client):
    # The default current user is an attendee.
    # Override the admin dependency to reject the request.
    from fastapi import HTTPException
    from security import get_current_admin
    from main import app

    def deny_admin():
        raise HTTPException(status_code=403, detail="Admin access required")

    app.dependency_overrides[get_current_admin] = deny_admin

    try:
        response = client.post(
            "/venues/",
            json={
                "name": "Unauthorized Venue",
                "location": "Campus",
                "capacity": 100,
                "description": "Test",
                "hourly_hire_rate": 1000,
                "is_open_for_private_hire": True,
                "turnaround_minutes": 30,
            },
        )

        assert response.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_admin, None)


def test_get_missing_venue(client):
    response = client.get("/venues/99999")

    assert response.status_code == 404
