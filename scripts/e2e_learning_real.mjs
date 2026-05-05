const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function request(path, init) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  const text = await response.text();
  if (!response.ok) throw new Error(`${path} returned ${response.status}: ${text}`);
  return text ? JSON.parse(text) : null;
}

await request("/internal/learning/run-evaluations", {
  method: "POST",
  body: JSON.stringify({
    category: "Education",
    language: "vi",
    monetization: "subscription",
    final_status: "NEEDS_HUMAN_REVIEW",
    provider: "deterministic",
    quality_score: 42,
    policy_passed: true,
    qa_passed: true,
    store_readiness_score: 45,
    failure_reason: "generic placeholder copy and weak core feature",
    metrics_json: { e2e: "learning-real" },
  }),
});

const rules = await request("/learning/rules");
const rule = rules.find((item) => item.rule_key === "force_deeper_feature_flow");
if (!rule) throw new Error("force_deeper_feature_flow learning rule was not created");
if (!rule.enabled) throw new Error("force_deeper_feature_flow should be enabled");

const brief = await request("/factory-briefs", {
  method: "POST",
  body: JSON.stringify({
    mode: "manual_idea",
    title: `E2E Learning Real ${Date.now()}`,
    raw_prompt: "Tạo app học tiếng Trung cho người Việt, có subscription mô phỏng và nội dung không generic.",
    target_category: "Education",
    target_language: "vi",
    target_country: "VN",
    monetization_mode: "subscription",
    subscription_enabled: true,
  }),
});

const applied = brief.runtime_config_snapshot_json?.applied_learning_rules || [];
if (!applied.some((item) => item.rule_key === "force_deeper_feature_flow")) {
  throw new Error("New brief did not apply force_deeper_feature_flow in runtime config snapshot");
}
const skills = brief.runtime_config_snapshot_json?.enabled_skills || [];
if (!skills.some((item) => item.slug === "product_depth_enhancer")) {
  throw new Error("Runtime config does not expose product_depth_enhancer for learned strategy");
}
if (Number(brief.quality_threshold) < 80) {
  throw new Error(`Learning rule did not raise quality threshold; got ${brief.quality_threshold}`);
}

console.log(`Learning real passed; rule ${rule.id} applied to brief ${brief.id}`);
