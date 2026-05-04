const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function request(path, init) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!response.ok) throw new Error(`${path} returned ${response.status}: ${await response.text()}`);
  return response.json();
}

await request("/internal/learning/run-evaluations", {
  method: "POST",
  body: JSON.stringify({
    final_status: "NEEDS_HUMAN_REVIEW",
    provider: "deterministic",
    quality_score: 40,
    failure_reason: "generic placeholder copy",
    metrics_json: { e2e: true },
  }),
});
const rules = await request("/learning/rules");
const rule = rules.find((item) => item.rule_key === "force_deeper_feature_flow") || rules[0];
if (!rule) throw new Error("No learning rule created");
const toggled = await request(`/learning/rules/${rule.id}`, { method: "PATCH", body: JSON.stringify({ enabled: !rule.enabled }) });
await request(`/learning/rules/${rule.id}`, { method: "PATCH", body: JSON.stringify({ enabled: rule.enabled }) });
if (toggled.enabled === rule.enabled) throw new Error("Learning rule toggle did not change state");
console.log(`Learning rule toggle passed for ${rule.rule_key}`);
