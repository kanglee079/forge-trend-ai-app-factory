"use client";

import { useEffect, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import { api, ApiError, QueueSummary } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";
import { Badge, Button, Card, Notice, PageHeader } from "@/components/ui";

export default function QueuesPage() {
  const { t } = useLanguage();
  const [summary, setSummary] = useState<QueueSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<{ tone: "danger"; message: string } | null>(null);

  async function load() {
    setLoading(true);
    try {
      setSummary(await api.queueSummary());
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Không tải được queue." });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load().catch(console.error); }, []);

  const items = [
    ["Factory brief queue", summary?.factory_brief_queue],
    ["Project pipeline queue", summary?.project_pipeline_queue],
    ["Running jobs", summary?.running_jobs],
    ["Retryable jobs", summary?.retryable_jobs],
    ["Failed jobs", summary?.failed_jobs],
    ["Dead letter jobs", summary?.dead_letter_jobs],
  ];

  return (
    <>
      <PageHeader title={t("queueMonitorTitle")} description={t("queueMonitorHelp")} action={<Button type="button" variant="secondary" onClick={() => load()} disabled={loading}>{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw size={16} />}{t("refresh")}</Button>} />
      {notice ? <Notice tone={notice.tone}>{notice.message}</Notice> : null}
      <div className="grid gap-4 md:grid-cols-3">
        {items.map(([label, value]) => <Card key={label as string}><div className="text-sm text-muted-foreground">{label}</div><div className="mt-2 text-2xl font-semibold">{value ?? "-"}</div></Card>)}
      </div>
      <Notice tone="neutral" className="mt-5"><Badge>Next action</Badge> {summary?.next_action ?? "Worker state is loading."}</Notice>
    </>
  );
}
