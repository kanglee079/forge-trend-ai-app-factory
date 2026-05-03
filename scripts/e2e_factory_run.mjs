const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const TIMEOUT_MS = Number(process.env.E2E_FACTORY_TIMEOUT_MS || 10 * 60 * 1000);
const POLL_MS = Number(process.env.E2E_FACTORY_POLL_MS || 5000);
const REQUIRE_WORKER = process.env.E2E_REQUIRE_WORKER !== "false";
const SKIP_START = process.env.E2E_SKIP_START === "true";

const terminalStatuses = new Set(["release_candidate", "NEEDS_HUMAN_REVIEW", "stopped", "failed"]);
const timeline = [];

function log(message) {
  const line = `[${new Date().toISOString()}] ${message}`;
  timeline.push(line);
  console.log(line);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function request(path, init) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}: ${text.slice(0, 1000)}`);
  }
  return text ? JSON.parse(text) : null;
}

async function waitFor(label, fn, timeoutMs = TIMEOUT_MS) {
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

async function waitForProjectTerminal(projectId) {
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

function briefPayload() {
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
  };
}

async function dumpProject(projectId) {
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
    if (event.stderr) console.log(`  stderr: ${event.stderr.slice(-1200)}`);
  }
}

async function main() {
  log(`Using API ${API_BASE}`);
  const health = await request("/health");
  if (health.status !== "ok") throw new Error(`/health is not ok: ${JSON.stringify(health)}`);
  log("API health ok");

  const doctor = await request("/doctor");
  log(`Doctor status ${doctor.status}`);

  const factory = await request("/factory/state");
  if (factory.mode !== "running") {
    throw new Error(`Factory mode is ${factory.mode}. Set it to running before E2E.`);
  }
  log("Factory mode running");

  const workers = await request("/workers");
  const readyWorkers = workers.filter((worker) => worker.status === "online" && worker.has_flutter && worker.has_codex);
  if (REQUIRE_WORKER && !readyWorkers.length) {
    throw new Error("No online worker with Flutter and Codex. Run codex login and pnpm dev:worker, or set E2E_REQUIRE_WORKER=false for API-only debugging.");
  }
  log(`${readyWorkers.length}/${workers.length} ready worker(s)`);

  const brief = await request("/factory-briefs", { method: "POST", body: JSON.stringify(briefPayload()) });
  log(`Created factory brief ${brief.id}`);

  if (!SKIP_START) {
    const queued = await request(`/factory-briefs/${brief.id}/start`, { method: "POST" });
    log(`Queued factory brief on ${queued.queue}`);
  }

  const detailWithFindings = await waitFor("Findings", async () => {
    const detail = await request(`/factory-briefs/${brief.id}`);
    return { ok: detail.findings.length >= 3, detail: `${detail.findings.length}/3`, value: detail };
  });

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

  const [tasks, qa, policy, artifacts] = await Promise.all([
    request(`/projects/${projectId}/tasks`),
    request(`/projects/${projectId}/qa`),
    request(`/projects/${projectId}/policy`),
    request(`/projects/${projectId}/artifacts`),
  ]);
  const artifactNames = new Set(artifacts.map((artifact) => artifact.name));
  const hasPrd = artifactNames.has("prd.md");
  const hasDesign = artifactNames.has("design_system.md") || artifactNames.has("screen_flow.md");
  const hasSource = artifacts.some((artifact) => artifact.kind === "source");
  const hasBuild = artifacts.some((artifact) => artifact.kind === "build" || artifact.name.endsWith(".apk"));

  console.log("\nFactory E2E result");
  console.log("==================");
  console.log(`Brief:   ${brief.id}`);
  console.log(`Project: ${projectId}`);
  console.log(`Status:  ${completedProject.status}`);
  console.log(`Tasks:   ${tasks.length}`);
  console.log(`QA:      ${qa.length}`);
  console.log(`Policy:  ${policy.length}`);
  console.log(`Artifacts: PRD=${hasPrd} design=${hasDesign} source=${hasSource} build=${hasBuild}`);

  if (!hasPrd || !hasDesign || !hasSource || !qa.length || !policy.length) {
    await dumpProject(projectId);
    throw new Error("Factory run reached terminal status but expected PRD/design/source/QA/policy outputs are missing.");
  }
  if (!hasBuild) {
    console.log("WARN build artifact is missing. This can be valid when QA failed and project ended NEEDS_HUMAN_REVIEW.");
  }
  if (!["release_candidate", "NEEDS_HUMAN_REVIEW"].includes(completedProject.status)) {
    await dumpProject(projectId);
    throw new Error(`Unexpected terminal status: ${completedProject.status}`);
  }

  await dumpProject(projectId);
  console.log("\nFactory E2E completed.");
}

main().catch(async (error) => {
  console.error("\nFactory E2E failed");
  console.error("==================");
  console.error(error instanceof Error ? error.message : String(error));
  console.error("\nTimeline");
  for (const line of timeline) console.error(line);
  process.exit(1);
});
