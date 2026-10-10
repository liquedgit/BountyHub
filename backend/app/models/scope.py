from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ScopeRule(Base):
    """Per-program scope rule. rule_type: domain | wildcard | ip | url."""

    __tablename__ = "scope_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(Integer, index=True)
    rule_type: Mapped[str] = mapped_column(String(16))
    pattern: Mapped[str] = mapped_column(String(512))
    in_scope: Mapped[bool] = mapped_column(Boolean, default=True)
