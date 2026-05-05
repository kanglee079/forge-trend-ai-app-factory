const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function request(path, init, expectOk = true) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  const text = await response.text();
  if (expectOk && !response.ok) throw new Error(`${path} returned ${response.status}: ${text}`);
  return { status: response.status, ok: response.ok, body: text ? JSON.parse(text) : null };
}

const scan = (await request("/scan/runs", {
  method: "POST",
  body: JSON.stringify({ source_type: "github_search", query: "flutter prompt skill policy store readiness", limit: 2 }),
})).body;
if (!scan.items?.length) throw new Error("Scanner returned no items");
for (const item of scan.items) {
  if (item.status !== "quarantined") throw new Error(`Item ${item.id} was not quarantined`);
  const safeMode = item.metadata_json?.safe_mode;
  if (!["metadata_only", "fallback"].includes(safeMode)) throw new Error(`Unexpected scanner safe_mode ${safeMode}`);
}

const item = scan.items[0];
const blocked = await request(`/source-items/${item.id}/convert-to-skill`, { method: "POST" }, false);
if (blocked.ok) throw new Error("Conversion before review should be blocked");
if (blocked.status !== 409) throw new Error(`Expected 409 for unreviewed conversion; got ${blocked.status}`);

await request(`/source-items/${item.id}`, { method: "PATCH", body: JSON.stringify({ status: "reviewed" }) });
const converted = (await request(`/source-items/${item.id}/convert-to-skill`, { method: "POST" })).body;
if (converted.enabled) throw new Error("Converted external skill must stay disabled until human explicitly enables it");
if (converted.source_type !== "external_quarantined") throw new Error(`Unexpected converted source_type ${converted.source_type}`);
if (!converted.prompts?.[0]?.prompt_template.includes("Do not execute code")) throw new Error("Converted prompt must state no external code execution");

console.log(`Scan safe passed; converted disabled skill ${converted.slug}`);
