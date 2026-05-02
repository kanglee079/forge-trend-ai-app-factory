from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    status: str
    service: str


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
