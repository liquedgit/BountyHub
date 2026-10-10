from sqlalchemy import text
from sqlalchemy.orm import Session


class HealthRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def ping_database(self) -> bool:
        try:
            self._db.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
