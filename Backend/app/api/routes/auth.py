"""Authentication routes — single login for all roles, session introspection."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import verify_password, create_access_token, get_password_hash
from app.models.models import User, AuditLog
from app.schemas.schemas import Token

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Single sign-in endpoint. The role is resolved from the stored account,
    never from the client, and returned so the UI can route to the right portal."""
    email = form_data.username.strip().lower()
    user = db.query(User).filter(User.email.ilike(email)).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Please contact the administrator.",
        )

    access_token = create_access_token(data={"sub": str(user.id), "role": user.role.value})
    db.add(AuditLog(user_id=user.id, action="login", resource_type="user", resource_id=user.id))
    db.commit()
    return Token(
        access_token=access_token,
        token_type="bearer",
        role=user.role.value,
        full_name=user.full_name,
        user_id=user.id,
    )


@router.get("/me")
def get_me(user: User = Depends(get_current_user)):
    """Return the authenticated user's identity and role (used to restore sessions)."""
    return {
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "is_active": user.is_active,
    }


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)


@router.post("/change-password")
def change_password(
    data: ChangePasswordIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.hashed_password = get_password_hash(data.new_password)
    db.add(AuditLog(user_id=user.id, action="change_password", resource_type="user", resource_id=user.id))
    db.commit()
    return {"message": "Password updated successfully"}
