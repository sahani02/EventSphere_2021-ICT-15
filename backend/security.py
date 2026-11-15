
import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .database import get_db
from .models import User


# =========================================================
# SECURITY CONFIGURATION
# =========================================================

SECRET_KEY = os.getenv("SECRET_KEY")

if not SECRET_KEY:
    # Development fallback only.
    # Set a strong SECRET_KEY environment variable before deployment.
    SECRET_KEY = "development-only-change-this-secret-key"

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

password_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# =========================================================
# PASSWORD HASHING
# =========================================================

def get_password_hash(password: str) -> str:
    """Hash a password before saving it in the database."""
    return password_context.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
    """Compare a submitted password with its stored hash."""
    return password_context.verify(plain_password, hashed_password)


# =========================================================
# JWT TOKEN
# =========================================================

def create_access_token(
    user_id: int,
    role: str,
    expires_delta: timedelta | None = None
) -> str:
    """Create a JWT access token for an authenticated user."""

    if expires_delta is None:
        expires_delta = timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )

    expire = datetime.now(timezone.utc) + expires_delta

    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


# =========================================================
# GET CURRENT USER
# =========================================================

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        user_id = payload.get("sub")

        if user_id is None:
            raise credentials_exception

        user_id = int(user_id)

    except (JWTError, ValueError, TypeError):
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This user account is inactive."
        )

    return user


# =========================================================
# ROLE-BASED AUTHORIZATION
# =========================================================

def require_roles(*allowed_roles: str):
    """
    Restrict an endpoint to selected roles.

    Example:
        Depends(require_roles("admin", "staff"))
    """

    def role_checker(
        current_user: User = Depends(get_current_user)
    ) -> User:

        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource."
            )

        return current_user

    return role_checker


# =========================================================
# COMMON ROLE DEPENDENCIES
# =========================================================

def get_current_admin(
    current_user: User = Depends(require_roles("admin"))
) -> User:
    return current_user


def get_current_staff(
    current_user: User = Depends(require_roles("staff", "admin"))
) -> User:
    return current_user


def get_current_attendee(
    current_user: User = Depends(require_roles("attendee"))
) -> User:
    return current_user
