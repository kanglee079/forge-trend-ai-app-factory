import { spawn } from "node:child_process";

const children = new Set();

function commandName(command) {
  if (process.platform !== "win32") return command;
  return `${command}.cmd`;
}

function spawnScript(name, args) {
  const child = spawn(commandName("pnpm"), args, {
    cwd: process.cwd(),
    env: process.env,
    stdio: ["inherit", "pipe", "pipe"],
    shell: false,
  });
  children.add(child);
  child.stdout.on("data", (chunk) => process.stdout.write(`[${name}] ${chunk}`));
  child.stderr.on("data", (chunk) => process.stderr.write(`[${name}] ${chunk}`));
  child.on("exit", (code, signal) => {
    children.delete(child);
    if (code && code !== 0) {
      console.error(`[${name}] exited with ${code}`);
      stopAll();
      process.exitCode = code;
    } else if (signal) {
      console.error(`[${name}] stopped by ${signal}`);
    }
  });
}

function stopAll() {
  for (const child of children) {
    try {
      child.kill("SIGTERM");
    } catch {
      // Process already exited.
    }
  }
}

async function main() {
  spawnScript("api", ["dev:api"]);
  spawnScript("worker", ["dev:worker"]);
  spawnScript("dashboard", ["serve:dashboard"]);
}

main().catch((error) => {
  console.error(error);
  stopAll();
  process.exit(1);
});

process.on("SIGINT", () => {
  stopAll();
  process.exit(130);
});

process.on("SIGTERM", () => {
  stopAll();
  process.exit(143);
});
