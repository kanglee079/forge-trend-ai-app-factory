"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Activity, AlertTriangle, CheckCircle2, KeyRound, Loader2, Pause, Play, RefreshCw, Server, Smartphone, Square } from "lucide-react";
import { AgentEvent, api, ApiError, ApiKey, Artifact, DoctorResponse, FactoryState, Project, Worker } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Badge, Button, Card, EmptyState, Notice, PageHeader, Progress, Skeleton, StatusBadge } from "@/components/ui";

type OverviewState = {
  health: { status: string; service: string };
  doctor: DoctorResponse | null;
  keys: ApiKey[];
  workers: Worker[];
  projects: Project[];
  events: AgentEvent[];
  artifacts: Artifact[];
  factory: FactoryState | null;
};

export default function OverviewPage() {
  const [data, setData] = useState<OverviewState | null>(null);
  const [loading, setLoading] = useState(true);
  const [modeSaving, setModeSaving] = useState<FactoryState["mode"] | null>(null);
  const [notice, setNotice] = useState<{ tone: "success" | "danger" | "warning"; message: string } | null>(null);

  async function load({ quiet = false } = {}) {
    setLoading(true);
    try {
      const [health, doctor, keys, workers, projects, events, factory] = await Promise.all([
        api.health().catch(() => ({ status: "offline", service: "forge-trend-api" })),
        api.doctor().catch(() => null),
        api.apiKeys().catch(() => []),
        api.workers().catch(() => []),
        api.projects().catch(() => []),
        api.allEvents({ limit: 80 }).catch(() => []),
        api.factoryState().catch(() => null)
      ]);
      const artifactGroups = await Promise.all(projects.slice(0, 8).map((project) => api.artifacts(project.id).catch(() => [])));
      setData({ health, doctor, keys, workers, projects, events, artifacts: artifactGroups.flat(), factory });
      if (!quiet) setNotice({ tone: "success", message: "Command center refreshed." });
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Could not load command center." });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load({ quiet: true }).catch(console.error);
  }, []);

  async function setFactoryMode(mode: FactoryState["mode"]) {
    setModeSaving(mode);
    try {
      const factory = await api.updateFactoryState(mode);
      setData((current) => current ? { ...current, factory } : current);
      setNotice({ tone: mode === "running" ? "success" : "warning", message: `Factory mode set to ${mode}. Workers will observe this before taking new jobs.` });
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Could not update factory mode." });
    } finally {
      setModeSaving(null);
    }
  }

  const readiness = useMemo(() => (data ? calculateReadiness(data) : { score: 0, items: [] }), [data]);
  const activeProjects = data?.projects.filter((project) => ["queued", "running", "stop_requested"].includes(project.status)).slice(0, 4) ?? [];
  const recentFailures = data?.events.filter((event) => event.level === "error" || event.level === "warning").slice(0, 5) ?? [];
  const latestArtifacts = [...(data?.artifacts ?? [])].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 5);
  const onlineWorkers = data?.workers.filter((worker) => worker.status === "online") ?? [];
  const readyWorkers = onlineWorkers.filter((worker) => worker.has_codex && worker.has_flutter);
  const activeKeys = data?.keys.filter((key) => key.status === "active") ?? [];

  if (!data && loading) {
    return <OverviewSkeleton />;
  }

  return (
    <>
      <PageHeader
        title="Command Center"
        description="Readiness, running jobs, recent failures, artifacts, and factory controls in one place."
        action={
          <Button type="button" variant="secondary" onClick={() => load()} disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw size={16} />}
            {loading ? "Refreshing..." : "Refresh"}
          </Button>
        }
      />
      {notice ? <Notice tone={notice.tone}>{notice.message}</Notice> : null}

      <div className="grid gap-5 xl:grid-cols-[1.25fr_0.75fr]">
        <Card>
          <div className="mb-5 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="text-base font-semibold">System Readiness</h2>
              <p className="text-sm text-muted-foreground">This score answers one question: can the factory build a Flutter app right now?</p>
            </div>
            <div className="text-3xl font-semibold">{readiness.score}%</div>
          </div>
          <Progress value={readiness.score} />
          <div className="mt-5 grid gap-3 md:grid-cols-2">
            {readiness.items.map((item) => (
              <Link key={item.label} href={item.href} className="rounded-md border border-border bg-background p-3 transition hover:bg-muted">
                <div className="flex items-center gap-2">
                  {item.complete ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <AlertTriangle className="h-4 w-4 text-amber-600" />}
                  <div className="font-medium">{item.label}</div>
                  <Badge tone={item.complete ? "success" : "warning"}>{item.complete ? "ready" : "action"}</Badge>
                </div>
                <div className="mt-1 text-xs text-muted-foreground">{item.detail}</div>
              </Link>
            ))}
          </div>
        </Card>

        <Card>
          <h2 className="mb-4 text-base font-semibold">Factory Controls</h2>
          <div className="mb-4 rounded-md border border-border bg-background p-3">
            <div className="text-sm text-muted-foreground">Mode</div>
            <div className="mt-1 text-xl font-semibold capitalize">{data?.factory?.mode ?? "unknown"}</div>
          </div>
          <div className="grid gap-2 sm:grid-cols-3 xl:grid-cols-1">
            <Button type="button" onClick={() => setFactoryMode("running")} disabled={Boolean(modeSaving)}>
              {modeSaving === "running" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play size={15} />}
              Start
            </Button>
            <Button type="button" variant="secondary" onClick={() => setFactoryMode("paused")} disabled={Boolean(modeSaving)}>
              {modeSaving === "paused" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Pause size={15} />}
              Pause
            </Button>
            <Button type="button" variant="danger" onClick={() => setFactoryMode("stopped")} disabled={Boolean(modeSaving)}>
              {modeSaving === "stopped" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Square size={15} />}
              Stop
            </Button>
          </div>
          <p className="mt-3 text-xs text-muted-foreground">Paused/stopped workers stop taking new jobs. Stop also cancels between agent steps.</p>
        </Card>
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <Metric icon={<Activity size={18} />} label="API" value={data?.health.status ?? "offline"} tone={data?.health.status === "ok" ? "success" : "danger"} />
        <Metric icon={<KeyRound size={18} />} label="Active Keys" value={String(activeKeys.length)} tone={activeKeys.length ? "success" : "warning"} />
        <Metric icon={<Server size={18} />} label="Ready Workers" value={`${readyWorkers.length}/${onlineWorkers.length}`} tone={readyWorkers.length ? "success" : "warning"} />
        <Metric icon={<Smartphone size={18} />} label="Projects" value={String(data?.projects.length ?? 0)} />
        <Metric icon={<AlertTriangle size={18} />} label="Recent Issues" value={String(recentFailures.length)} tone={recentFailures.length ? "warning" : "success"} />
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[1fr_1fr]">
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-base font-semibold">Active Runs</h2>
            <Link href="/projects" className="text-sm text-primary">Projects</Link>
          </div>
          <div className="space-y-3">
            {activeProjects.map((project) => (
              <Link key={project.id} href={`/projects/${project.id}`} className="block rounded-md border border-border bg-background p-3 hover:bg-muted">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="font-medium">{project.name}</div>
                    <div className="text-xs text-muted-foreground">{project.workspace_path ?? "workspace pending"}</div>
                  </div>
                  <StatusBadge status={project.status} />
                </div>
              </Link>
            ))}
            {!activeProjects.length ? <EmptyState title="No active runs" body="Create or open a project, then run the pipeline when a ready worker is online." href="/projects" /> : null}
          </div>
        </Card>

        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-base font-semibold">Recent Failures</h2>
            <Link href="/logs" className="text-sm text-primary">Logs</Link>
          </div>
          <div className="space-y-3">
            {recentFailures.map((event) => (
              <div key={event.id} className="rounded-md border border-border bg-background p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge>{event.step}</Badge>
                  <Badge tone={event.level === "error" ? "danger" : "warning"}>{event.level}</Badge>
                  <span className="text-xs text-muted-foreground">{formatDate(event.created_at)}</span>
                </div>
                <p className="mt-2 text-sm">{event.message}</p>
              </div>
            ))}
            {!recentFailures.length ? <p className="text-sm text-muted-foreground">No warning or error events yet.</p> : null}
          </div>
        </Card>
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[1fr_1fr]">
        <Card>
          <h2 className="mb-4 text-base font-semibold">Latest Artifacts</h2>
          <div className="space-y-3">
            {latestArtifacts.map((artifact) => (
              <div key={artifact.id} className="rounded-md border border-border bg-background p-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="font-medium">{artifact.name}</div>
                    <div className="max-w-lg truncate text-xs text-muted-foreground">{artifact.path}</div>
                  </div>
                  <Badge>{artifact.kind}</Badge>
                </div>
              </div>
            ))}
            {!latestArtifacts.length ? <p className="text-sm text-muted-foreground">No artifacts produced yet.</p> : null}
          </div>
        </Card>
        <Card>
          <h2 className="mb-4 text-base font-semibold">Cost / Budget</h2>
          <div className="rounded-md border border-border bg-background p-3">
            <div className="text-sm text-muted-foreground">Estimated spend</div>
            <div className="mt-1 text-2xl font-semibold">$0.00</div>
          </div>
          <p className="mt-3 text-sm text-muted-foreground">Provider cost telemetry is still a placeholder; budget warnings on API keys are ready for the next pass.</p>
        </Card>
      </div>
    </>
  );
}

function calculateReadiness(data: OverviewState) {
  const onlineWorkers = data.workers.filter((worker) => worker.status === "online");
  const readyWorkers = onlineWorkers.filter((worker) => worker.has_codex && worker.has_flutter);
  const activeKeys = data.keys.filter((key) => key.status === "active");
  const requiredDoctorPassed = data.doctor ? data.doctor.checks.filter((check) => check.required).every((check) => check.status === "passed") : data.health.status === "ok";
  const items = [
    { label: "API online", complete: data.health.status === "ok", detail: data.health.status === "ok" ? "FastAPI is responding." : "Start the API service.", href: "/doctor" },
    { label: "Core services", complete: requiredDoctorPassed, detail: data.doctor?.status ?? "Doctor unavailable", href: "/doctor" },
    { label: "Provider key", complete: activeKeys.length > 0, detail: `${activeKeys.length} active key(s)`, href: "/api-keys" },
    { label: "Pipeline worker", complete: readyWorkers.length > 0, detail: `${readyWorkers.length} ready / ${onlineWorkers.length} online`, href: "/workers" },
    { label: "Project exists", complete: data.projects.length > 0, detail: `${data.projects.length} project(s)`, href: "/projects" }
  ];
  return { score: Math.round((items.filter((item) => item.complete).length / items.length) * 100), items };
}

function Metric({ icon, label, value, tone = "neutral" }: { icon: React.ReactNode; label: string; value: string; tone?: "success" | "warning" | "danger" | "neutral" }) {
  return (
    <Card>
      <div className="flex items-center justify-between">
        <div className="text-muted-foreground">{icon}</div>
        <Badge tone={tone}>{label}</Badge>
      </div>
      <div className="mt-5 text-2xl font-semibold">{value}</div>
    </Card>
  );
}

function OverviewSkeleton() {
  return (
    <>
      <PageHeader title="Command Center" description="Loading factory readiness and recent run state." />
      <div className="grid gap-5 xl:grid-cols-[1.25fr_0.75fr]">
        <Card><Skeleton className="h-8 w-48" /><Skeleton className="mt-5 h-2 w-full" /><div className="mt-5 grid gap-3 md:grid-cols-2"><Skeleton className="h-20" /><Skeleton className="h-20" /><Skeleton className="h-20" /><Skeleton className="h-20" /></div></Card>
        <Card><Skeleton className="h-8 w-40" /><Skeleton className="mt-5 h-28" /></Card>
      </div>
    </>
  );
}
