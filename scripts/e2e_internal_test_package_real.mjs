import fs from "node:fs";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function request(path, init) {
  const response = await fetch(`${API_BASE}${path}`, { headers: { "Content-Type": "application/json" }, ...init });
  const text = await response.text();
  if (!response.ok) throw new Error(`${path} failed: ${response.status} ${text}`);
  return text ? JSON.parse(text) : null;
}

const projects = await request("/projects");
const project = projects.find((item) => item.status === "release_candidate" || item.status === "NEEDS_HUMAN_REVIEW" || item.workspace_path);
if (!project) {
  throw new Error("No generated project found. Run WORKER_ENABLE_CODEX=false pnpm e2e:factory:vi first.");
}

const artifact = await request(`/projects/${project.id}/internal-test-package`, { method: "POST" });
const requiredFiles = [
  "source_path.txt",
  "factory_run_report.vi.md",
  "product_score_report.vi.md",
  "quality_gate_report.md",
  "store_readiness_report.md",
  "README_FOR_TESTER.vi.md",
  "RELEASE_BLOCKERS.vi.md",
];
for (const file of requiredFiles) {
  const full = `${artifact.path}/${file}`;
  if (!fs.existsSync(full)) throw new Error(`Missing ${full}`);
}
if (!fs.existsSync(`${artifact.path}/store_assets`)) throw new Error("Missing store_assets folder");
if (!artifact.metadata_json?.zip_path || !fs.existsSync(artifact.metadata_json.zip_path)) {
  throw new Error("Package metadata missing zip_path or zip does not exist");
}
const readme = fs.readFileSync(`${artifact.path}/README_FOR_TESTER.vi.md`, "utf8");
const blockers = fs.readFileSync(`${artifact.path}/RELEASE_BLOCKERS.vi.md`, "utf8");
if (!readme.includes("Không publish production")) throw new Error("Tester README must block production publish");
if (!blockers.includes("Human approval required")) throw new Error("Release blockers must require human approval");

console.log(`Internal test package real passed: ${artifact.path}`);
