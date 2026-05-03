import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Worker(Base):
    __tablename__ = "workers"

    id: Mapped[uuid.UUID] = uuid_pk()
    machine_name: Mapped[str] = mapped_column(String(255))
    os: Mapped[str] = mapped_column(String(80))
    arch: Mapped[str] = mapped_column(String(80))
    has_docker: Mapped[bool] = mapped_column(Boolean, default=False)
    has_flutter: Mapped[bool] = mapped_column(Boolean, default=False)
    has_android_sdk: Mapped[bool] = mapped_column(Boolean, default=False)
    has_xcode: Mapped[bool] = mapped_column(Boolean, default=False)
    has_codex: Mapped[bool] = mapped_column(Boolean, default=False)
    has_aider: Mapped[bool] = mapped_column(Boolean, default=False)
    worker_enable_codex: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(80), default="online")
    last_heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    current_job_id: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ApiKey(Base):
    __tablename__ = "api_keys"
    __table_args__ = (UniqueConstraint("provider", "key_fingerprint", name="uq_api_keys_provider_fingerprint"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    provider: Mapped[str] = mapped_column(String(120))
    label: Mapped[str] = mapped_column(String(255))
    encrypted_key: Mapped[str] = mapped_column(Text)
    key_fingerprint: Mapped[str] = mapped_column(String(64))
    key_hint: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(80), default="active")
    daily_budget_usd: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("5"))
    monthly_budget_usd: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("100"))
    total_estimated_spend_usd: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    assigned_worker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workers.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class Idea(Base):
    __tablename__ = "ideas"

    id: Mapped[uuid.UUID] = uuid_pk()
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(120), default="manual")
    opportunity_score: Mapped[int] = mapped_column(Integer, default=50)
    status: Mapped[str] = mapped_column(String(80), default="new")
    evidence_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), unique=True)
    idea_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ideas.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(80), default="created")
    target_platforms: Mapped[list[str]] = mapped_column(JSONB, default=lambda: ["android"])
    workspace_path: Mapped[str] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    agent_name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(80))
    input_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    output_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    iteration: Mapped[int] = mapped_column(Integer, default=0)


class AgentEvent(Base):
    __tablename__ = "agent_events"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    agent_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=True)
    step: Mapped[str] = mapped_column(String(160))
    level: Mapped[str] = mapped_column(String(40), default="info")
    message: Mapped[str] = mapped_column(Text)
    stdout: Mapped[str] = mapped_column(Text, nullable=True)
    stderr: Mapped[str] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Build(Base):
    __tablename__ = "builds"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    status: Mapped[str] = mapped_column(String(80))
    platform: Mapped[str] = mapped_column(String(80), default="android")
    artifact_path: Mapped[str] = mapped_column(String(512), nullable=True)
    logs: Mapped[str] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class QAResult(Base):
    __tablename__ = "qa_results"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    status: Mapped[str] = mapped_column(String(80))
    command: Mapped[str] = mapped_column(String(255))
    exit_code: Mapped[int] = mapped_column(Integer)
    stdout: Mapped[str] = mapped_column(Text, nullable=True)
    stderr: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PolicyResult(Base):
    __tablename__ = "policy_results"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    risk: Mapped[str] = mapped_column(String(80))
    passed: Mapped[bool] = mapped_column(Boolean)
    issues: Mapped[list] = mapped_column(JSONB, default=list)
    required_changes: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    kind: Mapped[str] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(String(512))
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CostUsage(Base):
    __tablename__ = "cost_usage"

    id: Mapped[uuid.UUID] = uuid_pk()
    api_key_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("api_keys.id"), nullable=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String(120))
    estimated_cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0"))
    purpose: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FactoryState(Base):
    __tablename__ = "factory_state"

    id: Mapped[uuid.UUID] = uuid_pk()
    mode: Mapped[str] = mapped_column(String(40), default="running")
    auto_trend_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    active_project_limit: Mapped[int] = mapped_column(Integer, default=1)
    daily_budget_usd: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("5"))
    monthly_budget_usd: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("100"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[uuid.UUID] = uuid_pk()
    default_provider: Mapped[str] = mapped_column(String(120), default="openai")
    default_model: Mapped[str] = mapped_column(String(160), default="gpt-5.2")
    max_fix_iterations: Mapped[int] = mapped_column(Integer, default=3)
    workspace_root: Mapped[str] = mapped_column(String(512), default="workspaces")
    auto_refresh_seconds: Mapped[int] = mapped_column(Integer, default=5)
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    theme: Mapped[str] = mapped_column(String(40), default="system")
    daily_budget_usd: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("5"))
    monthly_budget_usd: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("100"))
    default_platforms: Mapped[list[str]] = mapped_column(JSONB, default=lambda: ["android"])
    default_backend: Mapped[str] = mapped_column(String(80), default="none")
    default_monetization: Mapped[str] = mapped_column(String(80), default="none")
    default_language: Mapped[str] = mapped_column(String(80), default="en")
    default_target_country: Mapped[str] = mapped_column(String(80), default="US")
    policy_strictness: Mapped[str] = mapped_column(String(80), default="standard")
    feature_flags: Mapped[dict] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class FactoryBrief(Base):
    __tablename__ = "factory_briefs"

    id: Mapped[uuid.UUID] = uuid_pk()
    mode: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(255))
    raw_prompt: Mapped[str] = mapped_column(Text)
    target_category: Mapped[str] = mapped_column(String(120), nullable=True)
    target_platforms: Mapped[list[str]] = mapped_column(JSONB, default=lambda: ["android"])
    target_country: Mapped[str] = mapped_column(String(80), default="US")
    target_language: Mapped[str] = mapped_column(String(80), default="en")
    monetization_mode: Mapped[str] = mapped_column(String(80), default="none")
    iap_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    subscription_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    ads_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    backend_mode: Mapped[str] = mapped_column(String(80), default="none")
    complexity: Mapped[str] = mapped_column(String(80), default="medium")
    max_cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("5"))
    max_runtime_minutes: Mapped[int] = mapped_column(Integer, default=60)
    quality_threshold: Mapped[int] = mapped_column(Integer, default=75)
    policy_strictness: Mapped[str] = mapped_column(String(80), default="standard")
    status: Mapped[str] = mapped_column(String(80), default="draft")
    selected_idea_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ideas.id"), nullable=True)
    selected_project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TrendSource(Base):
    __tablename__ = "trend_sources"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(80), default="manual")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    rate_limit_per_hour: Mapped[int] = mapped_column(Integer, default=10)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ResearchFinding(Base):
    __tablename__ = "research_findings"

    id: Mapped[uuid.UUID] = uuid_pk()
    factory_brief_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("factory_briefs.id"))
    source: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(120), nullable=True)
    keywords: Mapped[list] = mapped_column(JSONB, default=list)
    pain_points: Mapped[list] = mapped_column(JSONB, default=list)
    competitor_gaps: Mapped[list] = mapped_column(JSONB, default=list)
    evidence_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    confidence_score: Mapped[int] = mapped_column(Integer, default=50)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OpportunityCandidate(Base):
    __tablename__ = "opportunity_candidates"

    id: Mapped[uuid.UUID] = uuid_pk()
    factory_brief_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("factory_briefs.id"))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    target_user: Mapped[str] = mapped_column(Text)
    problem: Mapped[str] = mapped_column(Text)
    unique_angle: Mapped[str] = mapped_column(Text)
    core_features: Mapped[list] = mapped_column(JSONB, default=list)
    monetization_plan: Mapped[str] = mapped_column(Text, nullable=True)
    iap_plan_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    subscription_plan_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    backend_plan_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    opportunity_score: Mapped[int] = mapped_column(Integer, default=50)
    demand_score: Mapped[int] = mapped_column(Integer, default=50)
    pain_score: Mapped[int] = mapped_column(Integer, default=50)
    monetization_score: Mapped[int] = mapped_column(Integer, default=50)
    build_feasibility_score: Mapped[int] = mapped_column(Integer, default=50)
    differentiation_score: Mapped[int] = mapped_column(Integer, default=50)
    policy_risk_score: Mapped[int] = mapped_column(Integer, default=20)
    originality_score: Mapped[int] = mapped_column(Integer, default=75)
    status: Mapped[str] = mapped_column(String(80), default="proposed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ProjectTask(Base):
    __tablename__ = "project_tasks"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    agent_name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(80), default="pending")
    priority: Mapped[int] = mapped_column(Integer, default=0)
    input_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    output_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    commit_sha: Mapped[str] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = uuid_pk()
    level: Mapped[str] = mapped_column(String(40), default="info")
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    entity_type: Mapped[str] = mapped_column(String(120), nullable=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
