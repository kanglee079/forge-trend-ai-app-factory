import { briefPayload, reportFailure, request, runFactoryE2E } from "./e2e_factory_shared.mjs";

async function ensureCodexConfigProfile() {
  const profile = await request("/config-profiles/import-toml", {
    method: "POST",
    body: JSON.stringify({
      name: `E2E Codex CLI ${Date.now()}`,
      toml_text: `
model_provider = "Codex CLI"
model = "gpt-5.5"
review_model = "gpt-5.5"
network_access = "enabled"
model_context_window = 200000
model_auto_compact_token_limit = 160000

[model_providers."Codex CLI"]
name = "Codex CLI"
provider_type = "codex_cli"
base_url = "https://api.openai.com/v1"
wire_api = "responses"
requires_openai_auth = false
enabled = true
`,
    }),
  });
  return profile.id;
}

const configProfileId = await ensureCodexConfigProfile();

runFactoryE2E({
  requireCodex: true,
  assertCodex: true,
  payload: briefPayload({ config_profile_id: configProfileId }),
}).catch((error) => {
  reportFailure(error, "Codex Factory E2E failed");
});
