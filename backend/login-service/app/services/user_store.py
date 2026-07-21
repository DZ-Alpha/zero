from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.social_account import SocialAccount
from app.models.user import User


class SocialAccountAlreadyLinkedError(Exception):
    pass


class LastSocialAccountError(Exception):
    pass


class SocialAccountNotFoundError(Exception):
    pass


class DuplicateEmailError(Exception):
    """다른 provider로 이미 가입된 이메일로 새 provider 최초 로그인을 시도한 경우.

    같은 사람이 네이버로 가입한 뒤 카카오로 로그인하면 provider_user_id 기준으로는
    "신규"지만, 이메일 기준으로는 이미 회원이다 — 여기서 걸러서 중복 계정 생성을 막는다.
    자동 연동은 하지 않는다: 이미 있는 /{provider}/link 플로우가 로그인된 세션에서만
    연동을 허용하는 동의 기반 설계라, 이메일 일치만으로 계정을 합치면 그 전제가 깨진다.
    """

    def __init__(self, existing_providers: list[str]):
        self.existing_providers = existing_providers
        super().__init__(f"이미 다른 소셜 계정으로 가입된 이메일입니다: {existing_providers}")


async def _find_social_account(db: AsyncSession, provider: str, provider_user_id: str) -> SocialAccount | None:
    stmt = (
        select(SocialAccount)
        .where(SocialAccount.provider == provider, SocialAccount.provider_user_id == provider_user_id)
        .options(selectinload(SocialAccount.user))
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _find_user_by_email(db: AsyncSession, email: str) -> User | None:
    stmt = select(User).where(User.email == email).options(selectinload(User.social_accounts))
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_or_create_user(
    db: AsyncSession,
    provider: str,
    provider_user_id: str,
    nickname: str,
    email: str | None,
    profile_image_url: str | None = None,
    gender: str | None = None,
    birthday: str | None = None,
    birthyear: str | None = None,
) -> tuple[User, bool]:
    existing = await _find_social_account(db, provider, provider_user_id)

    if existing is not None:
        return existing.user, False

    if email is not None:
        other_user = await _find_user_by_email(db, email)
        if other_user is not None:
            raise DuplicateEmailError([account.provider for account in other_user.social_accounts])

    user = User(email=email)
    social_account = SocialAccount(
        user=user,
        provider=provider,
        provider_user_id=provider_user_id,
        nickname=nickname,
        profile_image_url=profile_image_url,
        provider_email=email,
        provider_gender=gender,
        provider_birthday=birthday,
        provider_birthyear=birthyear,
    )
    db.add(user)
    db.add(social_account)
    await db.commit()
    await db.refresh(user)
    return user, True


async def link_social_account(
    db: AsyncSession,
    user_id: int,
    provider: str,
    provider_user_id: str,
    nickname: str,
    email: str | None,
    profile_image_url: str | None = None,
    gender: str | None = None,
    birthday: str | None = None,
    birthyear: str | None = None,
) -> tuple[User, bool]:
    existing = await _find_social_account(db, provider, provider_user_id)

    if existing is not None:
        if existing.user_id != user_id:
            raise SocialAccountAlreadyLinkedError(f"이미 다른 계정에 연결된 {provider} 계정입니다.")
        return existing.user, False

    user = await db.get(User, user_id)
    if user is None:
        raise SocialAccountAlreadyLinkedError("연동 대상 사용자를 찾을 수 없습니다.")

    social_account = SocialAccount(
        user_id=user_id,
        provider=provider,
        provider_user_id=provider_user_id,
        nickname=nickname,
        profile_image_url=profile_image_url,
        provider_email=email,
        provider_gender=gender,
        provider_birthday=birthday,
        provider_birthyear=birthyear,
    )
    db.add(social_account)
    await db.commit()
    await db.refresh(user)
    return user, True


async def unlink_social_account(db: AsyncSession, user_id: int, provider: str) -> list[str]:
    stmt = select(SocialAccount).where(SocialAccount.user_id == user_id)
    accounts = (await db.execute(stmt)).scalars().all()

    target = next((account for account in accounts if account.provider == provider), None)
    if target is None:
        raise SocialAccountNotFoundError(f"연동되어 있지 않은 {provider} 계정입니다.")

    if len(accounts) <= 1:
        raise LastSocialAccountError("마지막으로 남은 연동 계정은 해제할 수 없습니다.")

    await db.delete(target)
    await db.commit()

    return [account.provider for account in accounts if account.provider != provider]


async def delete_user(db: AsyncSession, user_id: int) -> None:
    user = await db.get(User, user_id)
    if user is None:
        return
    await db.delete(user)
    await db.commit()


async def handle_provider_unlink(db: AsyncSession, provider: str, provider_user_id: str) -> str:
    """Provider (Naver/Kakao) notified us that a user disconnected outside our app.

    Unlike unlink_social_account (user-initiated via our UI), this can't be blocked
    just because it's the user's last linked account — the disconnection already
    happened on the provider's side. If it's their only account, cascade to full
    account deletion instead of leaving an unreachable orphaned user.
    """
    account = await _find_social_account(db, provider, provider_user_id)
    if account is None:
        return "not_found"

    stmt = select(SocialAccount).where(SocialAccount.user_id == account.user_id)
    siblings = (await db.execute(stmt)).scalars().all()

    if len(siblings) <= 1:
        await db.delete(account.user)
        await db.commit()
        return "deleted_account"

    await db.delete(account)
    await db.commit()
    return "unlinked_social"
