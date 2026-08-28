"""add_registry_cache

Revision ID: e2f3g4h5i6j7
Revises: da5c2fa7e1aa
Create Date: 2026-08-24 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e2f3g4h5i6j7'
down_revision: Union[str, None] = 'da5c2fa7e1aa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.create_table('registry_cache',
        sa.Column('ecosystem', sa.String(length=255), nullable=False),
        sa.Column('package_name', sa.String(length=255), nullable=False),
        sa.Column('status', sa.Enum('SUCCESS', 'NOT_FOUND', 'PROVIDER_UNAVAILABLE', 'RATE_LIMITED', 'INVALID_RESPONSE', 'UNSUPPORTED_REQUEST', name='registry_status_enum', native_enum=False), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_registry_cache_ecosystem'), 'registry_cache', ['ecosystem'], unique=False)
    op.create_index(op.f('ix_registry_cache_package_name'), 'registry_cache', ['package_name'], unique=False)
    op.create_index(op.f('ix_registry_cache_expires_at'), 'registry_cache', ['expires_at'], unique=False)
    op.create_unique_constraint('uq_registry_cache_ecosystem_package', 'registry_cache', ['ecosystem', 'package_name'])


def downgrade() -> None:
    op.drop_constraint('uq_registry_cache_ecosystem_package', 'registry_cache', type_='unique')
    op.drop_index(op.f('ix_registry_cache_expires_at'), table_name='registry_cache')
    op.drop_index(op.f('ix_registry_cache_package_name'), table_name='registry_cache')
    op.drop_index(op.f('ix_registry_cache_ecosystem'), table_name='registry_cache')
    op.drop_table('registry_cache')
