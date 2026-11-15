
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import UserCreate, UserResponse, TokenResponse
from ..security import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_user,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    user_data: UserCreate,
    db: Session = Depends(get_db),
):
    existing_user = (
        db.query(User)
        .filter(User.email == user_data.email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email address is already registered.",
        )

    user = User(
        full_name=user_data.full_name,
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        role="attendee",
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except Exception:
        db.rollback()
        raise


@router.post("/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    # OAuth2 form uses "username"; accept the email in this field.
    user = (
        db.query(User)
        .filter(User.email == form_data.username)
        .first()
    )

    if (
        user is None
        or not verify_password(
            form_data.password,
            user.password_hash,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is inactive.",
        )

    token = create_access_token(
        user_id=user.id,
        role=user.role,
    )

    return {
        "access_token": token,
        "token_type": "bearer",
    }


@router.get("/me", response_model=UserResponse)
def get_profile(
    current_user: User = Depends(get_current_user),
):
    return current_user
