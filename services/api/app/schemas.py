from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    status: str
    service: str


class ActionResponse(BaseModel):
    status: str
    detail: str


class DoctorCheck(BaseModel):
    id: str
    label: str
    status: str
    detail: str
    required: bool = True
    guidance: str | None = None


class DoctorResponse(BaseModel):
    status: str
    generated_at: datetime
    checks: list[DoctorCheck]


class FactoryState(ApiModel):
    id: UUID
    mode: str = "running"
    auto_trend_enabled: bool = False
    active_project_limit: int = Field(default=1, ge=1, le=20)
    daily_budget_usd: Decimal = Decimal("5")
    monthly_budget_usd: Decimal = Decimal("100")
    updated_at: datetime


class FactoryStatePatch(BaseModel):
    mode: str | None = None
    auto_trend_enabled: bool | None = None
    active_project_limit: int | None = Field(default=None, ge=1, le=20)
    daily_budget_usd: Decimal | None = None
    monthly_budget_usd: Decimal | None = None


class AppSettings(ApiModel):
    id: UUID
    default_provider: str = "openai"
    default_model: str = "gpt-5.2"
    max_fix_iterations: int = Field(default=3, ge=0, le=20)
    workspace_root: str = "workspaces"
    auto_refresh_seconds: int = Field(default=5, ge=2, le=60)
    notifications_enabled: bool = True
    theme: str = "system"
    daily_budget_usd: Decimal = Decimal("5")
    monthly_budget_usd: Decimal = Decimal("100")
    default_platforms: list[str] = Field(default_factory=lambda: ["android"])
    default_backend: str = "none"
    default_monetization: str = "none"
    default_language: str = "en"
    default_target_country: str = "US"
    policy_strictness: str = "standard"
    feature_flags: dict[str, bool] = Field(default_factory=lambda: {
        "trend_radar": False,
        "provider_key_network_test": False,
        "minio_artifacts": False,
        "release_approval": False,
    })
    updated_at: datetime


class AppSettingsPatch(BaseModel):
    default_provider: str | None = None
    default_model: str | None = None
    max_fix_iterations: int | None = Field(default=None, ge=0, le=20)
    workspace_root: str | None = None
    auto_refresh_seconds: int | None = Field(default=None, ge=2, le=60)
    notifications_enabled: bool | None = None
    theme: str | None = None
    daily_budget_usd: Decimal | None = None
    monthly_budget_usd: Decimal | None = None
    default_platforms: list[str] | None = None
    default_backend: str | None = None
    default_monetization: str | None = None
    default_language: str | None = None
    default_target_country: str | None = None
    policy_strictness: str | None = None
    feature_flags: dict[str, bool] | None = None


class ApiKeyCreate(BaseModel):
    provider: str
    label: str
    key: str = Field(min_length=1)
    daily_budget_usd: Decimal = Decimal("5")
    monthly_budget_usd: Decimal = Decimal("100")
    assigned_worker_id: UUID | None = None


class ApiKeyPatch(BaseModel):
    label: str | None = None
    status: str | None = None
    daily_budget_usd: Decimal | None = None
    monthly_budget_usd: Decimal | None = None
    assigned_worker_id: UUID | None = None


class ApiKeyRead(ApiModel):
    id: UUID
    provider: str
    label: str
    key_hint: str
    status: str
    daily_budget_usd: Decimal
    monthly_budget_usd: Decimal
    total_estimated_spend_usd: Decimal
    assigned_worker_id: UUID | None
    created_at: datetime
    last_used_at: datetime | None


class ApiKeyTestResponse(BaseModel):
    status: str
    provider: str
    detail: str


class WorkerRegister(BaseModel):
    machine_name: str
    os: str
    arch: str
    has_docker: bool = False
    has_flutter: bool = False
    has_android_sdk: bool = False
    has_xcode: bool = False
    has_codex: bool = False
    has_aider: bool = False


class WorkerHeartbeat(BaseModel):
    status: str = "online"
    current_job_id: str | None = None


class WorkerRead(ApiModel):
    id: UUID
    machine_name: str
    os: str
    arch: str
    has_docker: bool
    has_flutter: bool
    has_android_sdk: bool
    has_xcode: bool
    has_codex: bool
    has_aider: bool
    status: str
    last_heartbeat_at: datetime | None
    current_job_id: str | None
    created_at: datetime


class IdeaCreate(BaseModel):
    title: str
    description: str
    source: str = "manual"
    opportunity_score: int = Field(default=50, ge=0, le=100)


class IdeaRead(ApiModel):
    id: UUID
    title: str
    description: str
    source: str
    opportunity_score: int
    status: str
    evidence_json: dict
    created_at: datetime
    updated_at: datetime


class ProjectCreate(BaseModel):
    idea_id: UUID | None = None
    name: str
    slug: str
    target_platforms: list[str] = Field(default_factory=lambda: ["android"])


class ProjectRead(ApiModel):
    id: UUID
    name: str
    slug: str
    idea_id: UUID | None
    status: str
    target_platforms: list[str]
    workspace_path: str | None
    created_at: datetime
    updated_at: datetime


class FactoryBriefCreate(BaseModel):
    mode: str = "manual_idea"
    title: str
    raw_prompt: str
    target_category: str | None = None
    target_platforms: list[str] = Field(default_factory=lambda: ["android"])
    target_country: str = "US"
    target_language: str = "en"
    monetization_mode: str = "none"
    iap_enabled: bool = False
    subscription_enabled: bool = False
    ads_enabled: bool = False
    backend_mode: str = "none"
    complexity: str = "medium"
    max_cost_usd: Decimal = Decimal("5")
    max_runtime_minutes: int = Field(default=60, ge=5, le=720)
    quality_threshold: int = Field(default=75, ge=0, le=100)
    policy_strictness: str = "standard"


class FactoryBriefStatusPatch(BaseModel):
    status: str


class FactoryBriefRunResponse(BaseModel):
    factory_brief_id: UUID
    status: str
    queue: str


class FactoryBriefRead(ApiModel):
    id: UUID
    mode: str
    title: str
    raw_prompt: str
    target_category: str | None
    target_platforms: list[str]
    target_country: str
    target_language: str
    monetization_mode: str
    iap_enabled: bool
    subscription_enabled: bool
    ads_enabled: bool
    backend_mode: str
    complexity: str
    max_cost_usd: Decimal
    max_runtime_minutes: int
    quality_threshold: int
    policy_strictness: str
    status: str
    selected_idea_id: UUID | None
    selected_project_id: UUID | None
    created_at: datetime
    updated_at: datetime


class ResearchFindingCreate(BaseModel):
    source: str
    title: str
    summary: str
    category: str | None = None
    keywords: list = Field(default_factory=list)
    pain_points: list = Field(default_factory=list)
    competitor_gaps: list = Field(default_factory=list)
    evidence_json: dict = Field(default_factory=dict)
    confidence_score: int = Field(default=50, ge=0, le=100)


class ResearchFindingRead(ApiModel):
    id: UUID
    factory_brief_id: UUID
    source: str
    title: str
    summary: str
    category: str | None
    keywords: list
    pain_points: list
    competitor_gaps: list
    evidence_json: dict
    confidence_score: int
    created_at: datetime


class OpportunityCandidateCreate(BaseModel):
    title: str
    description: str
    target_user: str
    problem: str
    unique_angle: str
    core_features: list = Field(default_factory=list)
    monetization_plan: str | None = None
    iap_plan_json: dict = Field(default_factory=dict)
    subscription_plan_json: dict = Field(default_factory=dict)
    backend_plan_json: dict = Field(default_factory=dict)
    opportunity_score: int = Field(default=50, ge=0, le=100)
    demand_score: int = Field(default=50, ge=0, le=100)
    pain_score: int = Field(default=50, ge=0, le=100)
    monetization_score: int = Field(default=50, ge=0, le=100)
    build_feasibility_score: int = Field(default=50, ge=0, le=100)
    differentiation_score: int = Field(default=50, ge=0, le=100)
    policy_risk_score: int = Field(default=20, ge=0, le=100)
    originality_score: int = Field(default=75, ge=0, le=100)
    status: str = "proposed"


class OpportunityCandidateRead(ApiModel):
    id: UUID
    factory_brief_id: UUID
    title: str
    description: str
    target_user: str
    problem: str
    unique_angle: str
    core_features: list
    monetization_plan: str | None
    iap_plan_json: dict
    subscription_plan_json: dict
    backend_plan_json: dict
    opportunity_score: int
    demand_score: int
    pain_score: int
    monetization_score: int
    build_feasibility_score: int
    differentiation_score: int
    policy_risk_score: int
    originality_score: int
    status: str
    created_at: datetime
    updated_at: datetime


class FactoryBriefDetail(FactoryBriefRead):
    findings: list[ResearchFindingRead] = Field(default_factory=list)
    candidates: list[OpportunityCandidateRead] = Field(default_factory=list)


class FactoryBriefFinalizeRequest(BaseModel):
    candidate_id: UUID
    queue_pipeline: bool = True


class ProjectTaskCreate(BaseModel):
    title: str
    description: str
    agent_name: str
    priority: int = 0
    input_json: dict = Field(default_factory=dict)


class ProjectTaskPatch(BaseModel):
    status: str | None = None
    output_json: dict | None = None
    error_message: str | None = None
    commit_sha: str | None = None


class ProjectTaskAgentPatch(ProjectTaskPatch):
    title: str | None = None
    description: str | None = None
    priority: int | None = None
    input_json: dict | None = None


class ProjectTaskRead(ApiModel):
    id: UUID
    project_id: UUID
    title: str
    description: str
    agent_name: str
    status: str
    priority: int
    input_json: dict
    output_json: dict
    error_message: str | None
    commit_sha: str | None
    created_at: datetime
    updated_at: datetime


class NotificationCreate(BaseModel):
    level: str = "info"
    title: str
    message: str
    entity_type: str | None = None
    entity_id: UUID | None = None


class NotificationRead(ApiModel):
    id: UUID
    level: str
    title: str
    message: str
    entity_type: str | None
    entity_id: UUID | None
    read_at: datetime | None
    created_at: datetime


class PipelineRunResponse(BaseModel):
    project_id: UUID
    status: str
    queue: str


class AgentRunCreate(BaseModel):
    agent_name: str
    status: str
    input_json: dict = Field(default_factory=dict)
    output_json: dict = Field(default_factory=dict)
    error_message: str | None = None
    iteration: int = 0


class AgentRunPatch(BaseModel):
    status: str | None = None
    output_json: dict | None = None
    error_message: str | None = None


class AgentRunRead(ApiModel):
    id: UUID
    project_id: UUID
    agent_name: str
    status: str
    input_json: dict
    output_json: dict
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    iteration: int


class AgentEventCreate(BaseModel):
    agent_run_id: UUID | None = None
    step: str
    level: str = "info"
    message: str
    stdout: str | None = None
    stderr: str | None = None
    metadata_json: dict = Field(default_factory=dict)


class AgentEventRead(ApiModel):
    id: UUID
    project_id: UUID
    agent_run_id: UUID | None
    step: str
    level: str
    message: str
    stdout: str | None
    stderr: str | None
    metadata_json: dict
    created_at: datetime


class QAResultCreate(BaseModel):
    status: str
    command: str
    exit_code: int
    stdout: str | None = None
    stderr: str | None = None


class QAResultRead(ApiModel):
    id: UUID
    project_id: UUID
    status: str
    command: str
    exit_code: int
    stdout: str | None
    stderr: str | None
    created_at: datetime


class PolicyResultCreate(BaseModel):
    risk: str
    passed: bool
    issues: list = Field(default_factory=list)
    required_changes: list = Field(default_factory=list)


class PolicyResultRead(ApiModel):
    id: UUID
    project_id: UUID
    risk: str
    passed: bool
    issues: list
    required_changes: list
    created_at: datetime


class ArtifactCreate(BaseModel):
    kind: str
    name: str
    path: str
    metadata_json: dict = Field(default_factory=dict)


class ArtifactRead(ApiModel):
    id: UUID
    project_id: UUID
    kind: str
    name: str
    path: str
    metadata_json: dict
    created_at: datetime


class BuildCreate(BaseModel):
    status: str
    platform: str = "android"
    artifact_path: str | None = None
    logs: str | None = None


class ProjectStatusPatch(BaseModel):
    status: str
    workspace_path: str | None = None
