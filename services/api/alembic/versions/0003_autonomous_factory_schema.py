"""autonomous factory schema

Revision ID: 0003_autonomous_factory_schema
Revises: 0002_api_key_fingerprint
Create Date: 2026-05-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_autonomous_factory_schema"
down_revision = "0002_api_key_fingerprint"
branch_labels = None
depends_on = None


def json_col():
    return postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "factory_state",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("mode", sa.String(length=40), nullable=False, server_default="running"),
        sa.Column("auto_trend_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("active_project_limit", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("daily_budget_usd", sa.Numeric(12, 2), nullable=False, server_default="5"),
        sa.Column("monthly_budget_usd", sa.Numeric(12, 2), nullable=False, server_default="100"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "app_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("default_provider", sa.String(length=120), nullable=False, server_default="openai"),
        sa.Column("default_model", sa.String(length=160), nullable=False, server_default="gpt-5.2"),
        sa.Column("max_fix_iterations", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("workspace_root", sa.String(length=512), nullable=False, server_default="workspaces"),
        sa.Column("auto_refresh_seconds", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("notifications_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("theme", sa.String(length=40), nullable=False, server_default="system"),
        sa.Column("daily_budget_usd", sa.Numeric(12, 2), nullable=False, server_default="5"),
        sa.Column("monthly_budget_usd", sa.Numeric(12, 2), nullable=False, server_default="100"),
        sa.Column("default_platforms", json_col(), nullable=False, server_default='["android"]'),
        sa.Column("default_backend", sa.String(length=80), nullable=False, server_default="none"),
        sa.Column("default_monetization", sa.String(length=80), nullable=False, server_default="none"),
        sa.Column("default_language", sa.String(length=80), nullable=False, server_default="en"),
        sa.Column("default_target_country", sa.String(length=80), nullable=False, server_default="US"),
        sa.Column("policy_strictness", sa.String(length=80), nullable=False, server_default="standard"),
        sa.Column("feature_flags", json_col(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "factory_briefs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("mode", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("raw_prompt", sa.Text(), nullable=False),
        sa.Column("target_category", sa.String(length=120), nullable=True),
        sa.Column("target_platforms", json_col(), nullable=False, server_default='["android"]'),
        sa.Column("target_country", sa.String(length=80), nullable=False, server_default="US"),
        sa.Column("target_language", sa.String(length=80), nullable=False, server_default="en"),
        sa.Column("monetization_mode", sa.String(length=80), nullable=False, server_default="none"),
        sa.Column("iap_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("subscription_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ads_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("backend_mode", sa.String(length=80), nullable=False, server_default="none"),
        sa.Column("complexity", sa.String(length=80), nullable=False, server_default="medium"),
        sa.Column("max_cost_usd", sa.Numeric(12, 2), nullable=False, server_default="5"),
        sa.Column("max_runtime_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("quality_threshold", sa.Integer(), nullable=False, server_default="75"),
        sa.Column("policy_strictness", sa.String(length=80), nullable=False, server_default="standard"),
        sa.Column("status", sa.String(length=80), nullable=False, server_default="draft"),
        sa.Column("selected_idea_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ideas.id"), nullable=True),
        sa.Column("selected_project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "trend_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=80), nullable=False, server_default="manual"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("config_json", json_col(), nullable=False, server_default="{}"),
        sa.Column("rate_limit_per_hour", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "research_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("factory_brief_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("factory_briefs.id"), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column("keywords", json_col(), nullable=False, server_default="[]"),
        sa.Column("pain_points", json_col(), nullable=False, server_default="[]"),
        sa.Column("competitor_gaps", json_col(), nullable=False, server_default="[]"),
        sa.Column("evidence_json", json_col(), nullable=False, server_default="{}"),
        sa.Column("confidence_score", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "opportunity_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("factory_brief_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("factory_briefs.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("target_user", sa.Text(), nullable=False),
        sa.Column("problem", sa.Text(), nullable=False),
        sa.Column("unique_angle", sa.Text(), nullable=False),
        sa.Column("core_features", json_col(), nullable=False, server_default="[]"),
        sa.Column("monetization_plan", sa.Text(), nullable=True),
        sa.Column("iap_plan_json", json_col(), nullable=False, server_default="{}"),
        sa.Column("subscription_plan_json", json_col(), nullable=False, server_default="{}"),
        sa.Column("backend_plan_json", json_col(), nullable=False, server_default="{}"),
        sa.Column("opportunity_score", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("demand_score", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("pain_score", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("monetization_score", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("build_feasibility_score", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("differentiation_score", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("policy_risk_score", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("originality_score", sa.Integer(), nullable=False, server_default="75"),
        sa.Column("status", sa.String(length=80), nullable=False, server_default="proposed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "project_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("agent_name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False, server_default="pending"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_json", json_col(), nullable=False, server_default="{}"),
        sa.Column("output_json", json_col(), nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("commit_sha", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("level", sa.String(length=40), nullable=False, server_default="info"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.String(length=120), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_index("ix_factory_briefs_status_created", "factory_briefs", ["status", "created_at"])
    op.create_index("ix_research_findings_brief", "research_findings", ["factory_brief_id"])
    op.create_index("ix_candidates_brief_score", "opportunity_candidates", ["factory_brief_id", "opportunity_score"])
    op.create_index("ix_project_tasks_project_priority", "project_tasks", ["project_id", "priority"])
    op.create_index("ix_notifications_read_created", "notifications", ["read_at", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_notifications_read_created", table_name="notifications")
    op.drop_index("ix_project_tasks_project_priority", table_name="project_tasks")
    op.drop_index("ix_candidates_brief_score", table_name="opportunity_candidates")
    op.drop_index("ix_research_findings_brief", table_name="research_findings")
    op.drop_index("ix_factory_briefs_status_created", table_name="factory_briefs")
    for table in [
        "notifications",
        "project_tasks",
        "opportunity_candidates",
        "research_findings",
        "trend_sources",
        "factory_briefs",
        "app_settings",
        "factory_state",
    ]:
        op.drop_table(table)
