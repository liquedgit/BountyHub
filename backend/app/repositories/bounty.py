from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bounty import Finding, Note, Program, ScopeRule, Target

T = TypeVar("T")


class BaseRepository[T]:
    model: type[T]

    def __init__(self, db: Session):
        self.db = db

    def get(self, id_: int) -> T | None:
        return self.db.get(self.model, id_)

    def add(self, obj: T) -> T:
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def save(self, obj: T) -> T:
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, obj: T) -> None:
        self.db.delete(obj)
        self.db.commit()


class ProgramRepository(BaseRepository[Program]):
    model = Program

    def list(self) -> list[Program]:
        return list(self.db.scalars(select(Program).order_by(Program.id)))


class _ChildRepository(BaseRepository[T]):
    def list_for_program(self, program_id: int) -> list[T]:
        stmt = select(self.model).where(self.model.program_id == program_id).order_by(self.model.id)
        return list(self.db.scalars(stmt))


class ScopeRuleRepository(_ChildRepository[ScopeRule]):
    model = ScopeRule


class TargetRepository(_ChildRepository[Target]):
    model = Target


class FindingRepository(_ChildRepository[Finding]):
    model = Finding


class NoteRepository(_ChildRepository[Note]):
    model = Note
