import fs from "node:fs";

for (const file of ["run.bat", "run.command", "scripts/bootstrap_windows.ps1", "scripts/bootstrap_macos.sh", "scripts/bootstrap_common.mjs"]) {
  if (!fs.existsSync(file)) throw new Error(`Missing ${file}`);
}

const bat = fs.readFileSync("run.bat", "utf8");
const command = fs.readFileSync("run.command", "utf8");
const win = fs.readFileSync("scripts/bootstrap_windows.ps1", "utf8");
const mac = fs.readFileSync("scripts/bootstrap_macos.sh", "utf8");
const common = fs.readFileSync("scripts/bootstrap_common.mjs", "utf8");
if (!bat.includes("bootstrap_windows.ps1")) throw new Error("run.bat does not call Windows bootstrap");
if (!command.includes("bootstrap_macos.sh")) throw new Error("run.command does not call macOS bootstrap");
for (const [label, text] of [["windows", win], ["macos", mac]]) {
  if (!text.includes("[1/12]") && !text.includes("$Index/12") && !text.includes("$1/12")) throw new Error(`${label} bootstrap does not use 12-step progress`);
  if (!text.includes("bootstrap.log")) throw new Error(`${label} bootstrap does not write logs/bootstrap.log`);
  if (!/Android SDK|ANDROID_HOME|ANDROID_SDK_ROOT/.test(text)) throw new Error(`${label} bootstrap does not check Android SDK`);
  if (!text.includes("doctor_ports.mjs")) throw new Error(`${label} bootstrap does not check stale ports`);
}
if (!common.includes("bootstrap.log")) throw new Error("bootstrap_common does not append to logs/bootstrap.log");
console.log("One-click bootstrap simulation passed.");
