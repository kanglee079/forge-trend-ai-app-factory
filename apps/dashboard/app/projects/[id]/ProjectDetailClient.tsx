"use client";

import { useEffect, useState } from "react";
import { Loader2, Play, RefreshCw } from "lucide-react";
import { AgentEvent, ApiError, api, Artifact, PolicyResult, Project, QAResult, Worker } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Badge, Button, Card, Notice, StatusBadge, Table, Td, Th } from "@/components/ui";

const tabs = ["Overview", "PRD", "Agent Timeline", "Logs", "QA", "Policy", "Artifacts", "Settings"] as const;
type Tab = (typeof tabs)[number];

export function ProjectDetailClient({ initialProject }: { initialProject: Project }) {
  const [project, setProject] = useState(initialProject);
  const [active, setActive] = useState<Tab>("Overview");
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [qa, setQa] = useState<QAResult[]>([]);
  const [policy, setPolicy] = useState<PolicyResult[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
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
    setRunning(true);
    setNotice(null);
    try {
      const response = await api.runPipeline(project.id);
      setProject((current) => ({ ...current, status: response.status }));
      setNotice({ tone: "success", message: `Pipeline queued on ${response.queue}. This page refreshes every 5 seconds while the worker reports events.` });
      await load();
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Could not queue pipeline." });
    } finally {
      setRunning(false);
    }
  }

  const prd = artifacts.find((item) => item.name === "prd.md");
  const hasReadyWorker = workers.some((worker) => worker.status === "online" && worker.has_codex && worker.has_flutter);

  return (
    <>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="mb-2"><StatusBadge status={project.status} /></div>
          <h1 className="text-2xl font-semibold">{project.name}</h1>
          <p className="text-sm text-muted-foreground">{project.slug} · {project.workspace_path ?? "workspace pending"}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => load()} disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw size={16} />}
            {loading ? "Refreshing..." : "Refresh"}
          </Button>
          <Button onClick={() => run()} disabled={running}>
            {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play size={16} />}
            {running ? "Queueing..." : "Run pipeline"}
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
      {active === "Overview" ? <Overview project={project} events={events} qa={qa} policy={policy} artifacts={artifacts} /> : null}
      {active === "PRD" ? <PrdPanel prdPath={prd?.path} /> : null}
      {active === "Agent Timeline" ? <Timeline events={events} /> : null}
      {active === "Logs" ? <Logs events={events} /> : null}
      {active === "QA" ? <QaPanel qa={qa} /> : null}
      {active === "Policy" ? <PolicyPanel policy={policy} /> : null}
      {active === "Artifacts" ? <ArtifactsPanel artifacts={artifacts} /> : null}
      {active === "Settings" ? <SettingsPanel project={project} /> : null}
    </>
  );
}

function Overview({ project, events, qa, policy, artifacts }: { project: Project; events: AgentEvent[]; qa: QAResult[]; policy: PolicyResult[]; artifacts: Artifact[] }) {
  const latestPolicy = policy[0];
  return (
    <div className="grid gap-4 md:grid-cols-4">
      <Card><div className="text-sm text-muted-foreground">Status</div><div className="mt-2"><StatusBadge status={project.status} /></div></Card>
      <Card><div className="text-sm text-muted-foreground">Events</div><div className="mt-2 text-2xl font-semibold">{events.length}</div></Card>
      <Card><div className="text-sm text-muted-foreground">QA Commands</div><div className="mt-2 text-2xl font-semibold">{qa.length}</div></Card>
      <Card><div className="text-sm text-muted-foreground">Policy</div><div className="mt-2">{latestPolicy ? <Badge tone={latestPolicy.passed ? "success" : "danger"}>{latestPolicy.risk}</Badge> : "Pending"}</div></Card>
      <Card className="md:col-span-4">
        <h2 className="mb-3 text-base font-semibold">Artifacts</h2>
        <div className="flex flex-wrap gap-2">{artifacts.map((item) => <Badge key={item.id}>{item.name}</Badge>)}</div>
      </Card>
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

function Logs({ events }: { events: AgentEvent[] }) {
  return (
    <div className="space-y-4">
      {events.filter((event) => event.stdout || event.stderr).map((event) => (
        <Card key={event.id}>
          <div className="mb-2 flex items-center gap-2"><Badge>{event.step}</Badge><span className="text-xs text-muted-foreground">{formatDate(event.created_at)}</span></div>
          {event.stdout ? <pre className="max-h-80 overflow-auto rounded-md bg-slate-950 p-3 text-xs text-slate-100">{event.stdout}</pre> : null}
          {event.stderr ? <pre className="mt-2 max-h-80 overflow-auto rounded-md bg-red-950 p-3 text-xs text-red-100">{event.stderr}</pre> : null}
        </Card>
      ))}
    </div>
  );
}

function QaPanel({ qa }: { qa: QAResult[] }) {
  return (
    <Table>
      <thead><tr><Th>Command</Th><Th>Status</Th><Th>Exit</Th><Th>Created</Th></tr></thead>
      <tbody>{qa.map((item) => <tr key={item.id}><Td>{item.command}</Td><Td><StatusBadge status={item.status} /></Td><Td>{item.exit_code}</Td><Td>{formatDate(item.created_at)}</Td></tr>)}</tbody>
    </Table>
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
