const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function request(path, init) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!response.ok) throw new Error(`${path} returned ${response.status}: ${await response.text()}`);
  return response.json();
}

const runtime = await request("/config-profiles/default/runtime");
if (!runtime.secrets_redacted) throw new Error("Runtime config should be secret-redacted");
const completion = await request("/internal/provider-completion", {
  method: "POST",
  body: JSON.stringify({
    config_profile_id: runtime.config_profile_id,
    purpose: "e2e_provider_runtime",
    prompt: "Return the word ok.",
    max_output_tokens: 32,
  }),
});
if (!["completed", "empty", "skipped", "failed"].includes(completion.status)) {
  throw new Error(`Unexpected provider completion status ${completion.status}`);
}
if (JSON.stringify(completion).includes("sk-")) throw new Error("Provider completion response leaked secret-looking text");
console.log(`Provider runtime passed with status ${completion.status}`);
