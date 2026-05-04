import { existsSync, mkdirSync, openSync, readFileSync, writeFileSync } from "node:fs";
import { spawn } from "node:child_process";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const root = resolve(scriptDir, "..");
const logsDir = join(root, "logs");
const launcherLogPath = join(logsDir, "launcher.log");
mkdirSync(logsDir, { recursive: true });
const children = new Set();

function log(message) {
  const line = `[${new Date().toISOString()}] ${message}`;
  console.log(message);
  writeFileSync(launcherLogPath, `${line}\n`, { flag: "a" });
}

function commandName(command) {
  if (process.platform !== "win32") return command;
  if (["pnpm", "docker", "node"].includes(command)) return `${command}.cmd`;
  return command;
}

function run(command, args, options = {}) {
  return new Promise((resolvePromise, reject) => {
    const child = spawn(commandName(command), args, { cwd: root, stdio: "inherit", shell: false, ...options });
    child.on("error", (error) => {
      reject(new Error(`${command} is not available: ${error.message}`));
    });
    child.on("exit", (code) => {
      if (code === 0) {
        resolvePromise();
      } else {
        reject(new Error(`${command} ${args.join(" ")} exited with ${code}`));
      }
    });
  });
}

function spawnLogged(name, command, args, env = {}) {
  const logPath = join(logsDir, `${name}.log`);
  const out = openSync(logPath, "a");
  const child = spawn(commandName(command), args, {
    cwd: root,
    env: { ...process.env, ...env },
    stdio: ["ignore", out, out],
    detached: false,
    shell: false,
  });
  writeFileSync(join(logsDir, `${name}.pid`), String(child.pid));
  children.add(child);
  child.on("exit", () => children.delete(child));
  return child;
}

function stopChildren() {
  for (const child of children) {
    try {
      child.kill("SIGTERM");
    } catch {
      // Already gone.
    }
  }
}

async function waitFor(url, label, timeoutMs = 60000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(url);
      if (response.ok) {
        return;
      }
    } catch {
      // Service is still booting.
    }
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 1000));
  }
  throw new Error(`${label} did not become ready at ${url}`);
}

async function isReady(url) {
  try {
    const response = await fetch(url);
    return response.ok;
  } catch {
    return false;
  }
}

async function isDashboardHealthy(url) {
  try {
    const response = await fetch(url);
    const html = await response.text();
    const match = html.match(/href="([^"]*?_next\/static\/[^"]+\.css[^"]*)"/i);
    if (!match) return false;
    const asset = new URL(match[1], url).toString();
    const assetResponse = await fetch(asset);
    return assetResponse.ok;
  } catch {
    return false;
  }
}

async function ensureDependencies() {
  await run("pnpm", ["install", "--frozen-lockfile=false"]);
  await run("pnpm", ["setup:python"]);
  const secretScript = process.platform === "win32" ? join(".venv", "Scripts", "python.exe") : join(".venv", "bin", "python");
  await run(secretScript, ["scripts/ensure_env_secret.py"]);
  await ensureElectronBinary();
}

async function ensureElectronBinary() {
  const electronInstall = join(root, "node_modules", ".pnpm", "electron@33.4.11", "node_modules", "electron", "install.js");
  if (existsSync(electronInstall)) {
    await run("node", [electronInstall]);
  }
}

async function main() {
  log("Starting ForgeTrend desktop...");
  await ensureDependencies();
  log("Starting Docker services: postgres, redis, minio");
  await run("docker", ["compose", "up", "-d", "postgres", "redis", "minio"]);
  log("Running database migrations");
  await run("pnpm", ["db:migrate"]);

  if (!(await isReady("http://localhost:8000/health"))) {
    spawnLogged("api", "pnpm", ["dev:api"]);
  }
  if (!(await isDashboardHealthy("http://localhost:3000"))) {
    spawnLogged("dashboard", "pnpm", ["serve:dashboard"]);
  }
  spawnLogged("worker", "pnpm", ["dev:worker"], { PYTHONUNBUFFERED: "1" });

  await waitFor("http://localhost:8000/health", "API");
  await waitFor("http://localhost:3000", "Dashboard");

  log("Opening ForgeTrend desktop window...");
  await run("pnpm", ["desktop"]);
}

main().catch((error) => {
  log(`Launcher failed: ${error instanceof Error ? error.message : String(error)}`);
  console.error(error);
  const detail = existsSync(join(logsDir, "api.log")) ? readFileSync(join(logsDir, "api.log"), "utf8").slice(-2000) : "";
  if (detail) {
    console.error("\nRecent API log:\n", detail);
  }
  process.exit(1);
});

process.on("SIGINT", () => {
  stopChildren();
  process.exit(130);
});

process.on("SIGTERM", () => {
  stopChildren();
  process.exit(143);
});

process.on("exit", stopChildren);
