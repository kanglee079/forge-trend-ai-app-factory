import { readFile } from "node:fs/promises";

const page = await readFile("apps/dashboard/app/how-it-works/page.tsx", "utf8");
const required = [
  "Ý tưởng",
  "Nghiên cứu",
  "Code Flutter",
  "Test và sửa lỗi",
  "Không auto-publish",
];

for (const text of required) {
  if (!page.includes(text)) {
    throw new Error(`How it works page is missing: ${text}`);
  }
}

console.log("How-it-works page content passed");
