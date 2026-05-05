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

function assertNoSecret(label, value) {
  const text = typeof value === "string" ? value : JSON.stringify(value);
  if (/sk-[A-Za-z0-9_-]{12,}|api[_-]?key\s*=\s*["'][^"']+/i.test(text)) {
    throw new Error(`${label} leaked raw-looking API key text`);
  }
}

const toml = `
model_provider = "OpenAI"
model = "gpt-5.5-config-runtime-real"
review_model = "gpt-5.5-review-runtime-real"
network_access = "enabled"
model_context_window = 777000
model_auto_compact_token_limit = 555000

[model_providers.OpenAI]
name = "OpenAI"
provider_type = "openai_compatible"
base_url = "https://custom-router.example.com/v1"
wire_api = "responses"
requires_openai_auth = true
enabled = true

[plugins."browser-use"]
name = "Browser Use"
enabled = true

[plugins."documents"]
name = "Documents"
enabled = true
`;

const profile = await request("/config-profiles/import-toml", {
  method: "POST",
  body: JSON.stringify({ toml_text: toml, name: `E2E Config Runtime ${Date.now()}`, set_default: true }),
});
const brief = await request("/factory-briefs", {
  method: "POST",
  body: JSON.stringify({
    config_profile_id: profile.id,
    mode: "manual_idea",
    title: `E2E Config Runtime ${Date.now()}`,
    raw_prompt: "Create a Vietnamese productivity app that proves config runtime snapshot wiring.",
    target_category: "Productivity",
    target_language: "vi",
    target_country: "VN",
  }),
});
const runtime = brief.runtime_config_snapshot_json;
if (runtime.model !== "gpt-5.5-config-runtime-real") throw new Error(`Unexpected model ${runtime.model}`);
if (runtime.review_model !== "gpt-5.5-review-runtime-real") throw new Error(`Unexpected review_model ${runtime.review_model}`);
if (runtime.network_access !== "enabled") throw new Error(`Unexpected network ${runtime.network_access}`);
if (runtime.provider?.base_url !== "https://custom-router.example.com/v1") throw new Error(`Unexpected base_url ${runtime.provider?.base_url}`);
if (!runtime.enabled_plugins?.some((item) => item.plugin_id === "browser-use")) throw new Error("browser-use plugin missing from runtime snapshot");
if (!Array.isArray(runtime.applied_learning_rules)) throw new Error("runtime snapshot missing applied_learning_rules array");

const completion = await request("/internal/provider-completion", {
  method: "POST",
  body: JSON.stringify({
    config_profile_id: profile.id,
    runtime_config_snapshot: runtime,
    purpose: "e2e_config_runtime",
    prompt: "Return ok.",
    max_output_tokens: 32,
  }),
});
if (completion.model !== "gpt-5.5-config-runtime-real") throw new Error(`Provider completion ignored snapshot model: ${completion.model}`);
const exported = await request(`/config-profiles/${profile.id}/export-toml`);
assertNoSecret("runtime", runtime);
assertNoSecret("provider completion", completion);
assertNoSecret("exported TOML", exported.toml_text);

console.log(`Config runtime real passed for brief ${brief.id}`);
