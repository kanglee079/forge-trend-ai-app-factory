import { readFileSync } from "node:fs";
import { runFactoryE2E, request, reportFailure, briefPayload } from "./e2e_factory_shared.mjs";

try {
  const result = await runFactoryE2E({
    requireCodex: false,
    assertVietnamese: true,
    payload: briefPayload({
      mode: "manual_idea",
      title: `E2E Skills Real ${Date.now()}`,
      raw_prompt: "Tạo app giáo dục tiếng Việt có subscription mô phỏng, ôn bài hằng ngày, paywall giả lập và UX tiếng Việt tự nhiên.",
      target_category: "Education",
      target_country: "VN",
      target_language: "vi",
      monetization_mode: "subscription",
      subscription_enabled: true,
      iap_enabled: false,
    }),
  });
  const skillRuns = await request(`/skill-runs?project_id=${result.project.id}&limit=500`);
  const slugsById = new Map((await request("/skill-packs")).map((pack) => [pack.id, pack.slug]));
  const usedSlugs = new Set(skillRuns.map((run) => slugsById.get(run.skill_pack_id)).filter(Boolean));
  for (const slug of ["vietnamese_ux_writer", "flutter_store_ready", "iap_subscription_placeholder"]) {
    if (!usedSlugs.has(slug)) throw new Error(`Expected SkillRun for ${slug}; got ${Array.from(usedSlugs).join(", ")}`);
  }
  const viReport = result.artifacts.find((artifact) => artifact.name === "factory_run_report.vi.md");
  if (!viReport) throw new Error("factory_run_report.vi.md missing");
  const reportText = readFileSync(viReport.path, "utf8");
  for (const slug of ["vietnamese_ux_writer", "flutter_store_ready", "iap_subscription_placeholder"]) {
    if (!reportText.includes(slug)) throw new Error(`Vietnamese run report does not list skill ${slug}`);
  }
  if (!/Token budget/i.test(reportText)) throw new Error("Vietnamese run report does not list estimated token budget");
  console.log(`Skills real passed for project ${result.project.id}`);
} catch (error) {
  reportFailure(error, "Skills real E2E failed");
}
