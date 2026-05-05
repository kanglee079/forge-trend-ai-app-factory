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
    worker_enable_codex: bool = True
    worker_mode_label: str = "Mode: Codex coding mode"
    research_enable_web: bool = False
    research_mode_label: str = "Research: deterministic fallback"


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
    default_language: str = "vi"
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


class ProviderProfileCreate(BaseModel):
    name: str = "OpenAI"
    provider_type: str = "openai_compatible"
    base_url: str = "https://api.openai.com/v1"
    wire_api: str = "responses"
    requires_openai_auth: bool = True
    api_key_id: UUID | None = None
    enabled: bool = True


class ProviderProfilePatch(BaseModel):
    name: str | None = None
    provider_type: str | None = None
    base_url: str | None = None
    wire_api: str | None = None
    requires_openai_auth: bool | None = None
    api_key_id: UUID | None = None
    enabled: bool | None = None


class ProviderProfileRead(ApiModel):
    id: UUID
    config_profile_id: UUID
    name: str
    provider_type: str
    base_url: str
    wire_api: str
    requires_openai_auth: bool
    api_key_id: UUID | None
    enabled: bool
    created_at: datetime
    updated_at: datetime


class ConfigPluginCreate(BaseModel):
    plugin_id: str
    name: str
    category: str = "plugin"
    enabled: bool = True
    source_type: str = "builtin"
    source: str = ""
    version: str = "1.0.0"


class ConfigPluginPatch(BaseModel):
    name: str | None = None
    category: str | None = None
    enabled: bool | None = None
    source_type: str | None = None
    source: str | None = None
    version: str | None = None


class ConfigPluginRead(ApiModel):
    id: UUID
    config_profile_id: UUID
    plugin_id: str
    name: str
    category: str
    enabled: bool
    source_type: str
    source: str
    version: str
    created_at: datetime
    updated_at: datetime


class TrustedProjectCreate(BaseModel):
    path: str
    trust_level: str = "trusted"


class TrustedProjectPatch(BaseModel):
    path: str | None = None
    trust_level: str | None = None


class TrustedProjectRead(ApiModel):
    id: UUID
    config_profile_id: UUID
    path: str
    trust_level: str
    created_at: datetime
    updated_at: datetime


class ConfigProfileCreate(BaseModel):
    name: str
    description: str = ""
    is_default: bool = False
    model_provider: str = "OpenAI"
    model: str = "gpt-5.5"
    review_model: str = "gpt-5.5"
    model_reasoning_effort: str = "medium"
    disable_response_storage: bool = False
    network_access: str = "disabled"
    model_context_window: int = Field(default=200000, ge=1000)
    model_auto_compact_token_limit: int = Field(default=160000, ge=1000)
    active_provider_profile_id: UUID | None = None


class ConfigProfilePatch(BaseModel):
    name: str | None = None
    description: str | None = None
    is_default: bool | None = None
    model_provider: str | None = None
    model: str | None = None
    review_model: str | None = None
    model_reasoning_effort: str | None = None
    disable_response_storage: bool | None = None
    network_access: str | None = None
    model_context_window: int | None = Field(default=None, ge=1000)
    model_auto_compact_token_limit: int | None = Field(default=None, ge=1000)
    active_provider_profile_id: UUID | None = None


class ConfigProfileRead(ApiModel):
    id: UUID
    name: str
    description: str
    is_default: bool
    model_provider: str
    model: str
    review_model: str
    model_reasoning_effort: str
    disable_response_storage: bool
    network_access: str
    model_context_window: int
    model_auto_compact_token_limit: int
    active_provider_profile_id: UUID | None
    created_at: datetime
    updated_at: datetime
    providers: list[ProviderProfileRead] = Field(default_factory=list)
    plugins: list[ConfigPluginRead] = Field(default_factory=list)
    trusted_projects: list[TrustedProjectRead] = Field(default_factory=list)


class ConfigProfileImportPayload(BaseModel):
    toml_text: str = Field(min_length=1)
    name: str | None = None
    set_default: bool = False


class ConfigProfileExportResponse(BaseModel):
    config_profile_id: UUID
    toml_text: str


class RuntimeConfigResponse(BaseModel):
    config_profile_id: UUID | None
    profile_name: str
    model_provider: str
    model: str
    review_model: str
    model_reasoning_effort: str
    disable_response_storage: bool
    network_access: str
    model_context_window: int
    model_auto_compact_token_limit: int
    provider: dict = Field(default_factory=dict)
    enabled_plugins: list[dict] = Field(default_factory=list)
    enabled_skills: list[dict] = Field(default_factory=list)
    trusted_projects: list[dict] = Field(default_factory=list)
    applied_learning_rules: list[dict] = Field(default_factory=list)
    secrets_redacted: bool = True


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
    worker_enable_codex: bool = True


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
    worker_enable_codex: bool = True
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
    config_profile_id: UUID | None = None
    run_profile_slug: str | None = None
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


class FactoryBriefEventCreate(BaseModel):
    level: str = "info"
    title: str
    message: str
    metadata_json: dict = Field(default_factory=dict)


class FactoryBriefRead(ApiModel):
    id: UUID
    config_profile_id: UUID | None
    runtime_config_snapshot_json: dict = Field(default_factory=dict)
    run_profile_slug: str | None
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
    metadata_json: dict = Field(default_factory=dict)
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


class RunEvaluationCreate(BaseModel):
    brief_id: UUID | None = None
    project_id: UUID | None = None
    category: str | None = None
    language: str | None = None
    monetization: str | None = None
    provider: str = "deterministic"
    archetype: str | None = None
    final_status: str
    qa_passed: bool = False
    quality_score: int = Field(default=0, ge=0, le=100)
    policy_passed: bool = False
    store_readiness_score: int = Field(default=0, ge=0, le=100)
    time_to_complete_seconds: int = 0
    fix_iterations: int = 0
    failure_reason: str | None = None
    human_review_reason: str | None = None
    metrics_json: dict = Field(default_factory=dict)


class RunEvaluationRead(ApiModel):
    id: UUID
    brief_id: UUID | None
    project_id: UUID | None
    category: str | None
    language: str | None
    monetization: str | None
    provider: str
    archetype: str | None
    final_status: str
    qa_passed: bool
    quality_score: int
    policy_passed: bool
    store_readiness_score: int
    time_to_complete_seconds: int
    fix_iterations: int
    failure_reason: str | None
    human_review_reason: str | None
    metrics_json: dict
    created_at: datetime


class FailurePatternRead(ApiModel):
    id: UUID
    taxonomy: str
    count: int
    last_project_id: UUID | None
    last_reason: str | None
    updated_at: datetime


class LearningRuleRead(ApiModel):
    id: UUID
    rule_key: str
    description: str
    enabled: bool
    confidence_score: int
    trigger_json: dict
    action_json: dict
    created_at: datetime
    updated_at: datetime


class LearningRulePatch(BaseModel):
    description: str | None = None
    enabled: bool | None = None
    confidence_score: int | None = Field(default=None, ge=0, le=100)
    trigger_json: dict | None = None
    action_json: dict | None = None


class LearningSummary(BaseModel):
    average_quality_score: float
    total_runs: int
    release_candidates: int
    needs_human_review: int
    common_failures: list[FailurePatternRead]
    active_rules: list[LearningRuleRead]
    provider_success: dict[str, dict[str, int]]
    archetype_scores: dict[str, float]


class SkillPromptRead(ApiModel):
    id: UUID
    skill_pack_id: UUID
    name: str
    purpose: str
    when_to_use: str
    prompt_template: str
    input_schema_json: dict
    output_schema_json: dict
    success_criteria_json: dict
    token_budget: int
    created_at: datetime
    updated_at: datetime


class SkillPackPatch(BaseModel):
    enabled: bool | None = None
    quality_score: int | None = Field(default=None, ge=0, le=100)
    token_budget: int | None = Field(default=None, ge=0)


class SkillPackRead(ApiModel):
    id: UUID
    name: str
    slug: str
    category: str
    description: str
    version: str
    enabled: bool
    source_type: str
    source_url: str | None
    local_path: str | None
    quality_score: int
    token_budget: int
    created_at: datetime
    updated_at: datetime
    prompts: list[SkillPromptRead] = Field(default_factory=list)
    score: dict = Field(default_factory=dict)


class SkillRunRead(ApiModel):
    id: UUID
    skill_pack_id: UUID
    project_id: UUID | None
    factory_brief_id: UUID | None
    agent_name: str
    input_hash: str
    output_summary: str
    tokens_estimated: int
    status: str
    created_at: datetime


class SkillTestPayload(BaseModel):
    sample_input: dict = Field(default_factory=dict)


class SkillTestResponse(BaseModel):
    skill_pack_id: UUID
    rendered_prompt: str
    estimated_tokens: int


class SourceScanCreate(BaseModel):
    source_type: str = "github_search"
    query: str
    limit: int = Field(default=5, ge=1, le=10)


class SourceScanRunRead(ApiModel):
    id: UUID
    source_type: str
    query: str
    status: str
    summary: str
    created_at: datetime
    finished_at: datetime | None


class SourceItemPatch(BaseModel):
    status: str | None = None
    usefulness_score: int | None = Field(default=None, ge=0, le=100)


class SourceItemRead(ApiModel):
    id: UUID
    scan_run_id: UUID | None
    title: str
    source_type: str
    source_url: str | None
    summary: str
    category: str | None
    usefulness_score: int
    status: str
    metadata_json: dict
    created_at: datetime
    updated_at: datetime


class ScanRunDetail(SourceScanRunRead):
    items: list[SourceItemRead] = Field(default_factory=list)


class RunProfileRead(ApiModel):
    id: UUID
    name: str
    slug: str
    description: str
    config_profile_id: UUID | None
    skill_slugs: list[str]
    token_budget: int
    quality_threshold: int
    max_iterations: int
    research_mode: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


class PromptContextSummary(BaseModel):
    prompt_fragments: list[dict] = Field(default_factory=list)
    context_packs: list[dict] = Field(default_factory=list)
    token_budget_decision: dict = Field(default_factory=dict)


class ContextPackCreate(BaseModel):
    project_id: UUID | None = None
    factory_brief_id: UUID | None = None
    pack_type: str
    full_text_hash: str = ""
    summary: str
    important_files: list[str] = Field(default_factory=list)
    token_estimate: int = 0


class ContextPackRead(ApiModel):
    id: UUID
    project_id: UUID | None
    factory_brief_id: UUID | None
    pack_type: str
    full_text_hash: str
    summary: str
    important_files: list
    token_estimate: int
    created_at: datetime
    updated_at: datetime


class ProviderCompletionRequest(BaseModel):
    config_profile_id: UUID | None = None
    runtime_config_snapshot: dict | None = None
    purpose: str = "agent_assist"
    prompt: str
    max_output_tokens: int = Field(default=1200, ge=16, le=8000)


class ProviderCompletionResponse(BaseModel):
    status: str
    provider: str
    model: str
    text: str
    detail: str
    tokens_estimated: int = 0


class ProviderStatus(BaseModel):
    id: str
    name: str
    enabled: bool
    available: bool
    auth_status: str
    current_model: str | None = None
    last_success: datetime | None = None
    last_failure: datetime | None = None
    recommended_action: str


class PluginStatus(BaseModel):
    id: str
    name: str
    type: str
    enabled: bool
    capabilities: list[str] = Field(default_factory=list)
    config_schema: dict = Field(default_factory=dict)
    missing_dependencies: list[str] = Field(default_factory=list)


class QueueSummary(BaseModel):
    factory_brief_queue: int
    project_pipeline_queue: int
    running_jobs: int
    retryable_jobs: int
    failed_jobs: int
    dead_letter_jobs: int
    next_action: str


class BuildCreate(BaseModel):
    status: str
    platform: str = "android"
    artifact_path: str | None = None
    logs: str | None = None


class ProjectStatusPatch(BaseModel):
    status: str
    workspace_path: str | None = None
