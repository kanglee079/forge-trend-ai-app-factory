import { spawnSync } from "node:child_process";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
export const TIMEOUT_MS = Number(process.env.E2E_FACTORY_TIMEOUT_MS || 10 * 60 * 1000);
export const POLL_MS = Number(process.env.E2E_FACTORY_POLL_MS || 5000);
export const REQUIRE_WORKER = process.env.E2E_REQUIRE_WORKER !== "false";
export const SKIP_START = process.env.E2E_SKIP_START === "true";

const terminalStatuses = new Set(["release_candidate", "NEEDS_HUMAN_REVIEW", "stopped", "failed"]);
export const timeline = [];

export function log(message) {
  const line = `[${new Date().toISOString()}] ${message}`;
  timeline.push(line);
  console.log(line);
}

export function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function request(path, init) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  const text = await response.text();
  if (!response.ok) {
    if (text.includes("Codex CLI is installed but not authenticated")) {
      throw new Error("Codex CLI is installed but not authenticated. Run: codex login");
    }
    throw new Error(`${path} returned ${response.status}: ${text.slice(0, 1000)}`);
  }
  return text ? JSON.parse(text) : null;
}

export async function waitFor(label, fn, timeoutMs = TIMEOUT_MS) {
  const started = Date.now();
  let lastDetail = "not checked yet";
  while (Date.now() - started < timeoutMs) {
    try {
      const result = await fn();
      if (result.ok) {
        log(`${label}: ${result.detail || "ok"}`);
        return result.value;
      }
      lastDetail = result.detail || "condition not met";
    } catch (error) {
      lastDetail = error instanceof Error ? error.message : String(error);
    }
    process.stdout.write(".");
    await sleep(POLL_MS);
  }
  process.stdout.write("\n");
  throw new Error(`${label} timed out after ${Math.round(timeoutMs / 1000)}s. Last detail: ${lastDetail}`);
}

export function briefPayload(overrides = {}) {
  const suffix = new Date().toISOString().replace(/[:.]/g, "-");
  return {
    mode: "auto_trend",
    title: `E2E Factory Run ${suffix}`,
    raw_prompt:
      "Create a local-first HSK learning app with subscription-ready premium study plans, IAP vocabulary packs, clear privacy posture, and a Flutter Android MVP.",
    target_category: "Education",
    target_platforms: ["android"],
    target_country: "US",
    target_language: "en",
    monetization_mode: "subscription",
    iap_enabled: true,
    subscription_enabled: true,
    ads_enabled: false,
    backend_mode: "none",
    complexity: "medium",
    max_cost_usd: 5,
    max_runtime_minutes: 60,
    quality_threshold: 75,
    policy_strictness: "standard",
    ...overrides,
  };
}

export function isReadyWorker(worker, requireCodex) {
  return worker.status === "online" && worker.has_flutter && (!requireCodex || worker.has_codex);
}

export function checkCodexInstalledAndAuthenticated() {
  const version = spawnSync(process.platform === "win32" ? "codex.cmd" : "codex", ["--version"], { encoding: "utf8" });
  if (version.status !== 0) {
    throw new Error("Codex CLI is not installed or not on PATH. Install Codex CLI, then run: codex login");
  }
  const auth = spawnSync(process.platform === "win32" ? "codex.cmd" : "codex", ["login", "status"], { encoding: "utf8" });
  if (auth.status !== 0) {
    throw new Error("Codex CLI is installed but not authenticated. Run: codex login");
  }
}

export async function dumpProject(projectId) {
  const [project, events, tasks, qa, policy, artifacts] = await Promise.all([
    request(`/projects/${projectId}`).catch((error) => ({ error: error.message })),
    request(`/projects/${projectId}/events`).catch(() => []),
    request(`/projects/${projectId}/tasks`).catch(() => []),
    request(`/projects/${projectId}/qa`).catch(() => []),
    request(`/projects/${projectId}/policy`).catch(() => []),
    request(`/projects/${projectId}/artifacts`).catch(() => []),
  ]);
  console.log("\nProject summary");
  console.log("===============");
  console.log(JSON.stringify(project, null, 2));
  console.log("\nTasks");
  for (const task of tasks) {
    console.log(`- ${task.status.padEnd(14)} ${task.agent_name.padEnd(14)} ${task.title}${task.error_message ? ` :: ${task.error_message}` : ""}`);
    if (task.output_json?.code_provider) console.log(`  code_provider=${JSON.stringify(task.output_json.code_provider)}`);
  }
  console.log("\nArtifacts");
  for (const artifact of artifacts) {
    console.log(`- ${artifact.kind.padEnd(10)} ${artifact.name} ${artifact.path}`);
  }
  console.log("\nQA");
  for (const item of qa) {
    console.log(`- ${item.status.padEnd(8)} exit=${item.exit_code} ${item.command}`);
    if (item.status !== "passed" || item.exit_code !== 0) {
      console.log((item.stderr || item.stdout || "").slice(-3000));
    }
  }
  console.log("\nPolicy");
  for (const item of policy) {
    console.log(`- ${item.passed ? "passed" : "failed"} risk=${item.risk}`);
    if (item.issues?.length) console.log(`  issues: ${item.issues.join("; ")}`);
    if (item.required_changes?.length) console.log(`  required: ${item.required_changes.join("; ")}`);
  }
  console.log("\nRecent events");
  for (const event of events.slice(-25)) {
    console.log(`- ${event.created_at} ${event.level.padEnd(7)} ${event.step.padEnd(18)} ${event.message}`);
    if (event.metadata_json && Object.keys(event.metadata_json).length) console.log(`  metadata: ${JSON.stringify(event.metadata_json).slice(0, 1200)}`);
    if (event.stderr) console.log(`  stderr: ${event.stderr.slice(-1200)}`);
  }
  return { project, events, tasks, qa, policy, artifacts };
}

export async function waitForProjectTerminal(projectId) {
  try {
    return await waitFor("Project terminal status", async () => {
      const project = await request(`/projects/${projectId}`);
      return { ok: terminalStatuses.has(project.status), detail: project.status, value: project };
    }, TIMEOUT_MS);
  } catch (error) {
    await dumpProject(projectId);
    throw error;
  }
}

export function hasCodexProof({ events, tasks }) {
  return (
    events.some((event) => event.step === "code_agent" && event.message.includes("Codex CLI pass finished")) ||
    events.some((event) => event.step === "code_agent" && event.metadata_json?.provider === "codex_cli") ||
    tasks.some((task) => task.agent_name === "code_agent" && task.output_json?.code_provider?.provider === "codex_cli")
  );
}

const bannedGeneratedPhrases = [
  "replace this",
  "sample error state",
  "local sample data",
  "adapt this item",
  "placeholder included",
  "generated by forgetrend",
  "core flow",
  "next action",
];

function readTextFiles(root) {
  const files = [];
  function walk(dir) {
    for (const entry of readdirSync(dir)) {
      const full = join(dir, entry);
      const stat = statSync(full);
      if (stat.isDirectory()) walk(full);
      else if (full.endsWith(".dart") || full.endsWith(".md")) files.push(readFileSync(full, "utf8"));
    }
  }
  walk(root);
  return files.join("\n");
}

export async function runFactoryE2E({ requireCodex = false, assertCodex = false, assertWebEvidence = false, assertVietnamese = false, payload = briefPayload() } = {}) {
  log(`Using API ${API_BASE}`);
  const health = await request("/health");
  if (health.status !== "ok") throw new Error(`/health is not ok: ${JSON.stringify(health)}`);
  log("API health ok");

  if (requireCodex) {
    checkCodexInstalledAndAuthenticated();
    log("Codex CLI installed and authenticated");
  }

  const doctor = await request("/doctor");
  log(`Doctor status ${doctor.status}; ${doctor.worker_mode_label}; ${doctor.research_mode_label}`);
  if (!requireCodex && doctor.worker_enable_codex === true) {
    log("WARN doctor currently reports Codex mode; deterministic readiness will still only require Flutter workers.");
  }

  const factory = await request("/factory/state");
  if (factory.mode !== "running") {
    throw new Error(`Factory mode is ${factory.mode}. Set it to running before E2E.`);
  }
  log("Factory mode running");

  const workers = await request("/workers");
  const readyWorkers = workers.filter((worker) => isReadyWorker(worker, requireCodex));
  if (requireCodex && !workers.some((worker) => worker.status === "online" && worker.worker_enable_codex)) {
    throw new Error("No online worker reports Codex coding mode. Start the worker with WORKER_ENABLE_CODEX=true pnpm dev:worker.");
  }
  if (REQUIRE_WORKER && !readyWorkers.length) {
    throw new Error(
      requireCodex
        ? "No online worker with Flutter and Codex. Run codex login, then WORKER_ENABLE_CODEX=true pnpm dev:worker."
        : "No online worker with Flutter. Run WORKER_ENABLE_CODEX=false pnpm dev:worker for deterministic mode.",
    );
  }
  log(`${readyWorkers.length}/${workers.length} ready worker(s) for ${requireCodex ? "Codex" : "deterministic"} mode`);

  const brief = await request("/factory-briefs", { method: "POST", body: JSON.stringify(payload) });
  log(`Created factory brief ${brief.id}`);

  if (!SKIP_START) {
    const queued = await request(`/factory-briefs/${brief.id}/start`, { method: "POST" });
    log(`Queued factory brief on ${queued.queue}`);
  }

  const detailWithFindings = await waitFor("Findings", async () => {
    const detail = await request(`/factory-briefs/${brief.id}`);
    return { ok: detail.findings.length >= 3, detail: `${detail.findings.length}/3 status=${detail.status}`, value: detail };
  });

  if (assertWebEvidence) {
    const hasWeb = detailWithFindings.findings.some((finding) => finding.evidence_json?.provider === "web_provider" && finding.evidence_json?.source_url);
    if (!hasWeb) {
      throw new Error("Expected at least one finding with evidence_json.provider=web_provider and source_url.");
    }
  }

  const detailWithCandidates = await waitFor("Candidates", async () => {
    const detail = await request(`/factory-briefs/${brief.id}`);
    return { ok: detail.candidates.length >= 3, detail: `${detail.candidates.length}/3`, value: detail };
  });

  const detailWithProject = await waitFor("Selected project", async () => {
    const detail = await request(`/factory-briefs/${brief.id}`);
    return { ok: Boolean(detail.selected_project_id), detail: detail.status, value: detail };
  });

  const projectId = detailWithProject.selected_project_id;
  log(`Selected project ${projectId}; findings=${detailWithFindings.findings.length}; candidates=${detailWithCandidates.candidates.length}`);

  const completedProject = await waitForProjectTerminal(projectId);

  const dump = await dumpProject(projectId);
  const artifactNames = new Set(dump.artifacts.map((artifact) => artifact.name));
  const hasPrd = artifactNames.has("prd.md");
  const hasDesign = artifactNames.has("design_system.md") || artifactNames.has("screen_flow.md");
  const hasSource = dump.artifacts.some((artifact) => artifact.kind === "source");
  const hasBuild = dump.artifacts.some((artifact) => artifact.kind === "build" || artifact.name.endsWith(".apk"));
  const hasRunReport = dump.artifacts.some((artifact) => artifact.kind === "document" && artifact.name === "factory_run_report.md");
  const hasViRunReport = artifactNames.has("factory_run_report.vi.md");
  const hasQualityReport = artifactNames.has("quality_gate_report.md");
  const hasStoreReport = artifactNames.has("store_readiness_report.md");

  console.log("\nFactory E2E result");
  console.log("==================");
  console.log(`Brief:   ${brief.id}`);
  console.log(`Project: ${projectId}`);
  console.log(`Status:  ${completedProject.status}`);
  console.log(`Tasks:   ${dump.tasks.length}`);
  console.log(`QA:      ${dump.qa.length}`);
  console.log(`Policy:  ${dump.policy.length}`);
  console.log(`Artifacts: PRD=${hasPrd} design=${hasDesign} source=${hasSource} build=${hasBuild} run_report=${hasRunReport} vi_report=${hasViRunReport} quality=${hasQualityReport} store=${hasStoreReport}`);

  if (!hasPrd || !hasDesign || !hasSource || !dump.qa.length || !dump.policy.length || !hasRunReport || !hasViRunReport || !hasQualityReport || !hasStoreReport) {
    throw new Error("Factory run reached terminal status but expected PRD/design/source/QA/policy/run-report/quality/store-readiness outputs are missing.");
  }
  if (dump.project?.workspace_path || completedProject.workspace_path) {
    const workspacePath = dump.project?.workspace_path || completedProject.workspace_path;
    const generatedText = readTextFiles(join(workspacePath, "app", "lib")).toLowerCase();
    const bannedHit = bannedGeneratedPhrases.find((phrase) => generatedText.includes(phrase));
    if (bannedHit) throw new Error(`Generated app still contains banned generic phrase: ${bannedHit}`);
    if (assertVietnamese) {
      const hasVietnamese = ["học", "ứng dụng", "tiến độ", "cài đặt", "quyền riêng tư"].some((word) => generatedText.includes(word));
      if (!hasVietnamese) throw new Error("Expected Vietnamese UI strings in generated app, but none were found.");
    }
  }
  if (!hasBuild) {
    console.log("WARN build artifact is missing. This can be valid when QA failed and project ended NEEDS_HUMAN_REVIEW.");
  }
  if (!["release_candidate", "NEEDS_HUMAN_REVIEW"].includes(completedProject.status)) {
    throw new Error(`Unexpected terminal status: ${completedProject.status}`);
  }
  if (assertCodex && !hasCodexProof(dump)) {
    throw new Error("Codex mode finished but no proof was found. Expected code_agent event or task output provider=codex_cli.");
  }
  console.log("\nFactory E2E completed.");
  return { brief, project: completedProject, ...dump };
}

export function reportFailure(error, title = "Factory E2E failed") {
  console.error(`\n${title}`);
  console.error("=".repeat(title.length));
  console.error(error instanceof Error ? error.message : String(error));
  console.error("\nTimeline");
  for (const line of timeline) console.error(line);
  process.exit(1);
}
