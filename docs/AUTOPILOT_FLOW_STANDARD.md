# Autopilot Flow Standard

ForgeTrend Autopilot is inspectable by design. Each run should emit events, artifacts, success criteria, fallback behavior, and a retrospective.

## 1. Load Config Profile

- Input: default or selected ConfigProfile.
- Output: sanitized runtime config snapshot.
- Success: provider, model, network, plugins, skills, and trust paths are resolved without secrets.
- Failure: missing profile or invalid provider.
- Retry policy: fallback to default deterministic profile.
- Fallback: deterministic scaffold mode.
- Event: `runtime_config_resolved`.
- Artifact: runtime config snapshot in FactoryBrief.

## 2. Select Mode

- Input: manual idea, auto trend, or continuation.
- Output: run profile and target constraints.
- Success: mode and run profile are stored on the brief.
- Failure: unknown mode.
- Retry policy: use manual idea.
- Fallback: `offline_deterministic`.
- Event: `brief_created`.
- Artifact: factory brief.

## 3. Select Skills

- Input: brief, runtime config, previous failures, quality issues.
- Output: ordered skill list.
- Success: relevant skill slugs and reasons are logged.
- Failure: no enabled skills.
- Retry policy: use built-in defaults.
- Fallback: deterministic prompts.
- Event: `skills_selected`.
- Artifact: skill_runs.

## 4. Research

- Input: prompt, category, country, language, research mode.
- Output: findings and evidence.
- Success: at least one finding.
- Failure: no finding or source unavailable.
- Retry policy: switch provider once.
- Fallback: deterministic evidence.
- Event: `research_provider_used`.
- Artifact: research findings.

## 5. Candidate Scoring

- Input: findings and brief constraints.
- Output: opportunity candidates.
- Success: candidates scored by demand, pain, monetization, feasibility, differentiation, originality, policy risk.
- Failure: no candidate.
- Retry policy: relax category once.
- Fallback: manual idea candidate.
- Event: `candidates_created`.
- Artifact: opportunity candidates.

## 6. Blueprint

- Input: selected candidate, config snapshot, selected skills.
- Output: app blueprint JSON and markdown.
- Success: app-specific core flow, screens, entities, actions, privacy, monetization posture.
- Failure: generic or empty blueprint.
- Retry policy: apply deeper feature-flow rule.
- Fallback: archetype blueprint.
- Event: `blueprint_created`.
- Artifact: `app_blueprint.json`.

## 7. Store Positioning

- Input: blueprint and policy constraints.
- Output: store asset drafts.
- Success: listing drafts are safe and marked for human review.
- Failure: copycat or exaggerated claims.
- Retry policy: rewrite naming/copy.
- Fallback: conservative generic-safe listing.
- Event: `store_assets_created`.
- Artifact: `store_assets/`.

## 8. Flutter Generation

- Input: blueprint, PRD, UX docs, code skill prompts.
- Output: Flutter source.
- Success: onboarding, home, core flow, settings, privacy, tests.
- Failure: source incomplete or Codex provider unavailable.
- Retry policy: deterministic scaffold first, optional Codex refinement.
- Fallback: deterministic generator.
- Event: `code_agent`.
- Artifact: source artifact.

## 9. Codex/Aider Refinement

- Input: workspace, PRD, UX docs, QA errors.
- Output: targeted patch.
- Success: provider exits cleanly and changed files are committed.
- Failure: auth, timeout, non-zero exit.
- Retry policy: one provider attempt per repair iteration.
- Fallback: deterministic code pass.
- Event: `code_agent`.
- Artifact: git commit and code event.

## 10. QA

- Input: Flutter source.
- Output: pub get, analyze, test, debug APK results.
- Success: all commands pass and APK artifact exists.
- Failure: first failing command.
- Retry policy: send failure to Code Agent until max iterations.
- Fallback: NEEDS_HUMAN_REVIEW.
- Event: `qa_agent`.
- Artifact: QA results and APK.

## 11. Auto-Fix

- Input: failed QA/policy/quality reason.
- Output: code/content repair.
- Success: failing gate passes on rerun.
- Failure: repeated same taxonomy.
- Retry policy: stop at configured max iterations.
- Fallback: NEEDS_HUMAN_REVIEW with blocker report.
- Event: `autopilot`.
- Artifact: `last_qa_error.txt` when relevant.

## 12. Quality Gate

- Input: source, artifacts, QA, policy, brief.
- Output: score and blocker list.
- Success: score meets threshold and no generic-copy blockers.
- Failure: weak flow, missing localization, missing artifact.
- Retry policy: apply deeper feature flow rule.
- Fallback: human review.
- Event: `quality_gate`.
- Artifact: quality reports.

## 13. Policy Gate

- Input: source, manifest, privacy, naming, monetization.
- Output: risk, issues, required changes.
- Success: risk is not high.
- Failure: trademark, secrets, permissions, missing privacy, billing confusion.
- Retry policy: safe rewrite/fix only.
- Fallback: human review.
- Event: `policy_agent`.
- Artifact: policy results.

## 14. Store Readiness

- Input: quality result, policy result, artifacts.
- Output: store readiness report.
- Success: tester can inspect one coherent package.
- Failure: missing APK, source, report, privacy, listing.
- Retry policy: regenerate missing docs/assets.
- Fallback: blocker list.
- Event: `store_readiness_checked`.
- Artifact: `store_readiness_report.md`.

## 15. Internal Test Package

- Input: project artifacts.
- Output: internal test package folder.
- Success: package includes APK/source pointer/report/store assets/README/blockers.
- Failure: required artifact missing.
- Retry policy: regenerate package after artifacts exist.
- Fallback: partial package with blockers.
- Event: `internal_test_package_created`.
- Artifact: `internal_test_package/`.

## 16. Learning Retrospective

- Input: final status, QA, policy, quality, provider, archetype, skills.
- Output: run evaluation, failure patterns, learning rules.
- Success: history is recorded without secrets.
- Failure: API write failure.
- Retry policy: best-effort once.
- Fallback: event log only.
- Event: `learning_recorded`.
- Artifact: run_evaluations and learning_rules.

## 17. Final Report

- Input: all run outputs.
- Output: Vietnamese and English reports.
- Success: report explains idea, research, candidate, config, provider, QA, policy, quality, artifacts, next action.
- Failure: missing linked brief.
- Retry policy: write partial report.
- Fallback: project-only report.
- Event: `pipeline_finished`.
- Artifact: `factory_run_report.vi.md`.
