import json
import shutil
from pathlib import Path
from typing import Any

from daemon.api import FactoryApi
from daemon.config import settings
from daemon.cost_guard import check_cost_limit
from daemon.provider_adapters import ADAPTERS, ProviderUnavailable, run_codex_cli
from daemon.research import DeterministicResearchProvider, ResearchBundle, WebResearchProvider
from daemon.safety import run_safe


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
    ) -> None:
        self.api = api
        self.project = project
        self.project_id = project["id"]
        self.workspace = workspace
        self.idea = idea
        self.tasks_by_agent = {task["agent_name"]: task for task in (tasks or [])}

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


def first_sentence(value: str, fallback: str) -> str:
    normalized = " ".join(value.strip().split())
    if not normalized:
        return fallback
    for marker in [". ", "! ", "? "]:
        if marker in normalized:
            return normalized.split(marker, 1)[0].strip()
    return normalized[:180]


def compact_list(values: list[Any], fallback: list[str]) -> list[str]:
    items = [str(item).strip() for item in values if str(item).strip()]
    return items[:6] or fallback


def derive_focus_terms(brief: dict[str, Any]) -> list[str]:
    raw = f"{brief.get('title', '')} {brief.get('raw_prompt', '')} {brief.get('target_category') or ''}".lower()
    stopwords = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "app",
        "build",
        "make",
        "create",
        "best",
        "trend",
        "search",
        "auto",
        "mobile",
        "user",
        "users",
        "have",
        "from",
        "into",
        "your",
        "their",
        "mvp",
    }
    terms: list[str] = []
    for token in "".join(char if char.isalnum() else " " for char in raw).split():
        if len(token) < 3 or token in stopwords:
            continue
        if token not in terms:
            terms.append(token)
    return terms[:8] or ["focused", "workflow", "assistant"]


def monetization_text(brief: dict[str, Any]) -> str:
    modes: list[str] = []
    if brief.get("iap_enabled"):
        modes.append("one-time in-app purchases for advanced packs or exports")
    if brief.get("subscription_enabled"):
        modes.append("subscription for ongoing coaching, sync, or premium automation")
    if brief.get("ads_enabled"):
        modes.append("careful ad placement after the core workflow is proven")
    if brief.get("monetization_mode") and brief.get("monetization_mode") != "none":
        modes.append(str(brief["monetization_mode"]).replace("_", " "))
    return "; ".join(modes) if modes else "Validate retention first, then add freemium upgrade points after human review."


def deterministic_findings(brief: dict[str, Any]) -> list[dict[str, Any]]:
    terms = derive_focus_terms(brief)
    category = brief.get("target_category") or terms[0].title()
    prompt_summary = first_sentence(str(brief.get("raw_prompt") or ""), "User wants the factory to identify a strong app opportunity.")
    return [
        {
            "source": "brief_intent",
            "title": f"{category} intent signal",
            "summary": prompt_summary,
            "category": category,
            "keywords": terms,
            "pain_points": [
                "Users need a clearer next action instead of another generic tracker.",
                "Existing tools often require too much setup before value appears.",
                "Trust, privacy, and originality need to be visible in the first session.",
            ],
            "competitor_gaps": [
                "Broad apps optimize for feature count instead of one repeated workflow.",
                "Onboarding rarely adapts to the user's first concrete goal.",
                "Monetization is often bolted on before the free value loop is proven.",
            ],
            "evidence_json": {"method": "deterministic_brief_analysis", "terms": terms},
            "confidence_score": 72,
        },
        {
            "source": "product_heuristic",
            "title": "MVP feasibility pattern",
            "summary": "A compact mobile app with onboarding, dashboard, guided actions, and settings can be built and tested by the current pipeline.",
            "category": category,
            "keywords": [*terms[:4], "onboarding", "dashboard", "qa"],
            "pain_points": [
                "Complex backend dependencies increase first-build failure risk.",
                "Thin scaffolds feel unfinished if the home screen has no state model.",
            ],
            "competitor_gaps": [
                "Many starter apps lack release policy checks.",
                "Most generated prototypes do not expose QA status and artifacts to the operator.",
            ],
            "evidence_json": {"pipeline_fit": "flutter_template_plus_codex_pass", "target_platforms": brief.get("target_platforms", ["android"])},
            "confidence_score": 68,
        },
        {
            "source": "monetization_fit",
            "title": "Revenue and policy fit",
            "summary": monetization_text(brief),
            "category": category,
            "keywords": [*terms[:3], "pricing", "policy", "retention"],
            "pain_points": [
                "Paid features need a clear value boundary.",
                "Subscription claims need careful copy and human review.",
            ],
            "competitor_gaps": [
                "Competitors often hide pricing until late in onboarding.",
                "Policy-sensitive domains need transparent disclaimers.",
            ],
            "evidence_json": {
                "iap_enabled": brief.get("iap_enabled", False),
                "subscription_enabled": brief.get("subscription_enabled", False),
                "ads_enabled": brief.get("ads_enabled", False),
            },
            "confidence_score": 64,
        },
    ]


def deterministic_candidates(brief: dict[str, Any], findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    terms = derive_focus_terms(brief)
    category = str(brief.get("target_category") or terms[0].title())
    title_seed = first_sentence(str(brief.get("title") or ""), f"{category} Companion")
    base_title = title_seed if len(title_seed) <= 54 else title_seed[:54].strip()
    raw_prompt = str(brief.get("raw_prompt") or brief.get("title") or "focused workflow")
    target_country = brief.get("target_country", "US")
    language = brief.get("target_language", "en")
    backend_mode = brief.get("backend_mode", "none")
    score_bonus = 8 if brief.get("subscription_enabled") or brief.get("iap_enabled") else 0
    backend_penalty = 8 if backend_mode not in {"none", "local"} else 0
    return [
        {
            "title": f"{base_title} Studio",
            "description": f"A focused {category.lower()} app that turns the user's first goal into a guided daily workflow with visible progress and privacy-aware defaults.",
            "target_user": f"Mobile users in {target_country} who want a practical {category.lower()} workflow in {language}.",
            "problem": first_sentence(raw_prompt, "The user needs a simpler way to turn intent into repeated action."),
            "unique_angle": "Start with one concrete user goal, then generate only the next useful action instead of a cluttered feature hub.",
            "core_features": [
                "Goal capture onboarding",
                "Daily action dashboard",
                "Progress and confidence status cards",
                "Local-first settings and export placeholder",
                "Human-review release checklist",
            ],
            "monetization_plan": monetization_text(brief),
            "iap_plan_json": {"enabled": bool(brief.get("iap_enabled")), "items": ["Advanced templates", "Export packs"]},
            "subscription_plan_json": {"enabled": bool(brief.get("subscription_enabled")), "tiers": ["Pro monthly", "Pro annual"]},
            "backend_plan_json": {"mode": backend_mode, "first_release": "local-first" if backend_mode == "none" else backend_mode},
            "opportunity_score": min(92, 74 + score_bonus - backend_penalty),
            "demand_score": 76,
            "pain_score": 78,
            "monetization_score": 72 + score_bonus,
            "build_feasibility_score": 84 - backend_penalty,
            "differentiation_score": 73,
            "policy_risk_score": 22,
            "originality_score": 81,
            "status": "proposed",
        },
        {
            "title": f"{category} Sprint Coach",
            "description": "A lightweight coach that creates short action sprints, reflection prompts, and a clean timeline for users who abandon heavier apps.",
            "target_user": "Users who already tried generic trackers but need a narrower guided routine.",
            "problem": "Generic productivity and learning tools create planning overhead before the user gets a useful action.",
            "unique_angle": "Compress planning into one short sprint loop: choose goal, do next action, reflect, repeat.",
            "core_features": [
                "Sprint setup",
                "Next-action queue",
                "Reflection log",
                "Progress streaks",
                "Privacy and export settings",
            ],
            "monetization_plan": monetization_text(brief),
            "iap_plan_json": {"enabled": bool(brief.get("iap_enabled")), "items": ["Sprint packs"]},
            "subscription_plan_json": {"enabled": bool(brief.get("subscription_enabled")), "tiers": ["Coach Plus"]},
            "backend_plan_json": {"mode": backend_mode},
            "opportunity_score": min(88, 69 + score_bonus),
            "demand_score": 72,
            "pain_score": 75,
            "monetization_score": 68 + score_bonus,
            "build_feasibility_score": 88 - backend_penalty,
            "differentiation_score": 68,
            "policy_risk_score": 18,
            "originality_score": 76,
            "status": "proposed",
        },
        {
            "title": f"{category} Field Notes",
            "description": "A note-to-action app that helps users capture friction, classify recurring pain points, and turn them into repeatable personal workflows.",
            "target_user": "Operators, learners, and creators who need structured field notes rather than a blank notes app.",
            "problem": "Useful observations get lost because capture tools do not convert notes into an executable plan.",
            "unique_angle": "Mine the user's own notes for recurring patterns, then suggest the next experiment.",
            "core_features": [
                "Structured capture",
                "Pattern tags",
                "Experiment planner",
                "Evidence timeline",
                "Review dashboard",
            ],
            "monetization_plan": "Best kept free-first until note retention is validated; add export packs later.",
            "iap_plan_json": {"enabled": bool(brief.get("iap_enabled")), "items": ["Export templates"]},
            "subscription_plan_json": {"enabled": False},
            "backend_plan_json": {"mode": "none"},
            "opportunity_score": 66,
            "demand_score": 65,
            "pain_score": 70,
            "monetization_score": 56,
            "build_feasibility_score": 90,
            "differentiation_score": 70,
            "policy_risk_score": 15,
            "originality_score": 78,
            "status": "proposed",
        },
    ]


def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def build_research_bundle(brief: dict[str, Any]) -> ResearchBundle:
    deterministic = DeterministicResearchProvider(deterministic_findings, deterministic_candidates).run(brief)
    urls = parse_csv(settings.research_allowed_urls)
    if brief.get("mode") != "auto_trend" or not urls:
        return deterministic

    web = WebResearchProvider(
        urls,
        allowed_domains=parse_csv(settings.research_allowed_domains),
        timeout_seconds=settings.research_web_timeout_seconds,
        delay_seconds=settings.research_web_delay_seconds,
    ).run(brief)
    findings = [*web.findings, *deterministic.findings]
    candidates = deterministic.candidates
    evidence = [*web.evidence, *deterministic.evidence]
    for finding in findings:
        evidence_json = dict(finding.get("evidence_json") or {})
        evidence_json.setdefault("research_evidence", evidence[:8])
        finding["evidence_json"] = evidence_json
    return ResearchBundle(findings=findings, candidates=candidates, evidence=evidence)


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


def run_factory_brief(api: FactoryApi, brief_id: str) -> None:
    brief = api.get_factory_brief(brief_id)
    api.factory_brief_event(brief_id, "Worker picked brief", "A worker picked up this factory brief.", metadata_json={"mode": brief.get("mode")})
    api.set_factory_brief_status(brief_id, "researching")
    api.factory_brief_event(brief_id, "Research started", "Research provider pass started.")
    bundle = build_research_bundle(brief)
    findings: list[dict[str, Any]] = []
    for payload in bundle.findings:
        findings.append(api.research_finding(brief_id, payload))
    api.factory_brief_event(
        brief_id,
        "Findings created",
        f"{len(findings)} research finding(s) were stored.",
        metadata_json={"finding_count": len(findings), "evidence": bundle.evidence[:6]},
    )

    api.set_factory_brief_status(brief_id, "scoring_candidates")
    api.factory_brief_event(brief_id, "Candidate scoring started", "Opportunity candidates are being scored.")
    candidates: list[dict[str, Any]] = []
    for payload in bundle.candidates:
        candidates.append(api.opportunity_candidate(brief_id, payload))
    candidates.sort(key=lambda item: int(item.get("opportunity_score") or 0), reverse=True)
    if not candidates:
        raise RuntimeError("Factory brief produced no candidates")
    api.factory_brief_event(
        brief_id,
        "Candidates created",
        f"{len(candidates)} opportunity candidate(s) were scored.",
        metadata_json={"candidate_count": len(candidates), "top_score": candidates[0].get("opportunity_score")},
    )

    write_factory_brief_report(brief, findings, candidates)
    selected = candidates[0]
    api.set_factory_brief_status(brief_id, "selecting_candidate")
    api.factory_brief_event(
        brief_id,
        "Candidate selected",
        f"{selected['title']} selected with score {selected.get('opportunity_score')}.",
        metadata_json={"candidate_id": selected["id"], "opportunity_score": selected.get("opportunity_score")},
    )
    response = api.finalize_factory_brief(brief_id, selected["id"], queue_pipeline=True)
    api.set_factory_brief_status(brief_id, "project_queued")
    project_id = response["project_id"]
    api.factory_brief_event(
        brief_id,
        "Project pipeline queued",
        f"Project {project_id} was queued on {response.get('queue')}.",
        metadata_json={"project_id": project_id, "queue": response.get("queue")},
    )
    api.event(
        project_id,
        "factory_brief",
        f"Autonomous factory selected candidate: {selected['title']}",
        metadata_json={"factory_brief_id": brief_id, "candidate_id": selected["id"], "opportunity_score": selected.get("opportunity_score")},
    )


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
    return f"""You are the ForgeTrend Code Agent running inside a local project workspace.

Task: {mode}.

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
- Settings with privacy and export placeholders.
- Local-first sample data and no hardcoded secrets.

## Screens
- Onboarding
- Home
- Settings

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
    path = ctx.docs_dir / "prd.md"
    write_text(path, prd)
    ctx.api.artifact(ctx.project_id, "document", "prd.md", str(path))
    ctx.event("prd_agent", "PRD generated", metadata_json={"path": str(path)})
    git_commit(ctx, "Generate PRD")
    return {"prd_path": str(path)}


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
    design_path = ctx.docs_dir / "design_system.md"
    flow_path = ctx.docs_dir / "screen_flow.md"
    write_text(design_path, design_system)
    write_text(flow_path, screen_flow)
    ctx.api.artifact(ctx.project_id, "document", "design_system.md", str(design_path))
    ctx.api.artifact(ctx.project_id, "document", "screen_flow.md", str(flow_path))
    ctx.event("ux_agent", "UX documents generated", metadata_json={"design_system": str(design_path), "screen_flow": str(flow_path)})
    git_commit(ctx, "Generate UX documents")
    return {"design_system_path": str(design_path), "screen_flow_path": str(flow_path)}


def code_agent(ctx: PipelineContext, iteration: int = 0, qa_error: str | None = None) -> dict[str, Any]:
    decision = check_cost_limit("deterministic_code_agent")
    if not decision.allowed:
        raise RuntimeError(decision.reason)
    created_app = False
    if not ctx.app_dir.exists():
        ignore = shutil.ignore_patterns(".dart_tool", "build", ".idea", "*.iml", "android/local.properties")
        shutil.copytree(TEMPLATE_ROOT, ctx.app_dir, ignore=ignore)
        created_app = True
        ctx.event("code_agent", "Flutter template copied", metadata_json={"template": str(TEMPLATE_ROOT), "app_dir": str(ctx.app_dir)})
    else:
        ctx.event("code_agent", "Flutter app already exists; preparing code pass", metadata_json={"iteration": iteration})

    if created_app or not (ctx.app_dir / "lib" / "core" / "app_content.dart").exists():
        title = ctx.project["name"]
        about = ctx.idea["description"] if ctx.idea else "A focused original mobile app generated by ForgeTrend."
        constants = f"""class AppContent {{
  const AppContent._();

  static const String appName = '{title.replace("'", "\\'")}';
  static const String tagline = 'Original workflow, clear next action.';
  static const String idea = '{about.replace("'", "\\'").replace("\n", " ")}';
}}
"""
        write_text(ctx.app_dir / "lib" / "core" / "app_content.dart", constants)

    if created_app or not (ctx.app_dir / "test" / "widget_test.dart").exists():
        widget_test = """import 'package:flutter_test/flutter_test.dart';
import 'package:forge_trend_app_template/app.dart';
import 'package:forge_trend_app_template/core/app_content.dart';

void main() {
  testWidgets('onboarding leads to home dashboard', (tester) async {
    await tester.pumpWidget(const ForgeTrendApp());

    expect(find.text(AppContent.appName), findsOneWidget);
    expect(find.text('Start'), findsOneWidget);

    await tester.tap(find.text('Start'));
    await tester.pumpAndSettle();

    expect(find.text('Today'), findsOneWidget);
    expect(find.text('Next action'), findsOneWidget);
  });
}
"""
        write_text(ctx.app_dir / "test" / "widget_test.dart", widget_test)

    if created_app or not (ctx.app_dir / "PRIVACY_POLICY.md").exists():
        privacy = f"""# Privacy Policy Placeholder

{ctx.project["name"]} does not ship with production analytics, ads, or third-party data sharing in this MVP scaffold.

Replace this placeholder with a reviewed policy before store submission.
"""
        write_text(ctx.app_dir / "PRIVACY_POLICY.md", privacy)

    if qa_error:
        write_text(ctx.workspace / "last_qa_error.txt", qa_error[-4000:])
        ctx.event("code_agent", "Recorded QA failure for human-readable fix context", level="warning", metadata_json={"iteration": iteration})

    git_commit(ctx, f"Code agent iteration {iteration}")
    provider_result: dict[str, Any] = {"provider": "deterministic", "skipped_reason": None}
    if settings.worker_code_provider == "codex_cli":
        try:
            provider_result = run_codex_code_pass(ctx, iteration, qa_error)
        except ProviderUnavailable as exc:
            provider_result = {"provider": "codex_cli", "skipped_reason": str(exc)}
            ctx.event(
                "code_agent",
                "Codex CLI unavailable; kept deterministic scaffold",
                level="warning",
                metadata_json={"reason": str(exc), "iteration": iteration},
            )
        except Exception as exc:
            provider_result = {"provider": "codex_cli", "error": str(exc)}
            ctx.event(
                "code_agent",
                "Codex CLI pass failed or timed out; continuing to QA with current workspace",
                level="warning",
                stderr=str(exc),
                metadata_json={"iteration": iteration},
            )
    else:
        provider_result = {"provider": settings.worker_code_provider, "skipped_reason": "Provider is not implemented"}
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


def run_agent(ctx: PipelineContext, agent_name: str, fn, *, iteration: int = 0, **kwargs: Any) -> dict[str, Any]:
    ctx.update_task(agent_name, {"status": "running", "error_message": None})
    run = ctx.api.start_run(ctx.project_id, agent_name, {"project": ctx.project, "iteration": iteration}, iteration)
    run_id = run["id"]
    try:
        output = fn(ctx, **kwargs)
        ctx.api.finish_run(run_id, "succeeded", output_json=output)
        task_payload: dict[str, Any] = {"status": "succeeded", "output_json": output}
        head = git_head(ctx)
        if head:
            task_payload["commit_sha"] = head
        ctx.update_task(agent_name, task_payload)
        return output
    except Exception as exc:
        ctx.api.finish_run(run_id, "failed", error_message=str(exc))
        ctx.update_task(agent_name, {"status": "failed", "error_message": str(exc)})
        ctx.event(agent_name, f"{agent_name} failed", level="error", agent_run_id=run_id, stderr=str(exc))
        raise


def run_pipeline(api: FactoryApi, project_id: str) -> None:
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
    runtime_settings = api.app_settings()
    max_fix_iterations = int(runtime_settings.get("max_fix_iterations") or settings.worker_max_fix_iterations)
    api.set_project_status(project_id, "running", str(workspace))
    ctx.event("pipeline", "Pipeline started", metadata_json={"workspace": str(workspace)})

    try:
        run_checked_agent(ctx, "prd_agent", prd_agent)
        run_checked_agent(ctx, "ux_agent", ux_agent)
        run_checked_agent(ctx, "code_agent", code_agent, iteration=0)

        qa_output: dict[str, Any] | None = None
        for iteration in range(max_fix_iterations + 1):
            qa_output = run_checked_agent(ctx, "qa_agent", qa_agent, iteration=iteration)
            if qa_output.get("passed"):
                break
            failed = qa_output["failed"]
            if iteration >= max_fix_iterations:
                break
            error_text = f"{failed['command']}\nSTDOUT:\n{failed['stdout'][-4000:]}\nSTDERR:\n{failed['stderr'][-4000:]}"
            run_checked_agent(ctx, "code_agent", code_agent, iteration=iteration + 1, qa_error=error_text)

        policy_output = run_checked_agent(ctx, "policy_agent", policy_agent)
        if qa_output and qa_output.get("passed") and policy_output.get("passed"):
            api.set_project_status(project_id, "release_candidate", str(workspace))
            ctx.event("pipeline", "Pipeline completed successfully")
        else:
            api.set_project_status(project_id, "NEEDS_HUMAN_REVIEW", str(workspace))
            ctx.event("pipeline", "Pipeline needs human review", level="warning")
    except PipelineStopped as exc:
        api.set_project_status(project_id, "stopped", str(workspace))
        ctx.event("pipeline", "Pipeline stopped", level="warning", stderr=str(exc))
    except Exception:
        api.set_project_status(project_id, "NEEDS_HUMAN_REVIEW", str(workspace))
        raise
