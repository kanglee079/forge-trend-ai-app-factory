export type ProjectStatus =
  | "created"
  | "queued"
  | "running"
  | "release_candidate"
  | "NEEDS_HUMAN_REVIEW";

export const PIPELINE_STEPS = [
  "prd_agent",
  "ux_agent",
  "code_agent",
  "qa_agent",
  "policy_agent",
] as const;

export type PipelineStep = (typeof PIPELINE_STEPS)[number];
