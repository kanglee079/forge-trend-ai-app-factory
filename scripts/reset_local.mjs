import { existsSync, rmSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { join } from "node:path";

const root = process.cwd();
const resetWorkspaces = process.env.RESET_WORKSPACES === "true";
const dryRun = process.env.DRY_RUN === "true";
const forceReset = process.env.FORCE_RESET === "true";

const ports = [3000, 8000];
const processPatterns = [
  "uvicorn app.main:app",
  "next dev",
  "next start",
  "daemon.main",
];

function commandName(command) {
  if (process.platform !== "win32") return command;
  if (["pnpm", "docker", "node"].includes(command)) return `${command}.cmd`;
  return command;
}

function run(command, args, options = {}) {
  console.log(`$ ${command} ${args.join(" ")}`);
  if (dryRun) return { status: 0, stdout: "", stderr: "" };
  const result = spawnSync(commandName(command), args, { cwd: root, encoding: "utf8", stdio: options.stdio || "pipe", shell: false });
  if (result.status !== 0 && !options.allowFail) {
    throw new Error(`${command} ${args.join(" ")} exited with ${result.status}\n${result.stderr || result.stdout}`);
  }
  return result;
}

function raw(command, args) {
  const result = spawnSync(command, args, { encoding: "utf8" });
  return result.status === 0 ? result.stdout.trim() : "";
}

function pidsForPort(port) {
  if (process.platform === "win32") {
    const output = raw("netstat", ["-ano", "-p", "tcp"]);
    const pids = new Set();
    for (const line of output.split(/\r?\n/)) {
      if (line.includes(`:${port}`) && /LISTENING/i.test(line)) {
        const pid = line.trim().split(/\s+/).at(-1);
        if (pid) pids.add(pid);
      }
    }
    return [...pids];
  }
  const output = raw("lsof", ["-nP", "-iTCP:" + port, "-sTCP:LISTEN", "-t"]);
  return output ? [...new Set(output.split(/\s+/).filter(Boolean))] : [];
}

function commandForPid(pid) {
  if (process.platform === "win32") {
    return raw("wmic", ["process", "where", `ProcessId=${pid}`, "get", "CommandLine", "/value"]).replace(/^CommandLine=/, "");
  }
  return raw("ps", ["-p", String(pid), "-o", "command="]);
}

function killPid(pid, reason) {
  const command = commandForPid(pid);
  console.log(`Stopping pid ${pid} (${reason}) ${command ? `:: ${command}` : ""}`);
  if (dryRun) return;
  try {
    if (process.platform === "win32") {
      spawnSync("taskkill", ["/PID", String(pid), "/T", "/F"], { stdio: "ignore" });
    } else {
      process.kill(Number(pid), "SIGTERM");
    }
  } catch {
    // Process may already be gone.
  }
}

function belongsToForgeTrend(command, { allowRepoPath = false } = {}) {
  return processPatterns.some((pattern) => command.includes(pattern)) || (allowRepoPath && command.includes("forge-trend-ai-app-factory"));
}

function stopLocalProcesses() {
  const seen = new Set();
  for (const port of ports) {
    for (const pid of pidsForPort(port)) {
      if (seen.has(pid)) continue;
      const command = commandForPid(pid);
      console.log(`Port ${port} is used by pid ${pid}: ${command || "unknown command"}`);
      if (forceReset || belongsToForgeTrend(command, { allowRepoPath: true })) {
        seen.add(pid);
        killPid(pid, forceReset ? `port ${port}, FORCE_RESET=true` : `ForgeTrend process on port ${port}`);
      } else {
        console.log(`Port ${port} is used by another process. Set FORCE_RESET=true to kill it.`);
      }
    }
  }
  if (process.platform !== "win32") {
    const output = raw("ps", ["-axo", "pid=,command="]);
    for (const line of output.split(/\r?\n/)) {
      const trimmed = line.trim();
      const [pid] = trimmed.split(/\s+/, 1);
      if (!pid || seen.has(pid)) continue;
      if (belongsToForgeTrend(trimmed)) {
        seen.add(pid);
        killPid(pid, "ForgeTrend dev process");
      }
    }
  }
}

function cleanCaches() {
  const cachePaths = [
    join(root, "apps", "dashboard", ".next"),
    join(root, "apps", "dashboard", "tsconfig.tsbuildinfo"),
  ];
  for (const path of cachePaths) {
    if (existsSync(path)) {
      console.log(`Removing cache ${path}`);
      if (!dryRun) rmSync(path, { recursive: true, force: true });
    }
  }
  if (resetWorkspaces) {
    const workspacePath = join(root, "workspaces");
    console.log(`RESET_WORKSPACES=true, removing generated workspaces at ${workspacePath}`);
    if (!dryRun) {
      rmSync(workspacePath, { recursive: true, force: true });
      run("git", ["checkout", "--", "workspaces/.gitkeep"], { allowFail: true });
    }
  }
}

async function main() {
  console.log("ForgeTrend local reset");
  console.log("======================");
  console.log(forceReset ? "FORCE_RESET=true: port-only kills are enabled." : "Safe mode: only ForgeTrend-owned port processes will be stopped.");
  run("docker", ["compose", "stop", "api", "dashboard", "worker-daemon"], { stdio: "inherit", allowFail: true });
  stopLocalProcesses();
  cleanCaches();
  run("docker", ["compose", "up", "-d", "postgres", "redis", "minio"], { stdio: "inherit" });
  run("pnpm", ["db:migrate"], { stdio: "inherit" });
  run("pnpm", ["doctor:ports"], { stdio: "inherit", allowFail: true });
  console.log("");
  console.log("Local reset complete.");
  console.log("Next:");
  console.log("  codex login");
  console.log("  pnpm dev");
  console.log("  pnpm e2e:factory");
  console.log("");
  console.log("Workspaces were preserved. Set RESET_WORKSPACES=true only when you intentionally want to remove generated runs.");
  console.log("Set FORCE_RESET=true only when you intentionally want to kill unrelated processes on ports 3000/8000.");
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});
