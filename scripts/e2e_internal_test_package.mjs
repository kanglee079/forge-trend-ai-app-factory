import fs from "node:fs";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function request(path, init) {
  const response = await fetch(`${API}${path}`, { headers: { "Content-Type": "application/json" }, ...init });
  if (!response.ok) throw new Error(`${path} failed: ${response.status} ${await response.text()}`);
  return response.json();
}

const projects = await request("/projects");
const project = projects.find((item) => item.status === "release_candidate" || item.workspace_path);
if (!project) {
  console.log("No generated project found; run WORKER_ENABLE_CODEX=false pnpm e2e:factory:vi first.");
  process.exit(0);
}

const artifact = await request(`/projects/${project.id}/internal-test-package`, { method: "POST" });
for (const file of ["README_FOR_TESTER.vi.md", "STORE_LISTING_DRAFT.vi.md", "PRIVACY_REVIEW_CHECKLIST.vi.md", "SCREENSHOT_PLAN.md", "RELEASE_BLOCKERS.md"]) {
  const full = `${artifact.path}/${file}`;
  if (!fs.existsSync(full)) throw new Error(`Missing ${full}`);
}
console.log(`Internal test package ok: ${artifact.path}`);
