"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Bot, CheckCircle2, FolderOpen, Loader2, PlusCircle, RefreshCw, Search, Settings2, Smartphone } from "lucide-react";
import { AgentEvent, api, ApiError, ApiKey, DoctorResponse, Project, Worker } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";
import { formatDate, isReadyWorker } from "@/lib/utils";
import { Badge, Button, Card, EmptyState, Notice, PageHeader, Skeleton, StatusBadge } from "@/components/ui";

type OverviewState = {
  health: { status: string; service: string };
  doctor: DoctorResponse | null;
  keys: ApiKey[];
  workers: Worker[];
  projects: Project[];
  events: AgentEvent[];
};

const modeStorageKey = "forge-overview-mode";

export default function OverviewPage() {
  const { t } = useLanguage();
  const [data, setData] = useState<OverviewState | null>(null);
  const [loading, setLoading] = useState(true);
  const [advanced, setAdvanced] = useState(false);
  const [notice, setNotice] = useState<{ tone: "success" | "danger"; message: string } | null>(null);

  useEffect(() => {
    setAdvanced(window.localStorage.getItem(modeStorageKey) === "advanced");
  }, []);

  function setMode(nextAdvanced: boolean) {
    setAdvanced(nextAdvanced);
    window.localStorage.setItem(modeStorageKey, nextAdvanced ? "advanced" : "simple");
  }

  async function load({ quiet = false } = {}) {
    setLoading(true);
    try {
      const [health, doctor, keys, workers, projects, events] = await Promise.all([
        api.health().catch(() => ({ status: "offline", service: "forge-trend-api" })),
        api.doctor().catch(() => null),
        api.apiKeys().catch(() => []),
        api.workers().catch(() => []),
        api.projects().catch(() => []),
        api.allEvents({ limit: 80 }).catch(() => [])
      ]);
      setData({ health, doctor, keys, workers, projects, events });
      if (!quiet) setNotice({ tone: "success", message: "Đã làm mới trạng thái." });
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Không tải được tổng quan." });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load({ quiet: true }).catch(console.error);
  }, []);

  const onlineWorkers = data?.workers.filter((worker) => worker.status === "online") ?? [];
  const readyWorkers = onlineWorkers.filter(isReadyWorker);
  const activeProjects = data?.projects.filter((project) => ["queued", "running", "stop_requested"].includes(project.status)).slice(0, 4) ?? [];
  const completedProjects = data?.projects.filter((project) => ["release_candidate", "NEEDS_HUMAN_REVIEW"].includes(project.status)).slice(0, 6) ?? [];
  const issues = data?.events.filter((event) => event.level === "error" || event.level === "warning").slice(0, 5) ?? [];
  const requiredDoctorPassed = data?.doctor ? data.doctor.checks.filter((check) => check.required).every((check) => check.status === "passed") : data?.health.status === "ok";
  const ready = Boolean(data?.health.status === "ok" && requiredDoctorPassed && readyWorkers.length);
  const statusItems = useMemo(
    () => [
      { label: "API", complete: data?.health.status === "ok", detail: data?.health.status === "ok" ? "API đang phản hồi." : "Cần khởi động API." },
      { label: "Worker", complete: readyWorkers.length > 0, detail: `${readyWorkers.length}/${onlineWorkers.length} worker sẵn sàng.` },
      { label: "Flutter", complete: readyWorkers.some((worker) => worker.has_flutter), detail: "Cần Flutter để build APK Android." },
      { label: "Codex", complete: !data?.doctor?.worker_enable_codex || readyWorkers.some((worker) => worker.has_codex), detail: data?.doctor?.worker_mode_label ?? "Đang kiểm tra mode." }
    ],
    [data?.doctor?.worker_enable_codex, data?.doctor?.worker_mode_label, data?.health.status, onlineWorkers.length, readyWorkers]
  );

  if (!data && loading) return <OverviewSkeleton />;

  return (
    <>
      <PageHeader
        title="ForgeTrend"
        description="Tạo app Flutter từ ý tưởng, xem tiến trình dễ hiểu, rồi mở APK/source/report để con người review."
        action={
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="secondary" onClick={() => load()} disabled={loading}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw size={16} />}
              {t("refresh")}
            </Button>
            <Button type="button" variant={advanced ? "secondary" : "primary"} onClick={() => setMode(false)}>
              {t("simpleMode")}
            </Button>
            <Button type="button" variant={advanced ? "primary" : "secondary"} onClick={() => setMode(true)}>
              <Settings2 size={16} />
              {t("advancedMode")}
            </Button>
          </div>
        }
      />
      {notice ? <Notice tone={notice.tone}>{notice.message}</Notice> : null}

      <Card className="mb-5">
        <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold">{t("whatToday")}</h2>
            <p className="text-sm text-muted-foreground">Chọn một việc chính. Các khái niệm kỹ thuật nằm trong chế độ nâng cao.</p>
          </div>
          <Badge tone={ready ? "success" : "warning"}>{ready ? t("readyToCreate") : t("needsSetup")}</Badge>
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          <ActionTile href="/create" icon={<PlusCircle size={20} />} title={t("createFromIdea")} body={t("createFromIdeaHelp")} primary />
          <ActionTile href="/create?mode=auto_trend" icon={<Search size={20} />} title={t("autoTrendCreate")} body={t("autoTrendCreateHelp")} />
          <ActionTile href="/projects" icon={<FolderOpen size={20} />} title={t("openRecentProject")} body={t("openRecentProjectHelp")} />
        </div>
      </Card>

      <div className="grid gap-5 xl:grid-cols-[0.85fr_1.15fr]">
        <Card>
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 className="text-base font-semibold">{t("systemReady")}</h2>
            <Badge tone={ready ? "success" : "warning"}>{ready ? "OK" : "Action"}</Badge>
          </div>
          <div className="space-y-3">
            {statusItems.map((item) => (
              <div key={item.label} className="rounded-md border border-border bg-background p-3">
                <div className="flex items-center gap-2">
                  {item.complete ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <AlertTriangle className="h-4 w-4 text-amber-600" />}
                  <div className="font-medium">{item.label}</div>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{item.detail}</p>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 className="text-base font-semibold">{t("runningProjects")}</h2>
            <Link className="text-sm text-primary" href="/projects">Tất cả dự án</Link>
          </div>
          <ProjectList projects={activeProjects} empty={t("noRunningProjects")} />
        </Card>
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[1fr_1fr]">
        <Card>
          <h2 className="mb-4 text-base font-semibold">{t("appCandidates")}</h2>
          <ProjectList projects={completedProjects} empty="Chưa có app ứng viên." />
        </Card>
        <Card>
          <h2 className="mb-4 text-base font-semibold">{t("issuesToFix")}</h2>
          <div className="space-y-3">
            {issues.map((event) => (
              <Link key={event.id} href={event.project_id ? `/projects/${event.project_id}` : "/logs"} className="block rounded-md border border-border bg-background p-3 hover:bg-muted">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={event.level === "error" ? "danger" : "warning"}>{event.level}</Badge>
                  <span className="text-xs text-muted-foreground">{event.step} · {formatDate(event.created_at)}</span>
                </div>
                <p className="mt-2 text-sm">{event.message}</p>
              </Link>
            ))}
            {!issues.length ? <p className="text-sm text-muted-foreground">{t("noIssues")}</p> : null}
          </div>
        </Card>
      </div>

      {advanced ? (
        <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <Metric icon={<Bot size={18} />} label="Factory mode" value={data?.doctor?.worker_mode_label ?? "unknown"} />
          <Metric icon={<Smartphone size={18} />} label="Projects" value={String(data?.projects.length ?? 0)} />
          <Metric icon={<CheckCircle2 size={18} />} label="Active keys" value={String(data?.keys.filter((key) => key.status === "active").length ?? 0)} />
          <Metric icon={<AlertTriangle size={18} />} label="Recent issues" value={String(issues.length)} />
        </div>
      ) : null}
    </>
  );
}

function ActionTile({ href, icon, title, body, primary = false }: { href: string; icon: React.ReactNode; title: string; body: string; primary?: boolean }) {
  return (
    <Link className="rounded-md border border-border bg-background p-4 transition hover:bg-muted" href={href}>
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-md bg-primary text-primary-foreground">{icon}</div>
      <div className="font-semibold">{title}</div>
      <p className="mt-1 text-sm text-muted-foreground">{body}</p>
      <div className="mt-4">
        <Badge tone={primary ? "success" : "neutral"}>{primary ? "Khuyến nghị" : "Mở"}</Badge>
      </div>
    </Link>
  );
}

function ProjectList({ projects, empty }: { projects: Project[]; empty: string }) {
  return (
    <div className="space-y-3">
      {projects.map((project) => (
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
      {!projects.length ? <EmptyState title={empty} body="Khi có app đang chạy hoặc đã tạo, chúng sẽ xuất hiện ở đây." href="/create" /> : null}
    </div>
  );
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <Card>
      <div className="text-muted-foreground">{icon}</div>
      <div className="mt-4 text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="mt-1 text-xl font-semibold">{value}</div>
    </Card>
  );
}

function OverviewSkeleton() {
  return (
    <>
      <PageHeader title="ForgeTrend" description="Đang tải trạng thái xưởng tạo app." />
      <div className="grid gap-5 xl:grid-cols-[0.85fr_1.15fr]">
        <Card><Skeleton className="h-8 w-48" /><Skeleton className="mt-5 h-28" /></Card>
        <Card><Skeleton className="h-8 w-40" /><Skeleton className="mt-5 h-28" /></Card>
      </div>
    </>
  );
}
