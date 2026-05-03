import { briefPayload, reportFailure, runFactoryE2E } from "./e2e_factory_shared.mjs";

runFactoryE2E({
  requireCodex: false,
  assertCodex: false,
  assertVietnamese: true,
  payload: briefPayload({
    title: `E2E App học HSK ${new Date().toISOString().replace(/[:.]/g, "-")}`,
    raw_prompt: "Tạo app học HSK cho người Việt, có gói premium mô phỏng, offline-first, Android trước.",
    target_category: "Education",
    target_country: "VN",
    target_language: "vi",
    monetization_mode: "subscription",
    iap_enabled: true,
    subscription_enabled: true,
  }),
}).catch((error) => {
  reportFailure(error, "Vietnamese Factory E2E failed");
});
