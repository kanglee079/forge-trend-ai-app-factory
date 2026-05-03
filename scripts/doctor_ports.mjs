import { execFileSync, spawnSync } from "node:child_process";

const ports = [
  { port: 3000, label: "Dashboard", url: "http://localhost:3000" },
  { port: 8000, label: "API", url: "http://localhost:8000/health" },
  { port: 6379, label: "Redis" },
  { port: 5432, label: "Postgres" },
  { port: 9000, label: "MinIO" },
];

function run(command, args) {
  const result = spawnSync(command, args, { encoding: "utf8" });
  if (result.status !== 0) return "";
  return result.stdout.trim();
}

function commandForPid(pid) {
  if (!pid) return "";
  if (process.platform === "win32") {
    return run("wmic", ["process", "where", `ProcessId=${pid}`, "get", "CommandLine", "/value"]).replace(/^CommandLine=/, "");
  }
  return run("ps", ["-p", String(pid), "-o", "command="]);
}

function pidsForPort(port) {
  if (process.platform === "win32") {
    const output = run("netstat", ["-ano", "-p", "tcp"]);
    const pids = new Set();
    for (const line of output.split(/\r?\n/)) {
      if (line.includes(`:${port}`) && /LISTENING/i.test(line)) {
        const parts = line.trim().split(/\s+/);
        const pid = parts.at(-1);
        if (pid) pids.add(pid);
      }
    }
    return [...pids];
  }
  const output = run("lsof", ["-nP", "-iTCP:" + port, "-sTCP:LISTEN", "-t"]);
  return output ? [...new Set(output.split(/\s+/).filter(Boolean))] : [];
}

async function httpStatus(url) {
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(1500) });
    return { status: response.status, ok: response.ok, text: await response.text().catch(() => "") };
  } catch (error) {
    return { status: 0, ok: false, text: error instanceof Error ? error.message : String(error) };
  }
}

async function detectApiFreshness() {
  const health = await httpStatus("http://localhost:8000/health");
  const settings = await httpStatus("http://localhost:8000/settings");
  const briefs = await httpStatus("http://localhost:8000/factory-briefs");
  const events = await httpStatus("http://localhost:8000/events?limit=1");
  const fresh = health.ok && settings.ok && briefs.ok && events.ok;
  if (fresh) return { fresh, detail: "API routes are fresh" };
  if (health.ok && (settings.status === 404 || briefs.status === 404 || events.status === 404)) {
    return { fresh, detail: "Stale API detected: /health works, but newer routes return 404" };
  }
  return { fresh, detail: `API incomplete: health=${health.status} settings=${settings.status} factory-briefs=${briefs.status} events=${events.status}` };
}

async function main() {
  console.log("ForgeTrend port doctor");
  console.log("======================");
  for (const item of ports) {
    const pids = pidsForPort(item.port);
    const status = pids.length ? "BUSY" : "FREE";
    console.log(`${status.padEnd(5)} ${String(item.port).padEnd(5)} ${item.label}`);
    for (const pid of pids) {
      console.log(`      pid ${pid}: ${commandForPid(pid) || "unknown command"}`);
    }
    if (item.url) {
      const result = await httpStatus(item.url);
      console.log(`      ${item.url} -> ${result.status || result.text}`);
    }
  }

  const api = await detectApiFreshness();
  console.log("");
  console.log(`${api.fresh ? "OK" : "WARN"}  localhost:8000 freshness`);
  console.log(`      ${api.detail}`);
  if (!api.fresh) {
    console.log("      Run pnpm reset:local, or kill the stale PID above before pnpm dev.");
    process.exitCode = 1;
  }

  try {
    const docker = execFileSync("docker", ["compose", "ps", "--format", "json"], { encoding: "utf8" }).trim();
    if (docker) {
      console.log("\nDocker compose services");
      for (const line of docker.split(/\r?\n/).filter(Boolean)) {
        const service = JSON.parse(line);
        console.log(`      ${service.Service || service.Name}: ${service.State}${service.Health ? ` (${service.Health})` : ""}`);
      }
    }
  } catch {
    console.log("\nDocker compose status unavailable.");
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});
