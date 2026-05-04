const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function request(path, init) {
  const response = await fetch(`${API}${path}`, { headers: { "Content-Type": "application/json" }, ...init });
  if (!response.ok) throw new Error(`${path} failed: ${response.status} ${await response.text()}`);
  return response.json();
}

const events = await request("/events?search=Autopilot&limit=50");
if (!Array.isArray(events)) throw new Error("Autopilot events endpoint returned invalid payload");
console.log(`Autopilot timeline reachable; ${events.length} recent event(s).`);
