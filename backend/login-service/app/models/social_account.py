from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.user import User


class SocialAccount(Base):
    __tablename__ = "social_accounts"
    __table_args__ = (UniqueConstraint("provider", "provider_user_id", name="uq_social_provider_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(20))
    provider_user_id: Mapped[str] = mapped_column(String(255))
    nickname: Mapped[str] = mapped_column(String(100))
    profile_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    provider_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_gender: Mapped[str | None] = mapped_column(String(10), nullable=True)
    provider_birthday: Mapped[str | None] = mapped_column(String(10), nullable=True)
    provider_birthyear: Mapped[str | None] = mapped_column(String(4), nullable=True)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="social_accounts")
