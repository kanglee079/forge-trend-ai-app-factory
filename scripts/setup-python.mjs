import { existsSync } from "node:fs";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const root = process.cwd();
const venvDir = join(root, ".venv");
const isWindows = process.platform === "win32";
const pythonCandidates = isWindows ? ["python", "py"] : ["python3", "python"];

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: options.cwd ?? root,
    stdio: options.stdio ?? "inherit",
    shell: false
  });
  return result;
}

function findPython() {
  for (const candidate of pythonCandidates) {
    const args = candidate === "py" ? ["-3", "--version"] : ["--version"];
    const result = run(candidate, args, { stdio: "pipe" });
    if (result.status === 0) return candidate;
  }
  throw new Error("Python was not found. Install Python 3.12+ and rerun pnpm setup:python.");
}

function venvPython() {
  return isWindows ? join(venvDir, "Scripts", "python.exe") : join(venvDir, "bin", "python");
}

const systemPython = findPython();
if (!existsSync(venvPython())) {
  const args = systemPython === "py" ? ["-3", "-m", "venv", ".venv"] : ["-m", "venv", ".venv"];
  const result = run(systemPython, args);
  if (result.status !== 0) process.exit(result.status ?? 1);
}

const python = venvPython();
let result = run(python, ["-m", "pip", "install", "--upgrade", "pip"]);
if (result.status !== 0) process.exit(result.status ?? 1);

result = run(python, [
  "-m",
  "pip",
  "install",
  "-r",
  "services/api/requirements.txt",
  "-r",
  "workers/daemon/requirements.txt"
]);
if (result.status !== 0) process.exit(result.status ?? 1);

console.log(`Python environment ready at ${venvDir}`);
