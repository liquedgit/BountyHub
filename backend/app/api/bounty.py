from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import bounty as s
from app.services.bounty import (
    FindingService,
    NoteService,
    NotFoundError,
    ProgramService,
    ScopeRuleService,
    TargetService,
    ValidationError,
)

router = APIRouter(prefix="/programs", tags=["bounty"])


def _call(fn, *args):
    try:
        return fn(*args)
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
    except ValidationError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from e


# ---- programs ----
@router.get("", response_model=list[s.ProgramRead])
def list_programs(db: Session = Depends(get_db)):
    return ProgramService(db).list()


@router.post("", response_model=s.ProgramRead, status_code=201)
def create_program(data: s.ProgramCreate, db: Session = Depends(get_db)):
    return ProgramService(db).create(data)


@router.get("/{program_id}", response_model=s.ProgramRead)
def get_program(program_id: int, db: Session = Depends(get_db)):
    return _call(ProgramService(db).get, program_id)


@router.patch("/{program_id}", response_model=s.ProgramRead)
def update_program(program_id: int, data: s.ProgramUpdate, db: Session = Depends(get_db)):
    return _call(ProgramService(db).update, program_id, data)


@router.delete("/{program_id}", status_code=204)
def delete_program(program_id: int, db: Session = Depends(get_db)):
    _call(ProgramService(db).delete, program_id)
    return Response(status_code=204)


@router.post("/{program_id}/scope-check", response_model=s.ScopeCheckResult)
def scope_check(program_id: int, data: s.ScopeCheckRequest, db: Session = Depends(get_db)):
    d = _call(ProgramService(db).check_scope, program_id, data.host)
    return s.ScopeCheckResult(host=data.host, in_scope=d.in_scope, reason=d.reason)


def _crud(path: str, service_cls, read, create, update):
    @router.get(f"/{{program_id}}/{path}", response_model=list[read], name=f"list_{path}")
    def _list(program_id: int, db: Session = Depends(get_db)):
        return _call(service_cls(db).list, program_id)

    @router.post(
        f"/{{program_id}}/{path}", response_model=read, status_code=201, name=f"create_{path}"
    )
    def _create(program_id: int, data: create, db: Session = Depends(get_db)):  # type: ignore[valid-type]
        return _call(service_cls(db).create, program_id, data)

    @router.get(f"/{{program_id}}/{path}/{{item_id}}", response_model=read, name=f"get_{path}")
    def _get(program_id: int, item_id: int, db: Session = Depends(get_db)):
        return _call(service_cls(db).get, program_id, item_id)

    @router.patch(f"/{{program_id}}/{path}/{{item_id}}", response_model=read, name=f"update_{path}")
    def _update(program_id: int, item_id: int, data: update, db: Session = Depends(get_db)):  # type: ignore[valid-type]
        return _call(service_cls(db).update, program_id, item_id, data)

    @router.delete(f"/{{program_id}}/{path}/{{item_id}}", status_code=204, name=f"delete_{path}")
    def _delete(program_id: int, item_id: int, db: Session = Depends(get_db)):
        _call(service_cls(db).delete, program_id, item_id)
        return Response(status_code=204)


_crud("scope-rules", ScopeRuleService, s.ScopeRuleRead, s.ScopeRuleCreate, s.ScopeRuleUpdate)
_crud("targets", TargetService, s.TargetRead, s.TargetCreate, s.TargetUpdate)
_crud("findings", FindingService, s.FindingRead, s.FindingCreate, s.FindingUpdate)
_crud("notes", NoteService, s.NoteRead, s.NoteCreate, s.NoteUpdate)
