import json
import shutil
import time
from pathlib import Path
from typing import Any

from daemon.api import FactoryApi
from daemon.autopilot import autopilot_decision, build_run_evaluation
from daemon.autopilot.policies import MAX_POLICY_FIX_ITERATIONS, MAX_QUALITY_FIX_ITERATIONS
from daemon.config import settings
from daemon.config_profile_resolver import config_summary, sanitized_runtime_config
from daemon.cost_guard import check_cost_limit
from daemon.prompt_planner import plan_context_pack, skill_prompt_header
from daemon.provider_adapters import ADAPTERS, ProviderUnavailable, run_codex_cli
from daemon.quality_gate import build_quality_gate_result, quality_gate_report_markdown, store_readiness_report_markdown
from daemon.research.providers import build_research_bundle
from daemon.safety import run_safe
from daemon.app_archetypes import ARCHETYPES, choose_archetype
from daemon.skills import select_skills


REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_ROOT = REPO_ROOT / "templates" / "flutter_mobile_app"


class PipelineStopped(RuntimeError):
    pass


def slug_to_title(slug: str) -> str:
    return " ".join(word.capitalize() for word in slug.replace("_", "-").split("-") if word)


class PipelineContext:
    def __init__(
        self,
        api: FactoryApi,
        project: dict[str, Any],
        workspace: Path,
        idea: dict[str, Any] | None,
        tasks: list[dict[str, Any]] | None = None,
        runtime_config: dict[str, Any] | None = None,
        selected_skills: list[dict[str, Any]] | None = None,
    ) -> None:
        self.api = api
        self.project = project
        self.project_id = project["id"]
        self.workspace = workspace
        self.idea = idea
        self.tasks_by_agent = {task["agent_name"]: task for task in (tasks or [])}
        self.runtime_config = runtime_config or {}
        self.selected_skills = selected_skills or []

    @property
    def app_dir(self) -> Path:
        return self.workspace / "app"

    @property
    def docs_dir(self) -> Path:
        return self.workspace / "docs"

    @property
    def artifacts_dir(self) -> Path:
        return self.workspace / "artifacts"

    def event(self, step: str, message: str, **kwargs: Any) -> None:
        self.api.event(self.project_id, step, message, **kwargs)

    def update_task(self, agent_name: str, payload: dict[str, Any]) -> None:
        task = self.tasks_by_agent.get(agent_name)
        if not task:
            return
        updated = self.api.update_project_task(task["id"], payload)
        self.tasks_by_agent[agent_name] = updated

    def context_pack(self, pack_type: str, text: str, important_files: list[str] | None = None) -> dict[str, Any]:
        token_limit = int(self.runtime_config.get("model_auto_compact_token_limit") or 4000)
        planner_limit = min(max(token_limit // 100, 1500), 6000)
        pack = plan_context_pack(pack_type=pack_type, text=text, important_files=important_files, token_limit=planner_limit)
        payload = {
            "project_id": self.project_id,
            "factory_brief_id": linked_brief_id(self) or None,
            "pack_type": pack["pack_type"],
            "full_text_hash": pack["full_text_hash"],
            "summary": pack["summary"],
            "important_files": pack["important_files"],
            "token_estimate": pack["token_estimate"],
        }
        try:
            self.api.context_pack(payload)
            self.event("prompt_planner", f"Context pack planned: {pack_type}", metadata_json=pack["decision"])
        except Exception as exc:
            self.event("prompt_planner", f"Context pack planning skipped: {pack_type}", level="warning", stderr=str(exc), metadata_json=pack["decision"])
        return pack

    def provider_text_assist(self, purpose: str, prompt: str, max_output_tokens: int = 1200) -> dict[str, Any]:
        config_profile_id = self.runtime_config.get("config_profile_id")
        try:
            result = self.api.provider_completion(
                {
                    "config_profile_id": config_profile_id,
                    "runtime_config_snapshot": self.runtime_config,
                    "purpose": purpose,
                    "prompt": prompt,
                    "max_output_tokens": max_output_tokens,
                }
            )
            level = "info" if result.get("status") == "completed" else "warning"
            self.event(
                "provider_router",
                f"Provider text assist {result.get('status')}: {purpose}",
                level=level,
                metadata_json={
                    "provider": result.get("provider"),
                    "model": result.get("model"),
                    "detail": result.get("detail"),
                    "tokens_estimated": result.get("tokens_estimated"),
                },
            )
            return result
        except Exception as exc:
            self.event("provider_router", f"Provider text assist skipped: {purpose}", level="warning", stderr=str(exc))
            return {"status": "failed", "text": "", "detail": str(exc)}

    def record_selected_skill_usage(self, agent_name: str, status: str, summary: str = "") -> None:
        for skill in self.selected_skills:
            try:
                self.api.record_skill_run(
                    {
                        "skill_slug": skill["slug"],
                        "project_id": self.project_id,
                        "factory_brief_id": linked_brief_id(self) or None,
                        "agent_name": agent_name,
                        "output_summary": summary or skill.get("reason", ""),
                        "tokens_estimated": skill.get("token_budget", 0),
                        "status": status,
                    }
                )
            except Exception:
                pass


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def init_git(ctx: PipelineContext) -> None:
    if not (ctx.workspace / ".git").exists():
        run_safe(["git", "init"], cwd=ctx.workspace, workspace=ctx.workspace)
        run_safe(["git", "config", "user.email", "worker@forge-trend.local"], cwd=ctx.workspace, workspace=ctx.workspace)
        run_safe(["git", "config", "user.name", "ForgeTrend Worker"], cwd=ctx.workspace, workspace=ctx.workspace)


def git_commit(ctx: PipelineContext, message: str) -> None:
    init_git(ctx)
    run_safe(["git", "add", "."], cwd=ctx.workspace, workspace=ctx.workspace)
    diff = run_safe(["git", "diff", "--cached", "--quiet"], cwd=ctx.workspace, workspace=ctx.workspace)
    if diff.returncode == 1:
        run_safe(["git", "commit", "-m", message], cwd=ctx.workspace, workspace=ctx.workspace)


def git_head(ctx: PipelineContext) -> str | None:
    init_git(ctx)
    completed = run_safe(["git", "rev-parse", "--short", "HEAD"], cwd=ctx.workspace, workspace=ctx.workspace)
    if completed.returncode == 0:
        value = completed.stdout.strip()
        return value or None
    return None


def compact_list(values: list[Any], fallback: list[str]) -> list[str]:
    items = [str(item).strip() for item in values if str(item).strip()]
    return items[:6] or fallback


def dart_string(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ")


def linked_brief_id(ctx: PipelineContext) -> str:
    return next(
        (
            str(task.get("input_json", {}).get("factory_brief_id"))
            for task in ctx.tasks_by_agent.values()
            if task.get("input_json", {}).get("factory_brief_id")
        ),
        "",
    )


def linked_candidate_id(ctx: PipelineContext) -> str:
    return next(
        (
            str(task.get("input_json", {}).get("candidate_id"))
            for task in ctx.tasks_by_agent.values()
            if task.get("input_json", {}).get("candidate_id")
        ),
        "",
    )


def get_linked_brief(ctx: PipelineContext) -> dict[str, Any] | None:
    brief_id = linked_brief_id(ctx)
    return ctx.api.get_factory_brief(brief_id) if brief_id else None


def get_selected_candidate(brief: dict[str, Any] | None, candidate_id: str) -> dict[str, Any] | None:
    if not brief:
        return None
    candidates = brief.get("candidates", [])
    return next((item for item in candidates if item.get("id") == candidate_id), None) or next(
        (item for item in candidates if item.get("status") == "selected"),
        None,
    )


def brief_learning_context(brief: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "category": (brief or {}).get("target_category"),
        "language": (brief or {}).get("target_language"),
        "monetization": (brief or {}).get("monetization_mode"),
        "prompt": (brief or {}).get("raw_prompt"),
        "quality_threshold": (brief or {}).get("quality_threshold"),
    }


def with_latest_learning_rules(api: FactoryApi, runtime_config: dict[str, Any], brief: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(runtime_config or {})
    try:
        rules = api.applicable_learning_rules(brief_learning_context(brief))
        if rules:
            merged["applied_learning_rules"] = rules
    except Exception:
        merged.setdefault("applied_learning_rules", runtime_config.get("applied_learning_rules") or [])
    return merged


def preferred_archetype_from_learning(runtime_config: dict[str, Any]) -> dict[str, Any] | None:
    for rule in runtime_config.get("applied_learning_rules") or []:
        action = rule.get("action_json") or {}
        preferred = action.get("preferred_archetype")
        if preferred and preferred in ARCHETYPES:
            return ARCHETYPES[preferred]
    return None


def build_app_blueprint(ctx: PipelineContext, brief: dict[str, Any] | None, candidate: dict[str, Any] | None, *, is_vi: bool, has_paywall: bool) -> dict[str, Any]:
    archetype = preferred_archetype_from_learning(ctx.runtime_config) or choose_archetype((brief or {}).get("target_category"), (brief or {}).get("raw_prompt", ctx.project["name"]))
    features = compact_list(
        (candidate or {}).get("core_features", []) or archetype.get("core_actions", []) or archetype.get("actions", []),
        ["Onboarding", "Home dashboard", "Core feature flow", "Progress history", "Settings", "Privacy"],
    )
    if any((rule.get("action_json") or {}).get("require_interactive_core_flow") for rule in ctx.runtime_config.get("applied_learning_rules") or []):
        features = compact_list(
            [*features, "Domain-specific guided action", "Meaningful saved progress state", "Reviewable activity history"],
            features,
        )
    return {
        "app_name": ctx.project["name"],
        "target_user": (candidate or {}).get("target_user") or ("Người dùng Việt cần một app tập trung" if is_vi else "People who need one focused mobile workflow"),
        "primary_job_to_be_done": (candidate or {}).get("problem") or (brief or {}).get("raw_prompt") or ctx.project["name"],
        "main_user_journey": [
            "Start",
            "Input or select one focused item",
            "Review the suggested plan",
            "Complete action and see progress",
            "Return to history/settings",
        ],
        "archetype": archetype["id"],
        "screens": [
            "Onboarding",
            "Home dashboard",
            *archetype.get("screens", []),
            "Core feature flow",
            "Progress/history",
            "Settings",
            "Privacy/about",
            *(["Paywall"] if has_paywall else []),
        ],
        "core_entities": archetype.get("core_entities", []) or archetype.get("entities", []) or ["UserPreference", "ProgressItem", "ActivityLog", "StoreDraft"],
        "core_actions": features,
        "empty_states": ["No activity yet", "No saved items yet"],
        "error_states": ["Data load failed", "Build or configuration needs review"],
        "success_states": ["Progress updated", "Plan refreshed"],
        "monetization": {
            "mode": (brief or {}).get("monetization_mode", "none"),
            "simulated_only": True,
            "human_billing_review_required": True,
        },
        "privacy": {
            "local_first": True,
            "no_production_analytics": True,
            "no_auto_publish": True,
        },
        "store_positioning": {
            "title": ctx.project["name"],
            "short_description_vi": "App tập trung giúp người dùng hoàn thành một mục tiêu rõ ràng mỗi ngày.",
            "differentiation_claim": (candidate or {}).get("unique_angle") or "Focused local-first workflow with human-reviewed release gates.",
        },
        "localization": {
            "default_language": "vi" if is_vi else "en",
            "supported_languages": ["vi", "en"],
        },
    }


def write_blueprint_artifacts(ctx: PipelineContext, blueprint: dict[str, Any]) -> None:
    json_path = ctx.artifacts_dir / "app_blueprint.json"
    md_path = ctx.artifacts_dir / "app_blueprint.md"
    write_text(json_path, json.dumps(blueprint, indent=2, ensure_ascii=False))
    lines = [
        f"# App Blueprint: {blueprint['app_name']}",
        "",
        f"- Target user: {blueprint['target_user']}",
        f"- JTBD: {blueprint['primary_job_to_be_done']}",
        f"- Default language: {blueprint['localization']['default_language']}",
        "",
        "## Main User Journey",
        *[f"- {item}" for item in blueprint["main_user_journey"]],
        "",
        "## Screens",
        *[f"- {item}" for item in blueprint["screens"]],
        "",
        "## Core Actions",
        *[f"- {item}" for item in blueprint["core_actions"]],
    ]
    write_text(md_path, "\n".join(lines))
    ctx.api.artifact(ctx.project_id, "document", "app_blueprint.json", str(json_path), blueprint)
    ctx.api.artifact(ctx.project_id, "document", "app_blueprint.md", str(md_path), {"screens": blueprint["screens"], "core_actions": blueprint["core_actions"]})


def write_store_asset_drafts(ctx: PipelineContext, blueprint: dict[str, Any]) -> None:
    store_dir = ctx.artifacts_dir / "store_assets"
    app_name = blueprint["app_name"]
    target_user = blueprint["target_user"]
    differentiation = blueprint["store_positioning"]["differentiation_claim"]
    assets = {
        "app_name.md": f"# {app_name}\n\nHuman review required before store use.\n",
        "short_description.vi.md": f"{app_name} giúp {target_user} hoàn thành một mục tiêu rõ ràng mỗi ngày.",
        "long_description.vi.md": f"# {app_name}\n\nỨng viên app này tập trung vào hành trình: bắt đầu, chọn việc cần làm, xử lý, xem tiến độ và quay lại lịch sử/cài đặt.\n\nĐiểm khác biệt: {differentiation}\n\nChưa được tự động publish. Cần con người review policy, billing, screenshot và listing.",
        "short_description.en.md": f"{app_name} helps its target users complete one focused workflow with clear progress.",
        "long_description.en.md": f"# {app_name}\n\nThis app candidate focuses on a simple journey: start, select an item, review/process, see progress, and return to history/settings.\n\nDifferentiation: {differentiation}\n\nHuman review is required before store submission.",
        "screenshot_plan.md": "\n".join([
            "# Screenshot Plan",
            "",
            "1. Onboarding value prop",
            "2. Home dashboard",
            "3. Core feature flow",
            "4. Progress/history",
            "5. Premium/settings/privacy",
        ]),
        "keywords.md": f"# Keywords\n\n{app_name.lower()}, productivity, mobile workflow, vietnamese app, local-first, progress tracker\n",
        "privacy_summary.md": "# Privacy Summary\n\nLocal-first MVP candidate. No production analytics, no bundled secrets, no auto-publish. Human privacy review required.\n",
    }
    for name, content in assets.items():
        path = store_dir / name
        write_text(path, content)
        ctx.api.artifact(ctx.project_id, "store_asset", name, str(path), {"app_name": app_name})


def product_score_report_markdown(result: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Product Score Report",
            "",
            f"Overall: {result.get('score')}/100",
            "",
            "## Dimensions",
            f"- Product specificity: {result.get('product_specificity_score')}",
            f"- User journey clarity: {result.get('user_journey_clarity_score')}",
            f"- Feature depth: {result.get('feature_depth_score')}",
            f"- UX completeness: {result.get('ux_completeness_score')}",
            f"- Vietnamese localization: {result.get('localization_score')}",
            f"- Monetization clarity: {result.get('monetization_clarity_score')}",
            f"- Store readiness: {result.get('store_readiness_score')}",
            f"- Policy safety: {result.get('policy_safety_score')}",
            f"- Technical quality: {result.get('technical_quality_score')}",
            "",
            "## Human Review Gate",
            "- App có khác biệt thật không?",
            "- UI có đủ dùng không?",
            "- Có copy thương hiệu không?",
            "- Có chính sách quyền riêng tư chưa?",
            "- Có billing thật chưa?",
            "- Có thể đẩy test nội bộ chưa?",
        ]
    )


def write_factory_brief_report(brief: dict[str, Any], findings: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> None:
    workspace_root = settings.worker_workspace_root
    if not workspace_root.is_absolute():
        workspace_root = REPO_ROOT / workspace_root
    report_dir = workspace_root / "factory_briefs"
    report_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Factory Brief Report: {brief['title']}",
        "",
        f"Status: {brief.get('status', 'running')}",
        f"Mode: {brief.get('mode', 'manual_idea')}",
        f"Prompt: {brief.get('raw_prompt', '')}",
        "",
        "## Findings",
    ]
    for finding in findings:
        lines.extend(
            [
                f"### {finding['title']}",
                finding["summary"],
                f"Keywords: {', '.join(compact_list(finding.get('keywords', []), []))}",
                "",
            ]
        )
    lines.append("## Candidates")
    for candidate in candidates:
        lines.extend(
            [
                f"### {candidate['title']} ({candidate['opportunity_score']}/100)",
                candidate["description"],
                f"Unique angle: {candidate['unique_angle']}",
                f"Features: {', '.join(compact_list(candidate.get('core_features', []), []))}",
                "",
            ]
        )
    write_text(report_dir / f"{brief['id']}.md", "\n".join(lines))


def summarize_artifacts(artifacts: list[dict[str, Any]]) -> str:
    if not artifacts:
        return "- None recorded yet"
    return "\n".join(f"- {item.get('kind')}: {item.get('name')} ({item.get('path')})" for item in artifacts)


def write_factory_run_report(
    ctx: PipelineContext,
    qa_output: dict[str, Any] | None,
    policy_output: dict[str, Any] | None,
    final_status: str,
    quality_output: dict[str, Any] | None = None,
) -> None:
    brief_id = linked_brief_id(ctx)
    candidate_id = linked_candidate_id(ctx)
    brief = ctx.api.get_factory_brief(brief_id) if brief_id else None
    events = ctx.api.list_project_events(ctx.project_id)
    tasks = ctx.api.list_project_tasks(ctx.project_id)
    qa = ctx.api.list_project_qa(ctx.project_id)
    policy = ctx.api.list_project_policy(ctx.project_id)
    artifacts = ctx.api.list_project_artifacts(ctx.project_id)
    selected_candidate = None
    if brief:
        selected_candidate = next((item for item in brief.get("candidates", []) if item.get("id") == candidate_id), None)
        selected_candidate = selected_candidate or next((item for item in brief.get("candidates", []) if item.get("status") == "selected"), None)
    runtime_config = ctx.runtime_config or sanitized_runtime_config(ctx.api, brief)
    config_info = config_summary(runtime_config)
    selected_skills = ctx.selected_skills or select_skills(brief=brief, runtime_config=runtime_config)
    selected_skill_lines = [
        f"- {skill.get('slug')} ({skill.get('token_budget', 0)} tokens): {skill.get('reason') or skill.get('category')}"
        for skill in selected_skills
    ] or ["- none"]
    selected_skill_token_budget = sum(int(skill.get("token_budget") or 0) for skill in selected_skills)
    code_events = [event for event in events if event.get("step") == "code_agent"]
    codex_event = next((event for event in code_events if event.get("metadata_json", {}).get("provider") == "codex_cli"), None)
    code_task = next((task for task in tasks if task.get("agent_name") == "code_agent"), None)
    code_provider = (code_task or {}).get("output_json", {}).get("code_provider", {})
    report_path = ctx.artifacts_dir / "factory_run_report.md"
    lines = [
        f"# Factory Run Report: {ctx.project['name']}",
        "",
        "## Brief",
        f"- Brief ID: {brief_id or 'not linked'}",
        f"- Title: {(brief or {}).get('title', ctx.project['name'])}",
        f"- Mode: {(brief or {}).get('mode', 'manual')}",
        f"- Prompt: {(brief or {}).get('raw_prompt', (ctx.idea or {}).get('description', ''))}",
        "",
        "## Runtime Config Snapshot",
        f"- Profile: {config_info.get('profile_name')}",
        f"- Provider: {config_info.get('model_provider')}",
        f"- Model: {config_info.get('model')}",
        f"- Review model: {config_info.get('review_model')}",
        f"- Network: {config_info.get('network_access')}",
        f"- Auth mode: {config_info.get('provider_auth_mode')}",
        f"- Plugins: {', '.join(config_info.get('plugins') or []) or 'none'}",
        f"- Skills: {', '.join(config_info.get('skills') or []) or 'none'}",
        f"- Applied learning rules: {', '.join(rule.get('rule_key') for rule in runtime_config.get('applied_learning_rules') or []) or 'none'}",
        "",
        "## Selected Skills Used",
        f"- Estimated token budget: {selected_skill_token_budget}",
        *selected_skill_lines,
        "",
        "## Selected Candidate",
        f"- Candidate ID: {candidate_id or 'unknown'}",
        f"- Title: {(selected_candidate or {}).get('title', ctx.project['name'])}",
        f"- Score: {(selected_candidate or {}).get('opportunity_score', 'unknown')}",
        f"- Why selected: Highest opportunity score after demand, pain, monetization, feasibility, originality, and policy-risk scoring.",
        "",
        "## Research Findings",
    ]
    for finding in (brief or {}).get("findings", []):
        evidence = finding.get("evidence_json") or {}
        source = evidence.get("source_url") or evidence.get("provider") or finding.get("source")
        lines.append(f"- {finding.get('title')}: {finding.get('summary')} Source: {source}")
    if not (brief or {}).get("findings"):
        lines.append("- No linked findings were returned by the API.")
    lines.extend(["", "## Tasks"])
    for task in tasks:
        provider = ""
        if task.get("agent_name") == "code_agent":
            provider = f" provider={task.get('output_json', {}).get('code_provider', {}).get('provider', 'unknown')}"
        lines.append(f"- {task.get('status')} {task.get('agent_name')}: {task.get('title')}{provider}")
    lines.extend(
        [
            "",
            "## Codex Provider Status",
            f"- Worker mode: {'Codex coding mode' if settings.worker_enable_codex else 'Deterministic scaffold mode'}",
            f"- Code provider result: {json.dumps(code_provider, ensure_ascii=True)}",
            f"- Codex proof event: {'yes' if codex_event else 'no'}",
            "",
            "## QA Result",
            f"- Summary: {json.dumps(qa_output or {}, ensure_ascii=True)[:2000]}",
        ]
    )
    for item in qa:
        lines.append(f"- {item.get('status')} exit={item.get('exit_code')} {item.get('command')}")
    lines.extend(
        [
            "",
            "## Policy Result",
            f"- Summary: {json.dumps(policy_output or {}, ensure_ascii=True)[:2000]}",
        ]
    )
    for item in policy:
        lines.append(f"- passed={item.get('passed')} risk={item.get('risk')} issues={'; '.join(item.get('issues') or [])}")
    lines.extend(
        [
            "",
            "## Product Quality Gate",
            f"- Summary: {json.dumps(quality_output or {}, ensure_ascii=True)[:2000]}",
            "",
            "## Artifacts",
            summarize_artifacts(artifacts),
            "",
            "## Final Status",
            final_status,
            "",
            "## Next Recommended Action",
            "Open the generated Flutter workspace, review QA/policy output, and keep human approval in the loop before any production release.",
        ]
    )
    write_text(report_path, "\n".join(lines))
    ctx.api.artifact(ctx.project_id, "document", "factory_run_report.md", str(report_path), {"brief_id": brief_id, "final_status": final_status})

    vi_research_lines = [
        f"- {finding.get('title')}: {finding.get('summary')}"
        for finding in (brief or {}).get("findings", [])
    ] or ["- Không có finding liên kết trong API."]
    vi_feature_lines = [
        f"- {item}"
        for item in compact_list(
            (selected_candidate or {}).get("core_features", []),
            ["Luồng chính", "Theo dõi tiến độ", "Cài đặt và quyền riêng tư"],
        )
    ]
    vi_report_path = ctx.artifacts_dir / "factory_run_report.vi.md"
    vi_lines = [
        "# Báo cáo chạy xưởng tạo app",
        "",
        "## Ý tưởng đầu vào",
        f"- Tên brief: {(brief or {}).get('title', ctx.project['name'])}",
        f"- Nội dung: {(brief or {}).get('raw_prompt', (ctx.idea or {}).get('description', ''))}",
        "",
        "## Kết quả nghiên cứu",
        *vi_research_lines,
        "",
        "## Ứng viên được chọn",
        f"- {(selected_candidate or {}).get('title', ctx.project['name'])}",
        f"- Điểm cơ hội: {(selected_candidate or {}).get('opportunity_score', 'unknown')}",
        "",
        "## Tính năng chính",
        *vi_feature_lines,
        "",
        "## Kết quả code",
        f"- Provider: {code_provider.get('provider', 'unknown')}",
        "",
        "## Cấu hình runtime",
        f"- Profile: {config_info.get('profile_name')}",
        f"- Model: {config_info.get('model')}",
        f"- Review model: {config_info.get('review_model')}",
        f"- Network: {config_info.get('network_access')}",
        f"- Plugin: {', '.join(config_info.get('plugins') or []) or 'không có'}",
        f"- Skill: {', '.join(config_info.get('skills') or []) or 'không có'}",
        f"- Learning rule: {', '.join(rule.get('rule_key') for rule in runtime_config.get('applied_learning_rules') or []) or 'không có'}",
        "",
        "## Skill đã dùng",
        f"- Token budget ước tính: {selected_skill_token_budget}",
        *selected_skill_lines,
        "",
        "## Kết quả QA",
        f"- Passed: {(qa_output or {}).get('passed')}",
        "",
        "## Kết quả kiểm tra chất lượng sản phẩm",
        f"- Score: {(quality_output or {}).get('score', 'unknown')}",
        f"- Passed: {(quality_output or {}).get('passed', 'unknown')}",
        "",
        "## Kết quả kiểm tra chính sách",
        f"- Risk: {(policy_output or {}).get('risk', 'unknown')}",
        f"- Passed: {(policy_output or {}).get('passed', 'unknown')}",
        "",
        "## Artifact tạo được",
        summarize_artifacts(artifacts),
        "",
        "## Có thể đẩy store chưa?",
        "Chưa. ForgeTrend chỉ tạo ứng viên phát hành để con người review, không tự động publish.",
        "",
        "## Việc cần làm tiếp theo",
        "Mở app Flutter đã tạo, đọc báo cáo QA/chất lượng/chính sách, chỉnh nội dung sản phẩm và chỉ phát hành sau khi con người phê duyệt.",
    ]
    write_text(vi_report_path, "\n".join(vi_lines))
    ctx.api.artifact(ctx.project_id, "document", "factory_run_report.vi.md", str(vi_report_path), {"brief_id": brief_id, "final_status": final_status})

    en_report_path = ctx.artifacts_dir / "factory_run_report.en.md"
    write_text(en_report_path, "\n".join(lines))
    ctx.api.artifact(ctx.project_id, "document", "factory_run_report.en.md", str(en_report_path), {"brief_id": brief_id, "final_status": final_status})


def run_factory_brief(api: FactoryApi, brief_id: str) -> None:
    brief = api.get_factory_brief(brief_id)
    runtime_config = with_latest_learning_rules(api, sanitized_runtime_config(api, brief), brief)
    selected_skills = select_skills(brief=brief, runtime_config=runtime_config)
    try:
        api.factory_brief_event(
            brief_id,
            "worker_picked_brief",
            "A worker picked up this factory brief.",
            metadata_json={"step": "worker_picked_brief", "mode": brief.get("mode"), "config": config_summary(runtime_config)},
        )
        api.factory_brief_event(
            brief_id,
            "skills_selected",
            "Autopilot selected skills: " + (", ".join(item["slug"] for item in selected_skills) or "none"),
            metadata_json={"step": "skills_selected", "skills": selected_skills, "config_profile": runtime_config.get("profile_name")},
        )
        applied_rule_keys = [rule.get("rule_key") for rule in runtime_config.get("applied_learning_rules") or []]
        if applied_rule_keys:
            api.factory_brief_event(
                brief_id,
                "learning_rules_applied",
                "Learning Memory applied rules: " + ", ".join(applied_rule_keys),
                metadata_json={"step": "learning_rules_applied", "applied_learning_rules": runtime_config.get("applied_learning_rules")},
            )
        for skill in selected_skills:
            try:
                api.record_skill_run(
                    {
                        "skill_slug": skill["slug"],
                        "factory_brief_id": brief_id,
                        "agent_name": "autopilot_research",
                        "output_summary": skill.get("reason", ""),
                        "tokens_estimated": skill.get("token_budget", 0),
                        "status": "used",
                    }
                )
            except Exception:
                pass
        try:
            pack = plan_context_pack(
                pack_type="context_pack_research_brief",
                text=f"{brief.get('title', '')}\n\n{brief.get('raw_prompt', '')}\n\n{skill_prompt_header(selected_skills)}",
                important_files=[],
                token_limit=3000,
            )
            api.context_pack(
                {
                    "factory_brief_id": brief_id,
                    "pack_type": pack["pack_type"],
                    "full_text_hash": pack["full_text_hash"],
                    "summary": pack["summary"],
                    "important_files": pack["important_files"],
                    "token_estimate": pack["token_estimate"],
                }
            )
        except Exception:
            pass
        api.set_factory_brief_status(brief_id, "researching")
        api.factory_brief_event(
            brief_id,
            "research_started",
            "Research provider pass started.",
            metadata_json={"step": "research_started", "research_enable_web": settings.research_enable_web},
        )
        bundle = build_research_bundle(brief)
        provider_names = sorted({str(item.get("provider") or "unknown") for item in bundle.evidence})
        fallback = any(bool(item.get("fallback")) for item in bundle.evidence)
        api.factory_brief_event(
            brief_id,
            "research_provider_used",
            f"Research provider(s): {', '.join(provider_names) or 'deterministic_provider'}; fallback={fallback}.",
            metadata_json={"step": "research_provider_used", "providers": provider_names, "fallback": fallback, "evidence": bundle.evidence[:6]},
        )
        findings: list[dict[str, Any]] = []
        for payload in bundle.findings:
            findings.append(api.research_finding(brief_id, payload))
        api.factory_brief_event(
            brief_id,
            "findings_created",
            f"{len(findings)} research finding(s) were stored.",
            metadata_json={"step": "findings_created", "finding_count": len(findings), "evidence": bundle.evidence[:6]},
        )

        api.set_factory_brief_status(brief_id, "scoring_candidates")
        api.factory_brief_event(
            brief_id,
            "candidate_scoring_started",
            "Opportunity candidates are being scored.",
            metadata_json={"step": "candidate_scoring_started"},
        )
        candidates: list[dict[str, Any]] = []
        for payload in bundle.candidates:
            candidates.append(api.opportunity_candidate(brief_id, payload))
        candidates.sort(key=lambda item: int(item.get("opportunity_score") or 0), reverse=True)
        if not candidates:
            raise RuntimeError("Factory brief produced no candidates")
        api.factory_brief_event(
            brief_id,
            "candidates_created",
            f"{len(candidates)} opportunity candidate(s) were scored.",
            metadata_json={"step": "candidates_created", "candidate_count": len(candidates), "top_score": candidates[0].get("opportunity_score")},
        )

        write_factory_brief_report(brief, findings, candidates)
        selected = candidates[0]
        api.set_factory_brief_status(brief_id, "selecting_candidate")
        api.factory_brief_event(
            brief_id,
            "candidate_selected",
            f"{selected['title']} selected with score {selected.get('opportunity_score')}.",
            metadata_json={"step": "candidate_selected", "candidate_id": selected["id"], "opportunity_score": selected.get("opportunity_score")},
        )
        response = api.finalize_factory_brief(brief_id, selected["id"], queue_pipeline=True)
        api.set_factory_brief_status(brief_id, "project_queued")
        project_id = response["project_id"]
        api.factory_brief_event(
            brief_id,
            "pipeline_queued",
            f"Project {project_id} was queued on {response.get('queue')}.",
            metadata_json={"step": "pipeline_queued", "project_id": project_id, "queue": response.get("queue")},
        )
        api.event(
            project_id,
            "factory_brief",
            f"Autonomous factory selected candidate: {selected['title']}",
            metadata_json={"factory_brief_id": brief_id, "candidate_id": selected["id"], "opportunity_score": selected.get("opportunity_score")},
        )
    except Exception as exc:
        api.set_factory_brief_status(brief_id, "failed")
        api.factory_brief_event(
            brief_id,
            "brief_failed",
            f"Failed at: factory_brief\nReason: {exc}\nNext action: Check worker logs, doctor output, and factory configuration, then start a new brief or retry after fixing the issue.",
            level="error",
            metadata_json={
                "step": "brief_failed",
                "failed_at": "factory_brief",
                "reason": str(exc),
                "next_action": "Check worker logs, doctor output, and factory configuration, then retry.",
            },
        )
        raise


def ensure_not_stopped(ctx: PipelineContext) -> None:
    factory_state = ctx.api.factory_state()
    if factory_state.get("mode") == "stopped":
        raise PipelineStopped("Factory was stopped from the dashboard.")
    project = ctx.api.get_project(ctx.project_id)
    ctx.project = project
    if project.get("status") in {"stop_requested", "stopped"}:
        raise PipelineStopped("Project stop was requested from the dashboard.")


def run_checked_agent(ctx: PipelineContext, agent_name: str, fn, *, iteration: int = 0, **kwargs: Any) -> dict[str, Any]:
    ensure_not_stopped(ctx)
    output = run_agent(ctx, agent_name, fn, iteration=iteration, **kwargs)
    ensure_not_stopped(ctx)
    return output


def build_codex_prompt(ctx: PipelineContext, iteration: int, qa_error: str | None) -> str:
    prd_path = ctx.docs_dir / "prd.md"
    design_path = ctx.docs_dir / "design_system.md"
    flow_path = ctx.docs_dir / "screen_flow.md"
    prd = prd_path.read_text(encoding="utf-8") if prd_path.exists() else ""
    design = design_path.read_text(encoding="utf-8") if design_path.exists() else ""
    flow = flow_path.read_text(encoding="utf-8") if flow_path.exists() else ""
    mode = "fix the QA failure" if qa_error else "customize the generated Flutter skeleton"
    error_block = f"\nQA failure to fix:\n```text\n{qa_error[-6000:]}\n```\n" if qa_error else ""
    context_text = "\n\n".join([prd, design, flow, qa_error or ""])
    pack = ctx.context_pack(
        "context_pack_code_agent",
        context_text,
        important_files=[str(prd_path), str(design_path), str(flow_path), "app/lib", "app/test"],
    )
    skill_header = skill_prompt_header(ctx.selected_skills)
    return f"""You are the ForgeTrend Code Agent running inside a local project workspace.

Task: {mode}.
{skill_header}

Hard rules:
- Edit only files under the current workspace.
- Work primarily in app/lib, app/test, and app/PRIVACY_POLICY.md.
- Keep the app original; do not copy names, UI, icons, copy, or store metadata from existing apps.
- Do not add secrets, API keys, analytics credentials, or production publishing automation.
- Preserve Flutter buildability.
- Keep the MVP compact but not empty: onboarding, home, settings, theme, and shared widgets should remain meaningful.

Project:
- Name: {ctx.project["name"]}
- Slug: {ctx.project["slug"]}
- Iteration: {iteration}
- App directory: app/

PRD:
```markdown
{prd[-8000:]}
```

Design system:
```markdown
{design[-5000:]}
```

Screen flow:
```markdown
{flow[-5000:]}
```

Compressed context pack:
```text
{pack["summary"]}
```
{error_block}
Finish by summarizing the files you changed. Do not run destructive commands.
"""


def run_codex_code_pass(ctx: PipelineContext, iteration: int, qa_error: str | None = None) -> dict[str, Any]:
    prompt = build_codex_prompt(ctx, iteration, qa_error)
    ctx.event(
        "code_agent",
        "Codex CLI pass started",
        metadata_json={"iteration": iteration, "timeout_seconds": settings.worker_codex_timeout_seconds},
    )
    completed = run_codex_cli(prompt, cwd=ctx.workspace, workspace=ctx.workspace)
    level = "info" if completed.returncode == 0 else "warning"
    ctx.event(
        "code_agent",
        "Codex CLI pass finished" if completed.returncode == 0 else "Codex CLI pass returned non-zero",
        level=level,
        stdout=completed.stdout[-4000:],
        stderr=completed.stderr[-4000:],
        metadata_json={"exit_code": completed.returncode, "provider": "codex_cli", "iteration": iteration},
    )
    if completed.returncode != 0:
        raise RuntimeError(f"Codex CLI failed with exit code {completed.returncode}")
    git_commit(ctx, f"Codex code agent iteration {iteration}")
    return {"provider": "codex_cli", "exit_code": completed.returncode}


def prd_agent(ctx: PipelineContext) -> dict[str, Any]:
    decision = check_cost_limit("deterministic_prd_agent")
    if not decision.allowed:
        raise RuntimeError(decision.reason)
    idea_text = ctx.idea["description"] if ctx.idea else ctx.project["name"]
    title = ctx.project["name"]
    prd = f"""# {title} PRD

## Target user
People with a recurring mobile workflow that is underserved by existing generic tools.

## Problem
{idea_text}

## USP
Create a focused, privacy-aware mobile workflow with original naming, original UI, and a clear job-to-be-done instead of copying another app.

## Competitor gap
Existing solutions are often broad, cluttered, or weak on guided onboarding and actionable status.

## MVP features
- Guided onboarding for the core workflow.
- Home dashboard with next best action.
- Core feature screen with local sample data.
- Progress/status cards for the user's current state.
- Loading, empty, error, and success feedback states.
- Settings with privacy and export placeholders.
- Privacy/about screen.
- Subscription or IAP placeholder when configured.
- Local-first sample data and no hardcoded secrets.

## Screens
- Onboarding
- Home
- Core feature
- Progress/status
- Settings
- Privacy/about
- Paywall placeholder when configured

## Data model
- UserPreference
- TaskItem
- ActivityLog

## Monetization
Freemium placeholder with human review before any store release.

## Risks
- Minimum functionality risk if the project scope is reduced too far.
- Naming similarity risk if market research is not reviewed.
- Build environment drift across macOS and Windows.

## Definition of Done
- Flutter analyze passes.
- Flutter tests pass.
- Android debug APK builds.
- Policy checklist passes.
- Human approval remains required before production publishing.
"""
    assist_prompt = f"""{skill_prompt_header(ctx.selected_skills)}

Create a concise PRD improvement for this app. Keep it original, store-safe, and implementation-ready.

Project: {title}
Idea: {idea_text}

Return markdown sections for target user, problem, MVP features, risks, and definition of done."""
    provider_result = ctx.provider_text_assist("prd_agent", assist_prompt, max_output_tokens=1400)
    if provider_result.get("status") == "completed" and len(str(provider_result.get("text") or "")) > 300:
        prd = f"{prd}\n\n## Provider Assisted Product Notes\n\n{provider_result['text']}\n"
    ctx.context_pack("context_pack_prd", prd, important_files=["docs/prd.md"])
    path = ctx.docs_dir / "prd.md"
    write_text(path, prd)
    ctx.api.artifact(ctx.project_id, "document", "prd.md", str(path))
    ctx.event("prd_agent", "PRD generated", metadata_json={"path": str(path)})
    git_commit(ctx, "Generate PRD")
    return {"prd_path": str(path), "provider_assist": {"status": provider_result.get("status"), "provider": provider_result.get("provider"), "detail": provider_result.get("detail")}}


def ux_agent(ctx: PipelineContext) -> dict[str, Any]:
    decision = check_cost_limit("deterministic_ux_agent")
    if not decision.allowed:
        raise RuntimeError(decision.reason)
    design_system = f"""# Design System

## Product
{ctx.project["name"]}

## Visual direction
Calm productivity UI with strong contrast, compact cards, and original content.

## Palette
- Ink: #172026
- Paper: #f7f9f8
- Action: #0f8b8d
- Accent: #f25f5c

## Typography
Use Material 3 defaults with clear hierarchy and no decorative type.

## Components
- Status cards
- Primary action button
- Timeline rows
- Empty-state panel
"""
    screen_flow = """# Screen Flow

1. Onboarding introduces the unique workflow and privacy posture.
2. Home shows status, next action, and recent activity.
3. Settings exposes privacy policy placeholder and app controls.

## Loading, empty, and error states
- Loading states use progress indicators with concise status text.
- Empty states offer one primary action.
- Errors describe the failed command or missing dependency.
"""
    ux_prompt = f"""{skill_prompt_header(ctx.selected_skills)}

Improve the UX plan for {ctx.project["name"]}. Return concise markdown for screens, empty/error/success states, and Vietnamese-first copy notes when relevant."""
    provider_result = ctx.provider_text_assist("ux_agent", ux_prompt, max_output_tokens=900)
    if provider_result.get("status") == "completed" and provider_result.get("text"):
        screen_flow = f"{screen_flow}\n\n## Provider Assisted UX Notes\n\n{provider_result['text']}\n"
    ctx.context_pack("context_pack_design", f"{design_system}\n\n{screen_flow}", important_files=["docs/design_system.md", "docs/screen_flow.md"])
    design_path = ctx.docs_dir / "design_system.md"
    flow_path = ctx.docs_dir / "screen_flow.md"
    write_text(design_path, design_system)
    write_text(flow_path, screen_flow)
    ctx.api.artifact(ctx.project_id, "document", "design_system.md", str(design_path))
    ctx.api.artifact(ctx.project_id, "document", "screen_flow.md", str(flow_path))
    ctx.event("ux_agent", "UX documents generated", metadata_json={"design_system": str(design_path), "screen_flow": str(flow_path)})
    git_commit(ctx, "Generate UX documents")
    return {"design_system_path": str(design_path), "screen_flow_path": str(flow_path), "provider_assist": {"status": provider_result.get("status"), "provider": provider_result.get("provider"), "detail": provider_result.get("detail")}}


def code_agent(ctx: PipelineContext, iteration: int = 0, qa_error: str | None = None) -> dict[str, Any]:
    decision = check_cost_limit("deterministic_code_agent")
    if not decision.allowed:
        raise RuntimeError(decision.reason)
    created_app = False
    if not ctx.app_dir.exists():
        ignore = shutil.ignore_patterns(".dart_tool", "build", ".idea", ".gradle", "*.iml", "android/local.properties")
        shutil.copytree(TEMPLATE_ROOT, ctx.app_dir, ignore=ignore)
        created_app = True
        ctx.event("code_agent", "Flutter template copied", metadata_json={"template": str(TEMPLATE_ROOT), "app_dir": str(ctx.app_dir)})
    else:
        ctx.event("code_agent", "Flutter app already exists; preparing code pass", metadata_json={"iteration": iteration})

    brief = get_linked_brief(ctx)
    candidate = get_selected_candidate(brief, linked_candidate_id(ctx))
    title = ctx.project["name"]
    raw_prompt = str((brief or {}).get("raw_prompt") or "")
    about = str((candidate or {}).get("description") or (ctx.idea or {}).get("description") or raw_prompt or "A focused original mobile app.")
    evidence = ctx.idea.get("evidence_json", {}) if ctx.idea else {}
    target_language = str((brief or {}).get("target_language") or "en").lower()
    prompt_lower = f"{raw_prompt} {about} {title}".lower()
    is_hsk = "hsk" in prompt_lower or "chinese" in prompt_lower or "tiếng trung" in prompt_lower
    is_vi = target_language == "vi" or "người việt" in prompt_lower or "vietnamese" in prompt_lower
    if is_vi and is_hsk:
        app_name = "Học HSK Mỗi Ngày"
        tagline = "Lộ trình ôn từ vựng và bài học HSK cho người Việt."
        idea_summary = "Ứng dụng giúp người học tiếng Trung duy trì lịch học hằng ngày, ôn từ vựng trọng tâm và xem tiến độ tuần."
        core_features = [
            "Ôn từ vựng HSK hôm nay",
            "Lộ trình bài học theo trình độ",
            "Theo dõi tiến độ tuần",
            "Nhắc lại từ khó",
            "Ghi chú mục tiêu học tập",
        ]
    elif is_vi:
        app_name = title
        tagline = "Một ứng dụng tập trung vào mục tiêu chính của người dùng."
        idea_summary = about
        core_features = compact_list((candidate or {}).get("core_features", []) or evidence.get("core_features", []), ["Việc cần làm hôm nay", "Theo dõi tiến độ", "Lịch sử hoạt động", "Cài đặt riêng tư"])
    else:
        app_name = title
        tagline = "A focused workflow with clear progress and privacy-first controls."
        idea_summary = about
        core_features = compact_list((candidate or {}).get("core_features", []) or evidence.get("core_features", []), ["Plan today's session", "Track weekly progress", "Review saved activity", "Manage privacy settings"])
    has_paywall = any(
        bool(value)
        for value in [
            (evidence.get("subscription_plan_json") or {}).get("enabled") if isinstance(evidence.get("subscription_plan_json"), dict) else False,
            (evidence.get("iap_plan_json") or {}).get("enabled") if isinstance(evidence.get("iap_plan_json"), dict) else False,
            "subscription" in about.lower(),
            "iap" in about.lower(),
        ]
    )
    blueprint = build_app_blueprint(ctx, brief, candidate, is_vi=is_vi, has_paywall=has_paywall)
    write_blueprint_artifacts(ctx, blueprint)
    write_store_asset_drafts(ctx, blueprint)
    core_features = compact_list(blueprint.get("core_actions", []), core_features)
    dart_features = ",\n".join(f"    '{dart_string(feature)}'" for feature in core_features)
    title_literal = dart_string(app_name)
    about_literal = dart_string(idea_summary)[:900]
    language_literal = "vi" if is_vi else "en"
    strings = {
        "home_title": "Hôm nay" if is_vi else "Today",
        "primary_action": "Bắt đầu buổi học" if is_vi and is_hsk else ("Mở luồng chính" if is_vi else "Open main workflow"),
        "progress_title": "Tiến độ tuần này" if is_vi else "Weekly progress",
        "feature_title": "Lộ trình học" if is_vi and is_hsk else ("Luồng sản phẩm chính" if is_vi else "Main product flow"),
        "history_title": "Hoạt động gần đây" if is_vi else "Recent activity",
        "settings": "Cài đặt" if is_vi else "Settings",
        "privacy": "Quyền riêng tư" if is_vi else "Privacy",
        "paywall": "Gói Premium" if is_vi else "Premium",
        "start": "Bắt đầu" if is_vi else "Start",
        "empty": "Chưa có dữ liệu. Hãy hoàn thành mục đầu tiên để tạo lịch sử." if is_vi else "No activity yet. Complete the first item to create history.",
        "loading": "Đang chuẩn bị dữ liệu học tập..." if is_vi else "Preparing your workflow...",
        "error": "Không thể tải dữ liệu mẫu. Kiểm tra lại cấu hình rồi thử lại." if is_vi else "Could not load the workflow data. Check configuration and try again.",
        "success": "Đã cập nhật tiến độ." if is_vi else "Progress updated.",
        "reset": "Đặt lại tiến độ" if is_vi else "Reset progress",
    }
    constants = f"""class AppContent {{
  const AppContent._();

  static const String appName = '{title_literal}';
  static const String defaultLanguage = '{language_literal}';
  static const String tagline = '{dart_string(tagline)}';
  static const String idea = '{about_literal}';
  static const bool subscriptionEnabled = {'true' if has_paywall else 'false'};
  static const String homeTitle = '{dart_string(strings["home_title"])}';
  static const String primaryActionLabel = '{dart_string(strings["primary_action"])}';
  static const String progressTitle = '{dart_string(strings["progress_title"])}';
  static const String featureTitle = '{dart_string(strings["feature_title"])}';
  static const String historyTitle = '{dart_string(strings["history_title"])}';
  static const String settingsLabel = '{dart_string(strings["settings"])}';
  static const String privacyTitle = '{dart_string(strings["privacy"])}';
  static const String paywallTitle = '{dart_string(strings["paywall"])}';
  static const String startLabel = '{dart_string(strings["start"])}';
  static const String emptyStateTitle = '{dart_string(strings["empty"])}';
  static const String loadingStateTitle = '{dart_string(strings["loading"])}';
  static const String errorStateTitle = '{dart_string(strings["error"])}';
  static const String successMessage = '{dart_string(strings["success"])}';
  static const String resetLabel = '{dart_string(strings["reset"])}';
  static const List<String> coreFeatures = [
{dart_features}
  ];

  static const Map<String, Map<String, String>> localized = {{
    'vi': {{
      'start': 'Bắt đầu',
      'settings': 'Cài đặt',
      'privacy': 'Quyền riêng tư',
      'paywall': 'Gói Premium',
    }},
    'en': {{
      'start': 'Start',
      'settings': 'Settings',
      'privacy': 'Privacy',
      'paywall': 'Premium',
    }},
  }};

  static String text(String key, [String locale = defaultLanguage]) {{
    return localized[locale]?[key] ?? localized['en']?[key] ?? key;
  }}
}}
"""
    write_text(ctx.app_dir / "lib" / "core" / "app_content.dart", constants)

    onboarding_screen = """import 'package:flutter/material.dart';

import '../../core/app_content.dart';

class OnboardingScreen extends StatelessWidget {
  const OnboardingScreen({required this.onFinish, super.key});

  final VoidCallback onFinish;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Spacer(),
              Icon(
                Icons.school_outlined,
                size: 56,
                color: Theme.of(context).colorScheme.primary,
              ),
              const SizedBox(height: 24),
              Text(AppContent.appName, style: Theme.of(context).textTheme.headlineMedium),
              const SizedBox(height: 12),
              Text(AppContent.tagline, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 16),
              Text(AppContent.idea),
              const Spacer(),
              FilledButton(
                onPressed: onFinish,
                child: Text(AppContent.startLabel),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
"""
    write_text(ctx.app_dir / "lib" / "features" / "onboarding" / "onboarding_screen.dart", onboarding_screen)

    home_screen = """import 'package:flutter/material.dart';

import '../../core/app_content.dart';
import '../core_flow/core_flow_screen.dart';
import '../onboarding/onboarding_screen.dart';
import '../paywall/paywall_screen.dart';
import '../settings/settings_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  var _showOnboarding = true;
  var _selectedIndex = 0;
  var _completedToday = 1;

  @override
  Widget build(BuildContext context) {
    if (_showOnboarding) {
      return OnboardingScreen(onFinish: () => setState(() => _showOnboarding = false));
    }

    final pages = [
      _HomeDashboard(completedToday: _completedToday, onProgress: () => setState(() => _completedToday = (_completedToday + 1).clamp(0, AppContent.coreFeatures.length))),
      const SettingsScreen(),
    ];

    return Scaffold(
      appBar: AppBar(title: const Text(AppContent.appName)),
      body: pages[_selectedIndex],
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex,
        onDestinationSelected: (index) => setState(() => _selectedIndex = index),
        destinations: [
          NavigationDestination(icon: const Icon(Icons.dashboard_outlined), selectedIcon: const Icon(Icons.dashboard), label: AppContent.homeTitle),
          NavigationDestination(icon: const Icon(Icons.settings_outlined), selectedIcon: const Icon(Icons.settings), label: AppContent.settingsLabel),
        ],
      ),
    );
  }
}

class _HomeDashboard extends StatelessWidget {
  const _HomeDashboard({required this.completedToday, required this.onProgress});

  final int completedToday;
  final VoidCallback onProgress;

  @override
  Widget build(BuildContext context) {
    final total = AppContent.coreFeatures.length;
    final progress = total == 0 ? 0.0 : completedToday / total;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(AppContent.homeTitle, style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(AppContent.progressTitle, style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 8),
                LinearProgressIndicator(value: progress.clamp(0, 1)),
                const SizedBox(height: 8),
                Text('$completedToday / $total'),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        Card(
          child: ListTile(
            leading: const Icon(Icons.route_outlined),
            title: Text(AppContent.featureTitle),
            subtitle: Text(AppContent.coreFeatures.first),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const CoreFlowScreen())),
          ),
        ),
        const SizedBox(height: 12),
        Card(
          child: ListTile(
            leading: const Icon(Icons.history_outlined),
            title: Text(AppContent.historyTitle),
            subtitle: Text(completedToday > 0 ? AppContent.successMessage : AppContent.emptyStateTitle),
          ),
        ),
        const SizedBox(height: 16),
        FilledButton(
          onPressed: () {
            onProgress();
            ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(AppContent.successMessage)));
          },
          child: Text(AppContent.primaryActionLabel),
        ),
        const SizedBox(height: 8),
        OutlinedButton(
          onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const CoreFlowScreen())),
          child: Text(AppContent.featureTitle),
        ),
        if (AppContent.subscriptionEnabled) ...[
          const SizedBox(height: 8),
          OutlinedButton(
            onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const PaywallScreen())),
            child: Text(AppContent.paywallTitle),
          ),
        ],
      ],
    );
  }
}
"""
    write_text(ctx.app_dir / "lib" / "features" / "home" / "home_screen.dart", home_screen)

    core_flow_screen = """import 'package:flutter/material.dart';

import '../../core/app_content.dart';

class CoreFlowScreen extends StatefulWidget {
  const CoreFlowScreen({super.key});

  @override
  State<CoreFlowScreen> createState() => _CoreFlowScreenState();
}

class _CoreFlowScreenState extends State<CoreFlowScreen> {
  final Set<int> _completed = {0};
  var _loading = false;
  String? _errorMessage;

  Future<void> _refreshPlan() async {
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    await Future<void>.delayed(const Duration(milliseconds: 250));
    if (!mounted) return;
    setState(() => _loading = false);
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(AppContent.successMessage)));
  }

  Future<void> _confirmReset() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(AppContent.resetLabel),
        content: Text(AppContent.emptyStateTitle),
        actions: [
          TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text('No')),
          FilledButton(onPressed: () => Navigator.of(context).pop(true), child: const Text('OK')),
        ],
      ),
    );
    if (confirmed == true) {
      setState(() => _completed.clear());
    }
  }

  @override
  Widget build(BuildContext context) {
    final items = AppContent.coreFeatures;
    return Scaffold(
      appBar: AppBar(title: Text(AppContent.featureTitle)),
      body: RefreshIndicator(
        onRefresh: _refreshPlan,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (_loading) ...[
              LinearProgressIndicator(),
              const SizedBox(height: 12),
              Text(AppContent.loadingStateTitle),
            ],
            if (_errorMessage != null)
              Card(
                color: Theme.of(context).colorScheme.errorContainer,
                child: ListTile(
                  leading: const Icon(Icons.error_outline),
                  title: Text(AppContent.errorStateTitle),
                  subtitle: Text(_errorMessage!),
                  trailing: TextButton(onPressed: _refreshPlan, child: const Text('Retry')),
                ),
              ),
            if (items.isEmpty)
              Card(
                child: ListTile(
                  leading: const Icon(Icons.inbox_outlined),
                  title: Text(AppContent.emptyStateTitle),
                  trailing: FilledButton(onPressed: _refreshPlan, child: Text(AppContent.primaryActionLabel)),
                ),
              )
            else
              ...items.asMap().entries.map(
                    (entry) => CheckboxListTile(
                      value: _completed.contains(entry.key),
                      title: Text(entry.value),
                      subtitle: Text('${AppContent.progressTitle}: ${entry.key + 1}/${items.length}'),
                      onChanged: (checked) {
                        setState(() {
                          if (checked == true) {
                            _completed.add(entry.key);
                          } else {
                            _completed.remove(entry.key);
                          }
                        });
                      },
                    ),
                  ),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: _refreshPlan,
              icon: const Icon(Icons.sync),
              label: Text(AppContent.primaryActionLabel),
            ),
            const SizedBox(height: 8),
            OutlinedButton.icon(
              onPressed: _confirmReset,
              icon: const Icon(Icons.restart_alt),
              label: Text(AppContent.resetLabel),
            ),
          ],
        ),
      ),
    );
  }
}
"""
    write_text(ctx.app_dir / "lib" / "features" / "core_flow" / "core_flow_screen.dart", core_flow_screen)

    settings_screen = """import 'package:flutter/material.dart';

import '../../core/app_content.dart';
import '../privacy/privacy_screen.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(AppContent.settingsLabel, style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 12),
        Card(
          child: ListTile(
            leading: const Icon(Icons.language_outlined),
            title: Text(AppContent.defaultLanguage == 'vi' ? 'Ngôn ngữ' : 'Language'),
            subtitle: Text(AppContent.defaultLanguage == 'vi' ? 'Tiếng Việt, có English fallback' : 'English with Vietnamese support'),
          ),
        ),
        Card(
          child: ListTile(
            leading: const Icon(Icons.privacy_tip_outlined),
            title: Text(AppContent.privacyTitle),
            subtitle: Text(AppContent.defaultLanguage == 'vi' ? 'Dữ liệu MVP lưu cục bộ, chưa bật phân tích sản xuất.' : 'MVP data stays local; production analytics are not enabled.'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const PrivacyScreen())),
          ),
        ),
      ],
    );
  }
}
"""
    write_text(ctx.app_dir / "lib" / "features" / "settings" / "settings_screen.dart", settings_screen)

    privacy_screen = """import 'package:flutter/material.dart';

import '../../core/app_content.dart';

class PrivacyScreen extends StatelessWidget {
  const PrivacyScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final isVi = AppContent.defaultLanguage == 'vi';
    return Scaffold(
      appBar: AppBar(title: Text(AppContent.privacyTitle)),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: ListTile(
              leading: const Icon(Icons.shield_outlined),
              title: Text(isVi ? 'Cam kết dữ liệu' : 'Data posture'),
              subtitle: Text(isVi ? 'Ứng viên app này không nhúng API key, analytics sản xuất hoặc tự động publish.' : 'This app candidate does not bundle API keys, production analytics, or auto-publishing.'),
            ),
          ),
          Card(
            child: ListTile(
              leading: const Icon(Icons.fact_check_outlined),
              title: Text(isVi ? 'Cần con người duyệt' : 'Human review required'),
              subtitle: Text(isVi ? 'Hãy rà soát chính sách, nội dung, thanh toán và store listing trước khi phát hành.' : 'Review policy, content, billing, and store listing before release.'),
            ),
          ),
        ],
      ),
    );
  }
}
"""
    write_text(ctx.app_dir / "lib" / "features" / "privacy" / "privacy_screen.dart", privacy_screen)

    if has_paywall:
        purchase_service = """class PurchaseService {
  const PurchaseService();

  bool get productionBillingEnabled => false;

  Future<String> startPlaceholderPurchase(String planName) async {
    await Future<void>.delayed(const Duration(milliseconds: 300));
    return 'Mô phỏng thanh toán cho $planName. Cần cấu hình StoreKit hoặc Google Play Billing trước khi phát hành.';
  }
}
"""
        paywall_screen = """import 'package:flutter/material.dart';

import '../../core/app_content.dart';
import 'purchase_service.dart';

class PaywallScreen extends StatefulWidget {
  const PaywallScreen({super.key});

  @override
  State<PaywallScreen> createState() => _PaywallScreenState();
}

class _PaywallScreenState extends State<PaywallScreen> {
  final _purchaseService = const PurchaseService();
  String? _message;

  @override
  Widget build(BuildContext context) {
    final isVi = AppContent.defaultLanguage == 'vi';
    return Scaffold(
      appBar: AppBar(title: Text(AppContent.paywallTitle)),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(AppContent.paywallTitle, style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 12),
          Text(isVi ? 'Thanh toán đang ở chế độ mô phỏng. Cần cấu hình StoreKit hoặc Google Play Billing trước khi phát hành.' : '${AppContent.appName} uses simulated billing until real store billing is reviewed.'),
          const SizedBox(height: 12),
          Card(
            child: ListTile(
              leading: const Icon(Icons.workspace_premium_outlined),
              title: Text(isVi ? 'Gói học nâng cao' : 'Pro study plan'),
              subtitle: Text(isVi ? 'Mở khóa lộ trình nâng cao sau khi con người cấu hình thanh toán thật.' : 'Human-reviewed billing is required before store release.'),
              trailing: FilledButton(
                onPressed: () async {
                  final message = await _purchaseService.startPlaceholderPurchase(isVi ? 'Gói học nâng cao' : 'Pro study plan');
                  if (mounted) setState(() => _message = message);
                },
                child: Text(isVi ? 'Xem thử' : 'Preview'),
              ),
            ),
          ),
          if (_message != null) ...[
            const SizedBox(height: 12),
            Card(
              child: ListTile(
                leading: const Icon(Icons.check_circle_outline),
                title: Text(AppContent.successMessage),
                subtitle: Text(_message!),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
"""
        write_text(ctx.app_dir / "lib" / "features" / "paywall" / "purchase_service.dart", purchase_service)
        write_text(ctx.app_dir / "lib" / "features" / "paywall" / "paywall_screen.dart", paywall_screen)

    widget_test = """import 'package:flutter_test/flutter_test.dart';
import 'package:forge_trend_app_template/app.dart';
import 'package:forge_trend_app_template/core/app_content.dart';

void main() {
  testWidgets('onboarding leads to home dashboard', (tester) async {
    await tester.pumpWidget(const ForgeTrendApp());

    expect(find.text(AppContent.appName), findsOneWidget);
    expect(find.text(AppContent.startLabel), findsOneWidget);

    await tester.tap(find.text(AppContent.startLabel));
    await tester.pumpAndSettle();

    expect(find.text(AppContent.homeTitle), findsWidgets);
    expect(find.text(AppContent.featureTitle), findsWidgets);
    expect(find.text(AppContent.progressTitle), findsOneWidget);
  });

  testWidgets('paywall visible when subscription enabled', (tester) async {
    await tester.pumpWidget(const ForgeTrendApp());

    await tester.tap(find.text(AppContent.startLabel));
    await tester.pumpAndSettle();

    if (AppContent.subscriptionEnabled) {
      await tester.scrollUntilVisible(find.text(AppContent.paywallTitle), 120);
      expect(find.text(AppContent.paywallTitle), findsOneWidget);
    }
  });

  testWidgets('settings and privacy screen exists', (tester) async {
    await tester.pumpWidget(const ForgeTrendApp());

    await tester.tap(find.text(AppContent.startLabel));
    await tester.pumpAndSettle();
    await tester.tap(find.text(AppContent.settingsLabel));
    await tester.pumpAndSettle();

    expect(find.text(AppContent.settingsLabel), findsWidgets);
    expect(find.text(AppContent.privacyTitle), findsOneWidget);
  });

  testWidgets('core feature flow can update progress', (tester) async {
    await tester.pumpWidget(const ForgeTrendApp());

    await tester.tap(find.text(AppContent.startLabel));
    await tester.pumpAndSettle();
    await tester.tap(find.text(AppContent.featureTitle).last);
    await tester.pumpAndSettle();

    expect(find.text(AppContent.featureTitle), findsWidgets);
    await tester.tap(find.text(AppContent.primaryActionLabel));
    await tester.pumpAndSettle();
    expect(find.text(AppContent.successMessage), findsWidgets);
  });
}
"""
    write_text(ctx.app_dir / "test" / "widget_test.dart", widget_test)

    if created_app or not (ctx.app_dir / "PRIVACY_POLICY.md").exists():
        privacy = f"""# Privacy Policy Draft

{ctx.project["name"]} does not ship with production analytics, ads, or third-party data sharing in this MVP candidate.

Review this policy with a human before store submission.
"""
        write_text(ctx.app_dir / "PRIVACY_POLICY.md", privacy)

    if qa_error:
        write_text(ctx.workspace / "last_qa_error.txt", qa_error[-4000:])
        ctx.event("code_agent", "Recorded QA failure for human-readable fix context", level="warning", metadata_json={"iteration": iteration})

    git_commit(ctx, f"Code agent iteration {iteration}")
    runtime_provider = (ctx.runtime_config.get("provider") or {})
    runtime_provider_type = str(runtime_provider.get("provider_type") or "")
    runtime_auth_mode = str(runtime_provider.get("auth_mode") or "")
    configured_code_provider = "codex_cli" if runtime_provider_type == "codex_cli" else ("openai_compatible" if runtime_provider_type in {"openai_compatible", "openai"} else settings.worker_code_provider)
    provider_result: dict[str, Any] = {"provider": "deterministic", "skipped_reason": None, "runtime_provider_type": runtime_provider_type, "auth_mode": runtime_auth_mode}
    if not settings.worker_enable_codex and configured_code_provider == "codex_cli":
        ctx.event(
            "code_agent",
            "Deterministic scaffold mode active; Codex CLI was not required",
            metadata_json={"provider": "deterministic", "worker_enable_codex": False, "iteration": iteration},
        )
    elif configured_code_provider == "codex_cli":
        try:
            provider_result = run_codex_code_pass(ctx, iteration, qa_error)
        except ProviderUnavailable as exc:
            provider_result = {"provider": "codex_cli", "skipped_reason": str(exc)}
            ctx.event(
                "code_agent",
                "Codex CLI unavailable; falling back to deterministic scaffold",
                level="warning",
                metadata_json={"provider": "codex_cli", "reason": str(exc), "iteration": iteration},
            )
        except Exception as exc:
            provider_result = {"provider": "codex_cli", "error": str(exc)}
            ctx.event(
                "code_agent",
                "Codex CLI pass failed or timed out; falling back to deterministic scaffold and continuing QA",
                level="warning",
                stderr=str(exc),
                metadata_json={"provider": "codex_cli", "iteration": iteration},
            )
    elif configured_code_provider == "openai_compatible":
        strategy_prompt = f"""{skill_prompt_header(ctx.selected_skills)}

Review the generated Flutter app strategy for {ctx.project["name"]}. If there is a QA error, propose safe targeted fixes. Do not return secrets.

QA error:
{qa_error or "none"}"""
        assist = ctx.provider_text_assist("code_agent_strategy", strategy_prompt, max_output_tokens=900)
        assist_completed = assist.get("status") == "completed"
        provider_result = {
            "provider": "openai_compatible" if assist_completed else "deterministic",
            "status": assist.get("status"),
            "detail": assist.get("detail"),
            "skipped_reason": None if assist_completed else assist.get("detail"),
            "applied_as": "strategy_context" if assist_completed else "deterministic_fallback",
            "runtime_provider_type": runtime_provider_type,
            "auth_mode": runtime_auth_mode,
        }
        if assist.get("text"):
            strategy_path = ctx.artifacts_dir / f"provider_code_strategy_iteration_{iteration}.md"
            write_text(strategy_path, str(assist["text"]))
            ctx.api.artifact(ctx.project_id, "document", strategy_path.name, str(strategy_path), {"provider": assist.get("provider"), "status": assist.get("status")})
    else:
        provider_result = {"provider": configured_code_provider, "skipped_reason": "Provider is not implemented for code editing; deterministic scaffold kept", "runtime_provider_type": runtime_provider_type, "auth_mode": runtime_auth_mode}
        ctx.event(
            "code_agent",
            "Configured code provider is not implemented; kept deterministic scaffold",
            level="warning",
            metadata_json=provider_result,
        )

    ctx.api.artifact(ctx.project_id, "source", "Flutter app", str(ctx.app_dir))
    return {"app_dir": str(ctx.app_dir), "code_provider": provider_result, "providers": [adapter.describe() for adapter in ADAPTERS]}


def qa_agent(ctx: PipelineContext) -> dict[str, Any]:
    commands = [
        ["flutter", "pub", "get"],
        ["flutter", "analyze"],
        ["flutter", "test"],
        ["flutter", "build", "apk", "--debug"],
    ]
    results: list[dict[str, Any]] = []
    for command in commands:
        printable = " ".join(command)
        ctx.event("qa_agent", f"Running {printable}")
        completed = run_safe(command, cwd=ctx.app_dir, workspace=ctx.workspace, timeout=1200)
        ctx.api.qa_result(ctx.project_id, printable, completed.returncode, completed.stdout[-8000:], completed.stderr[-8000:])
        ctx.event(
            "qa_agent",
            f"Command finished: {printable}",
            level="info" if completed.returncode == 0 else "error",
            stdout=completed.stdout[-4000:],
            stderr=completed.stderr[-4000:],
            metadata_json={"exit_code": completed.returncode},
        )
        results.append(
            {
                "command": printable,
                "exit_code": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        )
        if completed.returncode != 0:
            return {"passed": False, "failed": results[-1], "results": results}

    apk_path = ctx.app_dir / "build" / "app" / "outputs" / "flutter-apk" / "app-debug.apk"
    if apk_path.exists():
        ctx.api.artifact(ctx.project_id, "build", "app-debug.apk", str(apk_path), {"platform": "android"})
        ctx.api.build(ctx.project_id, "passed", artifact_path=str(apk_path), logs="Android debug APK built")
    else:
        ctx.api.build(ctx.project_id, "passed", logs="Build command passed but APK path was not found")
    git_commit(ctx, "Record QA pass")
    return {"passed": True, "results": [{"command": item["command"], "exit_code": item["exit_code"]} for item in results]}


def policy_agent(ctx: PipelineContext) -> dict[str, Any]:
    issues: list[str] = []
    required_changes: list[str] = []

    suspicious_names = ["instagram", "tiktok", "spotify", "netflix", "whatsapp", "uber", "airbnb"]
    name_lower = ctx.project["name"].lower()
    if any(word in name_lower for word in suspicious_names):
        issues.append("Project name may include a protected brand or trademark.")
        required_changes.append("Rename the app with original branding before release.")

    privacy_path = ctx.app_dir / "PRIVACY_POLICY.md"
    if not privacy_path.exists():
        issues.append("Privacy policy placeholder is missing.")
        required_changes.append("Add a privacy policy placeholder before QA approval.")

    source_text = ""
    for path in ctx.app_dir.glob("lib/**/*.dart"):
        source_text += path.read_text(encoding="utf-8")
    if "sk-" in source_text or "api_key" in source_text.lower():
        issues.append("Potential hardcoded key marker found in Flutter source.")
        required_changes.append("Move all secrets to secure runtime configuration.")

    manifest = ctx.app_dir / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
    if manifest.exists() and "android.permission" in manifest.read_text(encoding="utf-8"):
        issues.append("Android permissions require human review.")
        required_changes.append("Remove permissions that are not essential to the MVP.")

    dart_files = list(ctx.app_dir.glob("lib/**/*.dart"))
    if len(dart_files) < 5:
        issues.append("Minimum functionality may be too thin.")
        required_changes.append("Keep onboarding, home, settings, theme, and shared widgets in the MVP.")

    risk = "low" if not issues else ("medium" if len(issues) <= 2 else "high")
    result = {"risk": risk, "passed": risk != "high", "issues": issues, "required_changes": required_changes}
    ctx.api.policy_result(ctx.project_id, result)
    ctx.event("policy_agent", "Policy checklist completed", level="info" if result["passed"] else "error", metadata_json=result)
    git_commit(ctx, "Record policy results")
    return result


def quality_gate_agent(ctx: PipelineContext, qa_output: dict[str, Any] | None = None, policy_output: dict[str, Any] | None = None) -> dict[str, Any]:
    brief = get_linked_brief(ctx)
    artifacts = ctx.api.list_project_artifacts(ctx.project_id)
    result = build_quality_gate_result(
        project=ctx.project,
        app_dir=ctx.app_dir,
        artifacts=artifacts,
        brief=brief,
        qa_output=qa_output,
        policy_output=policy_output,
    )
    quality_json_path = ctx.artifacts_dir / "quality_gate_report.json"
    quality_md_path = ctx.artifacts_dir / "quality_gate_report.md"
    store_md_path = ctx.artifacts_dir / "store_readiness_report.md"
    product_score_json_path = ctx.artifacts_dir / "product_score_report.json"
    product_score_md_path = ctx.artifacts_dir / "product_score_report.vi.md"
    write_text(quality_json_path, json.dumps(result, indent=2, ensure_ascii=False))
    write_text(quality_md_path, quality_gate_report_markdown(result))
    write_text(store_md_path, store_readiness_report_markdown(project=ctx.project, result=result, policy_output=policy_output))
    write_text(product_score_json_path, json.dumps(result, indent=2, ensure_ascii=False))
    write_text(product_score_md_path, product_score_report_markdown(result))
    ctx.api.artifact(ctx.project_id, "document", "quality_gate_report.json", str(quality_json_path), result)
    ctx.api.artifact(ctx.project_id, "document", "quality_gate_report.md", str(quality_md_path), {"score": result["score"], "passed": result["passed"]})
    ctx.api.artifact(ctx.project_id, "document", "store_readiness_report.md", str(store_md_path), {"score": result["score"], "passed": result["passed"]})
    ctx.api.artifact(ctx.project_id, "document", "product_score_report.json", str(product_score_json_path), result)
    ctx.api.artifact(ctx.project_id, "document", "product_score_report.vi.md", str(product_score_md_path), {"score": result["score"], "passed": result["passed"]})
    ctx.event(
        "quality_gate",
        "Product quality gate completed",
        level="info" if result["passed"] else "warning",
        metadata_json=result,
    )
    git_commit(ctx, "Record product quality gate reports")
    return result


def run_agent(ctx: PipelineContext, agent_name: str, fn, *, iteration: int = 0, **kwargs: Any) -> dict[str, Any]:
    ctx.update_task(agent_name, {"status": "running", "error_message": None})
    run = ctx.api.start_run(ctx.project_id, agent_name, {"project": ctx.project, "iteration": iteration}, iteration)
    run_id = run["id"]
    try:
        output = fn(ctx, **kwargs)
        ctx.api.finish_run(run_id, "succeeded", output_json=output)
        ctx.record_selected_skill_usage(agent_name, "succeeded", f"{agent_name} completed")
        task_payload: dict[str, Any] = {"status": "succeeded", "output_json": output}
        head = git_head(ctx)
        if head:
            task_payload["commit_sha"] = head
        ctx.update_task(agent_name, task_payload)
        return output
    except Exception as exc:
        ctx.api.finish_run(run_id, "failed", error_message=str(exc))
        ctx.record_selected_skill_usage(agent_name, "failed", f"{agent_name} failed: {exc}")
        ctx.update_task(agent_name, {"status": "failed", "error_message": str(exc)})
        ctx.event(agent_name, f"{agent_name} failed", level="error", agent_run_id=run_id, stderr=str(exc))
        raise


def run_pipeline(api: FactoryApi, project_id: str) -> None:
    started_at = time.monotonic()
    project = api.get_project(project_id)
    ideas = api.list_ideas()
    idea = next((item for item in ideas if item["id"] == project.get("idea_id")), None)
    tasks = api.list_project_tasks(project_id)

    workspace_root = settings.worker_workspace_root
    if not workspace_root.is_absolute():
        workspace_root = REPO_ROOT / workspace_root
    workspace_root.mkdir(parents=True, exist_ok=True)
    workspace = (workspace_root / project_id).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "docs").mkdir(exist_ok=True)
    (workspace / "artifacts").mkdir(exist_ok=True)

    ctx = PipelineContext(api, project, workspace, idea, tasks)
    linked_brief_for_config = get_linked_brief(ctx)
    runtime_config = with_latest_learning_rules(api, sanitized_runtime_config(api, linked_brief_for_config), linked_brief_for_config)
    selected_skills = select_skills(brief=linked_brief_for_config, runtime_config=runtime_config)
    ctx.runtime_config = runtime_config
    ctx.selected_skills = selected_skills
    runtime_settings = api.app_settings()
    max_fix_iterations = int(runtime_settings.get("max_fix_iterations") or settings.worker_max_fix_iterations)
    api.set_project_status(project_id, "running", str(workspace))
    ctx.event("pipeline", "Pipeline started", metadata_json={"workspace": str(workspace), "config": config_summary(runtime_config)})
    if runtime_config.get("applied_learning_rules"):
        ctx.event(
            "autopilot_strategy_change",
            "Learning Memory adjusted this run before agents started.",
            metadata_json={"applied_learning_rules": runtime_config.get("applied_learning_rules")},
        )
    ctx.event(
        "autopilot",
        "Autopilot started: planning full app factory run",
        metadata_json={"state": "planning", "project_id": project_id, "config": config_summary(runtime_config), "skills": selected_skills},
    )
    for skill in selected_skills:
        try:
            api.record_skill_run(
                {
                    "skill_slug": skill["slug"],
                    "project_id": project_id,
                    "factory_brief_id": (linked_brief_for_config or {}).get("id"),
                    "agent_name": "autopilot_pipeline",
                    "output_summary": skill.get("reason", ""),
                    "tokens_estimated": skill.get("token_budget", 0),
                    "status": "used",
                }
            )
        except Exception:
            pass
    for task in tasks:
        brief_id = task.get("input_json", {}).get("factory_brief_id")
        if brief_id:
            api.factory_brief_event(
                str(brief_id),
                "pipeline_started",
                f"Project pipeline started for {project['name']}.",
                metadata_json={"step": "pipeline_started", "project_id": project_id, "workspace": str(workspace)},
            )
            break

    try:
        ctx.event("autopilot", "Đang lập PRD từ brief và candidate đã chọn.", metadata_json={"state": "planning"})
        run_checked_agent(ctx, "prd_agent", prd_agent)
        ctx.event("autopilot", "Đang thiết kế luồng sản phẩm và trạng thái UX.", metadata_json={"state": "designing"})
        run_checked_agent(ctx, "ux_agent", ux_agent)
        ctx.event("autopilot", "Đang tạo source Flutter và artifact blueprint/store assets.", metadata_json={"state": "coding"})
        code_output = run_checked_agent(ctx, "code_agent", code_agent, iteration=0)

        qa_output: dict[str, Any] | None = None
        fix_iterations = 0
        for iteration in range(max_fix_iterations + 1):
            ctx.event("autopilot", f"Đang chạy QA lần {iteration + 1}.", metadata_json={"state": "testing", "iteration": iteration})
            qa_output = run_checked_agent(ctx, "qa_agent", qa_agent, iteration=iteration)
            if qa_output.get("passed"):
                break
            failed = qa_output["failed"]
            if iteration >= max_fix_iterations:
                break
            error_text = f"{failed['command']}\nSTDOUT:\n{failed['stdout'][-4000:]}\nSTDERR:\n{failed['stderr'][-4000:]}"
            decision = autopilot_decision("fixing", error_text, iteration + 1, max_fix_iterations)
            ctx.event("autopilot_decision", "QA failure classified and next action selected.", level="warning", metadata_json=decision)
            if decision["action"] != "retry_fix":
                ctx.event("autopilot_blocked", "Autopilot stopped QA repair and requires human review.", level="warning", metadata_json=decision)
                break
            ctx.event("autopilot", "QA thất bại. Autopilot đang yêu cầu Code Agent sửa lỗi.", level="warning", metadata_json=decision)
            ctx.event("autopilot_retry", "Retrying Code Agent after QA failure.", level="warning", metadata_json=decision)
            run_checked_agent(ctx, "code_agent", code_agent, iteration=iteration + 1, qa_error=error_text)
            fix_iterations += 1

        ctx.event("autopilot", "Đang chạy policy gate.", metadata_json={"state": "evaluating", "gate": "policy"})
        policy_output = run_checked_agent(ctx, "policy_agent", policy_agent)
        if not policy_output.get("passed"):
            for policy_iteration in range(MAX_POLICY_FIX_ITERATIONS):
                reason = "; ".join(policy_output.get("issues") or ["Policy gate failed"])
                decision = autopilot_decision("fixing", reason, policy_iteration + 1, MAX_POLICY_FIX_ITERATIONS)
                ctx.event("autopilot_decision", "Policy failure classified and next action selected.", level="warning", metadata_json=decision)
                ctx.event("autopilot", "Policy Gate phát hiện vấn đề. Autopilot thử sửa copy/naming/permission trong giới hạn an toàn.", level="warning", metadata_json=decision)
                if decision["action"] != "retry_fix":
                    ctx.event("autopilot_blocked", "Autopilot stopped policy repair and requires human review.", level="warning", metadata_json=decision)
                    break
                ctx.event("autopilot_retry", "Retrying Code Agent after policy failure.", level="warning", metadata_json=decision)
                run_checked_agent(ctx, "code_agent", code_agent, iteration=max_fix_iterations + policy_iteration + 1, qa_error=f"Policy gate failure:\n{reason}")
                fix_iterations += 1
                policy_output = run_checked_agent(ctx, "policy_agent", policy_agent)
                if policy_output.get("passed"):
                    break

        ctx.event("autopilot", "Đang chạy product quality/store readiness gate.", metadata_json={"state": "evaluating", "gate": "quality"})
        quality_output = run_checked_agent(ctx, "quality_gate_agent", quality_gate_agent, qa_output=qa_output, policy_output=policy_output)
        if not quality_output.get("passed"):
            for quality_iteration in range(MAX_QUALITY_FIX_ITERATIONS):
                reason = "; ".join(quality_output.get("issues") or ["Quality gate failed"])
                decision = autopilot_decision("fixing", reason, quality_iteration + 1, MAX_QUALITY_FIX_ITERATIONS)
                ctx.event("autopilot_decision", "Quality failure classified and next action selected.", level="warning", metadata_json=decision)
                ctx.event("autopilot", "Quality Gate phát hiện app còn yếu. Autopilot thử làm sâu feature flow.", level="warning", metadata_json=decision)
                if decision["action"] != "retry_fix":
                    ctx.event("autopilot_blocked", "Autopilot stopped quality repair and requires human review.", level="warning", metadata_json=decision)
                    break
                ctx.event("autopilot_strategy_change", "Switching to product-depth repair strategy.", level="warning", metadata_json=decision)
                ctx.event("autopilot_retry", "Retrying Code Agent after quality failure.", level="warning", metadata_json=decision)
                run_checked_agent(ctx, "code_agent", code_agent, iteration=max_fix_iterations + MAX_POLICY_FIX_ITERATIONS + quality_iteration + 1, qa_error=f"Quality gate failure:\n{reason}\nDeepen product-specific interaction and remove generic copy.")
                fix_iterations += 1
                qa_output = run_checked_agent(ctx, "qa_agent", qa_agent)
                policy_output = run_checked_agent(ctx, "policy_agent", policy_agent)
                quality_output = run_checked_agent(ctx, "quality_gate_agent", quality_gate_agent, qa_output=qa_output, policy_output=policy_output)
                if quality_output.get("passed"):
                    break

        final_status = "release_candidate" if qa_output and qa_output.get("passed") and policy_output.get("passed") and quality_output.get("passed") else "NEEDS_HUMAN_REVIEW"
        for skill in selected_skills:
            try:
                api.record_skill_run(
                    {
                        "skill_slug": skill["slug"],
                        "project_id": project_id,
                        "factory_brief_id": (linked_brief_for_config or {}).get("id"),
                        "agent_name": "autopilot_retrospective",
                        "output_summary": f"Final status {final_status}; quality score {(quality_output or {}).get('score')}",
                        "tokens_estimated": skill.get("token_budget", 0),
                        "status": "succeeded" if final_status == "release_candidate" else "used",
                        "quality_delta": int((quality_output or {}).get("score") or 0) - 75,
                    }
                )
            except Exception:
                pass
        provider = str((code_output or {}).get("code_provider", {}).get("provider") or "deterministic")
        archetype = None
        blueprint_path = ctx.artifacts_dir / "app_blueprint.json"
        if blueprint_path.exists():
            try:
                archetype = json.loads(blueprint_path.read_text(encoding="utf-8")).get("archetype")
            except Exception:
                archetype = None
        evaluation_payload = build_run_evaluation(
            brief=get_linked_brief(ctx),
            project=ctx.project,
            provider=provider,
            archetype=archetype,
            final_status=final_status,
            qa_output=qa_output,
            policy_output=policy_output,
            quality_output=quality_output,
            elapsed_seconds=int(time.monotonic() - started_at),
            fix_iterations=fix_iterations,
        )
        ctx.event("autopilot", "Đang ghi learning memory cho lần chạy này.", metadata_json={"state": "learning", "evaluation": evaluation_payload})
        ctx.api.run_evaluation(evaluation_payload)
        if final_status == "release_candidate":
            api.set_project_status(project_id, "release_candidate", str(workspace))
            write_factory_run_report(ctx, qa_output, policy_output, "release_candidate", quality_output)
            ctx.event("autopilot_completed", "Autopilot completed with release_candidate.", metadata_json={"final_status": final_status, "fix_iterations": fix_iterations})
            ctx.event("pipeline", "Pipeline completed successfully")
            for task in tasks:
                brief_id = task.get("input_json", {}).get("factory_brief_id")
                if brief_id:
                    api.factory_brief_event(
                        str(brief_id),
                        "pipeline_finished",
                        "Pipeline finished with release_candidate.",
                        level="success",
                        metadata_json={"step": "pipeline_finished", "project_id": project_id, "final_status": "release_candidate"},
                    )
                    break
        else:
            api.set_project_status(project_id, "NEEDS_HUMAN_REVIEW", str(workspace))
            write_factory_run_report(ctx, qa_output, policy_output, "NEEDS_HUMAN_REVIEW", quality_output)
            ctx.event("autopilot_blocked", "Autopilot reached limits or gates and needs human review.", level="warning", metadata_json={"final_status": final_status, "fix_iterations": fix_iterations})
            ctx.event(
                "pipeline",
                "Pipeline needs human review",
                level="warning",
                metadata_json={
                    "qa_passed": bool(qa_output and qa_output.get("passed")),
                    "policy_passed": bool(policy_output.get("passed")),
                    "quality_passed": bool(quality_output.get("passed")),
                    "quality_score": quality_output.get("score"),
                    "next_action": "Review quality_gate_report.md and store_readiness_report.md, fix required changes, then rerun.",
                },
            )
            for task in tasks:
                brief_id = task.get("input_json", {}).get("factory_brief_id")
                if brief_id:
                    api.factory_brief_event(
                        str(brief_id),
                        "pipeline_finished",
                        "Pipeline finished with NEEDS_HUMAN_REVIEW.",
                        level="warning",
                        metadata_json={"step": "pipeline_finished", "project_id": project_id, "final_status": "NEEDS_HUMAN_REVIEW"},
                    )
                    break
    except PipelineStopped as exc:
        api.set_project_status(project_id, "stopped", str(workspace))
        write_factory_run_report(ctx, None, None, "stopped")
        ctx.event("pipeline", "Pipeline stopped", level="warning", stderr=str(exc))
        for task in tasks:
            brief_id = task.get("input_json", {}).get("factory_brief_id")
            if brief_id:
                api.factory_brief_event(
                    str(brief_id),
                    "pipeline_finished",
                    "Pipeline stopped before completion.",
                    level="warning",
                    metadata_json={"step": "pipeline_finished", "project_id": project_id, "final_status": "stopped", "reason": str(exc)},
                )
                break
    except Exception:
        api.set_project_status(project_id, "NEEDS_HUMAN_REVIEW", str(workspace))
        write_factory_run_report(ctx, None, None, "NEEDS_HUMAN_REVIEW")
        raise
