import Link from "next/link";
import { Activity, CheckCircle2, KeyRound, Lightbulb, Server, Smartphone } from "lucide-react";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Badge, Card, PageHeader, StatusBadge } from "@/components/ui";

export default async function OverviewPage() {
  const [health, keys, workers, ideas, projects] = await Promise.all([
    api.health().catch(() => ({ status: "offline", service: "forge-trend-api" })),
    api.apiKeys().catch(() => []),
    api.workers().catch(() => []),
    api.ideas().catch(() => []),
    api.projects().catch(() => [])
  ]);
  const latestProjects = projects.slice(0, 5);

  return (
    <>
      <PageHeader title="Overview" description="Control plane for keys, workers, ideas, projects, pipeline logs, QA, and policy gates." />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <Metric icon={<Activity size={18} />} label="API" value={health.status} tone={health.status === "ok" ? "success" : "danger"} />
        <Metric icon={<KeyRound size={18} />} label="API Keys" value={keys.length.toString()} />
        <Metric icon={<Server size={18} />} label="Workers" value={workers.length.toString()} />
        <Metric icon={<Lightbulb size={18} />} label="Ideas" value={ideas.length.toString()} />
        <Metric icon={<Smartphone size={18} />} label="Projects" value={projects.length.toString()} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.3fr_0.7fr]">
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-base font-semibold">Latest Projects</h2>
            <Link href="/projects" className="text-sm text-primary">View all</Link>
          </div>
          <div className="space-y-3">
            {latestProjects.length ? latestProjects.map((project) => (
              <Link key={project.id} href={`/projects/${project.id}`} className="flex items-center justify-between rounded-md border border-border px-3 py-3 hover:bg-muted">
                <div>
                  <div className="font-medium">{project.name}</div>
                  <div className="text-xs text-muted-foreground">{project.slug} · {formatDate(project.updated_at)}</div>
                </div>
                <StatusBadge status={project.status} />
              </Link>
            )) : <p className="text-sm text-muted-foreground">No projects yet.</p>}
          </div>
        </Card>
        <Card>
          <h2 className="mb-4 text-base font-semibold">MVP Gates</h2>
          <div className="space-y-3 text-sm">
            {["Encrypted key storage", "Worker heartbeat", "PRD generation", "Flutter QA loop", "Policy checklist", "Human approval before production"].map((item) => (
              <div key={item} className="flex items-center gap-2">
                <CheckCircle2 className="text-primary" size={17} />
                <span>{item}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </>
  );
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
