"use client";

import { AlertTriangle, CheckCircle2, Circle, Clock, Copy, Loader2, XCircle } from "lucide-react";
import { AgentEvent, Artifact, PolicyResult, Project, QAResult } from "@/lib/api";
import { cn, formatDate } from "@/lib/utils";
import { Badge, Button, Card, Progress } from "@/components/ui";

export type PipelineStepStatus = "pending" | "running" | "passed" | "failed" | "skipped" | "needs_human_review";

export type PipelineStep = {
  id: string;
  label: string;
  status: PipelineStepStatus;
  latestMessage?: string;
  retryCount: number;
  updatedAt?: string;
};

const stepDefinitions = [
  { id: "environment", label: "Environment Check", eventSteps: ["pipeline"] },
  { id: "idea_validation", label: "Idea Validation", eventSteps: ["pipeline"] },
  { id: "opportunity", label: "Opportunity Scoring", eventSteps: ["pipeline"] },
  { id: "prd", label: "PRD Generation", eventSteps: ["prd_agent"] },
  { id: "ux", label: "UX / Design System", eventSteps: ["ux_agent"] },
  { id: "scaffold", label: "Flutter Scaffold", eventSteps: ["code_agent"] },
  { id: "code", label: "Code Agent Pass", eventSteps: ["code_agent"] },
  { id: "build", label: "Build", eventSteps: ["qa_agent"] },
  { id: "test", label: "Test", eventSteps: ["qa_agent"] },
  { id: "fix", label: "Auto Fix Loop", eventSteps: ["code_agent"] },
  { id: "policy", label: "Policy Gate", eventSteps: ["policy_agent"] },
  { id: "artifact", label: "Artifact Packaging", eventSteps: ["qa_agent", "pipeline"] },
  { id: "release", label: "Release Candidate", eventSteps: ["pipeline"] },
  { id: "approval", label: "Human Approval Required", eventSteps: ["pipeline"] }
];

const completedProjectStatuses = ["release_candidate"];
const reviewProjectStatuses = ["NEEDS_HUMAN_REVIEW", "needs_human_review", "stop_requested"];
const runningProjectStatuses = ["queued", "running"];

export function derivePipelineSteps({
  project,
  events,
  qa,
  policy,
  artifacts,
}: {
  project: Project;
  events: AgentEvent[];
  qa: QAResult[];
  policy: PolicyResult[];
  artifacts: Artifact[];
}): PipelineStep[] {
  const hasEvent = (steps: string[]) => events.some((event) => steps.includes(event.step));
  const latestFor = (steps: string[]) => [...events].reverse().find((event) => steps.includes(event.step));
  const hasErrorFor = (steps: string[]) => events.some((event) => steps.includes(event.step) && event.level === "error");
  const qaPassed = qa.some((item) => item.status === "passed" && item.exit_code === 0);
  const qaFailed = qa.some((item) => item.status === "failed" || item.exit_code !== 0);
  const latestPolicy = policy[0];
  const hasBuildArtifact = artifacts.some((artifact) => artifact.kind === "build" || artifact.name.endsWith(".apk"));
  const isComplete = completedProjectStatuses.includes(project.status);
  const needsReview = reviewProjectStatuses.includes(project.status);
  const isRunning = runningProjectStatuses.includes(project.status);

  return stepDefinitions.map((definition, index) => {
    const latest = latestFor(definition.eventSteps);
    let status: PipelineStepStatus = "pending";

    if (index <= 2 && (isRunning || events.length > 0 || project.workspace_path)) {
      status = "passed";
    }
    if (definition.id === "prd" && artifacts.some((artifact) => artifact.name === "prd.md")) status = "passed";
    if (definition.id === "ux" && artifacts.some((artifact) => artifact.name === "design_system.md" || artifact.name === "screen_flow.md")) status = "passed";
    if ((definition.id === "scaffold" || definition.id === "code") && hasEvent(["code_agent"])) status = "passed";
    if (definition.id === "build") status = hasBuildArtifact ? "passed" : qaFailed ? "failed" : hasEvent(["qa_agent"]) ? "running" : "pending";
    if (definition.id === "test") status = qaPassed ? "passed" : qaFailed ? "failed" : hasEvent(["qa_agent"]) ? "running" : "pending";
    if (definition.id === "fix") {
      const fixEvents = events.filter((event) => event.step === "code_agent" && Number(event.metadata_json?.iteration ?? 0) > 0);
      status = fixEvents.length ? "passed" : qaFailed ? "running" : "pending";
    }
    if (definition.id === "policy" && latestPolicy) status = latestPolicy.passed ? "passed" : latestPolicy.risk === "high" ? "failed" : "needs_human_review";
    if (definition.id === "artifact") status = artifacts.length ? "passed" : isComplete ? "failed" : "pending";
    if (definition.id === "release") status = isComplete ? "passed" : needsReview ? "needs_human_review" : "pending";
    if (definition.id === "approval") status = isComplete || needsReview ? "needs_human_review" : "pending";

    if (hasErrorFor(definition.eventSteps) && !["fix", "approval"].includes(definition.id)) {
      status = "failed";
    }
    if (latest?.level === "warning" && status === "pending") {
      status = "needs_human_review";
    }
    if (latest && status === "pending" && isRunning) {
      status = "running";
    }

    return {
      id: definition.id,
      label: definition.label,
      status,
      latestMessage: latest?.message,
      retryCount: events.filter((event) => definition.eventSteps.includes(event.step) && Number(event.metadata_json?.iteration ?? 0) > 0).length,
      updatedAt: latest?.created_at
    };
  });
}

export function getPipelineProgress(steps: PipelineStep[]) {
  const weighted = steps.reduce((total, step) => total + (step.status === "passed" ? 1 : step.status === "needs_human_review" ? 0.65 : step.status === "running" ? 0.35 : 0), 0);
  return Math.round((weighted / steps.length) * 100);
}

export function getCurrentStep(steps: PipelineStep[]) {
  return steps.find((step) => step.status === "running") ?? steps.find((step) => step.status === "failed") ?? steps.find((step) => step.status === "needs_human_review") ?? steps.find((step) => step.status === "pending") ?? steps[steps.length - 1];
}

export function getLatestFailure(events: AgentEvent[], qa: QAResult[]) {
  const eventFailure = [...events].reverse().find((event) => event.level === "error" || event.stderr);
  const qaFailure = qa.find((item) => item.status === "failed" || item.exit_code !== 0);
  const qaText = qaFailure ? [qaFailure.command, qaFailure.stdout, qaFailure.stderr].filter(Boolean).join("\n\n") : "";
  return eventFailure
    ? {
        title: `${eventFailure.step}: ${eventFailure.message}`,
        detail: [eventFailure.stderr, eventFailure.stdout].filter(Boolean).join("\n\n"),
        createdAt: eventFailure.created_at,
      }
    : qaFailure
      ? { title: `QA failed: ${qaFailure.command}`, detail: qaText, createdAt: qaFailure.created_at }
      : null;
}

export function PipelineStepper({
  steps,
  latestFailure,
  onCopyFailure,
}: {
  steps: PipelineStep[];
  latestFailure?: ReturnType<typeof getLatestFailure>;
  onCopyFailure?: () => void;
}) {
  const progress = getPipelineProgress(steps);
  const current = getCurrentStep(steps);
  return (
    <Card>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-base font-semibold">Pipeline</h2>
          <p className="text-sm text-muted-foreground">Current step: {current?.label ?? "Waiting for first event"}</p>
        </div>
        <Badge tone={progress >= 100 ? "success" : current?.status === "failed" ? "danger" : current?.status === "needs_human_review" ? "warning" : "neutral"}>{progress}%</Badge>
      </div>
      <Progress value={progress} />
      <div className="mt-5 grid gap-3 lg:grid-cols-2">
        {steps.map((step) => (
          <div key={step.id} className="flex gap-3 rounded-md border border-border bg-background p-3">
            <StepStatusIcon status={step.status} />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <div className="font-medium">{step.label}</div>
                <StepBadge status={step.status} />
                {step.retryCount ? <Badge tone="warning">retry {step.retryCount}</Badge> : null}
              </div>
              <div className="mt-1 truncate text-xs text-muted-foreground">{step.latestMessage ?? "No signal yet"}</div>
              {step.updatedAt ? <div className="mt-1 text-xs text-muted-foreground">{formatDate(step.updatedAt)}</div> : null}
            </div>
          </div>
        ))}
      </div>
      {latestFailure ? (
        <div className="mt-5 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-950">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div className="font-semibold">{latestFailure.title}</div>
              <div className="mt-1 text-red-900/75">{latestFailure.createdAt ? formatDate(latestFailure.createdAt) : "Latest failure"}</div>
            </div>
            {onCopyFailure ? (
              <Button type="button" variant="secondary" onClick={onCopyFailure}>
                <Copy size={15} />
                Copy log
              </Button>
            ) : null}
          </div>
          {latestFailure.detail ? <pre className="mt-3 max-h-56 overflow-auto rounded-md bg-red-950 p-3 text-xs text-red-50">{latestFailure.detail}</pre> : null}
        </div>
      ) : null}
    </Card>
  );
}

function StepStatusIcon({ status }: { status: PipelineStepStatus }) {
  const className = "mt-0.5 h-5 w-5 shrink-0";
  if (status === "passed") return <CheckCircle2 className={cn(className, "text-emerald-600")} />;
  if (status === "failed") return <XCircle className={cn(className, "text-red-600")} />;
  if (status === "running") return <Loader2 className={cn(className, "animate-spin text-primary")} />;
  if (status === "needs_human_review") return <AlertTriangle className={cn(className, "text-amber-600")} />;
  if (status === "skipped") return <Clock className={cn(className, "text-muted-foreground")} />;
  return <Circle className={cn(className, "text-muted-foreground")} />;
}

function StepBadge({ status }: { status: PipelineStepStatus }) {
  const tone = status === "passed" ? "success" : status === "failed" ? "danger" : status === "running" || status === "needs_human_review" ? "warning" : "neutral";
  return <Badge tone={tone}>{status}</Badge>;
}
