import json
import shutil
from pathlib import Path
from typing import Any

from daemon.api import FactoryApi
from daemon.config import settings
from daemon.cost_guard import check_cost_limit
from daemon.provider_adapters import ADAPTERS, ProviderUnavailable, run_codex_cli
from daemon.research.providers import build_research_bundle
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


def compact_list(values: list[Any], fallback: list[str]) -> list[str]:
    items = [str(item).strip() for item in values if str(item).strip()]
    return items[:6] or fallback


def dart_string(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ")


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


def write_factory_run_report(ctx: PipelineContext, qa_output: dict[str, Any] | None, policy_output: dict[str, Any] | None, final_status: str) -> None:
    brief_id = next(
        (
            str(task.get("input_json", {}).get("factory_brief_id"))
            for task in ctx.tasks_by_agent.values()
            if task.get("input_json", {}).get("factory_brief_id")
        ),
        "",
    )
    candidate_id = next(
        (
            str(task.get("input_json", {}).get("candidate_id"))
            for task in ctx.tasks_by_agent.values()
            if task.get("input_json", {}).get("candidate_id")
        ),
        "",
    )
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


def run_factory_brief(api: FactoryApi, brief_id: str) -> None:
    brief = api.get_factory_brief(brief_id)
    try:
        api.factory_brief_event(
            brief_id,
            "worker_picked_brief",
            "A worker picked up this factory brief.",
            metadata_json={"step": "worker_picked_brief", "mode": brief.get("mode")},
        )
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
        ignore = shutil.ignore_patterns(".dart_tool", "build", ".idea", ".gradle", "*.iml", "android/local.properties")
        shutil.copytree(TEMPLATE_ROOT, ctx.app_dir, ignore=ignore)
        created_app = True
        ctx.event("code_agent", "Flutter template copied", metadata_json={"template": str(TEMPLATE_ROOT), "app_dir": str(ctx.app_dir)})
    else:
        ctx.event("code_agent", "Flutter app already exists; preparing code pass", metadata_json={"iteration": iteration})

    title = ctx.project["name"]
    about = ctx.idea["description"] if ctx.idea else "A focused original mobile app generated by ForgeTrend."
    evidence = ctx.idea.get("evidence_json", {}) if ctx.idea else {}
    core_features = compact_list(evidence.get("core_features", []), ["Guided first session", "Daily progress dashboard", "Local sample data"])
    has_paywall = any(
        bool(value)
        for value in [
            (evidence.get("subscription_plan_json") or {}).get("enabled") if isinstance(evidence.get("subscription_plan_json"), dict) else False,
            (evidence.get("iap_plan_json") or {}).get("enabled") if isinstance(evidence.get("iap_plan_json"), dict) else False,
            "subscription" in about.lower(),
            "iap" in about.lower(),
        ]
    )
    dart_features = ",\n".join(f"    '{dart_string(feature)}'" for feature in core_features)
    title_literal = dart_string(title)
    about_literal = dart_string(about)[:900]
    constants = f"""class AppContent {{
  const AppContent._();

  static const String appName = '{title_literal}';
  static const String tagline = 'Original workflow, clear next action.';
  static const String idea = '{about_literal}';
  static const bool subscriptionEnabled = {'true' if has_paywall else 'false'};
  static const List<String> coreFeatures = [
{dart_features}
  ];
}}
"""
    write_text(ctx.app_dir / "lib" / "core" / "app_content.dart", constants)

    if has_paywall:
        purchase_service = """class PurchaseService {
  const PurchaseService();

  bool get productionBillingEnabled => false;

  Future<String> startPlaceholderPurchase(String planName) async {
    await Future<void>.delayed(const Duration(milliseconds: 300));
    return 'Purchase placeholder for $planName. Add reviewed store billing before release.';
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
    return Scaffold(
      appBar: AppBar(title: const Text('Premium')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Premium placeholder', style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 12),
          Text('${AppContent.appName} can reserve premium flows without enabling production billing.'),
          const SizedBox(height: 12),
          Card(
            child: ListTile(
              leading: const Icon(Icons.workspace_premium_outlined),
              title: const Text('Pro study plan'),
              subtitle: const Text('Human-reviewed billing is required before store release.'),
              trailing: FilledButton(
                onPressed: () async {
                  final message = await _purchaseService.startPlaceholderPurchase('Pro study plan');
                  if (mounted) setState(() => _message = message);
                },
                child: const Text('Preview'),
              ),
            ),
          ),
          if (_message != null) ...[
            const SizedBox(height: 12),
            Card(
              child: ListTile(
                leading: const Icon(Icons.check_circle_outline),
                title: const Text('Success feedback'),
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
    expect(find.text('Start'), findsOneWidget);

    await tester.tap(find.text('Start'));
    await tester.pumpAndSettle();

    expect(find.text('Today'), findsOneWidget);
    expect(find.text('Next action'), findsOneWidget);
    expect(find.text('Core flow'), findsOneWidget);
  });

  testWidgets('paywall visible when subscription enabled', (tester) async {
    await tester.pumpWidget(const ForgeTrendApp());

    await tester.tap(find.text('Start'));
    await tester.pumpAndSettle();

    if (AppContent.subscriptionEnabled) {
      await tester.scrollUntilVisible(find.text('Premium'), 120);
      expect(find.text('Premium'), findsOneWidget);
    }
  });

  testWidgets('settings and privacy screen exists', (tester) async {
    await tester.pumpWidget(const ForgeTrendApp());

    await tester.tap(find.text('Start'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Settings'));
    await tester.pumpAndSettle();

    expect(find.text('Settings'), findsWidgets);
    expect(find.text('Privacy policy'), findsOneWidget);
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
    if not settings.worker_enable_codex:
        ctx.event(
            "code_agent",
            "Deterministic scaffold mode active; Codex CLI was not required",
            metadata_json={"provider": "deterministic", "worker_enable_codex": False, "iteration": iteration},
        )
    elif settings.worker_code_provider == "codex_cli":
        try:
            provider_result = run_codex_code_pass(ctx, iteration, qa_error)
        except ProviderUnavailable as exc:
            provider_result = {"provider": "codex_cli", "skipped_reason": str(exc)}
            ctx.event(
                "code_agent",
                "Codex CLI unavailable; kept deterministic scaffold",
                level="warning",
                metadata_json={"provider": "codex_cli", "reason": str(exc), "iteration": iteration},
            )
            if settings.worker_enable_codex:
                raise
        except Exception as exc:
            provider_result = {"provider": "codex_cli", "error": str(exc)}
            ctx.event(
                "code_agent",
                "Codex CLI pass failed or timed out; continuing to QA with current workspace",
                level="warning",
                stderr=str(exc),
                metadata_json={"provider": "codex_cli", "iteration": iteration},
            )
            if settings.worker_enable_codex:
                raise
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
            write_factory_run_report(ctx, qa_output, policy_output, "release_candidate")
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
            write_factory_run_report(ctx, qa_output, policy_output, "NEEDS_HUMAN_REVIEW")
            ctx.event("pipeline", "Pipeline needs human review", level="warning")
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
