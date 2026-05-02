"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def json_col():
    return postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "workers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("machine_name", sa.String(length=255), nullable=False),
        sa.Column("os", sa.String(length=80), nullable=False),
        sa.Column("arch", sa.String(length=80), nullable=False),
        sa.Column("has_docker", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("has_flutter", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("has_android_sdk", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("has_xcode", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("has_codex", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("has_aider", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=80), nullable=False, server_default="online"),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_job_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(length=120), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("encrypted_key", sa.Text(), nullable=False),
        sa.Column("key_hint", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False, server_default="active"),
        sa.Column("daily_budget_usd", sa.Numeric(12, 2), nullable=False, server_default="5"),
        sa.Column("monthly_budget_usd", sa.Numeric(12, 2), nullable=False, server_default="100"),
        sa.Column("total_estimated_spend_usd", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("assigned_worker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workers.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "ideas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False, server_default="manual"),
        sa.Column("opportunity_score", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("status", sa.String(length=80), nullable=False, server_default="new"),
        sa.Column("evidence_json", json_col(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False, unique=True),
        sa.Column("idea_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ideas.id"), nullable=True),
        sa.Column("status", sa.String(length=80), nullable=False, server_default="created"),
        sa.Column("target_platforms", json_col(), nullable=False, server_default='["android"]'),
        sa.Column("workspace_path", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("agent_name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("input_json", json_col(), nullable=False, server_default="{}"),
        sa.Column("output_json", json_col(), nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("iteration", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "agent_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id"), nullable=True),
        sa.Column("step", sa.String(length=160), nullable=False),
        sa.Column("level", sa.String(length=40), nullable=False, server_default="info"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("stdout", sa.Text(), nullable=True),
        sa.Column("stderr", sa.Text(), nullable=True),
        sa.Column("metadata_json", json_col(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "builds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("platform", sa.String(length=80), nullable=False, server_default="android"),
        sa.Column("artifact_path", sa.String(length=512), nullable=True),
        sa.Column("logs", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "qa_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("command", sa.String(length=255), nullable=False),
        sa.Column("exit_code", sa.Integer(), nullable=False),
        sa.Column("stdout", sa.Text(), nullable=True),
        sa.Column("stderr", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "policy_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("risk", sa.String(length=80), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("issues", json_col(), nullable=False, server_default="[]"),
        sa.Column("required_changes", json_col(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("kind", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("metadata_json", json_col(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "cost_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("api_keys.id"), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("provider", sa.String(length=120), nullable=False),
        sa.Column("estimated_cost_usd", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("purpose", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_index("ix_agent_events_project_created", "agent_events", ["project_id", "created_at"])
    op.create_index("ix_qa_results_project_created", "qa_results", ["project_id", "created_at"])
    op.create_index("ix_policy_results_project_created", "policy_results", ["project_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_policy_results_project_created", table_name="policy_results")
    op.drop_index("ix_qa_results_project_created", table_name="qa_results")
    op.drop_index("ix_agent_events_project_created", table_name="agent_events")
    for table in [
        "cost_usage",
        "artifacts",
        "policy_results",
        "qa_results",
        "builds",
        "agent_events",
        "agent_runs",
        "projects",
        "ideas",
        "api_keys",
        "workers",
    ]:
        op.drop_table(table)
