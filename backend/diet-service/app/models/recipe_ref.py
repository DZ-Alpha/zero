from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RecipeRef(Base):
    """Recipe Service 소유 — service.recipes. 읽기 전용 스냅샷 조회용.

    itemType=recipe인 식단 기록(RC-0113)을 저장할 때 이름을 채우는 용도라
    id/name 외 컬럼은 매핑하지 않았었다. thumbnail_url은 recipe-service의
    실제 Recipe 모델(app/models/recipe.py)에 이미 있는 컬럼을 추가로
    매핑한 것뿐이라 별도 마이그레이션이 필요 없다 - 얌로그(rooms) 멀티소스
    사진 캐러셀에서 레시피로 등록한 항목도 사진이 뜨게 하려면 필요하다.
    """

    __tablename__ = "recipes"
    __table_args__ = {"schema": "service"}

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
