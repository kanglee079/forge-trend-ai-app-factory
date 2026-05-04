const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function request(path, init) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}: ${await response.text()}`);
  }
  return response.json();
}

const toml = `
model_provider = "OpenAI"
model = "gpt-5.5"
review_model = "gpt-5.5"
network_access = "enabled"
model_context_window = 1000000
model_auto_compact_token_limit = 900000

[model_providers.OpenAI]
name = "OpenAI"
base_url = "https://custom-router.example.com/v1"
wire_api = "responses"
requires_openai_auth = true

[plugins."documents"]
enabled = true

[plugins."browser-use"]
enabled = true

[projects."/tmp/forge-trend-test"]
trust_level = "trusted"
`;

const profile = await request("/config-profiles/import-toml", {
  method: "POST",
  body: JSON.stringify({ toml_text: toml, name: "E2E Config Import" }),
});
const exported = await request(`/config-profiles/${profile.id}/export-toml`);
const test = await request(`/config-profiles/${profile.id}/test`, { method: "POST" });

if (!exported.toml_text.includes("api_key_ref") && exported.toml_text.includes("sk-")) {
  throw new Error("Export leaked raw-looking secret text");
}
if (!["passed", "warning"].includes(test.status)) {
  throw new Error(`Unexpected test status ${test.status}`);
}

console.log(`Config import/export passed for ${profile.id}`);
