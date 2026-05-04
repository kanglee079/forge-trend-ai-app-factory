"use client";

import { Cpu, GitBranch, Loader2, RefreshCw, Route } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError, AppSettings, DoctorResponse, Worker } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";
import { Badge, Button, Card, Notice, PageHeader } from "@/components/ui";

export default function ProvidersPage() {
  const { t } = useLanguage();
  const [doctor, setDoctor] = useState<DoctorResponse | null>(null);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<{ tone: "danger"; message: string } | null>(null);

  async function load() {
    setLoading(true);
    try {
      const [doctorReport, appSettings, workerItems] = await Promise.all([api.doctor().catch(() => null), api.settings().catch(() => null), api.workers().catch(() => [])]);
      setDoctor(doctorReport);
      setSettings(appSettings);
      setWorkers(workerItems);
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Không tải được provider router." });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load().catch(console.error); }, []);

  const hasCodex = workers.some((worker) => worker.has_codex && worker.worker_enable_codex);
  const hasAider = workers.some((worker) => worker.has_aider);

  return (
    <>
      <PageHeader title={t("providerRouterTitle")} description={t("providerRouterHelp")} action={<Button type="button" variant="secondary" onClick={() => load()} disabled={loading}>{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw size={16} />}{t("refresh")}</Button>} />
      {notice ? <Notice tone={notice.tone}>{notice.message}</Notice> : null}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <ProviderCard icon={<Cpu size={18} />} title={t("deterministicProvider")} status="available" detail={t("providerRuleSmoke")} />
        <ProviderCard icon={<GitBranch size={18} />} title={t("codexProvider")} status={hasCodex ? "available" : "needs setup"} detail={t("providerRuleCode")} />
        <ProviderCard icon={<GitBranch size={18} />} title={t("aiderProvider")} status={hasAider ? "available" : "optional"} detail={t("providerRuleRefine")} />
        <ProviderCard icon={<Route size={18} />} title={t("openaiProvider")} status="planned" detail={t("providerRuleBudget")} />
      </div>
      <Card className="mt-5">
        <h2 className="mb-3 text-base font-semibold">Routing policy</h2>
        <div className="grid gap-2 md:grid-cols-2">
          {[t("providerRuleSmoke"), t("providerRuleCode"), t("providerRuleRefine"), t("providerRuleBudget")].map((rule) => <div key={rule} className="rounded-md border border-border bg-background p-3 text-sm">{rule}</div>)}
        </div>
      </Card>
      <Card className="mt-5">
        <h2 className="mb-3 text-base font-semibold">Current config</h2>
        <pre className="overflow-x-auto rounded-md bg-muted p-3 text-xs">{JSON.stringify({ doctor: doctor?.worker_mode_label, research: doctor?.research_mode_label, default_provider: settings?.default_provider, default_model: settings?.default_model }, null, 2)}</pre>
      </Card>
    </>
  );
}

function ProviderCard({ icon, title, status, detail }: { icon: React.ReactNode; title: string; status: string; detail: string }) {
  return <Card><div className="mb-3 flex items-center justify-between gap-3"><div className="text-primary">{icon}</div><Badge tone={status === "available" ? "success" : status === "planned" ? "neutral" : "warning"}>{status}</Badge></div><h2 className="font-semibold">{title}</h2><p className="mt-2 text-sm text-muted-foreground">{detail}</p></Card>;
}
