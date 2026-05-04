const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function request(path) {
  const response = await fetch(`${API}${path}`);
  if (!response.ok) throw new Error(`${path} failed: ${response.status} ${await response.text()}`);
  return response.json();
}

const summary = await request("/learning/summary");
if (typeof summary.total_runs !== "number") throw new Error("Learning summary missing total_runs");
if (!summary.provider_success || typeof summary.provider_success !== "object") throw new Error("Learning summary missing provider_success");
console.log(`Learning summary ok; runs=${summary.total_runs}, avg=${summary.average_quality_score}`);
