from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SocialAccountRef(Base):
    """login-service owns the real `social_accounts` table (public schema) —
    read-only mirror, same pattern as UserRef. Never written to, never in
    create_all() (see OWNED_TABLES).

    users.display_name is null until a user explicitly renames themselves in
    마이페이지 — until then, login-service falls back to the OAuth provider's
    nickname captured here at signup (app/routers/user.py의 동일 로직).
    get_display_names_bulk()가 이 fallback을 안 타서 대부분의 멤버가 "회원{id}"
    로만 보이던 버그(2026-07-26) — display_name 없는 사용자 전부가 여기 걸린다.
    """

    __tablename__ = "social_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer)
    nickname: Mapped[str] = mapped_column(String(100))
