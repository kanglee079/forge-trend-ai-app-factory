const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function request(path, init) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!response.ok) throw new Error(`${path} returned ${response.status}: ${await response.text()}`);
  return response.json();
}

const created = await request("/internal/context-packs", {
  method: "POST",
  body: JSON.stringify({
    pack_type: "e2e_context_pack",
    full_text_hash: `e2e-${Date.now()}`,
    summary: "E2E context pack verifies prompt planner storage.",
    important_files: ["docs/prd.md", "app/lib"],
    token_estimate: 42,
  }),
});
if (created.pack_type !== "e2e_context_pack") throw new Error("Context pack was not stored");
const summary = await request("/prompt-context/summary");
if (!summary.context_packs.some((item) => item.pack_type === "e2e_context_pack")) throw new Error("Context pack not visible in summary");
console.log(`Prompt context passed with pack ${created.id}`);
