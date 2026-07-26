from app.models.notice import Notice
from app.models.notice_like import NoticeLike
from app.models.room import Room
from app.models.room_idempotency_key import RoomIdempotencyKey
from app.models.room_invite import RoomInvite
from app.models.room_meal_comment import RoomMealComment
from app.models.room_meal_reaction import RoomMealReaction
from app.models.room_meal_thread import RoomMealThread
from app.models.room_member import RoomMember
from app.models.room_nudge import RoomNudge
from app.models.room_report import RoomReport
from app.models.social_account_ref import SocialAccountRef
from app.models.tag import Tag
from app.models.user_ref import UserRef

__all__ = [
    "Notice",
    "NoticeLike",
    "Room",
    "RoomIdempotencyKey",
    "RoomInvite",
    "RoomMealComment",
    "RoomMealReaction",
    "RoomMealThread",
    "RoomMember",
    "RoomNudge",
    "RoomReport",
    "SocialAccountRef",
    "Tag",
    "UserRef",
]

# Tables this service owns and self-migrates via create_all() in app/main.py.
# Tag (service.tags), UserRef (public.users), SocialAccountRef
# (public.social_accounts)는 READ-ONLY — Ingredients Service와 login-service가
# 각각 소유하며, create_all()이 이들까지 만들거나 고치려 들지 않도록 여기
# 절대 넣지 않는다.
OWNED_TABLES = [
    Notice.__table__,
    NoticeLike.__table__,
    Room.__table__,
    RoomMember.__table__,
    RoomInvite.__table__,
    RoomMealThread.__table__,
    RoomMealComment.__table__,
    RoomMealReaction.__table__,
    RoomNudge.__table__,
    RoomReport.__table__,
    RoomIdempotencyKey.__table__,
]
