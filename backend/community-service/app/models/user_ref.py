from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserRef(Base):
    """login-service owns the real `users` table (public schema) — this is a
    minimal stub so SQLAlchemy can resolve FKs from this service's own tables
    (notices.author_user_id, notice_likes.user_id, rooms.owner_id 등) to it.
    Never written to, and never included in create_all() (see OWNED_TABLES
    below). display_name은 얌로그(rooms)가 room_members/room_meal_threads의
    표시 이름을 채우기 위해 읽기 전용으로 추가했다 — login-service의
    user.py 모델과 동일 컬럼."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
