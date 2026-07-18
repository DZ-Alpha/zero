from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RecipeRef(Base):
    """Recipe Service 소유 — service.recipes. 읽기 전용 스냅샷 조회용.

    itemType=recipe인 식단 기록(RC-0113)을 저장할 때 이름을 채우는 용도라
    id/name 외 컬럼은 매핑하지 않는다. ProductRef와 같은 패턴.
    """

    __tablename__ = "recipes"
    __table_args__ = {"schema": "service"}

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
