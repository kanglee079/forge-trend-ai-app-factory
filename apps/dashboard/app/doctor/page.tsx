"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2, RefreshCw, XCircle } from "lucide-react";
import { api, ApiError, DoctorResponse } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Badge, Button, Card, Notice, PageHeader, Skeleton } from "@/components/ui";

export default function DoctorPage() {
  const [doctor, setDoctor] = useState<DoctorResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<{ tone: "success" | "danger"; message: string } | null>(null);

  async function load() {
    setLoading(true);
    try {
      setDoctor(await api.doctor());
      setNotice({ tone: "success", message: "Doctor checks refreshed." });
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Could not run doctor checks." });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load().catch(console.error);
  }, []);

  const required = doctor?.checks.filter((check) => check.required) ?? [];
  const optional = doctor?.checks.filter((check) => !check.required) ?? [];
  const passed = doctor?.checks.filter((check) => check.status === "passed").length ?? 0;
  const total = doctor?.checks.length ?? 0;

  return (
    <>
      <PageHeader
        title="Setup Doctor"
        description="Local machine readiness for Docker services, worker heartbeat, Flutter, Codex, and the app factory."
        action={
          <Button type="button" variant="secondary" onClick={() => load()} disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw size={16} />}
            {loading ? "Running..." : "Run doctor"}
          </Button>
        }
      />
      {notice ? <Notice tone={notice.tone}>{notice.message}</Notice> : null}
      {loading && !doctor ? (
        <div className="space-y-4">
          <Skeleton className="h-28" />
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
        </div>
      ) : doctor ? (
        <>
          <div className="mb-5 grid gap-4 md:grid-cols-3">
            <Card>
              <div className="text-sm text-muted-foreground">Overall</div>
              <div className="mt-2"><Badge tone={doctor.status === "passed" ? "success" : doctor.status === "warning" ? "warning" : "danger"}>{doctor.status}</Badge></div>
            </Card>
            <Card>
              <div className="text-sm text-muted-foreground">Checks passed</div>
              <div className="mt-2 text-2xl font-semibold">{passed}/{total}</div>
            </Card>
            <Card>
              <div className="text-sm text-muted-foreground">Generated</div>
              <div className="mt-2 text-sm">{formatDate(doctor.generated_at)}</div>
            </Card>
          </div>
          <Notice tone="neutral">{doctor.worker_mode_label}. {doctor.research_mode_label}</Notice>

          <section className="mb-6">
            <h2 className="mb-3 text-base font-semibold">Required</h2>
            <div className="grid gap-3 lg:grid-cols-2">
              {required.map((check) => <DoctorCheckCard key={check.id} check={check} />)}
            </div>
          </section>
          <section>
            <h2 className="mb-3 text-base font-semibold">Optional / Worker Features</h2>
            <div className="grid gap-3 lg:grid-cols-2">
              {optional.map((check) => <DoctorCheckCard key={check.id} check={check} />)}
            </div>
          </section>
        </>
      ) : null}
    </>
  );
}

function DoctorCheckCard({ check }: { check: DoctorResponse["checks"][number] }) {
  const Icon = check.status === "passed" ? CheckCircle2 : check.required ? XCircle : AlertTriangle;
  return (
    <Card>
      <div className="flex items-start gap-3">
        <Icon className={check.status === "passed" ? "mt-0.5 h-5 w-5 text-emerald-600" : check.required ? "mt-0.5 h-5 w-5 text-red-600" : "mt-0.5 h-5 w-5 text-amber-600"} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <div className="font-medium">{check.label}</div>
            <Badge tone={check.status === "passed" ? "success" : check.required ? "danger" : "warning"}>{check.status}</Badge>
            <Badge tone={check.required ? "neutral" : "warning"}>{check.required ? "required" : "optional"}</Badge>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">{check.detail}</p>
          {check.guidance ? <p className="mt-3 rounded-md bg-muted p-3 text-sm">{check.guidance}</p> : null}
        </div>
      </div>
    </Card>
  );
}
