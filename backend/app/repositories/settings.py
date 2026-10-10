from sqlalchemy.orm import Session

from app.models.setting import Setting


class SettingsRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, key: str) -> str | None:
        row = self._db.get(Setting, key)
        return row.value if row else None

    def set(self, key: str, value: str) -> None:
        row = self._db.get(Setting, key)
        if row:
            row.value = value
        else:
            self._db.add(Setting(key=key, value=value))
        self._db.commit()

    def delete(self, key: str) -> None:
        row = self._db.get(Setting, key)
        if row:
            self._db.delete(row)
            self._db.commit()
