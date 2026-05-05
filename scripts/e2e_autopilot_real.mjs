import { runFactoryE2E, reportFailure, briefPayload } from "./e2e_factory_shared.mjs";

try {
  const result = await runFactoryE2E({
    requireCodex: false,
    payload: briefPayload({
      title: `E2E Autopilot Real ${Date.now()}`,
      raw_prompt: "Create a local-first education app with store readiness, policy review, QA, and enough product depth for autopilot validation.",
      target_category: "Education",
      target_language: "en",
      monetization_mode: "subscription",
      subscription_enabled: true,
    }),
  });
  const steps = new Set(result.events.map((event) => event.step));
  if (!steps.has("autopilot_completed") && !steps.has("autopilot_blocked")) {
    throw new Error("Autopilot did not emit autopilot_completed or autopilot_blocked");
  }
  const hadFailedQa = result.qa.some((item) => item.status === "failed" || item.exit_code !== 0);
  if (hadFailedQa && (!steps.has("autopilot_decision") || !steps.has("autopilot_retry"))) {
    throw new Error("QA failed but autopilot decision/retry events were not emitted");
  }
  const hadPolicyFailure = result.policy.some((item) => !item.passed);
  if (hadPolicyFailure && !steps.has("autopilot_decision")) {
    throw new Error("Policy failed but autopilot_decision was not emitted");
  }
  console.log(`Autopilot real passed for project ${result.project.id}`);
} catch (error) {
  reportFailure(error, "Autopilot real E2E failed");
}
