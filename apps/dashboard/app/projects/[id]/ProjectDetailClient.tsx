"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Loader2, Play, RefreshCw, RotateCcw, Square } from "lucide-react";
import { AgentEvent, ApiError, api, Artifact, FactoryBriefDetail, PolicyResult, Project, ProjectTask, QAResult, Worker } from "@/lib/api";
import { formatDate, isReadyWorker } from "@/lib/utils";
import { Badge, Button, Card, Notice, StatusBadge, Table, Td, Th } from "@/components/ui";
import { useFeedback } from "@/components/feedback";
import { CopyButton, LogViewer } from "@/components/log-viewer";
import { derivePipelineSteps, getCurrentStep, getLatestFailure, getPipelineProgress, PipelineStepper } from "@/components/pipeline";

const tabs = ["Overview", "Research", "Tasks", "Code Agent", "PRD", "Agent Timeline", "Logs", "QA", "Policy", "Artifacts", "Settings"] as const;
type Tab = (typeof tabs)[number];

export function ProjectDetailClient({ initialProject }: { initialProject: Project }) {
  const feedback = useFeedback();
  const [project, setProject] = useState(initialProject);
  const [active, setActive] = useState<Tab>("Overview");
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [qa, setQa] = useState<QAResult[]>([]);
  const [policy, setPolicy] = useState<PolicyResult[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [tasks, setTasks] = useState<ProjectTask[]>([]);
  const [factoryBrief, setFactoryBrief] = useState<FactoryBriefDetail | null>(null);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [runningTaskId, setRunningTaskId] = useState<string | null>(null);
  const [stopping, setStopping] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [notice, setNotice] = useState<{ tone: "success" | "danger" | "warning"; message: string } | null>(null);

  async function load() {
    setLoading(true);
    try {
      const [projectItem, eventItems, qaItems, policyItems, artifactItems, taskItems, workerItems] = await Promise.all([
        api.project(project.id),
        api.events(project.id),
        api.qa(project.id),
        api.policy(project.id),
        api.artifacts(project.id),
        api.tasks(project.id),
        api.workers()
      ]);
      setProject(projectItem);
      setEvents(eventItems);
      setQa(qaItems);
      setPolicy(policyItems);
      setArtifacts(artifactItems);
      setTasks(taskItems);
      setWorkers(workerItems);
      const briefId = taskItems
        .map((task) => task.input_json.factory_brief_id)
        .find((value): value is string => typeof value === "string");
      setFactoryBrief(briefId ? await api.factoryBrief(briefId).catch(() => null) : null);
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
    const activeLocalWorker = workers.find(isReadyWorker);
    if (!activeLocalWorker) {
      setNotice({ tone: "warning", message: "No ready local worker is available. Deterministic workers need Flutter; Codex workers need Flutter plus codex login." });
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

  async function runTask(task: ProjectTask) {
    if (runningTaskId) return;
    setRunningTaskId(task.id);
    try {
      const response = await api.runTask(project.id, task.id);
      feedback.notify({ tone: "success", message: `${task.title} queued on ${response.queue}.` });
      await load();
    } catch (error) {
      feedback.notify({ tone: "danger", message: error instanceof ApiError ? error.detail : "Could not queue task." });
    } finally {
      setRunningTaskId(null);
    }
  }

  async function createInternalTestPackage() {
    try {
      const artifact = await api.createInternalTestPackage(project.id);
      feedback.notify({ tone: "success", message: `Gói test nội bộ đã tạo: ${artifact.path}` });
      await load();
    } catch (error) {
      feedback.notify({ tone: "danger", message: error instanceof ApiError ? error.detail : "Không thể tạo gói test nội bộ." });
    }
  }

  const prd = artifacts.find((item) => item.name === "prd.md");
  const hasReadyWorker = workers.some(isReadyWorker);
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
      {factoryBrief ? (
        <Notice tone="neutral">
          Created from factory brief "{factoryBrief.title}". {factoryBrief.selected_project_id ? "Research, candidate scoring, and task plan are linked below." : "Research is linked below."}
        </Notice>
      ) : null}
      {!hasReadyWorker ? (
        <Notice tone="warning">Local worker is offline or missing required tools. Deterministic mode requires Flutter. Codex mode also requires Codex CLI and codex login.</Notice>
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
      {active === "Research" ? <ResearchPanel brief={factoryBrief} /> : null}
      {active === "Tasks" ? <TasksPanel tasks={tasks} runningTaskId={runningTaskId} onRun={runTask} /> : null}
      {active === "Code Agent" ? <CodeAgentPanel events={events} tasks={tasks} artifacts={artifacts} /> : null}
      {active === "PRD" ? <PrdPanel prdPath={prd?.path} /> : null}
      {active === "Agent Timeline" ? <Timeline events={events} /> : null}
      {active === "Logs" ? <LogViewer events={events} onClear={clearLogs} /> : null}
      {active === "QA" ? <QaPanel qa={qa} /> : null}
      {active === "Policy" ? <PolicyPanel policy={policy} /> : null}
      {active === "Artifacts" ? <ArtifactsPanel artifacts={artifacts} onCreateInternalTestPackage={createInternalTestPackage} /> : null}
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
  const apk = artifacts.find((item) => item.kind === "build" || item.name.endsWith(".apk"));
  const source = artifacts.find((item) => item.kind === "source");
  const quality = artifacts.find((item) => item.name === "product_score_report.json" || item.name === "quality_gate_report.json");
  const viReport = artifacts.find((item) => item.name.endsWith(".vi.md"));
  const needsHumanReview = project.status === "NEEDS_HUMAN_REVIEW";
  return (
    <div className="space-y-4">
      <Card>
        <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-base font-semibold">Kết quả tạo app</h2>
            <p className="text-sm text-muted-foreground">Tóm tắt đầu ra để người dùng không phải đào trong log thô.</p>
          </div>
          <StatusBadge status={project.status} />
        </div>
        <div className="grid gap-2 md:grid-cols-3">
          <SummaryCheck label="App name" value={project.name} />
          <SummaryCheck label="APK generated?" value={apk ? "yes" : "no"} tone={apk ? "success" : "warning"} />
          <SummaryCheck label="Quality score" value={String(quality?.metadata_json?.score ?? "-")} tone={Number(quality?.metadata_json?.score ?? 0) >= 75 ? "success" : "warning"} />
          <SummaryCheck label="Store readiness" value={artifacts.some((item) => item.name.includes("store_readiness")) ? "report ready" : "pending"} />
          <SummaryCheck label="Vietnamese support" value={viReport ? "yes" : "pending"} tone={viReport ? "success" : "warning"} />
          <SummaryCheck label="Needs human review?" value={needsHumanReview ? "yes" : "still required before release"} tone={needsHumanReview ? "warning" : "neutral"} />
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {source ? <CopyButton value={source.path} label="Copy source path" /> : null}
          {apk ? <CopyButton value={apk.path} label="Copy APK path" /> : null}
          <Link className="inline-flex min-h-10 items-center rounded-md border border-border bg-card px-4 py-2 text-sm font-medium hover:bg-muted" href="/artifacts">Open artifacts</Link>
        </div>
      </Card>
      <PipelineStepper
        steps={steps}
        latestFailure={latestFailure}
        onCopyFailure={latestFailure?.detail ? () => navigator.clipboard.writeText(latestFailure.detail) : undefined}
      />
      <LiveProgressExplanation steps={steps} latestFailure={latestFailure} events={events} artifacts={artifacts} />
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
      <ReleaseReadinessPanel project={project} qa={qa} policy={policy} artifacts={artifacts} />
    </div>
  );
}

function LiveProgressExplanation({
  steps,
  latestFailure,
  events,
  artifacts,
}: {
  steps: ReturnType<typeof derivePipelineSteps>;
  latestFailure: ReturnType<typeof getLatestFailure>;
  events: AgentEvent[];
  artifacts: Artifact[];
}) {
  const current = getCurrentStep(steps);
  const copy = currentStepCopy(current?.id ?? "waiting", Boolean(latestFailure));
  const latestArtifact = artifacts[0];
  const logText = latestFailure?.detail || events.slice(-20).map((event) => `[${event.created_at}] ${event.step}: ${event.message}${event.stderr ? `\n${event.stderr}` : ""}`).join("\n");
  return (
    <Card>
      <div className="grid gap-4 lg:grid-cols-4">
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Bước hiện tại</div>
          <div className="mt-1 font-semibold">{current?.label ?? "Đang chờ worker"}</div>
        </div>
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">ForgeTrend đang làm gì?</div>
          <p className="mt-1 text-sm text-muted-foreground">{copy.doing}</p>
        </div>
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Vì sao cần bước này?</div>
          <p className="mt-1 text-sm text-muted-foreground">{copy.why}</p>
        </div>
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Nếu lỗi thì sao?</div>
          <p className="mt-1 text-sm text-muted-foreground">{copy.failure}</p>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {logText ? <CopyButton value={logText} label="Copy log" /> : null}
        {latestArtifact ? <CopyButton value={latestArtifact.path} label="Copy artifact path" /> : null}
        <Link className="inline-flex min-h-10 items-center rounded-md border border-border bg-card px-4 py-2 text-sm font-medium hover:bg-muted" href="/artifacts">Mở artifact</Link>
      </div>
    </Card>
  );
}

function currentStepCopy(stepId: string, hasFailure: boolean) {
  if (hasFailure) {
    return {
      doing: "Hệ thống đã thấy lỗi gần nhất và giữ lại log để bạn copy hoặc để Autopilot dùng trong vòng sửa tiếp theo.",
      why: "Log lỗi là bằng chứng để Code Agent sửa đúng lỗi thật thay vì đoán.",
      failure: "Nếu còn trong giới hạn retry, Code Agent sẽ sửa. Nếu vượt giới hạn hoặc rủi ro policy cao, dự án chuyển sang NEEDS_HUMAN_REVIEW.",
    };
  }
  const copy: Record<string, { doing: string; why: string; failure: string }> = {
    brief: {
      doing: "Đang đọc brief, config snapshot, run profile và skill được chọn.",
      why: "Bước này khóa cấu hình runtime để worker dùng đúng provider, model, plugin và learning rules.",
      failure: "Nếu thiếu cấu hình quan trọng, hệ thống ghi event rõ ràng để bạn sửa ở Config Studio.",
    },
    research: {
      doing: "Đang tạo finding/candidate từ deterministic provider hoặc web allowlist.",
      why: "Research giúp chọn hướng app có vấn đề người dùng rõ hơn thay vì tạo scaffold chung chung.",
      failure: "Nếu web không sẵn sàng, ForgeTrend fallback deterministic thay vì dừng toàn bộ luồng.",
    },
    prd: {
      doing: "Đang biến candidate thành PRD và phạm vi MVP cụ thể.",
      why: "PRD là hợp đồng sản phẩm cho code agent, QA và quality gate.",
      failure: "Nếu PRD quá generic, learning rule sẽ ưu tiên blueprint sâu hơn ở lần sau.",
    },
    ux: {
      doing: "Đang tạo screen flow, trạng thái trống/lỗi/thành công và hướng thiết kế.",
      why: "UX flow giúp app đầu ra có hành trình thật, không chỉ vài màn hình rời rạc.",
      failure: "Nếu thiếu flow, quality gate sẽ yêu cầu làm sâu core feature.",
    },
    code: {
      doing: "Đang tạo source Flutter, blueprint, store assets và có thể gọi Codex nếu đã cấu hình.",
      why: "Đây là bước biến brief thành artifact có thể build/test trên máy local.",
      failure: "Nếu Codex lỗi hoặc chưa auth, worker giữ scaffold deterministic và tiếp tục QA khi có thể.",
    },
    qa: {
      doing: "Đang chạy Flutter pub get, analyze, test và debug APK.",
      why: "QA chứng minh app không chỉ được tạo file mà còn build/test được.",
      failure: "Lỗi QA sẽ được đưa lại cho Code Agent để sửa trong số vòng retry cho phép.",
    },
    policy: {
      doing: "Đang kiểm tra tên app, permission, privacy, billing disclosure và rủi ro copycat.",
      why: "Policy gate bảo vệ tài khoản store và giữ production publish trong vòng review của con người.",
      failure: "Lỗi policy nghiêm trọng sẽ chặn release candidate và yêu cầu con người review.",
    },
    quality: {
      doing: "Đang chấm độ cụ thể của sản phẩm, localization, feature depth và store readiness.",
      why: "Quality gate chặn app mỏng/generic trước khi bạn mất thời gian test nội bộ.",
      failure: "Nếu app còn yếu hoặc generic, Autopilot thử làm sâu luồng chính trước khi chặn.",
    },
    artifacts: {
      doing: "Đang ghi APK/source/report/store assets/gói test nội bộ để bạn review.",
      why: "Artifact là gói bàn giao để tester hoặc người duyệt có đủ ngữ cảnh.",
      failure: "Nếu thiếu artifact quan trọng, dự án chưa được xem là release candidate.",
    },
  };
  return copy[stepId] ?? {
    doing: "Đang chờ bước tiếp theo từ worker hoặc queue.",
    why: "Trạng thái này giúp bạn biết nên chờ worker hay kiểm tra cấu hình.",
    failure: "Nếu không có tiến triển, kiểm tra worker, doctor và log pipeline.",
  };
}

function SummaryCheck({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "success" | "warning" | "danger" | "neutral" }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-background px-3 py-2 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <Badge tone={tone}>{value}</Badge>
    </div>
  );
}

function PrdPanel({ prdPath }: { prdPath?: string }) {
  return <Card><h2 className="mb-2 text-base font-semibold">PRD</h2><p className="text-sm text-muted-foreground">{prdPath ? `Generated at ${prdPath}` : "PRD has not been generated yet."}</p></Card>;
}

function ResearchPanel({ brief }: { brief: FactoryBriefDetail | null }) {
  if (!brief) {
    return <Card><h2 className="mb-2 text-base font-semibold">Research</h2><p className="text-sm text-muted-foreground">This project was not created from a factory brief, or linked research is unavailable.</p></Card>;
  }
  const selectedCandidate = brief.candidates.find((candidate) => candidate.status === "selected");
  return (
    <div className="space-y-4">
      <Card>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <StatusBadge status={brief.status} />
          <Badge>{brief.mode}</Badge>
          {selectedCandidate ? <Badge tone="success">selected {selectedCandidate.opportunity_score}/100</Badge> : null}
        </div>
        <h2 className="text-base font-semibold">{brief.title}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{brief.raw_prompt}</p>
      </Card>
      <div className="grid gap-4 xl:grid-cols-[0.85fr_1.15fr]">
        <Card>
          <h3 className="mb-3 text-sm font-semibold">Findings</h3>
          <div className="space-y-3">
            {brief.findings.map((finding) => (
              <div key={finding.id} className="rounded-md border border-border bg-background p-3">
                <div className="mb-2 flex flex-wrap items-center gap-2"><Badge>{finding.source}</Badge><Badge>{finding.confidence_score}/100</Badge></div>
                <div className="font-medium">{finding.title}</div>
                <p className="mt-1 text-sm text-muted-foreground">{finding.summary}</p>
              </div>
            ))}
            {!brief.findings.length ? <p className="text-sm text-muted-foreground">No research findings yet.</p> : null}
          </div>
        </Card>
        <Card>
          <h3 className="mb-3 text-sm font-semibold">Candidates</h3>
          <div className="space-y-3">
            {brief.candidates.map((candidate) => (
              <div key={candidate.id} className="rounded-md border border-border bg-background p-3">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <Badge tone={candidate.status === "selected" ? "success" : "neutral"}>{candidate.status}</Badge>
                  <Badge tone={candidate.opportunity_score >= 75 ? "success" : "warning"}>{candidate.opportunity_score}/100</Badge>
                </div>
                <div className="font-medium">{candidate.title}</div>
                <p className="mt-1 text-sm text-muted-foreground">{candidate.description}</p>
              </div>
            ))}
            {!brief.candidates.length ? <p className="text-sm text-muted-foreground">No candidates yet.</p> : null}
          </div>
        </Card>
      </div>
    </div>
  );
}

function TasksPanel({ tasks, runningTaskId, onRun }: { tasks: ProjectTask[]; runningTaskId: string | null; onRun: (task: ProjectTask) => void }) {
  return (
    <Table>
      <thead><tr><Th>Task</Th><Th>Agent</Th><Th>Status</Th><Th>Commit</Th><Th>Updated</Th><Th>Action</Th></tr></thead>
      <tbody>
        {tasks.map((task) => (
          <tr key={task.id}>
            <Td><div className="font-medium">{task.title}</div><div className="max-w-lg text-xs text-muted-foreground">{task.description}</div>{task.error_message ? <div className="mt-2 text-xs text-red-700">{task.error_message}</div> : null}</Td>
            <Td><Badge>{task.agent_name}</Badge></Td>
            <Td><StatusBadge status={task.status} /></Td>
            <Td>{task.commit_sha ?? "-"}</Td>
            <Td>{formatDate(task.updated_at)}</Td>
            <Td>
              <Button type="button" variant="secondary" onClick={() => onRun(task)} disabled={Boolean(runningTaskId)}>
                {runningTaskId === task.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play size={15} />}
                Run
              </Button>
            </Td>
          </tr>
        ))}
        {!tasks.length ? <tr><Td className="text-muted-foreground" colSpan={6}>No project tasks yet. Factory-created projects generate a task plan automatically.</Td></tr> : null}
      </tbody>
    </Table>
  );
}

function CodeAgentPanel({ events, tasks, artifacts }: { events: AgentEvent[]; tasks: ProjectTask[]; artifacts: Artifact[] }) {
  const codeEvents = events.filter((event) => event.step === "code_agent");
  const codeTask = tasks.find((task) => task.agent_name === "code_agent");
  const sourceArtifacts = artifacts.filter((artifact) => artifact.kind === "source");
  return (
    <div className="space-y-4">
      <Card>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <Badge>code_agent</Badge>
          {codeTask ? <StatusBadge status={codeTask.status} /> : null}
          {codeTask?.commit_sha ? <Badge>{codeTask.commit_sha}</Badge> : null}
        </div>
        <h2 className="text-base font-semibold">Code Agent State</h2>
        <p className="mt-1 text-sm text-muted-foreground">{codeTask?.description ?? "The code agent copies the Flutter template, customizes app content, optionally runs Codex CLI, and records source artifacts."}</p>
      </Card>
      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <h3 className="mb-3 text-sm font-semibold">Source Artifacts</h3>
          <div className="space-y-2">
            {sourceArtifacts.map((artifact) => (
              <div key={artifact.id} className="rounded-md border border-border bg-background p-3">
                <div className="font-medium">{artifact.name}</div>
                <div className="max-w-xl truncate text-xs text-muted-foreground">{artifact.path}</div>
              </div>
            ))}
            {!sourceArtifacts.length ? <p className="text-sm text-muted-foreground">No source artifacts yet.</p> : null}
          </div>
        </Card>
        <Card>
          <h3 className="mb-3 text-sm font-semibold">Recent Code Events</h3>
          <div className="space-y-3">
            {codeEvents.map((event) => (
              <div key={event.id} className="rounded-md border border-border bg-background p-3">
                <div className="mb-1 flex flex-wrap items-center gap-2"><Badge tone={event.level === "warning" ? "warning" : event.level === "error" ? "danger" : "neutral"}>{event.level}</Badge><span className="text-xs text-muted-foreground">{formatDate(event.created_at)}</span></div>
                <div className="text-sm">{event.message}</div>
              </div>
            ))}
            {!codeEvents.length ? <p className="text-sm text-muted-foreground">No code agent events yet.</p> : null}
          </div>
        </Card>
      </div>
    </div>
  );
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

function ArtifactsPanel({ artifacts, onCreateInternalTestPackage }: { artifacts: Artifact[]; onCreateInternalTestPackage: () => void }) {
  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-base font-semibold">Gói test nội bộ</h2>
            <p className="text-sm text-muted-foreground">Gom APK, hướng dẫn tester, store listing draft, privacy checklist và blockers vào một folder local. Không upload store.</p>
          </div>
          <Button type="button" onClick={onCreateInternalTestPackage}>Tạo gói test nội bộ</Button>
        </div>
      </Card>
      <Table>
        <thead><tr><Th>Name</Th><Th>Kind</Th><Th>Path</Th><Th>Created</Th><Th>Action</Th></tr></thead>
        <tbody>{artifacts.map((item) => <tr key={item.id}><Td>{item.name}</Td><Td>{item.kind}</Td><Td className="max-w-xl truncate">{item.path}</Td><Td>{formatDate(item.created_at)}</Td><Td><CopyButton value={item.path} label="Copy path" /></Td></tr>)}</tbody>
      </Table>
    </div>
  );
}

function ReleaseReadinessPanel({ project, qa, policy, artifacts }: { project: Project; qa: QAResult[]; policy: PolicyResult[]; artifacts: Artifact[] }) {
  const latestPolicy = policy[0];
  const checks = [
    { label: "QA passed", complete: qa.some((item) => item.status === "passed" && item.exit_code === 0) && !qa.some((item) => item.status === "failed" || item.exit_code !== 0) },
    { label: "Policy passed", complete: Boolean(latestPolicy?.passed) },
    { label: "PRD generated", complete: artifacts.some((item) => item.name === "prd.md") },
    { label: "Design docs generated", complete: artifacts.some((item) => item.name === "design_system.md" || item.name === "screen_flow.md") },
    { label: "APK/build artifact exists", complete: artifacts.some((item) => item.kind === "build" || item.name.endsWith(".apk")) },
    { label: "Human approval still required", complete: project.status === "release_candidate" || project.status === "NEEDS_HUMAN_REVIEW" },
  ];
  const readyCount = checks.filter((check) => check.complete).length;
  return (
    <Card>
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold">Release Readiness Gate</h2>
          <p className="text-sm text-muted-foreground">Release automation remains blocked until QA, policy, artifacts, and human approval are all satisfied.</p>
        </div>
        <Badge tone={readyCount === checks.length ? "success" : "warning"}>{readyCount}/{checks.length}</Badge>
      </div>
      <div className="grid gap-2 md:grid-cols-2">
        {checks.map((check) => (
          <div key={check.label} className="flex items-center justify-between gap-3 rounded-md border border-border bg-background px-3 py-2 text-sm">
            <span>{check.label}</span>
            <Badge tone={check.complete ? "success" : "warning"}>{check.complete ? "ready" : "blocked"}</Badge>
          </div>
        ))}
      </div>
    </Card>
  );
}

function SettingsPanel({ project }: { project: Project }) {
  return <Card><h2 className="mb-2 text-base font-semibold">Settings</h2><p className="text-sm text-muted-foreground">Production publish is intentionally blocked in MVP. Human approval is required before any release automation is added.</p><pre className="mt-4 rounded-md bg-muted p-3 text-xs">{JSON.stringify(project, null, 2)}</pre></Card>;
}
