from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RecipeRef(Base):
    """Recipe Service 소유 — service.recipes. 읽기 전용 스냅샷 조회용.

    itemType=recipe인 식단 기록(RC-0113)을 저장할 때 이름을 채우는 용도라
    id/name 외 컬럼은 매핑하지 않았었다. thumbnail_url/video_id는 recipe-service의
    실제 Recipe 모델(app/models/recipe.py)에 이미 있는 컬럼을 추가로
    매핑한 것뿐이라 별도 마이그레이션이 필요 없다 - 얌로그(rooms) 멀티소스
    사진 캐러셀에서 레시피로 등록한 항목도 사진이 뜨게 하려면 필요하다.

    video_id도 같이 매핑해야 하는 이유(2026-07-26 실사용 중 재현) - source=
    "유튜브" 레시피는 thumbnail_url이 "/data/thumbnails/{id}.jpg" 같은 상대
    경로라 서빙하는 곳이 없어 항상 깨진다(recipe-service 자신도 app/routers/
    recipe.py의 _thumbnail_url()에서 이 경우 video_id로 유튜브 공개 썸네일을
    대신 쓴다). 여기서 thumbnail_url 컬럼만 그대로 넘기면 유튜브 레시피로
    등록한 사람만 얌로그에 사진이 안 뜨는 것처럼 보인다 - app/routers/diet.py
    에서 같은 폴백을 적용한다."""

    __tablename__ = "recipes"
    __table_args__ = {"schema": "service"}

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_id: Mapped[str] = mapped_column(String(100))
