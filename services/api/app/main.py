import json
import os
import re
import shutil
import socket
import subprocess
import tomllib
import urllib.request
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote_plus, urlparse
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
    ConfigPlugin,
    ConfigProfile,
    ContextPack,
    CostUsage,
    FactoryBrief,
    FactoryState,
    FailurePattern,
    Idea,
    LearningRule,
    Notification,
    OpportunityCandidate,
    PolicyResult,
    PromptFragment,
    ProviderProfile,
    Project,
    ProjectTask,
    QAResult,
    ResearchFinding,
    RunProfile,
    RunEvaluation,
    SkillPack,
    SkillPrompt,
    SkillScore,
    SkillRun,
    SourceItem,
    SourceRegistry,
    SourceScanRun,
    TrendSource,
    TrustedProject,
    Worker,
)
from app.queue import enqueue_factory_brief, enqueue_pipeline
from app.plugin_registry import PLUGINS
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
    ConfigPluginCreate,
    ConfigPluginPatch,
    ConfigPluginRead,
    ConfigProfileCreate,
    ConfigProfileExportResponse,
    ConfigProfileImportPayload,
    ConfigProfilePatch,
    ConfigProfileRead,
    ContextPackCreate,
    ContextPackRead,
    DoctorCheck,
    DoctorResponse,
    FactoryBriefEventCreate,
    FactoryBriefFinalizeRequest,
    FactoryBriefCreate,
    FactoryBriefDetail,
    FactoryBriefRead,
    FactoryBriefRunResponse,
    FactoryBriefStatusPatch,
    FactoryStatePatch,
    FactoryState as FactoryStateSchema,
    FailurePatternRead,
    HealthResponse,
    IdeaCreate,
    IdeaRead,
    LearningRuleRead,
    LearningRulePatch,
    LearningSummary,
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
    PluginStatus,
    PromptContextSummary,
    ProviderCompletionRequest,
    ProviderCompletionResponse,
    ProviderProfileCreate,
    ProviderProfilePatch,
    ProviderProfileRead,
    ProviderStatus,
    QueueSummary,
    QAResultCreate,
    QAResultRead,
    ResearchFindingCreate,
    ResearchFindingRead,
    RunProfileRead,
    RunEvaluationCreate,
    RunEvaluationRead,
    RuntimeConfigResponse,
    ScanRunDetail,
    SkillPackPatch,
    SkillPackRead,
    SkillPromptRead,
    SkillRunRead,
    SkillTestPayload,
    SkillTestResponse,
    SourceItemPatch,
    SourceItemRead,
    SourceScanCreate,
    SourceScanRunRead,
    WorkerHeartbeat,
    WorkerRead,
    WorkerRegister,
    TrustedProjectCreate,
    TrustedProjectPatch,
    TrustedProjectRead,
)
from app.security import decrypt_secret, encrypt_secret, key_hint, redact, secret_fingerprint

app = FastAPI(title="ForgeTrend AI App Factory API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3100",
        "http://127.0.0.1:3100",
    ],
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


def http_check(url: str, timeout: float = 3.0) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status < 500, f"HTTP {response.status}"
    except Exception as exc:
        return False, str(exc)


def env_path_check(*names: str) -> tuple[bool, str]:
    for name in names:
        value = os.getenv(name)
        if value:
            return True, f"{name}={value}"
    return False, f"missing {'/'.join(names)}"


def doctor_check(id: str, label: str, ok: bool, detail: str, *, required: bool = True, guidance: str | None = None) -> DoctorCheck:
    return DoctorCheck(id=id, label=label, status="passed" if ok else "failed", detail=detail, required=required, guidance=guidance)


def worker_mode_label() -> str:
    return "Mode: Codex coding mode" if settings.worker_enable_codex else "Mode: Deterministic scaffold mode"


def worker_mode_label_for_worker(worker: Worker) -> str:
    return "Mode: Codex coding mode" if worker.worker_enable_codex else "Mode: Deterministic scaffold mode"


def research_mode_label() -> str:
    if settings.research_enable_web and settings.research_allowed_urls.strip():
        return "Research: web evidence mode"
    if settings.research_enable_web:
        return "Research: deterministic fallback (no allowed URLs configured)"
    return "Research: deterministic fallback"


def worker_ready(worker: Worker, require_codex: bool | None = None) -> bool:
    require_codex = settings.worker_enable_codex if require_codex is None else require_codex
    if worker.status != "online" or not worker.has_flutter:
        return False
    if require_codex:
        return worker.has_codex
    return True


def refresh_worker_statuses(db: Session, workers: list[Worker]) -> list[Worker]:
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


def effective_worker_enable_codex(workers: list[Worker]) -> bool:
    online_workers = [worker for worker in workers if worker.status == "online"]
    if online_workers:
        return any(worker.worker_enable_codex for worker in online_workers)
    if workers and not any(worker.worker_enable_codex for worker in workers):
        return False
    return settings.worker_enable_codex


def build_doctor_report(db: Session) -> DoctorResponse:
    checks: list[DoctorCheck] = []
    workers = refresh_worker_statuses(db, list(db.scalars(select(Worker)).all()))
    effective_codex_mode = effective_worker_enable_codex(workers)
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
        if id == "codex":
            required = effective_codex_mode
        ok, detail = run_check(command)
        checks.append(doctor_check(id, label, ok, detail, required=required, guidance=None if ok else guidance))

    network_checks = [
        ("internet", "Internet connectivity", "https://www.google.com/generate_204", True, "Check network/VPN/firewall connectivity."),
        ("github", "GitHub reachable", "https://github.com", False, "GitHub is useful for template and dependency workflows."),
        ("pub_dev", "pub.dev reachable", "https://pub.dev", False, "Flutter pub get needs access to pub.dev."),
    ]
    for id, label, url, required, guidance in network_checks:
        ok, detail = http_check(url)
        checks.append(doctor_check(id, label, ok, detail, required=required, guidance=None if ok else guidance))

    java_ok, java_detail = run_check(["java", "-version"])
    checks.append(doctor_check("java", "Java runtime", java_ok, java_detail, required=False, guidance="Install a JDK for Android builds."))
    adb_ok, adb_detail = run_check(["adb", "--version"])
    checks.append(doctor_check("adb", "Android Debug Bridge", adb_ok, adb_detail, required=False, guidance="Install Android platform tools."))
    android_ok, android_detail = env_path_check("ANDROID_HOME", "ANDROID_SDK_ROOT")
    checks.append(doctor_check("android_sdk_env", "Android SDK path", android_ok, android_detail, required=False, guidance="Set ANDROID_HOME or ANDROID_SDK_ROOT."))
    flutter_doctor_ok, flutter_doctor_detail = run_check(["flutter", "doctor", "-v"], timeout=20)
    checks.append(doctor_check("flutter_doctor", "Flutter doctor", flutter_doctor_ok, flutter_doctor_detail, required=False, guidance="Run flutter doctor -v and fix Android toolchain issues."))
    codex_auth_ok, codex_auth_detail = run_check(["codex", "login", "status"], timeout=8)
    checks.append(
        doctor_check(
            "codex_auth_smoke",
            "Codex CLI auth",
            codex_auth_ok,
            codex_auth_detail,
            required=effective_codex_mode,
            guidance="Codex CLI is installed but not authenticated. Run: codex login",
        )
    )

    redis_ok, redis_detail = ping_host("127.0.0.1", 6379)
    checks.append(doctor_check("redis", "Redis", redis_ok, redis_detail, guidance="Run docker compose up -d redis."))
    postgres_ok, postgres_detail = ping_host("127.0.0.1", 5432)
    checks.append(doctor_check("postgres", "Postgres", postgres_ok, postgres_detail, guidance="Run docker compose up -d postgres."))
    minio_ok, minio_detail = ping_host("127.0.0.1", 9000)
    checks.append(doctor_check("minio", "MinIO", minio_ok, minio_detail, required=False, guidance="Run docker compose up -d minio."))
    checks.append(doctor_check("api", "API", True, "FastAPI responded to /doctor."))
    checks.append(doctor_check("api_route_freshness", "API route freshness", True, "/factory-briefs and /settings are registered in this API process."))
    checks.append(
        doctor_check(
            "worker_mode",
            "Worker coding mode",
            True,
            "Mode: Codex coding mode" if effective_codex_mode else "Mode: Deterministic scaffold mode",
            required=False,
            guidance="Set WORKER_ENABLE_CODEX=false for deterministic scaffold mode or true for Codex coding mode.",
        )
    )
    checks.append(
        doctor_check(
            "research_mode",
            "Research mode",
            True,
            research_mode_label(),
            required=False,
            guidance="Set RESEARCH_ENABLE_WEB=true and RESEARCH_ALLOWED_URLS for low-volume web evidence mode.",
        )
    )

    online_workers = [worker for worker in workers if worker.status == "online"]
    if effective_codex_mode:
        ready_workers = [worker for worker in workers if worker_ready(worker, True)]
    else:
        ready_workers = [worker for worker in workers if worker_ready(worker, False)]
    codex_enabled_workers = [worker for worker in workers if worker.worker_enable_codex]
    deterministic_workers = [worker for worker in workers if not worker.worker_enable_codex]
    doctor_requires_codex = effective_codex_mode
    missing_parts: list[str] = []
    if not online_workers:
        missing_parts.append("no online worker heartbeat")
    if online_workers and not any(worker.has_flutter for worker in online_workers):
        missing_parts.append("Flutter")
    if doctor_requires_codex and online_workers and not any(worker.has_codex for worker in online_workers if worker.worker_enable_codex):
        missing_parts.append("Codex CLI")
    required_capabilities = "Flutter and Codex" if doctor_requires_codex else "Flutter"
    checks.append(
        doctor_check(
            "worker_heartbeat",
            "Worker heartbeat",
            bool(online_workers),
            f"{len(online_workers)} online / {len(workers)} registered",
            guidance="Run pnpm dev:worker. In Codex mode, run codex login first.",
        )
    )
    checks.append(
        doctor_check(
            "worker_pipeline_ready",
            "Worker pipeline ready",
            bool(ready_workers),
            (
                f"{len(ready_workers)} worker(s) ready; required: {required_capabilities}. "
                f"Effective mode: {'Mode: Codex coding mode' if effective_codex_mode else 'Mode: Deterministic scaffold mode'}. "
                f"Workers reporting: {len(deterministic_workers)} deterministic, {len(codex_enabled_workers)} Codex. "
                f"Missing: {', '.join(missing_parts) if missing_parts else 'none'}"
            ),
            guidance=(
                "Install Flutter and restart pnpm dev:worker."
                if not doctor_requires_codex
                else "Install Flutter, install Codex CLI, run codex login, then restart pnpm dev:worker."
            ),
        )
    )
    for worker in workers:
        missing: list[str] = []
        if worker.status != "online":
            missing.append(f"status={worker.status}")
        if not worker.has_flutter:
            missing.append("Flutter")
        if effective_codex_mode and not worker.has_codex:
            missing.append("Codex CLI")
        checks.append(
            doctor_check(
                f"worker_{worker.id}_ready",
                f"Worker ready: {worker.machine_name}",
                worker_ready(worker, effective_codex_mode),
                (
                    f"Effective {'Mode: Codex coding mode' if effective_codex_mode else 'Mode: Deterministic scaffold mode'}; worker reports {worker_mode_label_for_worker(worker)}; "
                    f"Flutter={worker.has_flutter}; Codex={worker.has_codex}; "
                    f"Missing: {', '.join(missing) if missing else 'none'}"
                ),
                required=False,
                guidance=(
                    "Install Flutter and restart this deterministic worker."
                    if not effective_codex_mode
                    else "Install Flutter, install Codex CLI, run codex login, then restart this worker."
                ),
            )
        )

    required_failed = any(check.required and check.status != "passed" for check in checks)
    warning_failed = any(check.status != "passed" for check in checks)
    status = "failed" if required_failed else "warning" if warning_failed else "passed"
    return DoctorResponse(
        status=status,
        generated_at=datetime.now(UTC),
        checks=checks,
        worker_enable_codex=effective_codex_mode,
        worker_mode_label="Mode: Codex coding mode" if effective_codex_mode else "Mode: Deterministic scaffold mode",
        research_enable_web=settings.research_enable_web,
        research_mode_label=research_mode_label(),
    )


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
    metadata_json: dict | None = None,
) -> Notification:
    notification = Notification(
        level=level,
        title=title,
        message=redact(message) or "",
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_json=metadata_json or {},
    )
    db.add(notification)
    return notification


def factory_brief_event(
    db: Session,
    brief: FactoryBrief,
    *,
    level: str,
    title: str,
    message: str,
    metadata_json: dict | None = None,
) -> Notification:
    detail = dict(metadata_json or {})
    detail["factory_brief_id"] = str(brief.id)
    return create_notification(
        db,
        level=level,
        title=title,
        message=message,
        entity_type="factory_brief",
        entity_id=brief.id,
        metadata_json=detail,
    )


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


def classify_failure_reason(reason: str | None) -> str:
    text = (reason or "").lower()
    if not text:
        return "none"
    if "codex" in text and "auth" in text:
        return "provider_auth_missing"
    if "pub get" in text:
        return "flutter_pub_get_failed"
    if "analyze" in text:
        return "flutter_analyze_failed"
    if "test" in text:
        return "flutter_test_failed"
    if "build" in text or "apk" in text:
        return "flutter_build_failed"
    if "generic" in text or "placeholder" in text:
        return "generic_template_copy"
    if "vietnamese" in text or "missing_vietnamese" in text:
        return "missing_vietnamese"
    if "policy" in text or "trademark" in text:
        return "policy_risk"
    if "store asset" in text:
        return "store_asset_missing"
    if "budget" in text:
        return "budget_exceeded"
    if "timeout" in text:
        return "timeout"
    return "unknown"


def upsert_learning_rule(db: Session, *, rule_key: str, description: str, trigger_json: dict, action_json: dict, confidence_score: int = 60) -> LearningRule:
    rule = db.scalar(select(LearningRule).where(LearningRule.rule_key == rule_key))
    if not rule:
        rule = LearningRule(
            rule_key=rule_key,
            description=description,
            trigger_json=trigger_json,
            action_json=action_json,
            confidence_score=confidence_score,
        )
        db.add(rule)
    else:
        rule.description = description
        rule.trigger_json = trigger_json
        rule.action_json = action_json
        rule.confidence_score = max(rule.confidence_score, confidence_score)
        rule.enabled = True
    return rule


def record_learning_from_evaluation(db: Session, evaluation: RunEvaluation) -> None:
    taxonomy = classify_failure_reason(evaluation.failure_reason or evaluation.human_review_reason)
    if taxonomy != "none":
        pattern = db.scalar(select(FailurePattern).where(FailurePattern.taxonomy == taxonomy))
        if not pattern:
            pattern = FailurePattern(taxonomy=taxonomy, count=0)
            db.add(pattern)
        pattern.count += 1
        pattern.last_project_id = evaluation.project_id
        pattern.last_reason = evaluation.failure_reason or evaluation.human_review_reason
        if taxonomy in {"generic_template_copy", "weak_core_feature"}:
            upsert_learning_rule(
                db,
                rule_key="force_deeper_feature_flow",
                description="Nếu app fail vì copy generic hoặc luồng tính năng yếu, lần sau ép blueprint sâu hơn và thêm core flow tương tác.",
                trigger_json={"failure_taxonomy": taxonomy},
                action_json={
                    "blueprint_depth": "deep",
                    "require_interactive_core_flow": True,
                    "selected_skills": ["product_depth_enhancer", "flutter_store_ready", "code_review"],
                    "quality_threshold_min": 80,
                    "prompt_fragment": "force_domain_specific_core_flow",
                },
                confidence_score=75,
            )
        if taxonomy == "provider_auth_missing":
            upsert_learning_rule(
                db,
                rule_key="fallback_when_provider_auth_missing",
                description="Nếu Codex/Aider thiếu auth, fallback deterministic và báo rõ provider chưa sẵn sàng.",
                trigger_json={"failure_taxonomy": taxonomy},
                action_json={"provider": "deterministic", "notify_user": True},
                confidence_score=80,
            )
    elif evaluation.final_status == "release_candidate" and (evaluation.category or "").lower() == "education" and evaluation.language == "vi":
        upsert_learning_rule(
            db,
            rule_key="prefer_education_archetype_vi",
            description="Education + tiếng Việt đang pass tốt, ưu tiên education_archetype cho các brief tương tự.",
            trigger_json={"category": "Education", "language": "vi", "final_status": "release_candidate"},
            action_json={"preferred_archetype": "education"},
            confidence_score=70,
        )


def brief_learning_context(brief_data: dict | None = None, brief: FactoryBrief | None = None) -> dict:
    if brief is not None:
        return {
            "category": brief.target_category,
            "language": brief.target_language,
            "monetization": brief.monetization_mode,
            "prompt": brief.raw_prompt,
            "quality_threshold": brief.quality_threshold,
        }
    return {
        "category": (brief_data or {}).get("target_category"),
        "language": (brief_data or {}).get("target_language"),
        "monetization": (brief_data or {}).get("monetization_mode"),
        "prompt": (brief_data or {}).get("raw_prompt"),
        "quality_threshold": (brief_data or {}).get("quality_threshold"),
    }


def learning_rule_applies(rule: LearningRule, context: dict) -> bool:
    trigger = rule.trigger_json or {}
    category = str(context.get("category") or "").lower()
    language = str(context.get("language") or "").lower()
    monetization = str(context.get("monetization") or "").lower()
    if trigger.get("category") and str(trigger["category"]).lower() != category:
        return False
    if trigger.get("language") and str(trigger["language"]).lower() != language:
        return False
    if trigger.get("monetization") and str(trigger["monetization"]).lower() != monetization:
        return False
    if trigger.get("failure_taxonomy"):
        # Historical failure rules are global heuristics, but only apply when there is enough brief context
        # to prove this is a real future run rather than an unscoped default config request.
        return bool(category or language or monetization or context.get("prompt"))
    return bool(trigger)


def applicable_learning_rules(db: Session, context: dict | None = None, limit: int = 20) -> list[dict]:
    rules = list(
        db.scalars(
            select(LearningRule)
            .where(LearningRule.enabled.is_(True))
            .order_by(desc(LearningRule.confidence_score), LearningRule.rule_key)
            .limit(limit)
        ).all()
    )
    context = context or {}
    applied: list[dict] = []
    for rule in rules:
        if context and not learning_rule_applies(rule, context):
            continue
        applied.append(
            {
                "id": str(rule.id),
                "rule_key": rule.rule_key,
                "description": rule.description,
                "confidence_score": rule.confidence_score,
                "trigger_json": rule.trigger_json,
                "action_json": rule.action_json,
            }
        )
    return applied


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


REPO_ROOT = Path(__file__).resolve().parents[3]

BUILTIN_CONFIG_PLUGINS = [
    {"plugin_id": "documents", "name": "Documents", "category": "workspace", "source": "openai-primary-runtime", "version": "builtin"},
    {"plugin_id": "spreadsheets", "name": "Spreadsheets", "category": "workspace", "source": "openai-primary-runtime", "version": "builtin"},
    {"plugin_id": "presentations", "name": "Presentations", "category": "workspace", "source": "openai-primary-runtime", "version": "builtin"},
    {"plugin_id": "browser-use", "name": "Browser Use", "category": "automation", "source": "openai-bundled", "version": "builtin"},
    {"plugin_id": "computer-use", "name": "Computer Use", "category": "automation", "source": "openai-bundled", "version": "builtin"},
    {"plugin_id": "deterministic_research", "name": "Deterministic Research", "category": "research", "source": "local", "version": "builtin"},
    {"plugin_id": "web_research", "name": "Web Research", "category": "research", "source": "allowlist", "version": "builtin"},
]

BUILTIN_SKILLS = [
    {
        "name": "Flutter Store Ready",
        "slug": "flutter_store_ready",
        "category": "app_generation",
        "description": "Tao luong Flutter co onboarding, home, core flow, settings, privacy, QA va store-readiness.",
        "token_budget": 3000,
        "prompts": [
            {
                "name": "build_core_flow",
                "purpose": "Generate app-specific core feature flow before Flutter code generation.",
                "when_to_use": "Before code_agent writes Flutter screens.",
                "prompt_template": "Build a store-ready Flutter MVP for {{app_name}}. Require onboarding, home dashboard, app-specific core flow, settings, privacy, empty/error/success states, tests, and no production publishing automation.",
                "success_criteria_json": {"must_have": ["core_flow", "qa", "privacy", "store_readiness"]},
                "token_budget": 1200,
            }
        ],
    },
    {
        "name": "Product Depth Enhancer",
        "slug": "product_depth_enhancer",
        "category": "app_generation",
        "description": "Lam sau core flow khi app bi generic/thin, ep co tuong tac, data mau co y nghia va copy theo domain.",
        "token_budget": 1800,
        "prompts": [
            {
                "name": "deepen_core_flow",
                "purpose": "Turn a thin generated app into a product-specific MVP.",
                "when_to_use": "When learning memory or quality gate detects generic copy, placeholder-heavy screens, or weak core features.",
                "prompt_template": "Deepen {{app_name}} by adding domain-specific actions, meaningful sample data, empty/error/success states, and copy that proves the app solves a real user job. Remove generic placeholder language.",
                "success_criteria_json": {"must_have": ["domain_specific_actions", "meaningful_state", "no_generic_copy"]},
                "token_budget": 900,
            }
        ],
    },
    {
        "name": "Vietnamese UX Writer",
        "slug": "vietnamese_ux_writer",
        "category": "localization",
        "description": "Viet microcopy tieng Viet ro rang, tu nhien, tranh dich may moc.",
        "token_budget": 1600,
        "prompts": [
            {
                "name": "rewrite_microcopy_vi",
                "purpose": "Rewrite product copy for Vietnamese-first apps.",
                "when_to_use": "When target_language is vi or target_country is VN.",
                "prompt_template": "Rewrite UI copy for Vietnamese users. Keep it concise, natural, respectful, and action-oriented. Avoid generic template wording. App context: {{app_context}}",
                "success_criteria_json": {"must_have": ["natural_vietnamese", "domain_specific_copy"]},
                "token_budget": 700,
            }
        ],
    },
    {
        "name": "Google Play Policy",
        "slug": "google_play_policy",
        "category": "policy",
        "description": "Checklist rui ro ten app, privacy, permission, billing va spam policy truoc khi tao goi test.",
        "token_budget": 2200,
        "prompts": [
            {
                "name": "policy_gate",
                "purpose": "Identify release blockers before internal testing.",
                "when_to_use": "Before release candidate or when policy risk is high.",
                "prompt_template": "Review the app candidate for Google Play policy risk: copycat naming, misleading claims, privacy, permissions, billing disclosure, user generated content, and minimum functionality. Output blockers and safe fixes.",
                "success_criteria_json": {"must_have": ["release_blockers", "safe_fixes"]},
                "token_budget": 900,
            }
        ],
    },
    {
        "name": "App Store Readiness",
        "slug": "app_store_readiness",
        "category": "store_readiness",
        "description": "Danh gia tinh san sang cua app candidate truoc khi con nguoi review.",
        "token_budget": 1800,
        "prompts": [
            {
                "name": "readiness_check",
                "purpose": "Check whether app output is reviewable by a human tester.",
                "when_to_use": "After QA and quality gate.",
                "prompt_template": "Check APK/source/report/store asset readiness. Require clear blockers, tester README, privacy draft, screenshot plan, and no auto-publish.",
                "success_criteria_json": {"must_have": ["tester_readme", "blocker_list", "store_assets"]},
                "token_budget": 700,
            }
        ],
    },
    {
        "name": "ASO Listing",
        "slug": "aso_listing",
        "category": "store_assets",
        "description": "Tao draft store listing khong spam, khong copy brand, co keyword an toan.",
        "token_budget": 1400,
        "prompts": [
            {
                "name": "listing_draft",
                "purpose": "Draft store listing copy for human review.",
                "when_to_use": "When store assets are created.",
                "prompt_template": "Draft app name, short description, long description, keywords, and screenshot captions. Keep claims modest and require human approval.",
                "success_criteria_json": {"must_have": ["modest_claims", "human_review"]},
                "token_budget": 650,
            }
        ],
    },
    {
        "name": "IAP Subscription Placeholder",
        "slug": "iap_subscription_placeholder",
        "category": "monetization",
        "description": "Tao paywall mo phong va disclosure ro rang, khong bat billing that.",
        "token_budget": 1300,
        "prompts": [
            {
                "name": "billing_placeholder",
                "purpose": "Generate safe subscription/IAP placeholder flow.",
                "when_to_use": "When monetization is iap, subscription, freemium, or hybrid.",
                "prompt_template": "Design a simulated paywall with clear billing disclosure. Do not enable real purchases. Require human billing configuration before release.",
                "success_criteria_json": {"must_have": ["simulated_only", "billing_disclosure"]},
                "token_budget": 500,
            }
        ],
    },
    {
        "name": "QA Flutter Fix",
        "slug": "qa_flutter_fix",
        "category": "qa",
        "description": "Sua loi flutter pub get/analyze/test/build theo loi that.",
        "token_budget": 2200,
        "prompts": [
            {
                "name": "fix_flutter_failure",
                "purpose": "Repair Flutter QA failures.",
                "when_to_use": "When qa_agent returns a failed command.",
                "prompt_template": "Fix this Flutter failure without destructive commands. Keep app behavior intact. Error: {{qa_error}}",
                "success_criteria_json": {"must_have": ["analyze_passes", "tests_pass", "debug_apk"]},
                "token_budget": 1000,
            }
        ],
    },
    {
        "name": "Trend Research",
        "slug": "trend_research",
        "category": "research",
        "description": "Chon huong app dua tren pain, demand, feasibility, originality va policy risk.",
        "token_budget": 2400,
        "prompts": [
            {
                "name": "score_opportunity",
                "purpose": "Score candidate app opportunities.",
                "when_to_use": "During auto_trend and candidate scoring.",
                "prompt_template": "Score app opportunities by demand, pain, monetization, build feasibility, differentiation, originality, and policy risk. Prefer useful niche apps over clones.",
                "success_criteria_json": {"must_have": ["scores", "original_angle"]},
                "token_budget": 850,
            }
        ],
    },
    {
        "name": "Prompt Compression",
        "slug": "prompt_compression",
        "category": "token_optimization",
        "description": "Nen context thanh pack ngan gon truoc khi goi agent.",
        "token_budget": 900,
        "prompts": [
            {
                "name": "compress_context",
                "purpose": "Summarize long context into reusable context packs.",
                "when_to_use": "Before code/review calls or after large logs.",
                "prompt_template": "Compress context into decisions, constraints, important files, blockers, and open questions. Keep enough detail for the next agent.",
                "success_criteria_json": {"must_have": ["constraints", "important_files", "blockers"]},
                "token_budget": 450,
            }
        ],
    },
    {
        "name": "Code Review",
        "slug": "code_review",
        "category": "qa",
        "description": "Review bug/regression/security risk sau khi code pass.",
        "token_budget": 1800,
        "prompts": [
            {
                "name": "review_patch",
                "purpose": "Review generated source for defects.",
                "when_to_use": "After code changes and before quality gate.",
                "prompt_template": "Review generated app changes for bugs, missing tests, policy leakage, hardcoded secrets, and incomplete flows. Return findings first.",
                "success_criteria_json": {"must_have": ["findings_first", "tests"]},
                "token_budget": 700,
            }
        ],
    },
    {
        "name": "Privacy Policy",
        "slug": "privacy_policy",
        "category": "policy",
        "description": "Tao privacy draft an toan cho MVP local-first.",
        "token_budget": 1100,
        "prompts": [
            {
                "name": "privacy_draft",
                "purpose": "Draft privacy policy and summary.",
                "when_to_use": "When generating store assets or policy gate.",
                "prompt_template": "Draft a privacy policy placeholder for a local-first MVP. Mention no production analytics/secrets and require human legal review.",
                "success_criteria_json": {"must_have": ["local_first", "human_review"]},
                "token_budget": 500,
            }
        ],
    },
]

RUN_PROFILE_PRESETS = [
    {
        "name": "Nhanh & tiet kiem",
        "slug": "fast_cheap",
        "description": "Dung deterministic/local truoc, it iteration, phu hop smoke run.",
        "skill_slugs": ["trend_research", "flutter_store_ready", "qa_flutter_fix", "prompt_compression"],
        "token_budget": 8000,
        "quality_threshold": 70,
        "max_iterations": 2,
        "research_mode": "deterministic",
    },
    {
        "name": "Chat luong cao",
        "slug": "high_quality",
        "description": "Tang nguong chat luong va bat nhieu skill policy/store-readiness.",
        "skill_slugs": ["trend_research", "flutter_store_ready", "product_depth_enhancer", "vietnamese_ux_writer", "google_play_policy", "app_store_readiness", "code_review"],
        "token_budget": 30000,
        "quality_threshold": 85,
        "max_iterations": 5,
        "research_mode": "hybrid",
    },
    {
        "name": "Codex that",
        "slug": "codex_full_power",
        "description": "Uu tien Codex CLI khi worker da login, van giu fallback deterministic.",
        "skill_slugs": ["flutter_store_ready", "qa_flutter_fix", "code_review", "prompt_compression"],
        "token_budget": 40000,
        "quality_threshold": 80,
        "max_iterations": 6,
        "research_mode": "deterministic",
    },
    {
        "name": "Research web",
        "slug": "research_web",
        "description": "Uu tien web evidence khi allowlist duoc cau hinh.",
        "skill_slugs": ["trend_research", "google_play_policy", "aso_listing"],
        "token_budget": 22000,
        "quality_threshold": 78,
        "max_iterations": 4,
        "research_mode": "web",
    },
    {
        "name": "Offline deterministic",
        "slug": "offline_deterministic",
        "description": "Chay duoc khi khong co API key/Codex/web.",
        "skill_slugs": ["flutter_store_ready", "qa_flutter_fix", "privacy_policy"],
        "token_budget": 0,
        "quality_threshold": 72,
        "max_iterations": 3,
        "research_mode": "deterministic",
    },
    {
        "name": "App tieng Viet de test store",
        "slug": "vi_store_test",
        "description": "Mac dinh tieng Viet, tap trung copy, policy, store asset va goi test noi bo.",
        "skill_slugs": ["vietnamese_ux_writer", "flutter_store_ready", "product_depth_enhancer", "google_play_policy", "aso_listing", "privacy_policy"],
        "token_budget": 18000,
        "quality_threshold": 80,
        "max_iterations": 4,
        "research_mode": "deterministic",
    },
]

PROMPT_FRAGMENT_PRESETS = [
    ("flutter_architecture_rules", "app_generation", "Keep Flutter app compact, testable, local-first, and free of secrets or auto-publish automation."),
    ("vietnamese_ux_rules", "localization", "Vietnamese UI copy must be natural, specific to the app domain, concise, and not machine-translated."),
    ("policy_rules", "policy", "Check trademark, privacy, permissions, billing disclosure, misleading claims, and minimum functionality."),
    ("iap_rules", "monetization", "Billing must stay simulated until human configuration of StoreKit or Google Play Billing."),
    ("qa_fix_rules", "qa", "Fix the actual Flutter command failure and rerun analyze, tests, and debug APK."),
    ("store_listing_rules", "store_assets", "Draft store assets only for human review; never auto-submit or make unsupported claims."),
]


def seed_default_config_profile(db: Session) -> ConfigProfile:
    profile = db.scalar(select(ConfigProfile).where(ConfigProfile.is_default.is_(True)).order_by(desc(ConfigProfile.updated_at)))
    if profile:
        return profile
    profile = db.scalar(select(ConfigProfile).order_by(desc(ConfigProfile.updated_at)))
    if profile:
        profile.is_default = True
        db.commit()
        db.refresh(profile)
        return profile

    profile = ConfigProfile(
        name="Codex Full Power Mode",
        description="Profile mac dinh: OpenAI-compatible router, Codex/browser/document skills, deterministic fallback an toan.",
        is_default=True,
        model_provider="OpenAI",
        model="gpt-5.5",
        review_model="gpt-5.5",
        network_access="enabled",
        model_context_window=1000000,
        model_auto_compact_token_limit=900000,
    )
    db.add(profile)
    db.flush()
    provider = ProviderProfile(
        config_profile_id=profile.id,
        name="OpenAI",
        provider_type="openai_compatible",
        base_url="https://api.openai.com/v1",
        wire_api="responses",
        requires_openai_auth=True,
        enabled=True,
    )
    db.add(provider)
    db.flush()
    profile.active_provider_profile_id = provider.id
    for plugin in BUILTIN_CONFIG_PLUGINS:
        db.add(ConfigPlugin(config_profile_id=profile.id, **plugin, enabled=True))
    db.commit()
    db.refresh(profile)
    return profile


def set_config_profile_default(db: Session, profile: ConfigProfile) -> None:
    db.query(ConfigProfile).update({ConfigProfile.is_default: False}, synchronize_session=False)
    profile.is_default = True


def profile_providers(db: Session, profile_id: UUID) -> list[ProviderProfile]:
    return list(db.scalars(select(ProviderProfile).where(ProviderProfile.config_profile_id == profile_id).order_by(desc(ProviderProfile.enabled), ProviderProfile.name)).all())


def profile_plugins(db: Session, profile_id: UUID) -> list[ConfigPlugin]:
    return list(db.scalars(select(ConfigPlugin).where(ConfigPlugin.config_profile_id == profile_id).order_by(ConfigPlugin.category, ConfigPlugin.name)).all())


def profile_trusted_projects(db: Session, profile_id: UUID) -> list[TrustedProject]:
    return list(db.scalars(select(TrustedProject).where(TrustedProject.config_profile_id == profile_id).order_by(TrustedProject.path)).all())


def config_profile_read(db: Session, profile: ConfigProfile) -> ConfigProfileRead:
    return ConfigProfileRead.model_validate(profile).model_copy(
        update={
            "providers": [ProviderProfileRead.model_validate(item) for item in profile_providers(db, profile.id)],
            "plugins": [ConfigPluginRead.model_validate(item) for item in profile_plugins(db, profile.id)],
            "trusted_projects": [TrustedProjectRead.model_validate(item) for item in profile_trusted_projects(db, profile.id)],
        }
    )


def active_provider_for_profile(db: Session, profile: ConfigProfile) -> ProviderProfile | None:
    providers = profile_providers(db, profile.id)
    if profile.active_provider_profile_id:
        active = next((item for item in providers if item.id == profile.active_provider_profile_id), None)
        if active:
            return active
    return next((item for item in providers if item.enabled), None) or (providers[0] if providers else None)


def skill_prompt_fragments_for_runtime(db: Session, pack_id: UUID) -> list[dict]:
    prompts = list(db.scalars(select(SkillPrompt).where(SkillPrompt.skill_pack_id == pack_id).order_by(SkillPrompt.name)).all())
    return [
        {
            "name": item.name,
            "purpose": item.purpose,
            "when_to_use": item.when_to_use,
            "prompt_template": item.prompt_template,
            "token_budget": item.token_budget,
        }
        for item in prompts
    ]


def build_runtime_config(db: Session, profile: ConfigProfile | None = None, brief_context: dict | None = None) -> RuntimeConfigResponse:
    profile = profile or seed_default_config_profile(db)
    provider = active_provider_for_profile(db, profile)
    provider_payload: dict = {}
    if provider:
        api_key_hint_value = None
        if provider.api_key_id:
            api_key = db.get(ApiKey, provider.api_key_id)
            api_key_hint_value = api_key.key_hint if api_key else None
        provider_payload = {
            "id": str(provider.id),
            "name": provider.name,
            "provider_type": provider.provider_type,
            "base_url": provider.base_url,
            "wire_api": provider.wire_api,
            "requires_openai_auth": provider.requires_openai_auth,
            "api_key_id": str(provider.api_key_id) if provider.api_key_id else None,
            "api_key_hint": api_key_hint_value,
            "auth_mode": "dashboard_api_key" if provider.api_key_id else ("codex_cli_auth" if provider.provider_type == "codex_cli" else "not_configured"),
            "enabled": provider.enabled,
        }
    enabled_plugins = [
        {
            "plugin_id": item.plugin_id,
            "name": item.name,
            "category": item.category,
            "source_type": item.source_type,
            "version": item.version,
        }
        for item in profile_plugins(db, profile.id)
        if item.enabled
    ]
    enabled_skills = [
        {
            "slug": item.slug,
            "name": item.name,
            "category": item.category,
            "token_budget": item.token_budget,
            "quality_score": item.quality_score,
            "prompt_fragments": skill_prompt_fragments_for_runtime(db, item.id),
        }
        for item in db.scalars(select(SkillPack).where(SkillPack.enabled.is_(True)).order_by(desc(SkillPack.quality_score), SkillPack.name)).all()
    ]
    trusted_projects = [{"path": item.path, "trust_level": item.trust_level} for item in profile_trusted_projects(db, profile.id)]
    applied_rules = applicable_learning_rules(db, brief_context or {}, limit=20)
    return RuntimeConfigResponse(
        config_profile_id=profile.id,
        profile_name=profile.name,
        model_provider=profile.model_provider,
        model=profile.model,
        review_model=profile.review_model,
        model_reasoning_effort=profile.model_reasoning_effort,
        disable_response_storage=profile.disable_response_storage,
        network_access=profile.network_access,
        model_context_window=profile.model_context_window,
        model_auto_compact_token_limit=profile.model_auto_compact_token_limit,
        provider=provider_payload,
        enabled_plugins=enabled_plugins,
        enabled_skills=enabled_skills,
        trusted_projects=trusted_projects,
        applied_learning_rules=applied_rules,
        secrets_redacted=True,
    )


def runtime_config_snapshot(db: Session, profile: ConfigProfile | None = None, brief_context: dict | None = None) -> dict:
    return build_runtime_config(db, profile, brief_context).model_dump(mode="json")


def runtime_requires_codex_worker(runtime_snapshot: dict | None) -> bool:
    provider = (runtime_snapshot or {}).get("provider") or {}
    return str(provider.get("provider_type") or "").lower() == "codex_cli"


def project_requires_codex_worker(db: Session, project: Project) -> bool:
    brief = db.scalar(
        select(FactoryBrief)
        .where(FactoryBrief.selected_project_id == project.id)
        .order_by(desc(FactoryBrief.created_at))
    )
    return runtime_requires_codex_worker((brief.runtime_config_snapshot_json if brief else None) or {})


def toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if value is None:
        return '""'
    return json.dumps(str(value), ensure_ascii=False)


def toml_table_key(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def export_profile_toml(db: Session, profile: ConfigProfile) -> str:
    lines = [
        f'model_provider = {toml_value(profile.model_provider)}',
        f'model = {toml_value(profile.model)}',
        f'review_model = {toml_value(profile.review_model)}',
        f'model_reasoning_effort = {toml_value(profile.model_reasoning_effort)}',
        f'disable_response_storage = {toml_value(profile.disable_response_storage)}',
        f'network_access = {toml_value(profile.network_access)}',
        f'model_context_window = {toml_value(profile.model_context_window)}',
        f'model_auto_compact_token_limit = {toml_value(profile.model_auto_compact_token_limit)}',
        "",
    ]
    for provider in profile_providers(db, profile.id):
        lines.extend(
            [
                f"[model_providers.{toml_table_key(provider.name)}]",
                f"name = {toml_value(provider.name)}",
                f"provider_type = {toml_value(provider.provider_type)}",
                f"base_url = {toml_value(provider.base_url)}",
                f"wire_api = {toml_value(provider.wire_api)}",
                f"requires_openai_auth = {toml_value(provider.requires_openai_auth)}",
                f"enabled = {toml_value(provider.enabled)}",
            ]
        )
        if provider.api_key_id:
            lines.append(f"api_key_ref = {toml_value(str(provider.api_key_id))}")
        lines.append("")
    for plugin in profile_plugins(db, profile.id):
        lines.extend(
            [
                f"[plugins.{toml_table_key(plugin.plugin_id)}]",
                f"name = {toml_value(plugin.name)}",
                f"category = {toml_value(plugin.category)}",
                f"enabled = {toml_value(plugin.enabled)}",
                f"source_type = {toml_value(plugin.source_type)}",
                f"source = {toml_value(plugin.source)}",
                f"version = {toml_value(plugin.version)}",
                "",
            ]
        )
    for project in profile_trusted_projects(db, profile.id):
        lines.extend(
            [
                f"[projects.{toml_table_key(project.path)}]",
                f"trust_level = {toml_value(project.trust_level)}",
                "",
            ]
        )
    lines.append("# Secrets are redacted by default. Use api_key_ref or api_key_env instead of raw keys.")
    return "\n".join(lines).strip() + "\n"


def import_profile_from_toml(db: Session, payload: ConfigProfileImportPayload) -> ConfigProfile:
    try:
        parsed = tomllib.loads(payload.toml_text)
    except tomllib.TOMLDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"TOML is invalid: {exc}") from exc

    profile = ConfigProfile(
        name=payload.name or str(parsed.get("profile_name") or parsed.get("name") or f"{parsed.get('model_provider', 'Imported')} Config"),
        description=str(parsed.get("description") or "Imported from config.toml"),
        is_default=payload.set_default,
        model_provider=str(parsed.get("model_provider") or "OpenAI"),
        model=str(parsed.get("model") or "gpt-5.5"),
        review_model=str(parsed.get("review_model") or parsed.get("model") or "gpt-5.5"),
        model_reasoning_effort=str(parsed.get("model_reasoning_effort") or "medium"),
        disable_response_storage=bool(parsed.get("disable_response_storage", False)),
        network_access=str(parsed.get("network_access") or "disabled"),
        model_context_window=int(parsed.get("model_context_window") or 200000),
        model_auto_compact_token_limit=int(parsed.get("model_auto_compact_token_limit") or 160000),
    )
    if payload.set_default:
        set_config_profile_default(db, profile)
    db.add(profile)
    db.flush()

    providers = parsed.get("model_providers") or {}
    created_providers: list[ProviderProfile] = []
    for key, value in providers.items():
        if not isinstance(value, dict):
            continue
        api_key_id = None
        api_key_ref = value.get("api_key_ref")
        if api_key_ref:
            try:
                candidate_id = UUID(str(api_key_ref))
                if db.get(ApiKey, candidate_id):
                    api_key_id = candidate_id
            except ValueError:
                api_key_id = None
        provider = ProviderProfile(
            config_profile_id=profile.id,
            name=str(value.get("name") or key),
            provider_type=str(value.get("provider_type") or "openai_compatible"),
            base_url=str(value.get("base_url") or "https://api.openai.com/v1"),
            wire_api=str(value.get("wire_api") or "responses"),
            requires_openai_auth=bool(value.get("requires_openai_auth", True)),
            api_key_id=api_key_id,
            enabled=bool(value.get("enabled", True)),
        )
        db.add(provider)
        created_providers.append(provider)
    if not created_providers:
        provider = ProviderProfile(config_profile_id=profile.id, name=profile.model_provider, base_url="https://api.openai.com/v1")
        db.add(provider)
        created_providers.append(provider)
    db.flush()
    active = next((item for item in created_providers if item.name == profile.model_provider), created_providers[0])
    profile.active_provider_profile_id = active.id

    plugins = parsed.get("plugins") or {}
    if plugins:
        for key, value in plugins.items():
            value = value if isinstance(value, dict) else {}
            db.add(
                ConfigPlugin(
                    config_profile_id=profile.id,
                    plugin_id=str(key),
                    name=str(value.get("name") or key),
                    category=str(value.get("category") or "plugin"),
                    enabled=bool(value.get("enabled", True)),
                    source_type=str(value.get("source_type") or "imported"),
                    source=str(value.get("source") or ""),
                    version=str(value.get("version") or "1.0.0"),
                )
            )
    else:
        for plugin in BUILTIN_CONFIG_PLUGINS:
            db.add(ConfigPlugin(config_profile_id=profile.id, **plugin, enabled=True))

    projects = parsed.get("projects") or {}
    for path, value in projects.items():
        value = value if isinstance(value, dict) else {}
        db.add(TrustedProject(config_profile_id=profile.id, path=str(path), trust_level=str(value.get("trust_level") or "trusted")))
    db.commit()
    db.refresh(profile)
    return profile


def seed_builtin_skill_packs(db: Session) -> list[SkillPack]:
    packs: list[SkillPack] = []
    for spec in BUILTIN_SKILLS:
        pack = db.scalar(select(SkillPack).where(SkillPack.slug == spec["slug"]))
        if not pack:
            pack = SkillPack(
                name=spec["name"],
                slug=spec["slug"],
                category=spec["category"],
                description=spec["description"],
                token_budget=int(spec["token_budget"]),
                source_type="builtin",
                local_path=str(REPO_ROOT / "skills" / spec["slug"]),
                quality_score=76,
            )
            db.add(pack)
            db.flush()
        else:
            pack.name = spec["name"]
            pack.category = spec["category"]
            pack.description = spec["description"]
            pack.token_budget = int(spec["token_budget"])
            pack.local_path = pack.local_path or str(REPO_ROOT / "skills" / spec["slug"])
        for prompt_spec in spec["prompts"]:
            prompt = db.scalar(select(SkillPrompt).where(SkillPrompt.skill_pack_id == pack.id, SkillPrompt.name == prompt_spec["name"]))
            if not prompt:
                db.add(SkillPrompt(skill_pack_id=pack.id, **prompt_spec))
            else:
                prompt.purpose = prompt_spec["purpose"]
                prompt.when_to_use = prompt_spec["when_to_use"]
                prompt.prompt_template = prompt_spec["prompt_template"]
                prompt.success_criteria_json = prompt_spec.get("success_criteria_json", {})
                prompt.token_budget = int(prompt_spec["token_budget"])
        score = db.scalar(select(SkillScore).where(SkillScore.skill_pack_id == pack.id))
        if not score:
            db.add(SkillScore(skill_pack_id=pack.id))
        packs.append(pack)
    db.commit()
    return packs


def skill_pack_read(db: Session, pack: SkillPack) -> SkillPackRead:
    prompts = list(db.scalars(select(SkillPrompt).where(SkillPrompt.skill_pack_id == pack.id).order_by(SkillPrompt.name)).all())
    score = db.scalar(select(SkillScore).where(SkillScore.skill_pack_id == pack.id))
    return SkillPackRead.model_validate(pack).model_copy(
        update={
            "prompts": [SkillPromptRead.model_validate(item) for item in prompts],
            "score": {
                "success_count": score.success_count if score else 0,
                "failure_count": score.failure_count if score else 0,
                "avg_quality_delta": score.avg_quality_delta if score else 0,
                "avg_tokens_saved": score.avg_tokens_saved if score else 0,
                "last_used_at": score.last_used_at.isoformat() if score and score.last_used_at else None,
            },
        }
    )


def seed_run_profiles(db: Session) -> list[RunProfile]:
    default_profile = seed_default_config_profile(db)
    items: list[RunProfile] = []
    for spec in RUN_PROFILE_PRESETS:
        item = db.scalar(select(RunProfile).where(RunProfile.slug == spec["slug"]))
        if not item:
            item = RunProfile(config_profile_id=default_profile.id, **spec)
            db.add(item)
        else:
            item.name = spec["name"]
            item.description = spec["description"]
            item.skill_slugs = spec["skill_slugs"]
            item.token_budget = spec["token_budget"]
            item.quality_threshold = spec["quality_threshold"]
            item.max_iterations = spec["max_iterations"]
            item.research_mode = spec["research_mode"]
            item.config_profile_id = item.config_profile_id or default_profile.id
        items.append(item)
    db.commit()
    return items


def seed_prompt_fragments(db: Session) -> None:
    for slug, category, content in PROMPT_FRAGMENT_PRESETS:
        fragment = db.scalar(select(PromptFragment).where(PromptFragment.slug == slug))
        token_estimate = max(1, len(content.split()))
        if not fragment:
            db.add(PromptFragment(slug=slug, category=category, content=content, token_estimate=token_estimate))
        else:
            fragment.category = category
            fragment.content = content
            fragment.token_estimate = token_estimate
    db.commit()


def source_items_for_query(source_type: str, query: str, limit: int) -> list[dict]:
    fallback = [
        {
            "title": f"{query} prompt checklist",
            "source_url": None,
            "summary": "Quarantined template candidate generated from the scan query. Review before enabling.",
            "category": "prompt_library",
            "usefulness_score": 55,
            "metadata_json": {"safe_mode": "fallback", "query": query},
        }
    ]
    if source_type == "web_url":
        parsed_url = urlparse(query)
        allowed_domains = {item.strip().lower() for item in settings.research_allowed_domains.split(",") if item.strip()}
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
            raise HTTPException(status_code=422, detail="Scanner chỉ nhận URL http/https hợp lệ.")
        hostname = parsed_url.hostname.lower()
        if not any(hostname == domain or hostname.endswith(f".{domain}") for domain in allowed_domains):
            raise HTTPException(status_code=403, detail="Web scanner chỉ đọc domain trong allowlist và chỉ lấy text để review.")
        try:
            request = urllib.request.Request(query, headers={"User-Agent": "ForgeTrend-Scanner"})
            with urllib.request.urlopen(request, timeout=6) as response:
                content_type = response.headers.get("content-type", "")
                raw = response.read(120000).decode("utf-8", errors="ignore")
            title_match = re.search(r"<title[^>]*>(.*?)</title>", raw, flags=re.I | re.S)
            title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else query
            text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw, flags=re.I | re.S)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return [
                {
                    "title": title[:255],
                    "source_url": query,
                    "summary": text[:900] or f"Fetched {content_type or 'web page'} for review.",
                    "category": "web_url",
                    "usefulness_score": 60,
                    "metadata_json": {"safe_mode": "text_only", "content_type": content_type, "bytes_sampled": len(raw)},
                }
            ]
        except Exception as exc:
            item = dict(fallback[0])
            item["source_url"] = query
            item["summary"] = f"Web scan fallback because fetch failed: {exc}"
            item["metadata_json"] = {"safe_mode": "fallback", "query": query, "error": str(exc)}
            return [item]
    if source_type == "github_repo":
        if not re.match(r"^(https://github\.com/)?[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?$", query.strip()):
            raise HTTPException(status_code=422, detail="GitHub repo scanner chỉ nhận owner/repo hoặc https://github.com/owner/repo.")
        repo = query.replace("https://github.com/", "").strip("/")
        parts = repo.split("/")
        if len(parts) >= 2:
            owner, name = parts[0], parts[1]
            for branch in ["main", "master"]:
                try:
                    url = f"https://raw.githubusercontent.com/{owner}/{name}/{branch}/README.md"
                    request = urllib.request.Request(url, headers={"User-Agent": "ForgeTrend-Scanner"})
                    with urllib.request.urlopen(request, timeout=6) as response:
                        readme = response.read(120000).decode("utf-8", errors="ignore")
                    return [
                        {
                            "title": f"{owner}/{name}",
                            "source_url": f"https://github.com/{owner}/{name}",
                            "summary": readme[:1000] or "GitHub repository README fetched for review.",
                            "category": "github_repo",
                            "usefulness_score": 65,
                            "metadata_json": {"safe_mode": "readme_only", "branch": branch},
                        }
                    ]
                except Exception:
                    continue
        item = dict(fallback[0])
        item["summary"] = "GitHub repo scan could not fetch README. Item remains quarantined for manual review."
        item["metadata_json"] = {"safe_mode": "fallback", "query": query}
        return [item]
    if source_type != "github_search":
        return fallback[:limit]
    if not re.search(r"(prompt|skill|flutter|mobile|app|ux|qa|policy|store|readme)", query, flags=re.I):
        raise HTTPException(status_code=422, detail="GitHub scanner chỉ cho phép query liên quan prompt/skill/app factory để tránh scan rộng.")
    try:
        url = f"https://api.github.com/search/repositories?q={quote_plus(query)}&per_page={limit}"
        request = urllib.request.Request(url, headers={"User-Agent": "ForgeTrend-Scanner"})
        with urllib.request.urlopen(request, timeout=6) as response:
            data = json.loads(response.read().decode("utf-8"))
        items = []
        for repo in data.get("items", [])[:limit]:
            items.append(
                {
                    "title": repo.get("full_name") or repo.get("name") or "GitHub repository",
                    "source_url": repo.get("html_url"),
                    "summary": (repo.get("description") or "Repository discovered by controlled GitHub scan.")[:800],
                    "category": "github_repo",
                    "usefulness_score": min(90, 50 + int(repo.get("stargazers_count") or 0) // 50),
                    "metadata_json": {
                        "stars": repo.get("stargazers_count") or 0,
                        "language": repo.get("language"),
                        "safe_mode": "metadata_only",
                    },
                }
            )
        return items or fallback[:limit]
    except Exception as exc:
        item = dict(fallback[0])
        item["summary"] = f"GitHub scan fallback because live metadata fetch failed: {exc}"
        item["metadata_json"] = {"safe_mode": "fallback", "query": query, "error": str(exc)}
        return [item]


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="forge-trend-api")


@app.get("/doctor", response_model=DoctorResponse)
def doctor(db: Session = Depends(get_db)) -> DoctorResponse:
    return build_doctor_report(db)


@app.get("/config-profiles", response_model=list[ConfigProfileRead])
def list_config_profiles(db: Session = Depends(get_db)) -> list[ConfigProfileRead]:
    seed_default_config_profile(db)
    profiles = list(db.scalars(select(ConfigProfile).order_by(desc(ConfigProfile.is_default), desc(ConfigProfile.updated_at))).all())
    return [config_profile_read(db, item) for item in profiles]


@app.post("/config-profiles", response_model=ConfigProfileRead)
def create_config_profile(payload: ConfigProfileCreate, db: Session = Depends(get_db)) -> ConfigProfileRead:
    item = ConfigProfile(**payload.model_dump())
    if payload.is_default:
        set_config_profile_default(db, item)
    db.add(item)
    db.flush()
    provider = ProviderProfile(
        config_profile_id=item.id,
        name=item.model_provider,
        provider_type="openai_compatible",
        base_url="https://api.openai.com/v1",
        wire_api="responses",
        requires_openai_auth=True,
        enabled=True,
    )
    db.add(provider)
    db.flush()
    item.active_provider_profile_id = provider.id
    for plugin in BUILTIN_CONFIG_PLUGINS:
        db.add(ConfigPlugin(config_profile_id=item.id, **plugin, enabled=True))
    db.commit()
    db.refresh(item)
    return config_profile_read(db, item)


@app.get("/config-profiles/default/runtime", response_model=RuntimeConfigResponse)
def read_default_runtime_config(db: Session = Depends(get_db)) -> RuntimeConfigResponse:
    seed_builtin_skill_packs(db)
    return build_runtime_config(db)


@app.get("/config-profiles/{id}", response_model=ConfigProfileRead)
def get_config_profile(id: UUID, db: Session = Depends(get_db)) -> ConfigProfileRead:
    profile = get_or_404(db, ConfigProfile, id)
    return config_profile_read(db, profile)


@app.get("/config-profiles/{id}/runtime", response_model=RuntimeConfigResponse)
def read_runtime_config(id: UUID, db: Session = Depends(get_db)) -> RuntimeConfigResponse:
    seed_builtin_skill_packs(db)
    profile = get_or_404(db, ConfigProfile, id)
    return build_runtime_config(db, profile)


@app.patch("/config-profiles/{id}", response_model=ConfigProfileRead)
def patch_config_profile(id: UUID, payload: ConfigProfilePatch, db: Session = Depends(get_db)) -> ConfigProfileRead:
    profile = get_or_404(db, ConfigProfile, id)
    patch = payload.model_dump(exclude_unset=True)
    if patch.pop("is_default", None):
        set_config_profile_default(db, profile)
    for field, value in patch.items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return config_profile_read(db, profile)


@app.delete("/config-profiles/{id}", response_model=ActionResponse)
def delete_config_profile(id: UUID, db: Session = Depends(get_db)) -> ActionResponse:
    profile = get_or_404(db, ConfigProfile, id)
    db.query(FactoryBrief).filter(FactoryBrief.config_profile_id == id).update({FactoryBrief.config_profile_id: None}, synchronize_session=False)
    db.query(ProviderProfile).filter(ProviderProfile.config_profile_id == id).delete(synchronize_session=False)
    db.query(ConfigPlugin).filter(ConfigPlugin.config_profile_id == id).delete(synchronize_session=False)
    db.query(TrustedProject).filter(TrustedProject.config_profile_id == id).delete(synchronize_session=False)
    was_default = profile.is_default
    db.delete(profile)
    db.flush()
    if was_default:
        replacement = db.scalar(select(ConfigProfile).order_by(desc(ConfigProfile.updated_at)))
        if replacement:
            replacement.is_default = True
    db.commit()
    return ActionResponse(status="deleted", detail="Config profile deleted")


@app.post("/config-profiles/{id}/set-default", response_model=ConfigProfileRead)
def make_config_profile_default(id: UUID, db: Session = Depends(get_db)) -> ConfigProfileRead:
    profile = get_or_404(db, ConfigProfile, id)
    set_config_profile_default(db, profile)
    db.commit()
    db.refresh(profile)
    return config_profile_read(db, profile)


@app.post("/config-profiles/import-toml", response_model=ConfigProfileRead)
def import_config_profile_toml(payload: ConfigProfileImportPayload, db: Session = Depends(get_db)) -> ConfigProfileRead:
    profile = import_profile_from_toml(db, payload)
    return config_profile_read(db, profile)


@app.post("/config-profiles/{id}/import-toml", response_model=ConfigProfileRead)
def import_config_profile_toml_compat(id: UUID, payload: ConfigProfileImportPayload, db: Session = Depends(get_db)) -> ConfigProfileRead:
    get_or_404(db, ConfigProfile, id)
    profile = import_profile_from_toml(db, payload)
    return config_profile_read(db, profile)


@app.get("/config-profiles/{id}/export-toml", response_model=ConfigProfileExportResponse)
def export_config_profile(id: UUID, include_secrets: bool = False, db: Session = Depends(get_db)) -> ConfigProfileExportResponse:
    profile = get_or_404(db, ConfigProfile, id)
    toml_text = export_profile_toml(db, profile)
    if include_secrets:
        toml_text += "\n# include_secrets=true was requested, but ForgeTrend still exports api_key_ref only. Raw encrypted keys are never decrypted for TOML export.\n"
    return ConfigProfileExportResponse(config_profile_id=profile.id, toml_text=toml_text)


@app.post("/config-profiles/{id}/test", response_model=ActionResponse)
def test_config_profile(id: UUID, db: Session = Depends(get_db)) -> ActionResponse:
    profile = get_or_404(db, ConfigProfile, id)
    runtime = build_runtime_config(db, profile)
    provider = runtime.provider
    issues: list[str] = []
    if provider.get("requires_openai_auth") and not provider.get("api_key_id"):
        issues.append("provider requires auth but no dashboard API key is assigned")
    if profile.network_access not in {"enabled", "disabled", "restricted"}:
        issues.append("network_access should be enabled, disabled, or restricted")
    if profile.model_auto_compact_token_limit >= profile.model_context_window:
        issues.append("auto compact token limit should be lower than context window")
    status = "warning" if issues else "passed"
    detail = "; ".join(issues) if issues else f"Profile {profile.name} is locally valid. Secrets are redacted and provider base URL is configured."
    return ActionResponse(status=status, detail=detail)


@app.post("/config-profiles/{id}/provider-profiles", response_model=ProviderProfileRead)
def create_provider_profile(id: UUID, payload: ProviderProfileCreate, db: Session = Depends(get_db)) -> ProviderProfile:
    get_or_404(db, ConfigProfile, id)
    if payload.api_key_id:
        get_or_404(db, ApiKey, payload.api_key_id)
    item = ProviderProfile(config_profile_id=id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.patch("/provider-profiles/{id}", response_model=ProviderProfileRead)
def patch_provider_profile(id: UUID, payload: ProviderProfilePatch, db: Session = Depends(get_db)) -> ProviderProfile:
    item = get_or_404(db, ProviderProfile, id)
    patch = payload.model_dump(exclude_unset=True)
    if patch.get("api_key_id"):
        get_or_404(db, ApiKey, patch["api_key_id"])
    for field, value in patch.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@app.delete("/provider-profiles/{id}", response_model=ActionResponse)
def delete_provider_profile(id: UUID, db: Session = Depends(get_db)) -> ActionResponse:
    item = get_or_404(db, ProviderProfile, id)
    db.query(ConfigProfile).filter(ConfigProfile.active_provider_profile_id == id).update({ConfigProfile.active_provider_profile_id: None}, synchronize_session=False)
    db.delete(item)
    db.commit()
    return ActionResponse(status="deleted", detail="Provider profile deleted")


@app.post("/config-profiles/{id}/plugins", response_model=ConfigPluginRead)
def create_config_plugin(id: UUID, payload: ConfigPluginCreate, db: Session = Depends(get_db)) -> ConfigPlugin:
    get_or_404(db, ConfigProfile, id)
    item = ConfigPlugin(config_profile_id=id, **payload.model_dump())
    db.add(item)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Plugin already exists in this profile") from exc
    db.refresh(item)
    return item


@app.patch("/config-plugins/{id}", response_model=ConfigPluginRead)
def patch_config_plugin(id: UUID, payload: ConfigPluginPatch, db: Session = Depends(get_db)) -> ConfigPlugin:
    item = get_or_404(db, ConfigPlugin, id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@app.delete("/config-plugins/{id}", response_model=ActionResponse)
def delete_config_plugin(id: UUID, db: Session = Depends(get_db)) -> ActionResponse:
    item = get_or_404(db, ConfigPlugin, id)
    db.delete(item)
    db.commit()
    return ActionResponse(status="deleted", detail="Config plugin deleted")


@app.post("/config-profiles/{id}/trusted-projects", response_model=TrustedProjectRead)
def create_trusted_project(id: UUID, payload: TrustedProjectCreate, db: Session = Depends(get_db)) -> TrustedProject:
    get_or_404(db, ConfigProfile, id)
    item = TrustedProject(config_profile_id=id, **payload.model_dump())
    db.add(item)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Project path already exists in this profile") from exc
    db.refresh(item)
    return item


@app.patch("/trusted-projects/{id}", response_model=TrustedProjectRead)
def patch_trusted_project(id: UUID, payload: TrustedProjectPatch, db: Session = Depends(get_db)) -> TrustedProject:
    item = get_or_404(db, TrustedProject, id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@app.delete("/trusted-projects/{id}", response_model=ActionResponse)
def delete_trusted_project(id: UUID, db: Session = Depends(get_db)) -> ActionResponse:
    item = get_or_404(db, TrustedProject, id)
    db.delete(item)
    db.commit()
    return ActionResponse(status="deleted", detail="Trusted project deleted")


@app.get("/skill-packs", response_model=list[SkillPackRead])
@app.get("/skills/packs", response_model=list[SkillPackRead])
def list_skill_packs(db: Session = Depends(get_db)) -> list[SkillPackRead]:
    seed_builtin_skill_packs(db)
    packs = list(db.scalars(select(SkillPack).order_by(SkillPack.category, desc(SkillPack.quality_score), SkillPack.name)).all())
    return [skill_pack_read(db, item) for item in packs]


@app.post("/skill-packs/scan-installed", response_model=list[SkillPackRead])
def scan_installed_skill_packs(db: Session = Depends(get_db)) -> list[SkillPackRead]:
    seed_builtin_skill_packs(db)
    skills_dir = REPO_ROOT / "skills"
    if skills_dir.exists():
        for skill_file in skills_dir.glob("*/skill.toml"):
            try:
                parsed = tomllib.loads(skill_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            slug = str(parsed.get("slug") or skill_file.parent.name)
            pack = db.scalar(select(SkillPack).where(SkillPack.slug == slug))
            if not pack:
                pack = SkillPack(
                    name=str(parsed.get("name") or slug.replace("_", " ").title()),
                    slug=slug,
                    category=str(parsed.get("category") or "imported"),
                    description=str(parsed.get("description") or ""),
                    version=str(parsed.get("version") or "1.0.0"),
                    token_budget=int(parsed.get("token_budget") or 1000),
                    source_type="local_folder",
                    local_path=str(skill_file.parent),
                    enabled=True,
                )
                db.add(pack)
                db.flush()
            pack.local_path = str(skill_file.parent)
            pack.description = str(parsed.get("description") or pack.description or "")
            prompts = parsed.get("prompts") or {}
            for prompt_name, prompt_value in prompts.items():
                if not isinstance(prompt_value, dict):
                    continue
                prompt = db.scalar(select(SkillPrompt).where(SkillPrompt.skill_pack_id == pack.id, SkillPrompt.name == str(prompt_name)))
                if not prompt:
                    prompt_path = skill_file.parent / "prompts" / f"{prompt_name}.md"
                    template = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else str(prompt_value.get("prompt_template") or "")
                    db.add(
                        SkillPrompt(
                            skill_pack_id=pack.id,
                            name=str(prompt_name),
                            purpose=str(prompt_value.get("purpose") or ""),
                            when_to_use=str(prompt_value.get("when_to_use") or ""),
                            prompt_template=template,
                            token_budget=int(prompt_value.get("token_budget") or parsed.get("token_budget") or 1000),
                        )
                    )
        db.commit()
    packs = list(db.scalars(select(SkillPack).order_by(SkillPack.category, SkillPack.name)).all())
    return [skill_pack_read(db, item) for item in packs]


@app.get("/skill-packs/{id}", response_model=SkillPackRead)
def get_skill_pack(id: UUID, db: Session = Depends(get_db)) -> SkillPackRead:
    pack = get_or_404(db, SkillPack, id)
    return skill_pack_read(db, pack)


@app.patch("/skill-packs/{id}", response_model=SkillPackRead)
def patch_skill_pack(id: UUID, payload: SkillPackPatch, db: Session = Depends(get_db)) -> SkillPackRead:
    pack = get_or_404(db, SkillPack, id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(pack, field, value)
    db.commit()
    db.refresh(pack)
    return skill_pack_read(db, pack)


@app.post("/skill-packs/{id}/test", response_model=SkillTestResponse)
def test_skill_pack(id: UUID, payload: SkillTestPayload, db: Session = Depends(get_db)) -> SkillTestResponse:
    pack = get_or_404(db, SkillPack, id)
    prompt = db.scalar(select(SkillPrompt).where(SkillPrompt.skill_pack_id == pack.id).order_by(SkillPrompt.name))
    if not prompt:
        raise HTTPException(status_code=404, detail="Skill pack has no prompts")
    rendered = prompt.prompt_template
    for key, value in payload.sample_input.items():
        rendered = rendered.replace("{{" + str(key) + "}}", str(value))
    return SkillTestResponse(skill_pack_id=pack.id, rendered_prompt=rendered, estimated_tokens=max(1, len(rendered.split())))


@app.post("/internal/skill-runs", response_model=ActionResponse)
def record_skill_run(payload: dict, db: Session = Depends(get_db)) -> ActionResponse:
    skill_slug = str(payload.get("skill_slug") or "")
    pack = db.scalar(select(SkillPack).where(SkillPack.slug == skill_slug))
    if not pack:
        return ActionResponse(status="skipped", detail=f"Unknown skill {skill_slug}")
    db.add(
        SkillRun(
            skill_pack_id=pack.id,
            project_id=UUID(str(payload["project_id"])) if payload.get("project_id") else None,
            factory_brief_id=UUID(str(payload["factory_brief_id"])) if payload.get("factory_brief_id") else None,
            agent_name=str(payload.get("agent_name") or "autopilot"),
            input_hash=str(payload.get("input_hash") or ""),
            output_summary=str(payload.get("output_summary") or ""),
            tokens_estimated=int(payload.get("tokens_estimated") or 0),
            status=str(payload.get("status") or "used"),
        )
    )
    score = db.scalar(select(SkillScore).where(SkillScore.skill_pack_id == pack.id))
    if score:
        score.success_count += 1 if payload.get("status") in {None, "used", "succeeded"} else 0
        score.failure_count += 1 if payload.get("status") == "failed" else 0
        if payload.get("quality_delta") is not None:
            delta = int(payload.get("quality_delta") or 0)
            score.avg_quality_delta = int(round((score.avg_quality_delta + delta) / 2)) if score.success_count + score.failure_count > 1 else delta
        if payload.get("tokens_saved") is not None:
            tokens_saved = int(payload.get("tokens_saved") or 0)
            score.avg_tokens_saved = int(round((score.avg_tokens_saved + tokens_saved) / 2)) if score.success_count + score.failure_count > 1 else tokens_saved
        score.last_used_at = datetime.now(UTC)
    db.commit()
    return ActionResponse(status="recorded", detail=f"Skill run recorded for {skill_slug}")


@app.get("/skill-runs", response_model=list[SkillRunRead])
def list_skill_runs(
    project_id: UUID | None = None,
    factory_brief_id: UUID | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[SkillRun]:
    query = select(SkillRun).order_by(desc(SkillRun.created_at)).limit(min(max(limit, 1), 500))
    if project_id:
        query = select(SkillRun).where(SkillRun.project_id == project_id).order_by(desc(SkillRun.created_at)).limit(min(max(limit, 1), 500))
    if factory_brief_id:
        query = select(SkillRun).where(SkillRun.factory_brief_id == factory_brief_id).order_by(desc(SkillRun.created_at)).limit(min(max(limit, 1), 500))
    return list(db.scalars(query).all())


@app.get("/run-profiles", response_model=list[RunProfileRead])
def list_run_profiles(db: Session = Depends(get_db)) -> list[RunProfile]:
    seed_builtin_skill_packs(db)
    seed_run_profiles(db)
    return list(db.scalars(select(RunProfile).where(RunProfile.enabled.is_(True)).order_by(RunProfile.name)).all())


@app.post("/scan/runs", response_model=ScanRunDetail)
def create_source_scan(payload: SourceScanCreate, db: Session = Depends(get_db)) -> ScanRunDetail:
    allowed_types = {"github_search", "github_repo", "web_url"}
    if payload.source_type not in allowed_types:
        raise HTTPException(status_code=422, detail=f"source_type must be one of {', '.join(sorted(allowed_types))}")
    if len(payload.query.strip()) < 4:
        raise HTTPException(status_code=422, detail="Scan query is too short.")
    scan = SourceScanRun(source_type=payload.source_type, query=payload.query, status="completed", finished_at=datetime.now(UTC))
    db.add(scan)
    db.flush()
    item_payloads = source_items_for_query(payload.source_type, payload.query, payload.limit)
    items: list[SourceItem] = []
    for item_payload in item_payloads:
        item = SourceItem(scan_run_id=scan.id, source_type=payload.source_type, status="quarantined", **item_payload)
        db.add(item)
        items.append(item)
    scan.summary = f"{len(items)} item(s) discovered and quarantined. External text/config must be reviewed before enabling."
    db.commit()
    db.refresh(scan)
    return ScanRunDetail.model_validate(scan).model_copy(update={"items": [SourceItemRead.model_validate(item) for item in items]})


@app.get("/scan/runs", response_model=list[SourceScanRunRead])
def list_source_scans(db: Session = Depends(get_db)) -> list[SourceScanRun]:
    return list(db.scalars(select(SourceScanRun).order_by(desc(SourceScanRun.created_at)).limit(50)).all())


@app.get("/source-items", response_model=list[SourceItemRead])
def list_source_items(status: str | None = None, db: Session = Depends(get_db)) -> list[SourceItem]:
    query = select(SourceItem).order_by(desc(SourceItem.created_at)).limit(100)
    if status:
        query = select(SourceItem).where(SourceItem.status == status).order_by(desc(SourceItem.created_at)).limit(100)
    return list(db.scalars(query).all())


@app.patch("/source-items/{id}", response_model=SourceItemRead)
def patch_source_item(id: UUID, payload: SourceItemPatch, db: Session = Depends(get_db)) -> SourceItem:
    item = get_or_404(db, SourceItem, id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@app.post("/source-items/{id}/convert-to-skill", response_model=SkillPackRead)
def convert_source_item_to_skill(id: UUID, db: Session = Depends(get_db)) -> SkillPackRead:
    item = get_or_404(db, SourceItem, id)
    if item.status not in {"reviewed", "approved"}:
        raise HTTPException(status_code=409, detail="Source item must be reviewed before conversion. External code is never executed.")
    slug = slugify(item.title)[:120] or f"source-skill-{item.id}"
    slug = slug.replace("-", "_")
    existing = db.scalar(select(SkillPack).where(SkillPack.slug == slug))
    if existing:
        return skill_pack_read(db, existing)
    pack = SkillPack(
        name=item.title[:255],
        slug=slug,
        category=item.category or "external_prompt",
        description=item.summary,
        enabled=False,
        source_type="external_quarantined",
        source_url=item.source_url,
        quality_score=item.usefulness_score,
        token_budget=1000,
    )
    db.add(pack)
    db.flush()
    db.add(
        SkillPrompt(
            skill_pack_id=pack.id,
            name="review_before_use",
            purpose="Quarantined external prompt candidate. Review and rewrite before enabling.",
            when_to_use="Never auto-use before human review.",
            prompt_template=f"Source summary only. Do not execute code.\n\n{item.summary}",
            token_budget=500,
        )
    )
    item.status = "reviewed"
    db.commit()
    db.refresh(pack)
    return skill_pack_read(db, pack)


@app.get("/prompt-context/summary", response_model=PromptContextSummary)
def prompt_context_summary(db: Session = Depends(get_db)) -> PromptContextSummary:
    seed_prompt_fragments(db)
    fragments = list(db.scalars(select(PromptFragment).order_by(PromptFragment.category, PromptFragment.slug)).all())
    packs = list(db.scalars(select(ContextPack).order_by(desc(ContextPack.updated_at)).limit(20)).all())
    fragment_payloads = [
        {"slug": item.slug, "category": item.category, "token_estimate": item.token_estimate, "summary": item.content[:160]}
        for item in fragments
    ]
    pack_payloads = [
        {"pack_type": item.pack_type, "token_estimate": item.token_estimate, "important_files": item.important_files, "summary": item.summary[:240]}
        for item in packs
    ]
    total = sum(item["token_estimate"] for item in fragment_payloads) + sum(item["token_estimate"] for item in pack_payloads)
    return PromptContextSummary(
        prompt_fragments=fragment_payloads,
        context_packs=pack_payloads,
        token_budget_decision={
            "estimated_reusable_tokens": total,
            "policy": "Use only needed skill prompts and compressed context packs before agent calls.",
        },
    )


@app.post("/internal/context-packs", response_model=ContextPackRead)
def create_context_pack(payload: ContextPackCreate, db: Session = Depends(get_db)) -> ContextPack:
    existing = db.scalar(
        select(ContextPack).where(
            ContextPack.project_id == payload.project_id,
            ContextPack.factory_brief_id == payload.factory_brief_id,
            ContextPack.pack_type == payload.pack_type,
            ContextPack.full_text_hash == payload.full_text_hash,
        )
    )
    if existing:
        existing.summary = payload.summary
        existing.important_files = payload.important_files
        existing.token_estimate = payload.token_estimate
        db.commit()
        db.refresh(existing)
        return existing
    item = ContextPack(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.get("/learning/rules", response_model=list[LearningRuleRead])
def list_learning_rules(db: Session = Depends(get_db)) -> list[LearningRule]:
    return list(db.scalars(select(LearningRule).order_by(desc(LearningRule.enabled), desc(LearningRule.confidence_score), LearningRule.rule_key)).all())


@app.post("/internal/learning/applicable-rules")
def read_applicable_learning_rules(payload: dict, db: Session = Depends(get_db)) -> list[dict]:
    return applicable_learning_rules(db, payload or {}, limit=20)


@app.patch("/learning/rules/{id}", response_model=LearningRuleRead)
def patch_learning_rule(id: UUID, payload: LearningRulePatch, db: Session = Depends(get_db)) -> LearningRule:
    rule = get_or_404(db, LearningRule, id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    db.commit()
    db.refresh(rule)
    return rule


def provider_endpoint(base_url: str, wire_api: str) -> str:
    base = base_url.rstrip("/")
    if wire_api == "chat_completions":
        return base if base.endswith("/chat/completions") else f"{base}/chat/completions"
    return base if base.endswith("/responses") else f"{base}/responses"


def extract_provider_text(payload: dict, wire_api: str) -> str:
    if wire_api == "chat_completions":
        return str((((payload.get("choices") or [{}])[0].get("message") or {}).get("content")) or "")
    if payload.get("output_text"):
        return str(payload["output_text"])
    chunks: list[str] = []
    for item in payload.get("output") or []:
        for content in item.get("content") or []:
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                chunks.append(str(content["text"]))
    return "\n".join(chunks).strip()


@app.post("/internal/provider-completion", response_model=ProviderCompletionResponse)
def provider_completion(payload: ProviderCompletionRequest, db: Session = Depends(get_db)) -> ProviderCompletionResponse:
    profile = db.get(ConfigProfile, payload.config_profile_id) if payload.config_profile_id else seed_default_config_profile(db)
    if not profile:
        raise HTTPException(status_code=404, detail="Config profile not found")
    runtime_snapshot = payload.runtime_config_snapshot or {}
    runtime = runtime_snapshot or build_runtime_config(db, profile).model_dump(mode="json")
    applied_rules = runtime.get("applied_learning_rules") or []
    if any((rule.get("action_json") or {}).get("provider") == "deterministic" for rule in applied_rules):
        return ProviderCompletionResponse(status="skipped", provider="deterministic", model=str(runtime.get("model") or profile.model), text="", detail="Learning rule requested deterministic provider fallback.", tokens_estimated=max(1, len(payload.prompt.split())))
    provider_payload = runtime.get("provider") or {}
    provider_id = provider_payload.get("id")
    provider = db.get(ProviderProfile, UUID(str(provider_id))) if provider_id else None
    model_name = str(runtime.get("model") or profile.model)
    network_access = str(runtime.get("network_access") or profile.network_access)
    disable_storage = bool(runtime.get("disable_response_storage", profile.disable_response_storage))
    if not provider or not provider.enabled:
        return ProviderCompletionResponse(status="skipped", provider="deterministic", model=model_name, text="", detail="No enabled provider profile.", tokens_estimated=0)
    if provider.provider_type not in {"openai_compatible", "openai"}:
        return ProviderCompletionResponse(status="skipped", provider=provider.provider_type, model=model_name, text="", detail="Provider type is handled by worker runtime, not API completion.", tokens_estimated=0)
    if network_access == "disabled":
        return ProviderCompletionResponse(status="skipped", provider=provider.name, model=model_name, text="", detail="Network access is disabled for this config profile.", tokens_estimated=0)
    if not provider.api_key_id:
        return ProviderCompletionResponse(status="skipped", provider=provider.name, model=model_name, text="", detail="No API key assigned to provider profile.", tokens_estimated=0)
    api_key = db.get(ApiKey, provider.api_key_id)
    if not api_key or api_key.status != "active":
        return ProviderCompletionResponse(status="skipped", provider=provider.name, model=model_name, text="", detail="Assigned API key is not active.", tokens_estimated=0)
    raw_key = decrypt_secret(api_key.encrypted_key)
    endpoint = provider_endpoint(provider.base_url, provider.wire_api)
    if provider.wire_api == "chat_completions":
        body = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "You are assisting ForgeTrend. Return concise, directly usable text. Never include secrets."},
                {"role": "user", "content": payload.prompt},
            ],
            "max_tokens": payload.max_output_tokens,
        }
    else:
        body = {
            "model": model_name,
            "input": payload.prompt,
            "max_output_tokens": payload.max_output_tokens,
            "store": not disable_storage,
        }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {raw_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
        text = extract_provider_text(response_payload, provider.wire_api)
        api_key.last_used_at = datetime.now(UTC)
        db.commit()
        return ProviderCompletionResponse(
            status="completed" if text else "empty",
            provider=provider.name,
            model=model_name,
            text=redact(text) or "",
            detail="Provider completion succeeded; secrets were redacted.",
            tokens_estimated=max(1, len(payload.prompt.split()) + len((text or "").split())),
        )
    except Exception as exc:
        return ProviderCompletionResponse(status="failed", provider=provider.name, model=model_name, text="", detail=redact(str(exc)) or "Provider completion failed", tokens_estimated=max(1, len(payload.prompt.split())))


@app.get("/providers/status", response_model=list[ProviderStatus])
def provider_status(db: Session = Depends(get_db)) -> list[ProviderStatus]:
    codex_available = shutil.which("codex") is not None
    aider_available = shutil.which("aider") is not None
    codex_auth_ok = False
    codex_auth_detail = "not installed"
    if codex_available:
      codex_auth_ok, codex_auth_detail = run_check(["codex", "login", "status"], timeout=8)
    evaluations = list(db.scalars(select(RunEvaluation).order_by(desc(RunEvaluation.created_at)).limit(200)).all())

    def last(provider: str, success: bool) -> datetime | None:
        for item in evaluations:
            if item.provider == provider and ((item.final_status == "release_candidate") == success):
                return item.created_at
        return None

    return [
        ProviderStatus(
            id="codex_cli",
            name="Codex CLI",
            enabled=settings.worker_enable_codex,
            available=codex_available,
            auth_status="authenticated" if codex_auth_ok else codex_auth_detail,
            current_model=settings.worker_codex_model or None,
            last_success=last("codex_cli", True),
            last_failure=last("codex_cli", False),
            recommended_action="Sẵn sàng dùng coding pass." if codex_auth_ok else "Cài Codex CLI và chạy codex login, hoặc dùng deterministic fallback.",
        ),
        ProviderStatus(
            id="aider_cli",
            name="Aider CLI",
            enabled=False,
            available=aider_available,
            auth_status="optional",
            last_success=last("aider", True),
            last_failure=last("aider", False),
            recommended_action="Tuỳ chọn refinement pass; không bắt buộc.",
        ),
        ProviderStatus(
            id="deterministic",
            name="Deterministic generator",
            enabled=True,
            available=True,
            auth_status="not required",
            last_success=last("deterministic", True),
            last_failure=last("deterministic", False),
            recommended_action="Dùng cho smoke run, fallback và máy chưa có LLM provider.",
        ),
    ]


@app.get("/plugins/registry", response_model=list[PluginStatus])
def plugin_registry() -> list[PluginStatus]:
    missing_by_id = {
        "codex_cli": [] if shutil.which("codex") else ["codex CLI not found"],
        "aider_cli": [] if shutil.which("aider") else ["aider CLI not found"],
        "web_research": [] if settings.research_allowed_urls.strip() else ["RESEARCH_ALLOWED_URLS not configured"],
    }
    return [
        PluginStatus(**item, missing_dependencies=missing_by_id.get(item["id"], []))
        for item in PLUGINS
    ]


@app.get("/queues/summary", response_model=QueueSummary)
def queue_summary(db: Session = Depends(get_db)) -> QueueSummary:
    projects = list(db.scalars(select(Project)).all())
    briefs = list(db.scalars(select(FactoryBrief)).all())
    failed = [item for item in projects if item.status in {"failed", "NEEDS_HUMAN_REVIEW"}]
    running = [item for item in projects if item.status in {"queued", "running", "stop_requested"}]
    return QueueSummary(
        factory_brief_queue=sum(1 for item in briefs if item.status in {"queued", "researching", "scoring_candidates"}),
        project_pipeline_queue=sum(1 for item in projects if item.status == "queued"),
        running_jobs=len(running),
        retryable_jobs=sum(1 for item in failed if item.status == "NEEDS_HUMAN_REVIEW"),
        failed_jobs=len(failed),
        dead_letter_jobs=sum(1 for item in projects if item.status == "failed"),
        next_action="Review NEEDS_HUMAN_REVIEW projects or keep worker running.",
    )


@app.get("/learning/summary", response_model=LearningSummary)
def learning_summary(db: Session = Depends(get_db)) -> LearningSummary:
    evaluations = list(db.scalars(select(RunEvaluation).order_by(desc(RunEvaluation.created_at)).limit(500)).all())
    failures = list(db.scalars(select(FailurePattern).order_by(desc(FailurePattern.count), desc(FailurePattern.updated_at)).limit(10)).all())
    rules = list(db.scalars(select(LearningRule).where(LearningRule.enabled.is_(True)).order_by(desc(LearningRule.confidence_score)).limit(20)).all())
    total = len(evaluations)
    average = round(sum(item.quality_score for item in evaluations) / total, 1) if total else 0.0
    provider_success: dict[str, dict[str, int]] = {}
    archetype_values: dict[str, list[int]] = {}
    for item in evaluations:
        provider_bucket = provider_success.setdefault(item.provider, {"success": 0, "failure": 0})
        provider_bucket["success" if item.final_status == "release_candidate" else "failure"] += 1
        if item.archetype:
            archetype_values.setdefault(item.archetype, []).append(item.quality_score)
    return LearningSummary(
        average_quality_score=average,
        total_runs=total,
        release_candidates=sum(1 for item in evaluations if item.final_status == "release_candidate"),
        needs_human_review=sum(1 for item in evaluations if item.final_status == "NEEDS_HUMAN_REVIEW"),
        common_failures=[FailurePatternRead.model_validate(item) for item in failures],
        active_rules=[LearningRuleRead.model_validate(item) for item in rules],
        provider_success=provider_success,
        archetype_scores={key: round(sum(values) / len(values), 1) for key, values in archetype_values.items() if values},
    )


@app.post("/internal/learning/run-evaluations", response_model=RunEvaluationRead)
def create_run_evaluation(payload: RunEvaluationCreate, db: Session = Depends(get_db)) -> RunEvaluation:
    evaluation = RunEvaluation(**payload.model_dump())
    db.add(evaluation)
    db.flush()
    record_learning_from_evaluation(db, evaluation)
    db.commit()
    db.refresh(evaluation)
    return evaluation


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
    seed_builtin_skill_packs(db)
    seed_run_profiles(db)
    data = payload.model_dump()
    run_profile_slug = data.get("run_profile_slug")
    profile: ConfigProfile | None = None
    if data.get("config_profile_id"):
        profile = get_or_404(db, ConfigProfile, data["config_profile_id"])
    elif run_profile_slug:
        run_profile = db.scalar(select(RunProfile).where(RunProfile.slug == run_profile_slug, RunProfile.enabled.is_(True)))
        if run_profile and run_profile.config_profile_id:
            profile = db.get(ConfigProfile, run_profile.config_profile_id)
        if run_profile:
            data["quality_threshold"] = run_profile.quality_threshold
    profile = profile or seed_default_config_profile(db)
    data["config_profile_id"] = profile.id
    data["runtime_config_snapshot_json"] = runtime_config_snapshot(db, profile, brief_learning_context(data))
    applied_rules = data["runtime_config_snapshot_json"].get("applied_learning_rules") or []
    for rule in applied_rules:
        action = rule.get("action_json") or {}
        threshold_min = action.get("quality_threshold_min")
        if isinstance(threshold_min, int):
            data["quality_threshold"] = max(int(data.get("quality_threshold") or 0), threshold_min)
    item = FactoryBrief(**data, status="draft")
    db.add(item)
    db.flush()
    factory_brief_event(
        db,
        item,
        level="info",
        title="brief_created",
        message=f"{item.title} is ready to start.",
        metadata_json={
            "step": "brief_created",
            "config_profile_id": str(profile.id),
            "config_profile_name": profile.name,
            "run_profile_slug": run_profile_slug,
            "model": item.runtime_config_snapshot_json.get("model"),
            "applied_learning_rules": [rule.get("rule_key") for rule in applied_rules],
        },
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
    queue = enqueue_factory_brief(brief.id, requires_codex_worker=runtime_requires_codex_worker(brief.runtime_config_snapshot_json))
    factory_brief_event(
        db,
        brief,
        level="info",
        title="brief_queued",
        message=f"{brief.title} was queued for autonomous research and project creation.",
        metadata_json={"step": "brief_queued"},
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


@app.post("/internal/factory-briefs/{id}/events", response_model=NotificationRead)
def create_factory_brief_event(id: UUID, payload: FactoryBriefEventCreate, db: Session = Depends(get_db)) -> Notification:
    brief = get_or_404(db, FactoryBrief, id)
    notification = factory_brief_event(
        db,
        brief,
        level=payload.level,
        title=payload.title,
        message=payload.message,
        metadata_json=payload.metadata_json,
    )
    db.commit()
    db.refresh(notification)
    return notification


@app.get("/factory-briefs/{id}/events", response_model=list[NotificationRead])
def list_factory_brief_events(id: UUID, db: Session = Depends(get_db)) -> list[Notification]:
    get_or_404(db, FactoryBrief, id)
    return list(
        db.scalars(
            select(Notification)
            .where(Notification.entity_type == "factory_brief", Notification.entity_id == id)
            .order_by(desc(Notification.created_at))
        ).all()
    )


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
            queue = enqueue_pipeline(project.id, requires_codex_worker=runtime_requires_codex_worker(brief.runtime_config_snapshot_json))
            db.add(AgentEvent(project_id=project.id, step="factory_brief", level="info", message="Existing factory project queued again"))
            factory_brief_event(
                db,
                brief,
                level="info",
                title="pipeline_queued",
                message=f"{project.name} was queued again from this factory brief.",
                metadata_json={"step": "pipeline_queued", "project_id": str(project.id), "queue": queue},
            )
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
            "iap_plan_json": candidate.iap_plan_json,
            "subscription_plan_json": candidate.subscription_plan_json,
            "backend_plan_json": candidate.backend_plan_json,
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
        (
            "Run product quality gate",
            "Check product specificity, localization, minimum functionality, reports, and store-readiness blockers.",
            "quality_gate_agent",
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
    factory_brief_event(
        db,
        brief,
        level="success",
        title="project_created",
        message=f"{project.name} was created and linked to this brief.",
        metadata_json={"step": "project_created", "project_id": str(project.id), "candidate_id": str(candidate.id)},
    )
    factory_brief_event(
        db,
        brief,
        level="info",
        title="project_tasks_created",
        message=f"{len(task_specs)} project task(s) were created for the factory pipeline.",
        metadata_json={"step": "project_tasks_created", "project_id": str(project.id), "task_count": len(task_specs)},
    )
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
        queue = enqueue_pipeline(project.id, requires_codex_worker=runtime_requires_codex_worker(brief.runtime_config_snapshot_json))
        db.add(AgentEvent(project_id=project.id, step="factory_brief", level="info", message="Project created from factory brief and pipeline queued"))
        factory_brief_event(
            db,
            brief,
            level="info",
            title="pipeline_queued",
            message=f"{project.name} was queued on {queue}.",
            metadata_json={"step": "pipeline_queued", "project_id": str(project.id), "queue": queue},
        )
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
    return refresh_worker_statuses(db, workers)


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
    queue = enqueue_pipeline(project.id, requires_codex_worker=project_requires_codex_worker(db, project))
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
    queue = enqueue_pipeline(project.id, requires_codex_worker=project_requires_codex_worker(db, project))
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
    queue = enqueue_pipeline(project.id, requires_codex_worker=project_requires_codex_worker(db, project))
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


@app.post("/projects/{id}/internal-test-package", response_model=ArtifactRead)
def create_internal_test_package(id: UUID, db: Session = Depends(get_db)) -> Artifact:
    project = get_or_404(db, Project, id)
    artifacts = list(db.scalars(select(Artifact).where(Artifact.project_id == id).order_by(desc(Artifact.created_at))).all())
    workspace = Path(project.workspace_path or settings.local_artifact_root or "workspaces").resolve()
    package_dir = workspace / "artifacts" / "internal_test_package"
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True, exist_ok=True)

    apk = next((item for item in artifacts if item.kind == "build" or item.name.endswith(".apk")), None)
    source = next((item for item in artifacts if item.kind == "source"), None)
    by_name = {item.name: item for item in artifacts}
    blockers: list[str] = []

    if apk and Path(apk.path).exists():
        shutil.copy2(apk.path, package_dir / "app-debug.apk")
    else:
        blockers.append("Chưa có APK debug để test nội bộ.")

    (package_dir / "source_path.txt").write_text(source.path if source else "chưa có source artifact", encoding="utf-8")
    for report_name in [
        "factory_run_report.vi.md",
        "product_score_report.vi.md",
        "quality_gate_report.md",
        "store_readiness_report.md",
    ]:
        artifact = by_name.get(report_name)
        if artifact and Path(artifact.path).exists():
            shutil.copy2(artifact.path, package_dir / report_name)
        else:
            blockers.append(f"Thiếu report: {report_name}")
    store_assets = by_name.get("store_assets")
    if store_assets and Path(store_assets.path).exists() and Path(store_assets.path).is_dir():
        shutil.copytree(store_assets.path, package_dir / "store_assets")
    else:
        (package_dir / "store_assets").mkdir(exist_ok=True)
        copied_assets = 0
        for asset in [item for item in artifacts if item.kind == "store_asset" and Path(item.path).exists()]:
            shutil.copy2(asset.path, package_dir / "store_assets" / Path(asset.path).name)
            copied_assets += 1
        if not copied_assets:
            blockers.append("Thiếu thư mục store_assets hoặc chưa tạo draft store assets.")

    readme = [
        "# Hướng dẫn tester nội bộ",
        "",
        f"App: {project.name}",
        "",
        "## Cách dùng",
        "- Cài `app-debug.apk` trên thiết bị Android test.",
        "- Đọc QA, quality, store readiness và privacy checklist trước khi gửi feedback.",
        "- Không publish production từ gói này.",
        "",
        f"Source: {source.path if source else 'chưa có'}",
        "Report chính: factory_run_report.vi.md",
        "Blocker chính: RELEASE_BLOCKERS.vi.md",
    ]
    (package_dir / "README_FOR_TESTER.vi.md").write_text("\n".join(readme), encoding="utf-8")
    (package_dir / "PRIVACY_REVIEW_CHECKLIST.vi.md").write_text(
        "\n".join([
            "# Privacy Review Checklist",
            "",
            "- Có policy draft chưa?",
            "- Có API key hoặc secret hardcode không?",
            "- Có analytics/ads production chưa được khai báo không?",
            "- Billing thật đã được con người cấu hình và test chưa?",
        ]),
        encoding="utf-8",
    )
    (package_dir / "SCREENSHOT_PLAN.md").write_text(
        "\n".join(["# Screenshot Plan", "1. Onboarding", "2. Home dashboard", "3. Core feature", "4. Progress/history", "5. Settings/privacy/paywall"]),
        encoding="utf-8",
    )
    blockers.append("Human approval required before production release.")
    release_blockers = "\n".join(["# Release blockers", "", *[f"- {item}" for item in blockers]])
    (package_dir / "RELEASE_BLOCKERS.vi.md").write_text(release_blockers, encoding="utf-8")
    (package_dir / "RELEASE_BLOCKERS.md").write_text(release_blockers, encoding="utf-8")

    zip_path = package_dir.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in package_dir.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(package_dir.parent))

    artifact = Artifact(
        project_id=id,
        kind="internal_test_package",
        name="internal_test_package",
        path=str(package_dir),
        metadata_json={"apk": bool(apk and Path(apk.path).exists()), "source": source.path if source else None, "zip_path": str(zip_path), "human_approval_required": True},
    )
    db.add(artifact)
    create_notification(db, level="success", title="Internal test package created", message=f"Gói test nội bộ đã sẵn sàng cho {project.name}.", entity_type="project", entity_id=project.id)
    db.commit()
    db.refresh(artifact)
    return artifact


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
