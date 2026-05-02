import { existsSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";

const root = process.cwd();
const isWindows = process.platform === "win32";
const python = isWindows ? join(root, ".venv", "Scripts", "python.exe") : join(root, ".venv", "bin", "python");

if (!existsSync(python)) {
  const setup = spawnSync("node", ["scripts/setup-python.mjs"], { cwd: root, stdio: "inherit" });
  if (setup.status !== 0) process.exit(setup.status ?? 1);
}

const [cwdArg, ...pythonArgs] = process.argv.slice(2);
if (!cwdArg || pythonArgs.length === 0) {
  console.error("Usage: node scripts/venv-run.mjs <cwd> <python args...>");
  process.exit(2);
}

function loadDotEnv() {
  const envPath = join(root, ".env");
  if (!existsSync(envPath)) return {};
  const parsed = {};
  for (const line of readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
    const index = trimmed.indexOf("=");
    const key = trimmed.slice(0, index).trim();
    const value = trimmed.slice(index + 1).trim().replace(/^["']|["']$/g, "");
    parsed[key] = value;
  }
  return parsed;
}

const env = {
  ...loadDotEnv(),
  ...process.env,
  PYTHONPATH: [resolve(root, cwdArg), process.env.PYTHONPATH].filter(Boolean).join(isWindows ? ";" : ":")
};

const result = spawnSync(python, pythonArgs, {
  cwd: resolve(root, cwdArg),
  env,
  stdio: "inherit",
  shell: false
});

process.exit(result.status ?? 1);
