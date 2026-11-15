
def test_register_user(client):
    response = client.post(
        "/auth/register",
        json={
            "full_name": "New User",
            "email": "newuser@test.com",
            "password": "Password123",
        },
    )

    assert response.status_code == 201
    assert response.json()["email"] == "newuser@test.com"
    assert response.json()["role"] == "attendee"


def test_register_duplicate_email(client, attendee):
    response = client.post(
        "/auth/register",
        json={
            "full_name": "Duplicate User",
            "email": attendee.email,
            "password": "Password123",
        },
    )

    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()


def test_login_invalid_password(client):
    response = client.post(
        "/auth/login",
        data={
            "username": "attendee@test.com",
            "password": "WrongPassword",
        },
    )

    assert response.status_code == 401


def test_login_success(client):
    response = client.post(
        "/auth/login",
        data={
            "username": "attendee@test.com",
            "password": "Test12345",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_get_current_profile(client, attendee):
    response = client.get("/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == attendee.email
    assert response.json()["role"] == "attendee"
