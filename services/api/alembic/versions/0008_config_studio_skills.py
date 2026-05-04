"""config studio skills scanner and context packs

Revision ID: 0008_config_studio_skills
Revises: 0007_learning_memory
Create Date: 2026-05-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0008_config_studio_skills"
down_revision = "0007_learning_memory"
branch_labels = None
depends_on = None


def json_col():
    return postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "config_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("model_provider", sa.String(length=120), nullable=False, server_default="OpenAI"),
        sa.Column("model", sa.String(length=160), nullable=False, server_default="gpt-5.5"),
        sa.Column("review_model", sa.String(length=160), nullable=False, server_default="gpt-5.5"),
        sa.Column("model_reasoning_effort", sa.String(length=40), nullable=False, server_default="medium"),
        sa.Column("disable_response_storage", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("network_access", sa.String(length=40), nullable=False, server_default="disabled"),
        sa.Column("model_context_window", sa.Integer(), nullable=False, server_default="200000"),
        sa.Column("model_auto_compact_token_limit", sa.Integer(), nullable=False, server_default="160000"),
        sa.Column("active_provider_profile_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "provider_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("config_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("provider_type", sa.String(length=120), nullable=False, server_default="openai_compatible"),
        sa.Column("base_url", sa.String(length=512), nullable=False, server_default="https://api.openai.com/v1"),
        sa.Column("wire_api", sa.String(length=80), nullable=False, server_default="responses"),
        sa.Column("requires_openai_auth", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["config_profile_id"], ["config_profiles.id"]),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.id"]),
    )
    op.create_table(
        "config_plugins",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("config_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plugin_id", sa.String(length=160), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=False, server_default="plugin"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("source_type", sa.String(length=80), nullable=False, server_default="builtin"),
        sa.Column("source", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("version", sa.String(length=80), nullable=False, server_default="1.0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["config_profile_id"], ["config_profiles.id"]),
        sa.UniqueConstraint("config_profile_id", "plugin_id", name="uq_config_plugins_profile_plugin"),
    )
    op.create_table(
        "trusted_projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("config_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("trust_level", sa.String(length=80), nullable=False, server_default="trusted"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["config_profile_id"], ["config_profiles.id"]),
        sa.UniqueConstraint("config_profile_id", "path", name="uq_trusted_projects_profile_path"),
    )

    op.add_column("factory_briefs", sa.Column("config_profile_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("factory_briefs", sa.Column("runtime_config_snapshot_json", json_col(), nullable=False, server_default="{}"))
    op.add_column("factory_briefs", sa.Column("run_profile_slug", sa.String(length=120), nullable=True))
    op.create_foreign_key("fk_factory_briefs_config_profile", "factory_briefs", "config_profiles", ["config_profile_id"], ["id"])

    op.create_table(
        "skill_packs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False, unique=True),
        sa.Column("category", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.String(length=80), nullable=False, server_default="1.0.0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("source_type", sa.String(length=80), nullable=False, server_default="builtin"),
        sa.Column("source_url", sa.String(length=512), nullable=True),
        sa.Column("local_path", sa.String(length=512), nullable=True),
        sa.Column("quality_score", sa.Integer(), nullable=False, server_default="70"),
        sa.Column("token_budget", sa.Integer(), nullable=False, server_default="3000"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "skill_prompts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("skill_pack_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False, server_default=""),
        sa.Column("when_to_use", sa.Text(), nullable=False, server_default=""),
        sa.Column("prompt_template", sa.Text(), nullable=False),
        sa.Column("input_schema_json", json_col(), nullable=False, server_default="{}"),
        sa.Column("output_schema_json", json_col(), nullable=False, server_default="{}"),
        sa.Column("success_criteria_json", json_col(), nullable=False, server_default="{}"),
        sa.Column("token_budget", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["skill_pack_id"], ["skill_packs.id"]),
    )
    op.create_table(
        "skill_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("skill_pack_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("factory_brief_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("agent_name", sa.String(length=120), nullable=False),
        sa.Column("input_hash", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("output_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("tokens_estimated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=80), nullable=False, server_default="planned"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["skill_pack_id"], ["skill_packs.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["factory_brief_id"], ["factory_briefs.id"]),
    )
    op.create_table(
        "skill_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("skill_pack_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_quality_delta", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_tokens_saved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["skill_pack_id"], ["skill_packs.id"]),
    )
    op.create_table(
        "source_registries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=80), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("config_json", json_col(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "source_scan_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_type", sa.String(length=80), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False, server_default="completed"),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "source_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scan_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=80), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column("usefulness_score", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("status", sa.String(length=80), nullable=False, server_default="quarantined"),
        sa.Column("metadata_json", json_col(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["scan_run_id"], ["source_scan_runs.id"]),
    )
    op.create_table(
        "prompt_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(length=160), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=False, server_default="general"),
        sa.Column("template", sa.Text(), nullable=False),
        sa.Column("token_estimate", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "prompt_fragments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(length=160), nullable=False, unique=True),
        sa.Column("category", sa.String(length=120), nullable=False, server_default="general"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_estimate", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "prompt_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("cache_key", sa.String(length=160), nullable=False, unique=True),
        sa.Column("full_text_hash", sa.String(length=160), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("token_estimate", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "context_packs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("factory_brief_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("pack_type", sa.String(length=120), nullable=False),
        sa.Column("full_text_hash", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("important_files", json_col(), nullable=False, server_default="[]"),
        sa.Column("token_estimate", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["factory_brief_id"], ["factory_briefs.id"]),
    )
    op.create_table(
        "run_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("config_profile_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("skill_slugs", json_col(), nullable=False, server_default="[]"),
        sa.Column("token_budget", sa.Integer(), nullable=False, server_default="20000"),
        sa.Column("quality_threshold", sa.Integer(), nullable=False, server_default="75"),
        sa.Column("max_iterations", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("research_mode", sa.String(length=80), nullable=False, server_default="deterministic"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["config_profile_id"], ["config_profiles.id"]),
    )


def downgrade() -> None:
    op.drop_table("run_profiles")
    op.drop_table("context_packs")
    op.drop_table("prompt_cache")
    op.drop_table("prompt_fragments")
    op.drop_table("prompt_templates")
    op.drop_table("source_items")
    op.drop_table("source_scan_runs")
    op.drop_table("source_registries")
    op.drop_table("skill_scores")
    op.drop_table("skill_runs")
    op.drop_table("skill_prompts")
    op.drop_table("skill_packs")
    op.drop_constraint("fk_factory_briefs_config_profile", "factory_briefs", type_="foreignkey")
    op.drop_column("factory_briefs", "run_profile_slug")
    op.drop_column("factory_briefs", "runtime_config_snapshot_json")
    op.drop_column("factory_briefs", "config_profile_id")
    op.drop_table("trusted_projects")
    op.drop_table("config_plugins")
    op.drop_table("provider_profiles")
    op.drop_table("config_profiles")
