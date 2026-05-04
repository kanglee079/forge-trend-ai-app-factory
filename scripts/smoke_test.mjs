const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

const checks = [];

async function check(name, fn) {
  try {
    const detail = await fn();
    checks.push({ name, ok: true, detail: detail || "ok" });
  } catch (error) {
    checks.push({ name, ok: false, detail: error instanceof Error ? error.message : String(error) });
  }
}

async function fetchJson(path) {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}`);
  }
  return response.json();
}

await check("API health", async () => {
  const body = await fetchJson("/health");
  return body.status;
});

await check("Doctor endpoint", async () => {
  const body = await fetchJson("/doctor");
  return body.status;
});

await check("Settings endpoint", async () => {
  const body = await fetchJson("/settings");
  return body.default_model;
});

await check("Factory state endpoint", async () => {
  const body = await fetchJson("/factory-state");
  return body.mode;
});

await check("Factory briefs endpoint", async () => {
  const body = await fetchJson("/factory-briefs");
  return `${body.length} brief(s)`;
});

await check("Notifications endpoint", async () => {
  const body = await fetchJson("/notifications?limit=5");
  return `${body.length} notification(s)`;
});

await check("API keys endpoint", async () => {
  const body = await fetchJson("/api-keys");
  return `${body.length} key(s)`;
});

await check("Config profiles endpoint", async () => {
  const body = await fetchJson("/config-profiles");
  return `${body.length} profile(s)`;
});

await check("Runtime config endpoint", async () => {
  const body = await fetchJson("/config-profiles/default/runtime");
  return `${body.profile_name} / ${body.model}`;
});

await check("Skill packs endpoint", async () => {
  const body = await fetchJson("/skill-packs");
  return `${body.length} skill(s)`;
});

await check("Run profiles endpoint", async () => {
  const body = await fetchJson("/run-profiles");
  return `${body.length} run profile(s)`;
});

await check("Prompt context endpoint", async () => {
  const body = await fetchJson("/prompt-context/summary");
  return `${body.prompt_fragments.length} fragment(s), ${body.context_packs.length} pack(s)`;
});

await check("Learning rules endpoint", async () => {
  const body = await fetchJson("/learning/rules");
  return `${body.length} rule(s)`;
});

await check("Ideas endpoint", async () => {
  const body = await fetchJson("/ideas");
  return `${body.length} idea(s)`;
});

await check("Projects endpoint", async () => {
  const body = await fetchJson("/projects");
  return `${body.length} project(s)`;
});

await check("Events endpoint", async () => {
  const body = await fetchJson("/events?limit=5");
  return `${body.length} event(s)`;
});

const failed = checks.filter((item) => !item.ok);
console.log("ForgeTrend smoke test");
console.log("=====================");
for (const item of checks) {
  console.log(`${item.ok ? "OK  " : "FAIL"} ${item.name.padEnd(24)} ${item.detail}`);
}

if (failed.length) {
  console.log("\nFailed checks:");
  for (const item of failed) {
    console.log(`- ${item.name}: ${item.detail}`);
  }
  process.exit(1);
}

console.log("\nSmoke checks passed.");
