from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.bounty import Finding, Note, Program, ScopeRule, Target
from app.repositories.bounty import (
    FindingRepository,
    NoteRepository,
    ProgramRepository,
    ScopeRuleRepository,
    TargetRepository,
)
from app.services.scope_validator import ScopeDecision, ScopeValidator


class NotFoundError(Exception):
    def __init__(self, what: str):
        super().__init__(f"{what} not found")


class ValidationError(Exception):
    pass


def _apply(obj, data: BaseModel) -> None:
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)


class ProgramService:
    def __init__(self, db: Session):
        self.repo = ProgramRepository(db)

    def list(self) -> list[Program]:
        return self.repo.list()

    def get(self, program_id: int) -> Program:
        p = self.repo.get(program_id)
        if p is None:
            raise NotFoundError("program")
        return p

    def create(self, data: BaseModel) -> Program:
        return self.repo.add(Program(**data.model_dump()))

    def update(self, program_id: int, data: BaseModel) -> Program:
        p = self.get(program_id)
        _apply(p, data)
        return self.repo.save(p)

    def delete(self, program_id: int) -> None:
        self.repo.delete(self.get(program_id))

    def scope_validator(self, program_id: int) -> ScopeValidator:
        return ScopeValidator(self.get(program_id).scope_rules)

    def check_scope(self, program_id: int, host: str) -> ScopeDecision:
        return self.scope_validator(program_id).check(host)


class _ProgramChildService:
    repo_cls: type
    label: str
    model: type

    def __init__(self, db: Session):
        self.programs = ProgramService(db)
        self.repo = self.repo_cls(db)

    def list(self, program_id: int):
        self.programs.get(program_id)
        return self.repo.list_for_program(program_id)

    def get(self, program_id: int, item_id: int):
        obj = self.repo.get(item_id)
        if obj is None or obj.program_id != program_id:
            raise NotFoundError(self.label)
        return obj

    def _validate(self, program_id: int, data: BaseModel) -> None:
        pass

    def create(self, program_id: int, data: BaseModel):
        self.programs.get(program_id)
        self._validate(program_id, data)
        return self.repo.add(self.model(program_id=program_id, **data.model_dump()))

    def update(self, program_id: int, item_id: int, data: BaseModel):
        obj = self.get(program_id, item_id)
        self._validate(program_id, data)
        _apply(obj, data)
        return self.repo.save(obj)

    def delete(self, program_id: int, item_id: int) -> None:
        self.repo.delete(self.get(program_id, item_id))


class ScopeRuleService(_ProgramChildService):
    repo_cls, label, model = ScopeRuleRepository, "scope rule", ScopeRule


class TargetService(_ProgramChildService):
    repo_cls, label, model = TargetRepository, "target", Target


class FindingService(_ProgramChildService):
    repo_cls, label, model = FindingRepository, "finding", Finding

    def _validate(self, program_id: int, data: BaseModel) -> None:
        target_id = getattr(data, "target_id", None)
        if target_id is not None:
            t = TargetRepository(self.repo.db).get(target_id)
            if t is None or t.program_id != program_id:
                raise ValidationError("target does not belong to this program")


class NoteService(_ProgramChildService):
    repo_cls, label, model = NoteRepository, "note", Note

    def _validate(self, program_id: int, data: BaseModel) -> None:
        finding_id = getattr(data, "finding_id", None)
        if finding_id is not None:
            f = FindingRepository(self.repo.db).get(finding_id)
            if f is None or f.program_id != program_id:
                raise ValidationError("finding does not belong to this program")
