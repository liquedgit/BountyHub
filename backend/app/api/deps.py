from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthError, AuthService


def get_auth_service(
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> AuthService:
    return AuthService(UserRepository(db), settings)


def get_current_user(
    request: Request,
    service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
) -> User:
    token = request.cookies.get(settings.auth_cookie_name)
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    if not token:
        raise unauthorized
    try:
        return service.get_user_from_token(token)
    except AuthError:
        raise unauthorized from None
