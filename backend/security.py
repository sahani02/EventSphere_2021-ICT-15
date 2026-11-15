
import os
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt, JWTError

from fastapi import (
    Depends,
    HTTPException,
    status
)

from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials
)

from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import User


# ==========================================
# JWT CONFIGURATION
# ==========================================

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "eventsphere-development-secret-change-me"
)

ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 60

bearer_scheme = HTTPBearer()


# ==========================================
# PASSWORD HASHING
# ==========================================

def hash_password(password: str) -> str:
    """
    Hash a password before saving it in the database.
    """

    password_bytes = password.encode("utf-8")

    hashed = bcrypt.hashpw(
        password_bytes,
        bcrypt.gensalt()
    )

    return hashed.decode("utf-8")


def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
    """
    Verify a password against its stored hash.
    """

    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8")
    )


# ==========================================
# CREATE JWT ACCESS TOKEN
# ==========================================

def create_access_token(data: dict) -> str:
    """
    Create a JWT token for an authenticated user.
    """

    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    to_encode.update({
        "exp": expire
    })

    token = jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return token


# ==========================================
# GET CURRENT LOGGED-IN USER
# ==========================================

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(
        bearer_scheme
    ),
    db: Session = Depends(get_db)
):
    """
    Decode the JWT token and retrieve the user.
    """

    token = credentials.credentials

    try:

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        user_id = payload.get("sub")

        if user_id is None:

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )

        user_id = int(user_id)

    except (JWTError, ValueError, TypeError):

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )

    user = db.query(User).filter(
        User.id == user_id
    ).first()

    if user is None:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    return user


# ==========================================
# ROLE-BASED ACCESS CONTROL
# ==========================================

def require_role(*allowed_roles):
    """
    Check whether the current user has an allowed role.

    Example:
        Depends(require_role("admin"))
        Depends(require_role("admin", "staff"))
    """

    def role_checker(
        current_user=Depends(get_current_user)
    ):

        user_role = str(
            current_user.role
        ).lower()

        allowed = [
            str(role).lower()
            for role in allowed_roles
        ]

        if user_role not in allowed:

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource"
            )

        return current_user

    return role_checker
