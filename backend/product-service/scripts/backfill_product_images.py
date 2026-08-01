"""기존 products.image_url(외부 핫링크)을 우리 MinIO로 1회성 백필한다.

멱등: 이미 /b/product-images/ 인 행은 건너뛴다. 실패한 행은 원본 URL을
그대로 두고 계속 진행한다(중단 없음).

실행 전 준비(팀): product-images 버킷 생성 + public-read, product-service에
MINIO_ENDPOINT/ACCESS_KEY/SECRET_KEY env 주입. docs/ops/product-images-minio-runbook.md 참고.

사용:
  python -m scripts.backfill_product_images --dry-run            # 대상만 세어봄
  python -m scripts.backfill_product_images --limit 20           # 20건만
  python -m scripts.backfill_product_images                      # 전체
"""
import argparse
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_product_images")


async def run(dry_run: bool, limit: int | None) -> None:
    from sqlalchemy import select, update
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.core.config import settings
    from app.models.product import Product
    from app.services.image_storage import is_self_hosted, store_external_image

    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        stmt = select(Product.product_id, Product.image_url)
        result = await session.execute(stmt)
        rows = result.all()

    targets = [(pid, url) for pid, url in rows if url and not is_self_hosted(url)]
    logger.info("전체 %d건 중 백필 대상 %d건 (이미 self-hosted: %d건)",
                len(rows), len(targets), len(rows) - len(targets))
    if limit is not None:
        targets = targets[:limit]
        logger.info("--limit %d 적용 → %d건 처리", limit, len(targets))

    if dry_run:
        logger.info("[dry-run] 실제 저장/UPDATE 없이 종료")
        await engine.dispose()
        return

    ok = 0
    failed = 0
    async with Session() as session:
        for i, (pid, url) in enumerate(targets, 1):
            # store_external_image는 blocking(httpx/boto3) — 이벤트 루프 블로킹을
            # 피하려고 스레드로 넘긴다.
            stored = await asyncio.to_thread(store_external_image, url)
            if stored and stored != url:
                await session.execute(
                    update(Product).where(Product.product_id == pid).values(image_url=stored)
                )
                ok += 1
            else:
                failed += 1
                logger.warning("건너뜀(원본 유지) product_id=%s url=%s", pid, url)
            if i % 50 == 0:
                await session.commit()
                logger.info("진행 %d/%d (성공 %d, 실패 %d)", i, len(targets), ok, failed)
        await session.commit()

    logger.info("완료: 성공 %d, 실패(원본 유지) %d, 총 %d", ok, failed, len(targets))
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="대상만 세고 저장/UPDATE 안 함")
    parser.add_argument("--limit", type=int, default=None, help="처리할 최대 건수")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run, limit=args.limit))


if __name__ == "__main__":
    main()
