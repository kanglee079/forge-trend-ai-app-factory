import { existsSync, mkdirSync, openSync, readFileSync, writeFileSync } from "node:fs";
import { spawn } from "node:child_process";
import { join, resolve } from "node:path";

const root = resolve(new URL("..", import.meta.url).pathname);
const logsDir = join(root, "logs");
mkdirSync(logsDir, { recursive: true });
const children = new Set();

function run(command, args, options = {}) {
  return new Promise((resolvePromise, reject) => {
    const child = spawn(command, args, { cwd: root, stdio: "inherit", shell: false, ...options });
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
  const child = spawn(command, args, {
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
  console.log("Starting ForgeTrend desktop...");
  await ensureDependencies();
  await run("docker", ["compose", "up", "-d", "postgres", "redis", "minio"]);
  await run("pnpm", ["db:migrate"]);

  if (!(await isReady("http://localhost:8000/health"))) {
    spawnLogged("api", "pnpm", ["dev:api"]);
  }
  if (!(await isReady("http://localhost:3000"))) {
    spawnLogged("dashboard", "pnpm", ["dev:dashboard"]);
  }
  spawnLogged("worker", "pnpm", ["dev:worker"], { PYTHONUNBUFFERED: "1" });

  await waitFor("http://localhost:8000/health", "API");
  await waitFor("http://localhost:3000", "Dashboard");

  console.log("Opening ForgeTrend desktop window...");
  await run("pnpm", ["desktop"]);
}

main().catch((error) => {
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
