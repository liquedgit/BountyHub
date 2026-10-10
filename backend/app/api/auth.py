from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import get_auth_service, get_current_user
from app.core.config import Settings, get_settings
from app.models.user import User
from app.schemas.auth import Credentials, UserOut
from app.services.auth_service import (
    AuthError,
    AuthService,
    RegistrationClosedError,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: Credentials, service: AuthService = Depends(get_auth_service)):
    try:
        return service.register(body.email, body.password)
    except RegistrationClosedError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Registration is closed") from None


@router.post("/login", response_model=UserOut)
def login(
    body: Credentials,
    response: Response,
    service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
):
    try:
        user, token = service.login(body.email, body.password)
    except AuthError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials") from None
    response.set_cookie(
        settings.auth_cookie_name,
        token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        max_age=settings.jwt_expire_minutes * 60,
        path="/",
    )
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, settings: Settings = Depends(get_settings)):
    response.delete_cookie(settings.auth_cookie_name, path="/")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
