import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { spawn } from "node:child_process";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const root = resolve(scriptDir, "..");
const logsDir = join(root, "logs");
const logPath = join(logsDir, "bootstrap.log");
mkdirSync(logsDir, { recursive: true });

function log(message) {
  const line = `[${new Date().toISOString()}] ${message}`;
  console.log(message);
  writeFileSync(logPath, `${line}\n`, { flag: "a" });
}

function commandName(command) {
  if (process.platform !== "win32") return command;
  if (["pnpm", "docker", "node"].includes(command)) return `${command}.cmd`;
  return command;
}

function run(command, args, options = {}) {
  return new Promise((resolvePromise, reject) => {
    const child = spawn(commandName(command), args, { cwd: root, stdio: "inherit", shell: false, ...options });
    child.on("error", (error) => reject(new Error(`${command} is not available: ${error.message}`)));
    child.on("exit", (code) => code === 0 ? resolvePromise() : reject(new Error(`${command} ${args.join(" ")} exited with ${code}`)));
  });
}

async function waitFor(url, label, timeoutMs = 90000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // Still booting.
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

function spawnLogged(name, command, args, env = {}) {
  const out = join(logsDir, `${name}.log`);
  const child = spawn(commandName(command), args, {
    cwd: root,
    env: { ...process.env, ...env },
    stdio: ["ignore", "pipe", "pipe"],
    shell: false,
  });
  child.stdout.on("data", (data) => writeFileSync(out, data, { flag: "a" }));
  child.stderr.on("data", (data) => writeFileSync(out, data, { flag: "a" }));
  writeFileSync(join(logsDir, `${name}.pid`), String(child.pid));
  return child;
}

async function launch() {
  log("[1/4] Khởi động API nếu cần");
  if (!(await isReady("http://localhost:8000/health"))) spawnLogged("api", "pnpm", ["dev:api"]);
  log("[2/4] Khởi động Dashboard nếu cần");
  if (!(await isDashboardHealthy("http://localhost:3000"))) spawnLogged("dashboard", "pnpm", ["serve:dashboard"]);
  log("[3/4] Khởi động Worker");
  spawnLogged("worker", "pnpm", ["dev:worker"], { PYTHONUNBUFFERED: "1" });
  await waitFor("http://localhost:8000/health", "API");
  await waitFor("http://localhost:3000", "Dashboard");
  log("[4/4] Mở ForgeTrend desktop");
  await run("pnpm", ["desktop"]);
}

const command = process.argv[2];
if (command === "launch") {
  launch().catch((error) => {
    log(`Bootstrap failed: ${error instanceof Error ? error.message : String(error)}`);
    const apiLog = join(logsDir, "api.log");
    if (existsSync(apiLog)) console.error(readFileSync(apiLog, "utf8").slice(-2000));
    process.exit(1);
  });
} else {
  console.log("Usage: node scripts/bootstrap_common.mjs launch");
}
