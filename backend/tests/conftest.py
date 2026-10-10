import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.database import get_db
from app.core.redis import get_redis
from app.main import create_app
from app.models import Base
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService


@pytest.fixture
def engine():
    """Ephemeral in-memory database, created fresh for every test."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(engine):
    with sessionmaker(bind=engine)() as session:
        yield session


@pytest.fixture
def fake_redis():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def client(db_session, fake_redis):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: fake_redis
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_client(client, db_session):
    """`client` carrying a valid login cookie for a persisted user."""
    settings = get_settings()
    user = User(email="auth-client@example.com", password_hash="unused")
    db_session.add(user)
    db_session.commit()
    token = AuthService(UserRepository(db_session), settings).issue_token(user)
    client.cookies.set(settings.auth_cookie_name, token)
    return client
