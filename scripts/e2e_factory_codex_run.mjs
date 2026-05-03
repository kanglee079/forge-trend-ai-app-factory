import { reportFailure, runFactoryE2E } from "./e2e_factory_shared.mjs";

runFactoryE2E({ requireCodex: true, assertCodex: true }).catch((error) => {
  reportFailure(error, "Codex Factory E2E failed");
});
