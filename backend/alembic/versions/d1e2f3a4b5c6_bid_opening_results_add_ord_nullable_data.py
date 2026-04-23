"""bid_opening_results: add bid_ntce_ord to PK, make data nullable for error state

Revision ID: d1e2f3a4b5c6
Revises: c3e4f5a6b7c8
Create Date: 2026-04-23

data column semantics after this migration:
  NULL  → last fetch failed (error cooldown: 3 min)
  []    → fetch succeeded but no results yet (empty cooldown: 10 min)
  [...] → valid results (served from cache)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d1e2f3a4b5c6"
down_revision = "c3e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add bid_ntce_ord with server default "000"
    op.add_column(
        "bid_opening_results",
        sa.Column(
            "bid_ntce_ord",
            sa.String(10),
            nullable=False,
            server_default="000",
        ),
    )

    # 2. Drop old single-column PK
    op.drop_constraint("bid_opening_results_pkey", "bid_opening_results", type_="primary")

    # 3. Create composite PK
    op.create_primary_key(
        "bid_opening_results_pkey",
        "bid_opening_results",
        ["bid_ntce_no", "bid_ntce_ord"],
    )

    # 4. Allow data=NULL to represent fetch-error state
    op.alter_column("bid_opening_results", "data", nullable=True)


def downgrade() -> None:
    # Revert data to NOT NULL (set NULLs to [] first)
    op.execute("UPDATE bid_opening_results SET data = '[]' WHERE data IS NULL")
    op.alter_column("bid_opening_results", "data", nullable=False)

    # Remove composite PK, restore single-column PK
    op.drop_constraint("bid_opening_results_pkey", "bid_opening_results", type_="primary")
    op.create_primary_key("bid_opening_results_pkey", "bid_opening_results", ["bid_ntce_no"])

    # Remove bid_ntce_ord column
    op.drop_column("bid_opening_results", "bid_ntce_ord")
