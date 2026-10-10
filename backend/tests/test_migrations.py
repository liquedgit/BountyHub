from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command
from app.core.config import get_settings
from app.models import Base

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _schema(engine) -> dict[str, set[str]]:
    insp = inspect(engine)
    return {
        table: {col["name"] for col in insp.get_columns(table)}
        for table in insp.get_table_names()
        if table != "alembic_version"
    }


def test_upgrade_head_matches_models(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    try:
        cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        command.upgrade(cfg, "head")
    finally:
        get_settings.cache_clear()

    migrated = create_engine(url)
    expected_engine = create_engine("sqlite://")
    Base.metadata.create_all(expected_engine)
    try:
        assert _schema(migrated) == _schema(expected_engine)
        assert _schema(migrated)  # guard against an empty comparison
    finally:
        migrated.dispose()
        expected_engine.dispose()
