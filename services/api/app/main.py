import shutil
import socket
import subprocess
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import (
    AgentEvent,
    AgentRun,
    AppSettings,
    ApiKey,
    Artifact,
    Build,
    CostUsage,
    FactoryBrief,
    FactoryState,
    Idea,
    Notification,
    OpportunityCandidate,
    PolicyResult,
    Project,
    ProjectTask,
    QAResult,
    ResearchFinding,
    TrendSource,
    Worker,
)
from app.queue import enqueue_factory_brief, enqueue_pipeline
from app.schemas import (
    ActionResponse,
    AgentEventCreate,
    AgentEventRead,
    AgentRunCreate,
    AgentRunPatch,
    AgentRunRead,
    ApiKeyCreate,
    ApiKeyPatch,
    ApiKeyRead,
    ApiKeyTestResponse,
    AppSettingsPatch,
    AppSettings as AppSettingsSchema,
    ArtifactCreate,
    ArtifactRead,
    BuildCreate,
    DoctorCheck,
    DoctorResponse,
    FactoryBriefFinalizeRequest,
    FactoryBriefCreate,
    FactoryBriefDetail,
    FactoryBriefRead,
    FactoryBriefRunResponse,
    FactoryBriefStatusPatch,
    FactoryStatePatch,
    FactoryState as FactoryStateSchema,
    HealthResponse,
    IdeaCreate,
    IdeaRead,
    NotificationCreate,
    NotificationRead,
    OpportunityCandidateCreate,
    OpportunityCandidateRead,
    PipelineRunResponse,
    PolicyResultCreate,
    PolicyResultRead,
    ProjectCreate,
    ProjectRead,
    ProjectStatusPatch,
    ProjectTaskAgentPatch,
    ProjectTaskCreate,
    ProjectTaskPatch,
    ProjectTaskRead,
    QAResultCreate,
    QAResultRead,
    ResearchFindingCreate,
    ResearchFindingRead,
    WorkerHeartbeat,
    WorkerRead,
    WorkerRegister,
)
from app.security import decrypt_secret, encrypt_secret, key_hint, redact, secret_fingerprint

app = FastAPI(title="ForgeTrend AI App Factory API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_or_404(db: Session, model, item_id: UUID):
    item = db.get(model, item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return item


def normalize_provider(provider: str) -> str:
    return provider.strip().lower()


def ping_host(host: str, port: int, timeout: float = 0.8) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, f"reachable on {host}:{port}"
    except OSError as exc:
        return False, str(exc)


def run_check(command: list[str], timeout: int = 8) -> tuple[bool, str]:
    if not shutil.which(command[0]):
        return False, "not found"
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except Exception as exc:
        return False, str(exc)
    output = (result.stdout or result.stderr).strip().splitlines()
    return result.returncode == 0, output[0] if output else f"exit {result.returncode}"


def doctor_check(id: str, label: str, ok: bool, detail: str, *, required: bool = True, guidance: str | None = None) -> DoctorCheck:
    return DoctorCheck(id=id, label=label, status="passed" if ok else "failed", detail=detail, required=required, guidance=guidance)


def build_doctor_report(db: Session) -> DoctorResponse:
    checks: list[DoctorCheck] = []
    tool_checks = [
        ("git", "Git", ["git", "--version"], True, "Install Git and make sure it is available on PATH."),
        ("node", "Node.js", ["node", "--version"], True, "Install Node.js 20+."),
        ("pnpm", "pnpm", ["pnpm", "--version"], True, "Install pnpm with corepack enable, then corepack prepare pnpm@latest --activate."),
        ("python", "Python", ["python3", "--version"], True, "Install Python 3.11+ and rerun setup."),
        ("docker", "Docker", ["docker", "--version"], True, "Install Docker Desktop and start it."),
        ("docker_compose", "Docker Compose", ["docker", "compose", "version"], True, "Install/update Docker Desktop so docker compose is available."),
        ("flutter", "Flutter", ["flutter", "--version"], False, "Install Flutter and run flutter doctor."),
        ("codex", "Codex CLI", ["codex", "--version"], False, "Install Codex CLI and run codex login."),
        ("aider", "Aider", ["aider", "--version"], False, "Optional: install aider if you plan to use an aider adapter."),
    ]
    for id, label, command, required, guidance in tool_checks:
        ok, detail = run_check(command)
        checks.append(doctor_check(id, label, ok, detail, required=required, guidance=None if ok else guidance))

    redis_ok, redis_detail = ping_host("127.0.0.1", 6379)
    checks.append(doctor_check("redis", "Redis", redis_ok, redis_detail, guidance="Run docker compose up -d redis."))
    postgres_ok, postgres_detail = ping_host("127.0.0.1", 5432)
    checks.append(doctor_check("postgres", "Postgres", postgres_ok, postgres_detail, guidance="Run docker compose up -d postgres."))
    minio_ok, minio_detail = ping_host("127.0.0.1", 9000)
    checks.append(doctor_check("minio", "MinIO", minio_ok, minio_detail, required=False, guidance="Run docker compose up -d minio."))
    checks.append(doctor_check("api", "API", True, "FastAPI responded to /doctor."))

    workers = list(db.scalars(select(Worker)).all())
    online_workers = [worker for worker in workers if worker.status == "online"]
    ready_workers = [worker for worker in online_workers if worker.has_flutter and worker.has_codex]
    checks.append(
        doctor_check(
            "worker_heartbeat",
            "Worker heartbeat",
            bool(online_workers),
            f"{len(online_workers)} online / {len(workers)} registered",
            guidance="Run codex login, then pnpm dev:worker.",
        )
    )
    checks.append(
        doctor_check(
            "worker_pipeline_ready",
            "Worker pipeline ready",
            bool(ready_workers),
            f"{len(ready_workers)} worker(s) report Flutter and Codex",
            guidance="Install Flutter and Codex CLI on the worker machine, then restart pnpm dev:worker.",
        )
    )

    required_failed = any(check.required and check.status != "passed" for check in checks)
    warning_failed = any(check.status != "passed" for check in checks)
    status = "failed" if required_failed else "warning" if warning_failed else "passed"
    return DoctorResponse(status=status, generated_at=datetime.now(UTC), checks=checks)


def get_or_create_factory_state(db: Session) -> FactoryState:
    item = db.scalar(select(FactoryState).order_by(FactoryState.updated_at))
    if item:
        return item
    item = FactoryState()
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def get_or_create_app_settings(db: Session) -> AppSettings:
    item = db.scalar(select(AppSettings).order_by(AppSettings.updated_at))
    if item:
        return item
    item = AppSettings(
        feature_flags={
            "trend_radar": False,
            "provider_key_network_test": False,
            "minio_artifacts": False,
            "release_approval": False,
        }
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def create_notification(
    db: Session,
    *,
    level: str,
    title: str,
    message: str,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
) -> Notification:
    notification = Notification(level=level, title=title, message=redact(message) or "", entity_type=entity_type, entity_id=entity_id)
    db.add(notification)
    return notification


def slugify(value: str) -> str:
    chars: list[str] = []
    previous_dash = False
    for char in value.strip().lower():
        if char.isalnum():
            chars.append(char)
            previous_dash = False
        elif not previous_dash:
            chars.append("-")
            previous_dash = True
    slug = "".join(chars).strip("-")
    return slug or "factory-app"


def unique_project_slug(db: Session, base: str) -> str:
    slug = slugify(base)
    candidate = slug
    suffix = 2
    while db.scalar(select(Project).where(Project.slug == candidate)):
        candidate = f"{slug}-{suffix}"
        suffix += 1
    return candidate


def build_brief_detail(db: Session, brief: FactoryBrief) -> FactoryBriefDetail:
    findings = list(db.scalars(select(ResearchFinding).where(ResearchFinding.factory_brief_id == brief.id).order_by(desc(ResearchFinding.created_at))).all())
    candidates = list(
        db.scalars(
            select(OpportunityCandidate)
            .where(OpportunityCandidate.factory_brief_id == brief.id)
            .order_by(desc(OpportunityCandidate.opportunity_score), desc(OpportunityCandidate.created_at))
        ).all()
    )
    return FactoryBriefDetail.model_validate(brief).model_copy(
        update={
            "findings": [ResearchFindingRead.model_validate(item) for item in findings],
            "candidates": [OpportunityCandidateRead.model_validate(item) for item in candidates],
        }
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="forge-trend-api")


@app.get("/doctor", response_model=DoctorResponse)
def doctor(db: Session = Depends(get_db)) -> DoctorResponse:
    return build_doctor_report(db)


@app.get("/settings", response_model=AppSettingsSchema)
def read_settings(db: Session = Depends(get_db)) -> AppSettings:
    return get_or_create_app_settings(db)


@app.patch("/settings", response_model=AppSettingsSchema)
def update_settings(payload: AppSettingsPatch, db: Session = Depends(get_db)) -> AppSettings:
    item = get_or_create_app_settings(db)
    patch = payload.model_dump(exclude_unset=True)
    if "feature_flags" in patch:
        feature_flags = dict(item.feature_flags or {})
        feature_flags.update(patch.pop("feature_flags") or {})
        item.feature_flags = feature_flags
    for field, value in patch.items():
        if value is not None:
            setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@app.get("/factory-state", response_model=FactoryStateSchema)
@app.get("/factory/state", response_model=FactoryStateSchema)
def read_factory_state(db: Session = Depends(get_db)) -> FactoryState:
    return get_or_create_factory_state(db)


@app.patch("/factory-state", response_model=FactoryStateSchema)
@app.patch("/factory/state", response_model=FactoryStateSchema)
def update_factory_state(payload: FactoryStatePatch, db: Session = Depends(get_db)) -> FactoryState:
    item = get_or_create_factory_state(db)
    patch = payload.model_dump(exclude_unset=True)
    if "mode" in patch and patch["mode"] is not None:
        mode = patch["mode"].strip().lower()
        if mode not in {"running", "paused", "stopped"}:
            raise HTTPException(status_code=422, detail="Factory mode must be running, paused, or stopped")
        item.mode = mode
    for field in ["auto_trend_enabled", "active_project_limit", "daily_budget_usd", "monthly_budget_usd"]:
        if field in patch and patch[field] is not None:
            setattr(item, field, patch[field])
    create_notification(db, level="info", title="Factory state updated", message=f"Factory mode is {item.mode}", entity_type="factory_state", entity_id=item.id)
    db.commit()
    db.refresh(item)
    return item


@app.post("/factory-briefs", response_model=FactoryBriefRead)
def create_factory_brief(payload: FactoryBriefCreate, db: Session = Depends(get_db)) -> FactoryBrief:
    item = FactoryBrief(**payload.model_dump(), status="draft")
    db.add(item)
    db.flush()
    create_notification(
        db,
        level="info",
        title="Factory brief created",
        message=f"{item.title} is ready to start.",
        entity_type="factory_brief",
        entity_id=item.id,
    )
    db.commit()
    db.refresh(item)
    return item


@app.get("/factory-briefs", response_model=list[FactoryBriefRead])
def list_factory_briefs(db: Session = Depends(get_db)) -> list[FactoryBrief]:
    return list(db.scalars(select(FactoryBrief).order_by(desc(FactoryBrief.created_at))).all())


@app.get("/factory-briefs/{id}", response_model=FactoryBriefDetail)
def get_factory_brief(id: UUID, db: Session = Depends(get_db)) -> FactoryBriefDetail:
    brief = get_or_404(db, FactoryBrief, id)
    return build_brief_detail(db, brief)


@app.post("/factory-briefs/{id}/start", response_model=FactoryBriefRunResponse)
def start_factory_brief(id: UUID, db: Session = Depends(get_db)) -> FactoryBriefRunResponse:
    factory = get_or_create_factory_state(db)
    if factory.mode != "running":
        raise HTTPException(status_code=409, detail=f"Factory is {factory.mode}. Start it before queueing factory briefs.")
    brief = get_or_404(db, FactoryBrief, id)
    brief.status = "queued"
    queue = enqueue_factory_brief(brief.id)
    create_notification(
        db,
        level="info",
        title="Factory brief queued",
        message=f"{brief.title} was queued for autonomous research and project creation.",
        entity_type="factory_brief",
        entity_id=brief.id,
    )
    db.commit()
    return FactoryBriefRunResponse(factory_brief_id=brief.id, status=brief.status, queue=queue)


@app.patch("/internal/factory-briefs/{id}/status", response_model=FactoryBriefRead)
def patch_factory_brief_status(id: UUID, payload: FactoryBriefStatusPatch, db: Session = Depends(get_db)) -> FactoryBrief:
    brief = get_or_404(db, FactoryBrief, id)
    brief.status = payload.status
    db.commit()
    db.refresh(brief)
    return brief


@app.post("/internal/factory-briefs/{id}/findings", response_model=ResearchFindingRead)
def create_research_finding(id: UUID, payload: ResearchFindingCreate, db: Session = Depends(get_db)) -> ResearchFinding:
    get_or_404(db, FactoryBrief, id)
    finding = ResearchFinding(factory_brief_id=id, **payload.model_dump())
    db.add(finding)
    db.commit()
    db.refresh(finding)
    return finding


@app.get("/factory-briefs/{id}/findings", response_model=list[ResearchFindingRead])
def list_research_findings(id: UUID, db: Session = Depends(get_db)) -> list[ResearchFinding]:
    get_or_404(db, FactoryBrief, id)
    return list(db.scalars(select(ResearchFinding).where(ResearchFinding.factory_brief_id == id).order_by(desc(ResearchFinding.created_at))).all())


@app.post("/internal/factory-briefs/{id}/candidates", response_model=OpportunityCandidateRead)
def create_opportunity_candidate(id: UUID, payload: OpportunityCandidateCreate, db: Session = Depends(get_db)) -> OpportunityCandidate:
    get_or_404(db, FactoryBrief, id)
    candidate = OpportunityCandidate(factory_brief_id=id, **payload.model_dump())
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


@app.post("/internal/factory-briefs/{id}/finalize", response_model=PipelineRunResponse)
def finalize_factory_brief_internal(id: UUID, payload: FactoryBriefFinalizeRequest, db: Session = Depends(get_db)) -> PipelineRunResponse:
    return finalize_factory_brief(id, payload, db)


@app.get("/factory-briefs/{id}/candidates", response_model=list[OpportunityCandidateRead])
def list_opportunity_candidates(id: UUID, db: Session = Depends(get_db)) -> list[OpportunityCandidate]:
    get_or_404(db, FactoryBrief, id)
    return list(
        db.scalars(
            select(OpportunityCandidate)
            .where(OpportunityCandidate.factory_brief_id == id)
            .order_by(desc(OpportunityCandidate.opportunity_score), desc(OpportunityCandidate.created_at))
        ).all()
    )


@app.post("/factory-briefs/{id}/finalize", response_model=PipelineRunResponse)
def finalize_factory_brief(id: UUID, payload: FactoryBriefFinalizeRequest, db: Session = Depends(get_db)) -> PipelineRunResponse:
    factory = get_or_create_factory_state(db)
    if payload.queue_pipeline and factory.mode != "running":
        raise HTTPException(status_code=409, detail=f"Factory is {factory.mode}. Start it before queueing pipeline runs.")
    brief = get_or_404(db, FactoryBrief, id)
    candidate = get_or_404(db, OpportunityCandidate, payload.candidate_id)
    if candidate.factory_brief_id != brief.id:
        raise HTTPException(status_code=422, detail="Candidate does not belong to this factory brief")
    if brief.selected_project_id:
        project = get_or_404(db, Project, brief.selected_project_id)
        queue = "already_created"
        if payload.queue_pipeline:
            project.status = "queued"
            queue = enqueue_pipeline(project.id)
            db.add(AgentEvent(project_id=project.id, step="factory_brief", level="info", message="Existing factory project queued again"))
        db.commit()
        return PipelineRunResponse(project_id=project.id, status=project.status, queue=queue)

    idea = Idea(
        title=candidate.title,
        description=f"{candidate.description}\n\nTarget user: {candidate.target_user}\nProblem: {candidate.problem}\nUnique angle: {candidate.unique_angle}",
        source="factory",
        opportunity_score=candidate.opportunity_score,
        status="selected",
        evidence_json={
            "factory_brief_id": str(brief.id),
            "candidate_id": str(candidate.id),
            "core_features": candidate.core_features,
            "scores": {
                "demand": candidate.demand_score,
                "pain": candidate.pain_score,
                "monetization": candidate.monetization_score,
                "feasibility": candidate.build_feasibility_score,
                "differentiation": candidate.differentiation_score,
                "policy_risk": candidate.policy_risk_score,
                "originality": candidate.originality_score,
            },
        },
    )
    db.add(idea)
    db.flush()

    project = Project(
        idea_id=idea.id,
        name=candidate.title,
        slug=unique_project_slug(db, candidate.title),
        target_platforms=brief.target_platforms,
        status="queued" if payload.queue_pipeline else "created",
    )
    db.add(project)
    db.flush()

    task_specs = [
        (
            "Translate selected opportunity into PRD",
            "Use the selected candidate, research findings, monetization constraints, and policy strictness to produce the project PRD.",
            "prd_agent",
        ),
        (
            "Design mobile product flow",
            "Create the screen flow, visual direction, onboarding, home, settings, empty states, and error states for the target user.",
            "ux_agent",
        ),
        (
            "Implement Flutter MVP",
            "Customize the Flutter app from the PRD and design docs, then record source artifacts.",
            "code_agent",
        ),
        (
            "Run QA and repair loop",
            "Run Flutter dependency, analyze, test, and debug build checks, then trigger code fixes if needed.",
            "qa_agent",
        ),
        (
            "Run release policy gate",
            "Check naming, privacy, permissions, secrets, and release readiness before creating a release candidate.",
            "policy_agent",
        ),
    ]
    for priority, (title, description, agent_name) in enumerate(task_specs, start=10):
        db.add(
            ProjectTask(
                project_id=project.id,
                title=title,
                description=description,
                agent_name=agent_name,
                priority=priority,
                input_json={"factory_brief_id": str(brief.id), "candidate_id": str(candidate.id)},
            )
        )

    candidate.status = "selected"
    brief.status = "project_queued" if payload.queue_pipeline else "project_created"
    brief.selected_idea_id = idea.id
    brief.selected_project_id = project.id
    create_notification(
        db,
        level="success",
        title="Factory project created",
        message=f"{project.name} was created from {brief.title}.",
        entity_type="project",
        entity_id=project.id,
    )
    queue = "not_queued"
    if payload.queue_pipeline:
        queue = enqueue_pipeline(project.id)
        db.add(AgentEvent(project_id=project.id, step="factory_brief", level="info", message="Project created from factory brief and pipeline queued"))
    db.commit()
    return PipelineRunResponse(project_id=project.id, status=project.status, queue=queue)


@app.post("/api-keys", response_model=ApiKeyRead)
def create_api_key(payload: ApiKeyCreate, db: Session = Depends(get_db)) -> ApiKey:
    provider = normalize_provider(payload.provider)
    raw_key = payload.key.strip()
    fingerprint = secret_fingerprint(raw_key)
    existing = db.scalar(
        select(ApiKey).where(
            ApiKey.provider == provider,
            ApiKey.key_fingerprint == fingerprint,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="This provider key is already saved")

    api_key = ApiKey(
        provider=provider,
        label=payload.label.strip(),
        encrypted_key=encrypt_secret(raw_key),
        key_fingerprint=fingerprint,
        key_hint=key_hint(raw_key),
        daily_budget_usd=payload.daily_budget_usd,
        monthly_budget_usd=payload.monthly_budget_usd,
        assigned_worker_id=payload.assigned_worker_id,
    )
    db.add(api_key)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="This provider key is already saved") from exc
    db.refresh(api_key)
    return api_key


@app.get("/api-keys", response_model=list[ApiKeyRead])
def list_api_keys(db: Session = Depends(get_db)) -> list[ApiKey]:
    return list(db.scalars(select(ApiKey).order_by(desc(ApiKey.created_at))).all())


@app.patch("/api-keys/{id}", response_model=ApiKeyRead)
def patch_api_key(id: UUID, payload: ApiKeyPatch, db: Session = Depends(get_db)) -> ApiKey:
    api_key = get_or_404(db, ApiKey, id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(api_key, field, value)
    db.commit()
    db.refresh(api_key)
    return api_key


@app.delete("/api-keys/{id}", response_model=ActionResponse)
def delete_api_key(id: UUID, db: Session = Depends(get_db)) -> ActionResponse:
    api_key = get_or_404(db, ApiKey, id)
    db.query(CostUsage).filter(CostUsage.api_key_id == id).update({CostUsage.api_key_id: None}, synchronize_session=False)
    db.delete(api_key)
    db.commit()
    return ActionResponse(status="deleted", detail="API key deleted")


@app.post("/api-keys/{id}/test", response_model=ApiKeyTestResponse)
def test_api_key(id: UUID, db: Session = Depends(get_db)) -> ApiKeyTestResponse:
    api_key = get_or_404(db, ApiKey, id)
    if api_key.status != "active":
        raise HTTPException(status_code=409, detail="Only active keys can be tested")
    raw_key = decrypt_secret(api_key.encrypted_key)
    if len(raw_key.strip()) < 8:
        raise HTTPException(status_code=422, detail="Saved key is too short to use")
    api_key.last_used_at = datetime.now(UTC)
    db.commit()
    return ApiKeyTestResponse(
        status="passed",
        provider=api_key.provider,
        detail="Key decrypted and passed local validation. Provider network validation is not enabled yet.",
    )


@app.post("/workers/register", response_model=WorkerRead)
def register_worker(payload: WorkerRegister, db: Session = Depends(get_db)) -> Worker:
    existing = db.scalar(
        select(Worker).where(Worker.machine_name == payload.machine_name, Worker.os == payload.os, Worker.arch == payload.arch)
    )
    if existing:
        worker = existing
        for field, value in payload.model_dump().items():
            setattr(worker, field, value)
    else:
        worker = Worker(**payload.model_dump())
        db.add(worker)
    worker.status = "online"
    worker.last_heartbeat_at = datetime.now(UTC)
    db.commit()
    db.refresh(worker)
    return worker


@app.post("/workers/{id}/heartbeat", response_model=WorkerRead)
def worker_heartbeat(id: UUID, payload: WorkerHeartbeat, db: Session = Depends(get_db)) -> Worker:
    worker = get_or_404(db, Worker, id)
    worker.status = payload.status
    worker.current_job_id = payload.current_job_id
    worker.last_heartbeat_at = datetime.now(UTC)
    db.commit()
    db.refresh(worker)
    return worker


@app.get("/workers", response_model=list[WorkerRead])
def list_workers(db: Session = Depends(get_db)) -> list[Worker]:
    workers = list(db.scalars(select(Worker).order_by(desc(Worker.last_heartbeat_at))).all())
    stale_before = datetime.now(UTC) - timedelta(seconds=settings.worker_stale_seconds)
    changed = False
    for worker in workers:
        heartbeat = worker.last_heartbeat_at
        if heartbeat and heartbeat.tzinfo is None:
            heartbeat = heartbeat.replace(tzinfo=UTC)
        if worker.status != "offline" and (heartbeat is None or heartbeat < stale_before):
            worker.status = "offline"
            worker.current_job_id = None
            changed = True
    if changed:
        db.commit()
    return workers


@app.post("/ideas", response_model=IdeaRead)
def create_idea(payload: IdeaCreate, db: Session = Depends(get_db)) -> Idea:
    idea = Idea(**payload.model_dump(), evidence_json={"origin": payload.source})
    db.add(idea)
    db.commit()
    db.refresh(idea)
    return idea


@app.get("/ideas", response_model=list[IdeaRead])
def list_ideas(db: Session = Depends(get_db)) -> list[Idea]:
    return list(db.scalars(select(Idea).order_by(desc(Idea.created_at))).all())


@app.post("/projects", response_model=ProjectRead)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> Project:
    if payload.idea_id:
        get_or_404(db, Idea, payload.idea_id)
    project = Project(**payload.model_dump())
    db.add(project)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Project slug already exists") from exc
    db.refresh(project)
    return project


@app.get("/projects", response_model=list[ProjectRead])
def list_projects(db: Session = Depends(get_db)) -> list[Project]:
    return list(db.scalars(select(Project).order_by(desc(Project.created_at))).all())


@app.get("/projects/{id}", response_model=ProjectRead)
def get_project(id: UUID, db: Session = Depends(get_db)) -> Project:
    return get_or_404(db, Project, id)


@app.delete("/projects/{id}", response_model=ActionResponse)
def delete_project(id: UUID, db: Session = Depends(get_db)) -> ActionResponse:
    project = get_or_404(db, Project, id)
    db.query(FactoryBrief).filter(FactoryBrief.selected_project_id == id).update({FactoryBrief.selected_project_id: None}, synchronize_session=False)
    db.query(CostUsage).filter(CostUsage.project_id == id).delete(synchronize_session=False)
    for model in [ProjectTask, Artifact, Build, PolicyResult, QAResult, AgentEvent, AgentRun]:
        db.query(model).filter(model.project_id == id).delete(synchronize_session=False)
    db.delete(project)
    db.commit()
    return ActionResponse(status="deleted", detail="Project and related run records deleted")


@app.post("/projects/{id}/run-pipeline", response_model=PipelineRunResponse)
def run_pipeline(id: UUID, db: Session = Depends(get_db)) -> PipelineRunResponse:
    factory = get_or_create_factory_state(db)
    if factory.mode != "running":
        raise HTTPException(status_code=409, detail=f"Factory is {factory.mode}. Start it before queueing pipeline runs.")
    project = get_or_404(db, Project, id)
    project.status = "queued"
    queue = enqueue_pipeline(project.id)
    event = AgentEvent(project_id=project.id, step="pipeline", level="info", message="Pipeline queued")
    db.add(event)
    create_notification(db, level="info", title="Pipeline queued", message=f"{project.name} was queued.", entity_type="project", entity_id=project.id)
    db.commit()
    return PipelineRunResponse(project_id=project.id, status=project.status, queue=queue)


@app.post("/projects/{id}/retry", response_model=PipelineRunResponse)
def retry_pipeline(id: UUID, db: Session = Depends(get_db)) -> PipelineRunResponse:
    factory = get_or_create_factory_state(db)
    if factory.mode != "running":
        raise HTTPException(status_code=409, detail=f"Factory is {factory.mode}. Start it before queueing pipeline runs.")
    project = get_or_404(db, Project, id)
    project.status = "queued"
    queue = enqueue_pipeline(project.id)
    event = AgentEvent(project_id=project.id, step="pipeline", level="info", message="Retry requested and pipeline queued")
    db.add(event)
    create_notification(db, level="info", title="Retry queued", message=f"{project.name} was queued again.", entity_type="project", entity_id=project.id)
    db.commit()
    return PipelineRunResponse(project_id=project.id, status=project.status, queue=queue)


@app.post("/projects/{id}/stop", response_model=ActionResponse)
def stop_pipeline(id: UUID, db: Session = Depends(get_db)) -> ActionResponse:
    project = get_or_404(db, Project, id)
    project.status = "stop_requested"
    event = AgentEvent(
        project_id=project.id,
        step="pipeline",
        level="warning",
        message="Stop requested. Current worker pass may finish before the daemon observes cancellation.",
    )
    db.add(event)
    db.commit()
    return ActionResponse(status="stop_requested", detail="Stop requested for this project")


@app.get("/projects/{id}/tasks", response_model=list[ProjectTaskRead])
def list_project_tasks(id: UUID, db: Session = Depends(get_db)) -> list[ProjectTask]:
    get_or_404(db, Project, id)
    return list(db.scalars(select(ProjectTask).where(ProjectTask.project_id == id).order_by(ProjectTask.priority, ProjectTask.created_at)).all())


@app.post("/projects/{id}/tasks", response_model=ProjectTaskRead)
def create_project_task(id: UUID, payload: ProjectTaskCreate, db: Session = Depends(get_db)) -> ProjectTask:
    get_or_404(db, Project, id)
    task = ProjectTask(project_id=id, **payload.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@app.patch("/projects/{project_id}/tasks/{task_id}", response_model=ProjectTaskRead)
def patch_project_task(project_id: UUID, task_id: UUID, payload: ProjectTaskPatch, db: Session = Depends(get_db)) -> ProjectTask:
    get_or_404(db, Project, project_id)
    task = get_or_404(db, ProjectTask, task_id)
    if task.project_id != project_id:
        raise HTTPException(status_code=404, detail="ProjectTask not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task


@app.post("/projects/{project_id}/tasks/{task_id}/run", response_model=PipelineRunResponse)
def run_project_task(project_id: UUID, task_id: UUID, db: Session = Depends(get_db)) -> PipelineRunResponse:
    factory = get_or_create_factory_state(db)
    if factory.mode != "running":
        raise HTTPException(status_code=409, detail=f"Factory is {factory.mode}. Start it before queueing task runs.")
    project = get_or_404(db, Project, project_id)
    task = get_or_404(db, ProjectTask, task_id)
    if task.project_id != project.id:
        raise HTTPException(status_code=404, detail="ProjectTask not found")
    task.status = "queued"
    project.status = "queued"
    queue = enqueue_pipeline(project.id)
    db.add(AgentEvent(project_id=project.id, step=task.agent_name, level="info", message=f"Task queued: {task.title}", metadata_json={"task_id": str(task.id)}))
    create_notification(db, level="info", title="Task queued", message=f"{task.title} queued for {project.name}.", entity_type="project_task", entity_id=task.id)
    db.commit()
    return PipelineRunResponse(project_id=project.id, status=project.status, queue=queue)


@app.get("/projects/{id}/events", response_model=list[AgentEventRead])
def list_project_events(id: UUID, db: Session = Depends(get_db)) -> list[AgentEvent]:
    get_or_404(db, Project, id)
    return list(db.scalars(select(AgentEvent).where(AgentEvent.project_id == id).order_by(AgentEvent.created_at)).all())


@app.delete("/projects/{id}/events", response_model=ActionResponse)
def clear_project_events(id: UUID, db: Session = Depends(get_db)) -> ActionResponse:
    get_or_404(db, Project, id)
    deleted = db.query(AgentEvent).filter(AgentEvent.project_id == id).delete(synchronize_session=False)
    db.commit()
    return ActionResponse(status="deleted", detail=f"Deleted {deleted} event(s)")


@app.get("/events", response_model=list[AgentEventRead])
def list_events(
    project_id: UUID | None = None,
    level: str | None = None,
    search: str | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
) -> list[AgentEvent]:
    query = select(AgentEvent)
    if project_id:
        query = query.where(AgentEvent.project_id == project_id)
    if level:
        query = query.where(AgentEvent.level == level)
    if search:
        pattern = f"%{search}%"
        query = query.where(AgentEvent.message.ilike(pattern))
    query = query.order_by(desc(AgentEvent.created_at)).limit(min(max(limit, 1), 1000))
    return list(db.scalars(query).all())


@app.get("/projects/{id}/qa", response_model=list[QAResultRead])
def list_project_qa(id: UUID, db: Session = Depends(get_db)) -> list[QAResult]:
    get_or_404(db, Project, id)
    return list(db.scalars(select(QAResult).where(QAResult.project_id == id).order_by(desc(QAResult.created_at))).all())


@app.get("/projects/{id}/policy", response_model=list[PolicyResultRead])
def list_project_policy(id: UUID, db: Session = Depends(get_db)) -> list[PolicyResult]:
    get_or_404(db, Project, id)
    return list(db.scalars(select(PolicyResult).where(PolicyResult.project_id == id).order_by(desc(PolicyResult.created_at))).all())


@app.get("/projects/{id}/artifacts", response_model=list[ArtifactRead])
def list_project_artifacts(id: UUID, db: Session = Depends(get_db)) -> list[Artifact]:
    get_or_404(db, Project, id)
    return list(db.scalars(select(Artifact).where(Artifact.project_id == id).order_by(desc(Artifact.created_at))).all())


@app.post("/notifications", response_model=NotificationRead)
def create_user_notification(payload: NotificationCreate, db: Session = Depends(get_db)) -> Notification:
    notification = create_notification(
        db,
        level=payload.level,
        title=payload.title,
        message=payload.message,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
    )
    db.commit()
    db.refresh(notification)
    return notification


@app.get("/notifications", response_model=list[NotificationRead])
def list_notifications(limit: int = 50, unread_only: bool = False, db: Session = Depends(get_db)) -> list[Notification]:
    query = select(Notification)
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    query = query.order_by(desc(Notification.created_at)).limit(min(max(limit, 1), 200))
    return list(db.scalars(query).all())


@app.post("/notifications/{id}/read", response_model=NotificationRead)
def mark_notification_read(id: UUID, db: Session = Depends(get_db)) -> Notification:
    notification = get_or_404(db, Notification, id)
    notification.read_at = notification.read_at or datetime.now(UTC)
    db.commit()
    db.refresh(notification)
    return notification


@app.post("/notifications/read-all", response_model=ActionResponse)
def mark_all_notifications_read(db: Session = Depends(get_db)) -> ActionResponse:
    updated = db.query(Notification).filter(Notification.read_at.is_(None)).update({Notification.read_at: datetime.now(UTC)}, synchronize_session=False)
    db.commit()
    return ActionResponse(status="read", detail=f"Marked {updated} notification(s) as read")


@app.post("/internal/projects/{id}/agent-runs", response_model=AgentRunRead)
def create_agent_run(id: UUID, payload: AgentRunCreate, db: Session = Depends(get_db)) -> AgentRun:
    get_or_404(db, Project, id)
    run = AgentRun(project_id=id, started_at=datetime.now(UTC), **payload.model_dump())
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


@app.patch("/internal/agent-runs/{id}", response_model=AgentRunRead)
def patch_agent_run(id: UUID, payload: AgentRunPatch, db: Session = Depends(get_db)) -> AgentRun:
    run = get_or_404(db, AgentRun, id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(run, field, value)
    if payload.status in {"succeeded", "failed"}:
        run.finished_at = datetime.now(UTC)
    db.commit()
    db.refresh(run)
    return run


@app.post("/internal/projects/{id}/events", response_model=AgentEventRead)
def create_agent_event(id: UUID, payload: AgentEventCreate, db: Session = Depends(get_db)) -> AgentEvent:
    get_or_404(db, Project, id)
    event = AgentEvent(
        project_id=id,
        agent_run_id=payload.agent_run_id,
        step=payload.step,
        level=payload.level,
        message=redact(payload.message) or "",
        stdout=redact(payload.stdout),
        stderr=redact(payload.stderr),
        metadata_json=payload.metadata_json,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@app.post("/internal/projects/{id}/qa", response_model=QAResultRead)
def create_qa_result(id: UUID, payload: QAResultCreate, db: Session = Depends(get_db)) -> QAResult:
    get_or_404(db, Project, id)
    result = QAResult(
        project_id=id,
        status=payload.status,
        command=payload.command,
        exit_code=payload.exit_code,
        stdout=redact(payload.stdout),
        stderr=redact(payload.stderr),
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


@app.post("/internal/projects/{id}/policy", response_model=PolicyResultRead)
def create_policy_result(id: UUID, payload: PolicyResultCreate, db: Session = Depends(get_db)) -> PolicyResult:
    get_or_404(db, Project, id)
    result = PolicyResult(project_id=id, **payload.model_dump())
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


@app.post("/internal/projects/{id}/artifacts", response_model=ArtifactRead)
def create_artifact(id: UUID, payload: ArtifactCreate, db: Session = Depends(get_db)) -> Artifact:
    get_or_404(db, Project, id)
    artifact = Artifact(project_id=id, **payload.model_dump())
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return artifact


@app.patch("/internal/project-tasks/{id}", response_model=ProjectTaskRead)
def patch_project_task_internal(id: UUID, payload: ProjectTaskAgentPatch, db: Session = Depends(get_db)) -> ProjectTask:
    task = get_or_404(db, ProjectTask, id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task


@app.post("/internal/projects/{id}/builds")
def create_build(id: UUID, payload: BuildCreate, db: Session = Depends(get_db)) -> dict[str, str]:
    get_or_404(db, Project, id)
    build = Build(
        project_id=id,
        status=payload.status,
        platform=payload.platform,
        artifact_path=payload.artifact_path,
        logs=redact(payload.logs),
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    db.add(build)
    db.commit()
    return {"id": str(build.id), "status": build.status}


@app.patch("/internal/projects/{id}/status", response_model=ProjectRead)
def patch_project_status(id: UUID, payload: ProjectStatusPatch, db: Session = Depends(get_db)) -> Project:
    project = get_or_404(db, Project, id)
    project.status = payload.status
    if payload.workspace_path is not None:
        project.workspace_path = payload.workspace_path
    db.commit()
    db.refresh(project)
    return project
