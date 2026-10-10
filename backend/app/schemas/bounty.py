from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.bounty import FindingStatus, ScopeAction, ScopeType, Severity


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProgramBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    platform: str | None = None
    url: str | None = None
    reward_info: str | None = None


class ProgramCreate(ProgramBase):
    pass


class ProgramUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    platform: str | None = None
    url: str | None = None
    reward_info: str | None = None


class ProgramRead(ORM, ProgramBase):
    id: int
    created_at: datetime


class ScopeRuleCreate(BaseModel):
    action: ScopeAction
    type: ScopeType
    value: str = Field(min_length=1, max_length=500)


class ScopeRuleUpdate(BaseModel):
    action: ScopeAction | None = None
    type: ScopeType | None = None
    value: str | None = Field(default=None, min_length=1, max_length=500)


class ScopeRuleRead(ORM, ScopeRuleCreate):
    id: int
    program_id: int


class TargetCreate(BaseModel):
    value: str = Field(min_length=1, max_length=500)
    description: str | None = None


class TargetUpdate(BaseModel):
    value: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None


class TargetRead(ORM, TargetCreate):
    id: int
    program_id: int


class FindingCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    target_id: int | None = None
    status: FindingStatus = FindingStatus.NEW
    severity: Severity = Severity.INFO
    payout_cents: int | None = Field(default=None, ge=0)


class FindingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    target_id: int | None = None
    status: FindingStatus | None = None
    severity: Severity | None = None
    payout_cents: int | None = Field(default=None, ge=0)


class FindingRead(ORM, FindingCreate):
    id: int
    program_id: int


class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    body_md: str = ""
    finding_id: int | None = None


class NoteUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    body_md: str | None = None
    finding_id: int | None = None


class NoteRead(ORM, NoteCreate):
    id: int
    program_id: int


class ScopeCheckRequest(BaseModel):
    host: str = Field(min_length=1)


class ScopeCheckResult(BaseModel):
    host: str
    in_scope: bool
    reason: str
