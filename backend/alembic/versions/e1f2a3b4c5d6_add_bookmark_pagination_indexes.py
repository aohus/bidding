"""add bookmark pagination indexes

Revision ID: e1f2a3b4c5d6
Revises: d1e2f3a4b5c6
Create Date: 2026-04-23

"""
from alembic import op

revision = "e1f2a3b4c5d6"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_user_bookmarks_user_id", table_name="user_bookmarks")
    op.create_index(
        "ix_user_bookmarks_user_status_created",
        "user_bookmarks",
        ["user_id", "status", "created_at"],
    )
    op.create_index(
        "ix_user_bookmarks_notice_ord",
        "user_bookmarks",
        ["bid_notice_no", "bid_notice_ord"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_bookmarks_notice_ord", table_name="user_bookmarks")
    op.drop_index("ix_user_bookmarks_user_status_created", table_name="user_bookmarks")
    op.create_index(
        "ix_user_bookmarks_user_id",
        "user_bookmarks",
        ["user_id"],
    )
