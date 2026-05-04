"""set vietnamese as default dashboard language

Revision ID: 0006_vietnamese_default_language
Revises: 0005_worker_mode
Create Date: 2026-05-03 00:00:00.000000
"""

from alembic import op


revision = "0006_vietnamese_default_language"
down_revision = "0005_worker_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE app_settings ALTER COLUMN default_language SET DEFAULT 'vi'")
    op.execute("UPDATE app_settings SET default_language = 'vi' WHERE default_language IS NULL OR default_language = 'en'")


def downgrade() -> None:
    op.execute("ALTER TABLE app_settings ALTER COLUMN default_language SET DEFAULT 'en'")
