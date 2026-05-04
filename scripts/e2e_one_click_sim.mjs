import fs from "node:fs";

for (const file of ["run.bat", "run.command", "scripts/bootstrap_windows.ps1", "scripts/bootstrap_macos.sh", "scripts/bootstrap_common.mjs"]) {
  if (!fs.existsSync(file)) throw new Error(`Missing ${file}`);
}

const bat = fs.readFileSync("run.bat", "utf8");
const command = fs.readFileSync("run.command", "utf8");
if (!bat.includes("bootstrap_windows.ps1")) throw new Error("run.bat does not call Windows bootstrap");
if (!command.includes("bootstrap_macos.sh")) throw new Error("run.command does not call macOS bootstrap");
console.log("One-click bootstrap simulation passed.");
