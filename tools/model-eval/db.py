from dataclasses import dataclass, field

import asyncpg

import config


@dataclass
class SampleTag:
    tag_type: str
    tag_name: str
    description: str | None
    caution_text: str | None


@dataclass
class SampleProduct:
    product_id: str
    product_name: str
    brand_name: str | None
    calories: float | None
    sugars: float | None
    sodium: float | None
    protein: float | None
    ingredient_text: str | None
    tags: list[SampleTag] = field(default_factory=list)

    @property
    def sweetener_tags(self) -> list[SampleTag]:
        return [t for t in self.tags if t.tag_type == "SWEETENER"]

    @property
    def allergen_tags(self) -> list[SampleTag]:
        return [t for t in self.tags if t.tag_type == "ALLERGEN"]


async def fetch_sample_products(limit: int) -> list[SampleProduct]:
    """product-service DB(service.products/tags/product_tags)에서 읽기 전용으로
    실제 상품 N개 + 태그를 가져온다. 감미료(SWEETENER) 태그가 붙은 상품이
    최소 1개는 포함되도록 우선순위를 준다 - PR-0302 테스트가 의미 있으려면
    대체 당이 있는 상품이 있어야 한다."""
    conn = await asyncpg.connect(
        host=config.POSTGRES_HOST,
        port=config.POSTGRES_PORT,
        database=config.POSTGRES_DB,
        user=config.POSTGRES_USER,
        password=config.POSTGRES_PASSWORD,
    )
    try:
        rows = await conn.fetch(
            """
            SELECT p.product_id, p.product_name, p.brand_name, p.calories,
                   p.sugars, p.sodium, p.protein, p.ingredient_text,
                   EXISTS (
                       SELECT 1 FROM service.product_tags pt
                       JOIN service.tags t ON t.tag_id = pt.tag_id
                       WHERE pt.product_id = p.product_id AND t.tag_type = 'SWEETENER' AND t.active
                   ) AS has_sweetener
            FROM service.products p
            ORDER BY has_sweetener DESC, p.product_id
            LIMIT $1
            """,
            limit,
        )
        products = []
        for row in rows:
            tag_rows = await conn.fetch(
                """
                SELECT t.tag_type, t.tag_name, t.description, t.caution_text
                FROM service.tags t
                JOIN service.product_tags pt ON pt.tag_id = t.tag_id
                WHERE pt.product_id = $1 AND t.active
                """,
                row["product_id"],
            )
            tags = [
                SampleTag(r["tag_type"], r["tag_name"], r["description"], r["caution_text"])
                for r in tag_rows
            ]
            products.append(
                SampleProduct(
                    product_id=str(row["product_id"]),
                    product_name=row["product_name"],
                    brand_name=row["brand_name"],
                    calories=float(row["calories"]) if row["calories"] is not None else None,
                    sugars=float(row["sugars"]) if row["sugars"] is not None else None,
                    sodium=float(row["sodium"]) if row["sodium"] is not None else None,
                    protein=float(row["protein"]) if row["protein"] is not None else None,
                    ingredient_text=row["ingredient_text"],
                    tags=tags,
                )
            )
        return products
    finally:
        await conn.close()
