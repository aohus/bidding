"""add business info and dashboard features

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-02-10 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. User 테이블에 사업자정보 추가
    op.add_column('users', sa.Column('business_number', sa.String(20), nullable=True))
    op.add_column('users', sa.Column('company_name', sa.String(200), nullable=True))
    op.add_column('users', sa.Column('representative_name', sa.String(100), nullable=True))
    op.create_index('ix_users_business_number', 'users', ['business_number'])

    # 2. UserBookmark 테이블에 status, bid_price, bid_notice_ord, updated_at 추가
    op.add_column('user_bookmarks', sa.Column('status', sa.String(20), server_default='interested', nullable=False))
    op.add_column('user_bookmarks', sa.Column('bid_price', sa.BigInteger(), nullable=True))
    op.add_column('user_bookmarks', sa.Column('bid_notice_ord', sa.String(10), nullable=True))
    op.add_column('user_bookmarks', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()))

    # 3. 개찰결과 캐시 테이블 생성
    op.create_table(
        'bid_opening_results',
        sa.Column('bid_ntce_no', sa.String(50), primary_key=True),
        sa.Column('data', JSONB(), nullable=False),
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('bid_opening_results')

    op.drop_column('user_bookmarks', 'updated_at')
    op.drop_column('user_bookmarks', 'bid_notice_ord')
    op.drop_column('user_bookmarks', 'bid_price')
    op.drop_column('user_bookmarks', 'status')

    op.drop_index('ix_users_business_number', table_name='users')
    op.drop_column('users', 'representative_name')
    op.drop_column('users', 'company_name')
    op.drop_column('users', 'business_number')
