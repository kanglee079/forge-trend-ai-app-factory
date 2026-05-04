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

const scan = await request("/scan/runs", {
  method: "POST",
  body: JSON.stringify({ source_type: "prompt_library", query: "flutter store ready prompt", limit: 3 }),
});
if (!scan.items.length) throw new Error("Scan did not create quarantined items");
const item = scan.items[0];
if (item.status !== "quarantined") throw new Error(`Expected quarantined, got ${item.status}`);
const skill = await request(`/source-items/${item.id}/convert-to-skill`, { method: "POST" });
if (skill.enabled) throw new Error("Converted external skill should not be enabled automatically");
console.log(`Safe scan passed with item ${item.id}`);
