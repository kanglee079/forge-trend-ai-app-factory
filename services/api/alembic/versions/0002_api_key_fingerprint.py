"""add api key fingerprint

Revision ID: 0002_api_key_fingerprint
Revises: 0001_initial_schema
Create Date: 2026-05-02
"""

import sqlalchemy as sa
from alembic import op

from app.security import decrypt_secret, secret_fingerprint

revision = "0002_api_key_fingerprint"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    op.add_column("api_keys", sa.Column("key_fingerprint", sa.String(length=64), nullable=True))

    rows = connection.execute(
        sa.text("SELECT id, provider, encrypted_key FROM api_keys ORDER BY created_at ASC, id ASC")
    ).mappings()
    seen: set[tuple[str, str]] = set()
    for row in rows:
        provider = row["provider"].strip().lower()
        try:
            fingerprint = secret_fingerprint(decrypt_secret(row["encrypted_key"]))
        except Exception:
            fingerprint = secret_fingerprint(f"{row['encrypted_key']}:{row['id']}")
        duplicate_key = (provider, fingerprint)
        if duplicate_key in seen:
            fingerprint = secret_fingerprint(f"{fingerprint}:duplicate:{row['id']}")
            status = "duplicate"
        else:
            seen.add(duplicate_key)
            status = None
        update_sql = "UPDATE api_keys SET provider = :provider, key_fingerprint = :fingerprint"
        params = {"provider": provider, "fingerprint": fingerprint, "id": row["id"]}
        if status:
            update_sql += ", status = :status"
            params["status"] = status
        update_sql += " WHERE id = :id"
        connection.execute(
            sa.text(update_sql),
            params,
        )

    op.alter_column("api_keys", "key_fingerprint", nullable=False)
    op.create_unique_constraint(
        "uq_api_keys_provider_fingerprint",
        "api_keys",
        ["provider", "key_fingerprint"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_api_keys_provider_fingerprint", "api_keys", type_="unique")
    op.drop_column("api_keys", "key_fingerprint")
