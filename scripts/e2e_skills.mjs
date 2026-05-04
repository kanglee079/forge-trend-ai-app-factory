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

const skills = await request("/skill-packs/scan-installed", { method: "POST" });
if (!skills.length) throw new Error("No skills returned");
const vi = skills.find((item) => item.slug === "vietnamese_ux_writer") || skills[0];
const result = await request(`/skill-packs/${vi.id}/test`, {
  method: "POST",
  body: JSON.stringify({ sample_input: { app_context: "App tieng Viet", app_name: "Demo", qa_error: "flutter test failed" } }),
});
if (!result.rendered_prompt) throw new Error("Skill test did not render a prompt");
console.log(`Skill marketplace passed with ${skills.length} packs`);
