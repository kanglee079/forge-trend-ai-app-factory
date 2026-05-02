"use client";

import { useEffect, useState } from "react";
import { Loader2, Play, RefreshCw, RotateCcw, Square } from "lucide-react";
import { AgentEvent, ApiError, api, Artifact, PolicyResult, Project, QAResult, Worker } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Badge, Button, Card, Notice, StatusBadge, Table, Td, Th } from "@/components/ui";
import { useFeedback } from "@/components/feedback";
import { CopyButton, LogViewer } from "@/components/log-viewer";
import { derivePipelineSteps, getCurrentStep, getLatestFailure, getPipelineProgress, PipelineStepper } from "@/components/pipeline";

const tabs = ["Overview", "PRD", "Agent Timeline", "Logs", "QA", "Policy", "Artifacts", "Settings"] as const;
type Tab = (typeof tabs)[number];

export function ProjectDetailClient({ initialProject }: { initialProject: Project }) {
  const feedback = useFeedback();
  const [project, setProject] = useState(initialProject);
  const [active, setActive] = useState<Tab>("Overview");
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [qa, setQa] = useState<QAResult[]>([]);
  const [policy, setPolicy] = useState<PolicyResult[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [notice, setNotice] = useState<{ tone: "success" | "danger" | "warning"; message: string } | null>(null);

  async function load() {
    setLoading(true);
    try {
      const [projectItem, eventItems, qaItems, policyItems, artifactItems, workerItems] = await Promise.all([
        api.project(project.id),
        api.events(project.id),
        api.qa(project.id),
        api.policy(project.id),
        api.artifacts(project.id),
        api.workers()
      ]);
      setProject(projectItem);
      setEvents(eventItems);
      setQa(qaItems);
      setPolicy(policyItems);
      setArtifacts(artifactItems);
      setWorkers(workerItems);
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Could not refresh project state." });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const timer = setInterval(() => load().catch(console.error), 5000);
    load().catch(console.error);
    return () => clearInterval(timer);
  }, []);

  async function run() {
    if (running) {
      return;
    }
    const activeLocalWorker = workers.find((worker) => worker.status === "online" && worker.has_codex && worker.has_flutter);
    if (!activeLocalWorker) {
      setNotice({ tone: "warning", message: "No online local worker with Codex and Flutter is available. Start pnpm dev:worker, then run the pipeline again." });
      return;
    }
    if (project.workspace_path) {
      const confirmed = await feedback.confirm({
        title: "Run pipeline again?",
        description: "This can modify files in the existing generated workspace. Existing project events and artifacts stay visible.",
        confirmLabel: "Run pipeline",
      });
      if (!confirmed) return;
    }
    setRunning(true);
    setNotice(null);
    try {
      const response = await api.runPipeline(project.id);
      setProject((current) => ({ ...current, status: response.status }));
      feedback.notify({ tone: "success", message: `Pipeline queued on ${response.queue}.` });
      setNotice({ tone: "success", message: `Pipeline queued on ${response.queue}. This page refreshes every 5 seconds while the worker reports events.` });
      await load();
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Could not queue pipeline." });
    } finally {
      setRunning(false);
    }
  }

  async function retry() {
    if (running) return;
    const confirmed = await feedback.confirm({
      title: "Retry project pipeline?",
      description: "The project will be queued again using the current workspace and latest state.",
      confirmLabel: "Retry",
    });
    if (!confirmed) return;
    setRunning(true);
    try {
      const response = await api.retryPipeline(project.id);
      setProject((current) => ({ ...current, status: response.status }));
      feedback.notify({ tone: "success", message: `Retry queued on ${response.queue}.` });
      await load();
    } catch (error) {
      feedback.notify({ tone: "danger", message: error instanceof ApiError ? error.detail : "Could not queue retry." });
    } finally {
      setRunning(false);
    }
  }

  async function stop() {
    if (stopping) return;
    const confirmed = await feedback.confirm({
      title: "Request stop?",
      description: "The current worker pass may finish before cancellation is observed. The dashboard will mark the project as stop requested.",
      confirmLabel: "Request stop",
      tone: "danger",
    });
    if (!confirmed) return;
    setStopping(true);
    try {
      await api.stopPipeline(project.id);
      setProject((current) => ({ ...current, status: "stop_requested" }));
      feedback.notify({ tone: "warning", message: "Stop requested for this project." });
      await load();
    } catch (error) {
      feedback.notify({ tone: "danger", message: error instanceof ApiError ? error.detail : "Could not request stop." });
    } finally {
      setStopping(false);
    }
  }

  async function clearLogs() {
    if (clearing) return;
    const confirmed = await feedback.confirm({
      title: "Clear project logs?",
      description: "This removes stored agent events for this project. QA, policy, and artifacts remain.",
      confirmLabel: "Clear logs",
      tone: "danger",
    });
    if (!confirmed) return;
    setClearing(true);
    try {
      const response = await api.clearEvents(project.id);
      setEvents([]);
      feedback.notify({ tone: "success", message: response.detail });
    } catch (error) {
      feedback.notify({ tone: "danger", message: error instanceof ApiError ? error.detail : "Could not clear logs." });
    } finally {
      setClearing(false);
    }
  }

  const prd = artifacts.find((item) => item.name === "prd.md");
  const hasReadyWorker = workers.some((worker) => worker.status === "online" && worker.has_codex && worker.has_flutter);
  const steps = derivePipelineSteps({ project, events, qa, policy, artifacts });
  const latestFailure = getLatestFailure(events, qa);
  const currentStep = getCurrentStep(steps);
  const progress = getPipelineProgress(steps);

  return (
    <>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="mb-2"><StatusBadge status={project.status} /></div>
          <h1 className="text-2xl font-semibold">{project.name}</h1>
          <p className="text-sm text-muted-foreground">{project.slug} · {project.workspace_path ?? "workspace pending"}</p>
          <p className="mt-1 text-sm text-muted-foreground">{progress}% complete · current step: {currentStep?.label ?? "waiting"}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => load()} disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw size={16} />}
            {loading ? "Refreshing..." : "Refresh"}
          </Button>
          <Button onClick={() => run()} disabled={running}>
            {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play size={16} />}
            {running ? "Queueing..." : "Run pipeline"}
          </Button>
          <Button variant="secondary" onClick={() => retry()} disabled={running}>
            {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw size={16} />}
            Retry
          </Button>
          <Button variant="danger" onClick={() => stop()} disabled={stopping}>
            {stopping ? <Loader2 className="h-4 w-4 animate-spin" /> : <Square size={16} />}
            Stop
          </Button>
        </div>
      </div>
      {notice ? <Notice tone={notice.tone}>{notice.message}</Notice> : null}
      {!hasReadyWorker ? (
        <Notice tone="warning">Local worker is offline or missing Codex/Flutter. Run codex login and pnpm dev:worker in a terminal before starting this project pipeline.</Notice>
      ) : null}
      <div className="mb-5 flex flex-wrap gap-2">
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => setActive(tab)}
            className={`rounded-md border px-3 py-2 text-sm ${active === tab ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card"}`}
          >
            {tab}
          </button>
        ))}
      </div>
      {active === "Overview" ? <Overview project={project} events={events} qa={qa} policy={policy} artifacts={artifacts} steps={steps} latestFailure={latestFailure} /> : null}
      {active === "PRD" ? <PrdPanel prdPath={prd?.path} /> : null}
      {active === "Agent Timeline" ? <Timeline events={events} /> : null}
      {active === "Logs" ? <LogViewer events={events} onClear={clearLogs} /> : null}
      {active === "QA" ? <QaPanel qa={qa} /> : null}
      {active === "Policy" ? <PolicyPanel policy={policy} /> : null}
      {active === "Artifacts" ? <ArtifactsPanel artifacts={artifacts} /> : null}
      {active === "Settings" ? <SettingsPanel project={project} /> : null}
    </>
  );
}

function Overview({
  project,
  events,
  qa,
  policy,
  artifacts,
  steps,
  latestFailure,
}: {
  project: Project;
  events: AgentEvent[];
  qa: QAResult[];
  policy: PolicyResult[];
  artifacts: Artifact[];
  steps: ReturnType<typeof derivePipelineSteps>;
  latestFailure: ReturnType<typeof getLatestFailure>;
}) {
  const latestPolicy = policy[0];
  return (
    <div className="space-y-4">
      <PipelineStepper
        steps={steps}
        latestFailure={latestFailure}
        onCopyFailure={latestFailure?.detail ? () => navigator.clipboard.writeText(latestFailure.detail) : undefined}
      />
      <div className="grid gap-4 md:grid-cols-4">
        <Card><div className="text-sm text-muted-foreground">Status</div><div className="mt-2"><StatusBadge status={project.status} /></div></Card>
        <Card><div className="text-sm text-muted-foreground">Events</div><div className="mt-2 text-2xl font-semibold">{events.length}</div></Card>
        <Card><div className="text-sm text-muted-foreground">QA Commands</div><div className="mt-2 text-2xl font-semibold">{qa.length}</div></Card>
        <Card><div className="text-sm text-muted-foreground">Policy</div><div className="mt-2">{latestPolicy ? <Badge tone={latestPolicy.passed ? "success" : "danger"}>{latestPolicy.risk}</Badge> : "Pending"}</div></Card>
        <Card className="md:col-span-4">
          <h2 className="mb-3 text-base font-semibold">Artifacts</h2>
          <div className="flex flex-wrap gap-2">{artifacts.length ? artifacts.map((item) => <Badge key={item.id}>{item.name}</Badge>) : <span className="text-sm text-muted-foreground">No artifacts yet.</span>}</div>
        </Card>
      </div>
    </div>
  );
}

function PrdPanel({ prdPath }: { prdPath?: string }) {
  return <Card><h2 className="mb-2 text-base font-semibold">PRD</h2><p className="text-sm text-muted-foreground">{prdPath ? `Generated at ${prdPath}` : "PRD has not been generated yet."}</p></Card>;
}

function Timeline({ events }: { events: AgentEvent[] }) {
  return (
    <Card>
      <div className="space-y-3">
        {events.map((event) => (
          <div key={event.id} className="border-l-2 border-primary pl-4">
            <div className="flex flex-wrap items-center gap-2"><Badge>{event.step}</Badge><Badge tone={event.level === "error" ? "danger" : event.level === "warning" ? "warning" : "neutral"}>{event.level}</Badge><span className="text-xs text-muted-foreground">{formatDate(event.created_at)}</span></div>
            <p className="mt-1 text-sm">{event.message}</p>
          </div>
        ))}
        {!events.length ? <p className="text-sm text-muted-foreground">No events yet.</p> : null}
      </div>
    </Card>
  );
}

function QaPanel({ qa }: { qa: QAResult[] }) {
  return (
    <div className="space-y-4">
      <Table>
        <thead><tr><Th>Command</Th><Th>Status</Th><Th>Exit</Th><Th>Created</Th><Th>Log</Th></tr></thead>
        <tbody>{qa.map((item) => <tr key={item.id}><Td>{item.command}</Td><Td><StatusBadge status={item.status} /></Td><Td>{item.exit_code}</Td><Td>{formatDate(item.created_at)}</Td><Td><CopyButton value={[item.command, item.stdout, item.stderr].filter(Boolean).join("\n\n")} /></Td></tr>)}</tbody>
      </Table>
      {!qa.length ? <Card className="text-sm text-muted-foreground">No QA results yet.</Card> : null}
    </div>
  );
}

function PolicyPanel({ policy }: { policy: PolicyResult[] }) {
  const latest = policy[0];
  return (
    <Card>
      {latest ? (
        <>
          <div className="mb-4 flex items-center gap-2"><Badge tone={latest.passed ? "success" : "danger"}>{latest.passed ? "passed" : "failed"}</Badge><Badge>{latest.risk}</Badge></div>
          <h3 className="text-sm font-semibold">Issues</h3>
          <ul className="mt-2 list-disc pl-5 text-sm text-muted-foreground">{latest.issues.length ? latest.issues.map((issue) => <li key={issue}>{issue}</li>) : <li>No issues found.</li>}</ul>
          <h3 className="mt-4 text-sm font-semibold">Required changes</h3>
          <ul className="mt-2 list-disc pl-5 text-sm text-muted-foreground">{latest.required_changes.length ? latest.required_changes.map((item) => <li key={item}>{item}</li>) : <li>No required changes.</li>}</ul>
        </>
      ) : <p className="text-sm text-muted-foreground">Policy check pending.</p>}
    </Card>
  );
}

function ArtifactsPanel({ artifacts }: { artifacts: Artifact[] }) {
  return (
    <Table>
      <thead><tr><Th>Name</Th><Th>Kind</Th><Th>Path</Th><Th>Created</Th></tr></thead>
      <tbody>{artifacts.map((item) => <tr key={item.id}><Td>{item.name}</Td><Td>{item.kind}</Td><Td className="max-w-xl truncate">{item.path}</Td><Td>{formatDate(item.created_at)}</Td></tr>)}</tbody>
    </Table>
  );
}

function SettingsPanel({ project }: { project: Project }) {
  return <Card><h2 className="mb-2 text-base font-semibold">Settings</h2><p className="text-sm text-muted-foreground">Production publish is intentionally blocked in MVP. Human approval is required before any release automation is added.</p><pre className="mt-4 rounded-md bg-muted p-3 text-xs">{JSON.stringify(project, null, 2)}</pre></Card>;
}
