import json
import shutil
from pathlib import Path
from typing import Any

from daemon.api import FactoryApi
from daemon.config import settings
from daemon.cost_guard import check_cost_limit
from daemon.provider_adapters import ADAPTERS, ProviderUnavailable, run_codex_cli
from daemon.safety import run_safe


REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_ROOT = REPO_ROOT / "templates" / "flutter_mobile_app"


def slug_to_title(slug: str) -> str:
    return " ".join(word.capitalize() for word in slug.replace("_", "-").split("-") if word)


class PipelineContext:
    def __init__(self, api: FactoryApi, project: dict[str, Any], workspace: Path, idea: dict[str, Any] | None) -> None:
        self.api = api
        self.project = project
        self.project_id = project["id"]
        self.workspace = workspace
        self.idea = idea

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
                "Codex CLI pass failed; continuing to QA with current workspace",
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
    run = ctx.api.start_run(ctx.project_id, agent_name, {"project": ctx.project, "iteration": iteration}, iteration)
    run_id = run["id"]
    try:
        output = fn(ctx, **kwargs)
        ctx.api.finish_run(run_id, "succeeded", output_json=output)
        return output
    except Exception as exc:
        ctx.api.finish_run(run_id, "failed", error_message=str(exc))
        ctx.event(agent_name, f"{agent_name} failed", level="error", agent_run_id=run_id, stderr=str(exc))
        raise


def run_pipeline(api: FactoryApi, project_id: str) -> None:
    project = api.get_project(project_id)
    ideas = api.list_ideas()
    idea = next((item for item in ideas if item["id"] == project.get("idea_id")), None)

    workspace_root = settings.worker_workspace_root
    if not workspace_root.is_absolute():
        workspace_root = REPO_ROOT / workspace_root
    workspace_root.mkdir(parents=True, exist_ok=True)
    workspace = (workspace_root / project_id).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "docs").mkdir(exist_ok=True)
    (workspace / "artifacts").mkdir(exist_ok=True)

    ctx = PipelineContext(api, project, workspace, idea)
    api.set_project_status(project_id, "running", str(workspace))
    ctx.event("pipeline", "Pipeline started", metadata_json={"workspace": str(workspace)})

    try:
        run_agent(ctx, "prd_agent", prd_agent)
        run_agent(ctx, "ux_agent", ux_agent)
        run_agent(ctx, "code_agent", code_agent, iteration=0)

        qa_output: dict[str, Any] | None = None
        for iteration in range(settings.worker_max_fix_iterations + 1):
            qa_output = run_agent(ctx, "qa_agent", qa_agent, iteration=iteration)
            if qa_output.get("passed"):
                break
            failed = qa_output["failed"]
            if iteration >= settings.worker_max_fix_iterations:
                break
            error_text = f"{failed['command']}\nSTDOUT:\n{failed['stdout'][-4000:]}\nSTDERR:\n{failed['stderr'][-4000:]}"
            run_agent(ctx, "code_agent", code_agent, iteration=iteration + 1, qa_error=error_text)

        policy_output = run_agent(ctx, "policy_agent", policy_agent)
        if qa_output and qa_output.get("passed") and policy_output.get("passed"):
            api.set_project_status(project_id, "release_candidate", str(workspace))
            ctx.event("pipeline", "Pipeline completed successfully")
        else:
            api.set_project_status(project_id, "NEEDS_HUMAN_REVIEW", str(workspace))
            ctx.event("pipeline", "Pipeline needs human review", level="warning")
    except Exception:
        api.set_project_status(project_id, "NEEDS_HUMAN_REVIEW", str(workspace))
        raise
