import { reportFailure, runFactoryE2E } from "./e2e_factory_shared.mjs";

runFactoryE2E({ requireCodex: false, assertCodex: false }).catch((error) => {
  reportFailure(error, "Deterministic Factory E2E failed");
});
