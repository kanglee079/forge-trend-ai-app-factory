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
    ApiKey,
    Artifact,
    Build,
    CostUsage,
    Idea,
    PolicyResult,
    Project,
    QAResult,
    Worker,
)
from app.queue import enqueue_pipeline
from app.runtime_state import get_app_settings, get_factory_state, patch_app_settings, patch_factory_state
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
    AppSettings,
    AppSettingsPatch,
    ArtifactCreate,
    ArtifactRead,
    BuildCreate,
    DoctorCheck,
    DoctorResponse,
    FactoryState,
    FactoryStatePatch,
    HealthResponse,
    IdeaCreate,
    IdeaRead,
    PipelineRunResponse,
    PolicyResultCreate,
    PolicyResultRead,
    ProjectCreate,
    ProjectRead,
    ProjectStatusPatch,
    QAResultCreate,
    QAResultRead,
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


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="forge-trend-api")


@app.get("/doctor", response_model=DoctorResponse)
def doctor(db: Session = Depends(get_db)) -> DoctorResponse:
    return build_doctor_report(db)


@app.get("/settings", response_model=AppSettings)
def read_settings() -> AppSettings:
    return get_app_settings()


@app.patch("/settings", response_model=AppSettings)
def update_settings(payload: AppSettingsPatch) -> AppSettings:
    return patch_app_settings(payload)


@app.get("/factory/state", response_model=FactoryState)
def read_factory_state() -> FactoryState:
    return get_factory_state()


@app.patch("/factory/state", response_model=FactoryState)
def update_factory_state(payload: FactoryStatePatch) -> FactoryState:
    try:
        return patch_factory_state(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
    db.query(CostUsage).filter(CostUsage.project_id == id).delete(synchronize_session=False)
    for model in [Artifact, Build, PolicyResult, QAResult, AgentEvent, AgentRun]:
        db.query(model).filter(model.project_id == id).delete(synchronize_session=False)
    db.delete(project)
    db.commit()
    return ActionResponse(status="deleted", detail="Project and related run records deleted")


@app.post("/projects/{id}/run-pipeline", response_model=PipelineRunResponse)
def run_pipeline(id: UUID, db: Session = Depends(get_db)) -> PipelineRunResponse:
    factory = get_factory_state()
    if factory.mode != "running":
        raise HTTPException(status_code=409, detail=f"Factory is {factory.mode}. Start it before queueing pipeline runs.")
    project = get_or_404(db, Project, id)
    project.status = "queued"
    queue = enqueue_pipeline(project.id)
    event = AgentEvent(project_id=project.id, step="pipeline", level="info", message="Pipeline queued")
    db.add(event)
    db.commit()
    return PipelineRunResponse(project_id=project.id, status=project.status, queue=queue)


@app.post("/projects/{id}/retry", response_model=PipelineRunResponse)
def retry_pipeline(id: UUID, db: Session = Depends(get_db)) -> PipelineRunResponse:
    factory = get_factory_state()
    if factory.mode != "running":
        raise HTTPException(status_code=409, detail=f"Factory is {factory.mode}. Start it before queueing pipeline runs.")
    project = get_or_404(db, Project, id)
    project.status = "queued"
    queue = enqueue_pipeline(project.id)
    event = AgentEvent(project_id=project.id, step="pipeline", level="info", message="Retry requested and pipeline queued")
    db.add(event)
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
