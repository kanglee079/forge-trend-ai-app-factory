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

const runProfiles = await request("/run-profiles");
const profile = runProfiles.find((item) => item.slug === "vi_store_test") || runProfiles[0];
if (!profile) throw new Error("No run profiles returned");
const brief = await request("/factory-briefs", {
  method: "POST",
  body: JSON.stringify({
    mode: "manual_idea",
    run_profile_slug: profile.slug,
    title: "E2E Run Profile Brief",
    raw_prompt: "Tao app checklist hoc tap tieng Viet de test run profile.",
    target_category: "Education",
    target_language: "vi",
    target_country: "VN",
    target_platforms: ["android"],
  }),
});
if (brief.run_profile_slug !== profile.slug) throw new Error("Brief did not store run profile slug");
if (!brief.runtime_config_snapshot_json?.model) throw new Error("Brief did not store runtime config snapshot");
console.log(`Run profile snapshot passed for brief ${brief.id}`);
