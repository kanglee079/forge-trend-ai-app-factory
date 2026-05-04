import { spawnSync } from "node:child_process";

const commands = [
  ["node", ["scripts/doctor_ports.mjs"]],
  ["python3", ["scripts/doctor.py"]],
];

for (const [cmd, args] of commands) {
  const result = spawnSync(cmd, args, { stdio: "inherit", shell: process.platform === "win32" });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

console.log("First-run checks completed.");
