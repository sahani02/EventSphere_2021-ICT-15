from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend import models
from backend.schemas import UserRegister, UserLogin, UserResponse
from backend.security import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=201)
def register_user(data: UserRegister, db: Session = Depends(get_db)):
    email = data.email.lower()
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(400, "Email already registered")
    user = models.User(full_name=data.full_name, email=email,
                       password_hash=hash_password(data.password), role="attendee")
    db.add(user); db.commit(); db.refresh(user)
    return user

@router.post("/login")
def login_user(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == data.email.lower()).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    return {"access_token": create_access_token(user.id, user.role),
            "token_type":"bearer", "user":UserResponse.model_validate(user)}

@router.get("/me", response_model=UserResponse)
def me(user=Depends(get_current_user)):
    return user
