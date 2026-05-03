import { briefPayload, reportFailure, request, runFactoryE2E } from "./e2e_factory_shared.mjs";

async function main() {
  if (!process.env.RESEARCH_ALLOWED_URLS) {
    throw new Error("RESEARCH_ALLOWED_URLS is required. Example: RESEARCH_ALLOWED_URLS=https://www.producthunt.com pnpm e2e:research-web");
  }
  const health = await request("/health");
  if (health.status !== "ok") throw new Error(`/health is not ok: ${JSON.stringify(health)}`);
  const doctor = await request("/doctor");
  if (!doctor.research_enable_web) {
    throw new Error("API does not report web research mode. Start API/worker with RESEARCH_ENABLE_WEB=true.");
  }

  await runFactoryE2E({
    requireCodex: false,
    assertWebEvidence: true,
    payload: briefPayload({
      title: `E2E Web Research ${new Date().toISOString().replace(/[:.]/g, "-")}`,
      raw_prompt: "Use allowed web evidence to evaluate a local-first HSK learning app with subscription and IAP placeholders.",
    }),
  });
}

main().catch((error) => {
  reportFailure(error, "Web Research E2E failed");
});
