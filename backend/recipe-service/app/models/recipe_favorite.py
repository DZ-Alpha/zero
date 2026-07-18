from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RecipeFavorite(Base):
    """Recipe Service 소유 — recipe.recipe_favorites (RC-0111/0112).

    `service` 스키마는 데이터팀 소유라 새 테이블을 못 만들어서, community-service의
    notice_likes와 같은 패턴으로 이 서비스 전용 `recipe` 스키마에 둔다.
    """

    __tablename__ = "recipe_favorites"
    __table_args__ = {"schema": "recipe"}

    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("service.recipes.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
