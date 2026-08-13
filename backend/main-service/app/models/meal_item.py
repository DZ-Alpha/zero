import uuid
from decimal import Decimal

from sqlalchemy import Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MealItem(Base):
    """Diet Service owns this table (service.meal_items) — main-service only
    reads it, to sum a user's daily calorie/sugar intake for the home gauge.

    Only the columns the gauge needs are mapped. The table has more (item_name,
    serving_value/unit, carbohydrate, product_id, external_recipe_id); mapping
    them here would mean main-service has to track a table it doesn't own.
    Never written to and never in OWNED_TABLES, so create_all() skips it."""

    __tablename__ = "meal_items"
    __table_args__ = {"schema": "service"}

    meal_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    meal_log_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    calories: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    sugars: Mapped[Decimal] = mapped_column(Numeric(10, 2))
