from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from jose import JWTError, jwt

from app.core.config import Settings
from app.models.user import User
from app.repositories.user_repository import UserRepository


class AuthError(Exception):
    """Invalid credentials or token."""


class RegistrationClosedError(Exception):
    """A user already exists; the app is single-user."""


class AuthService:
    _hasher = PasswordHasher()
    # Verified against when the email is unknown, to keep timing similar.
    _dummy_hash = _hasher.hash("bountyhub-dummy-password")

    def __init__(self, users: UserRepository, settings: Settings):
        self._users = users
        self._settings = settings

    # --- passwords ---
    def hash_password(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            return False

    # --- tokens ---
    def issue_token(self, user: User) -> str:
        now = datetime.now(UTC)
        claims = {
            "sub": str(user.id),
            "iat": now,
            "exp": now + timedelta(minutes=self._settings.jwt_expire_minutes),
        }
        return jwt.encode(
            claims, self._settings.jwt_secret, algorithm=self._settings.jwt_algorithm
        )

    def verify_token(self, token: str) -> int:
        try:
            claims = jwt.decode(
                token,
                self._settings.jwt_secret,
                algorithms=[self._settings.jwt_algorithm],
            )
            return int(claims["sub"])
        except (JWTError, KeyError, ValueError) as exc:
            raise AuthError("Invalid token") from exc

    # --- use cases ---
    def register(self, email: str, password: str) -> User:
        if self._users.count() > 0:
            raise RegistrationClosedError("Registration is closed")
        return self._users.create(email, self.hash_password(password))

    def authenticate(self, email: str, password: str) -> User:
        user = self._users.get_by_email(email)
        if user is None:
            self.verify_password(password, self._dummy_hash)
            raise AuthError("Invalid credentials")
        if not self.verify_password(password, user.password_hash):
            raise AuthError("Invalid credentials")
        return user

    def login(self, email: str, password: str) -> tuple[User, str]:
        user = self.authenticate(email, password)
        return user, self.issue_token(user)

    def get_user_from_token(self, token: str) -> User:
        user = self._users.get_by_id(self.verify_token(token))
        if user is None:
            raise AuthError("Unknown user")
        return user
