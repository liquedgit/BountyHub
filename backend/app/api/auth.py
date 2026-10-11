from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.api.deps import get_auth_service, get_current_user
from app.core.config import Settings, get_settings
from app.models.user import User
from app.schemas.auth import AuthStatus, Credentials, UserOut
from app.services.auth_service import (
    AuthError,
    AuthService,
    RegistrationClosedError,
)
from app.services.login_throttle import TOO_MANY_DETAIL, LoginThrottle, client_key

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/status", response_model=AuthStatus)
def auth_status(service: AuthService = Depends(get_auth_service)):
    return AuthStatus(registration_open=service.registration_open())


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: Credentials, service: AuthService = Depends(get_auth_service)):
    try:
        return service.register(body.email, body.password)
    except RegistrationClosedError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Registration is closed") from None


@router.post("/login", response_model=UserOut)
def login(
    request: Request,
    body: Credentials,
    response: Response,
    service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
):
    throttle: LoginThrottle = request.app.state.login_throttle
    key = client_key(request)
    wait = throttle.retry_after(key)
    if wait is not None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            TOO_MANY_DETAIL,
            headers={"Retry-After": str(wait)},
        )
    try:
        user, token = service.login(body.email, body.password)
    except AuthError:
        throttle.record_failure(key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials") from None
    throttle.record_success(key)
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


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_user)],
)
def logout(response: Response, settings: Settings = Depends(get_settings)):
    response.delete_cookie(settings.auth_cookie_name, path="/")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
