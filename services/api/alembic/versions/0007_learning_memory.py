"""learning memory and autopilot evaluations

Revision ID: 0007_learning_memory
Revises: 0006_vietnamese_default_language
Create Date: 2026-05-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0007_learning_memory"
down_revision = "0006_vietnamese_default_language"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "run_evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brief_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column("language", sa.String(length=80), nullable=True),
        sa.Column("monetization", sa.String(length=80), nullable=True),
        sa.Column("provider", sa.String(length=120), nullable=False, server_default="deterministic"),
        sa.Column("archetype", sa.String(length=120), nullable=True),
        sa.Column("final_status", sa.String(length=80), nullable=False),
        sa.Column("qa_passed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("quality_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("policy_passed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("store_readiness_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("time_to_complete_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fix_iterations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("human_review_reason", sa.Text(), nullable=True),
        sa.Column("metrics_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["brief_id"], ["factory_briefs.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
    )
    op.create_table(
        "failure_patterns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("taxonomy", sa.String(length=120), nullable=False, unique=True),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_reason", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["last_project_id"], ["projects.id"]),
    )
    op.create_table(
        "learning_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("rule_key", sa.String(length=160), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("confidence_score", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("trigger_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("action_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("learning_rules")
    op.drop_table("failure_patterns")
    op.drop_table("run_evaluations")
