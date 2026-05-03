"""worker mode

Revision ID: 0005_worker_mode
Revises: 0004_notification_metadata
Create Date: 2026-05-03
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_worker_mode"
down_revision = "0004_notification_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workers", sa.Column("worker_enable_codex", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    op.drop_column("workers", "worker_enable_codex")
