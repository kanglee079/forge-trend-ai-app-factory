"use client";

import { useEffect, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import { api, ApiError, LearningSummary } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";
import { Badge, Button, Card, Notice, PageHeader, Table, Td, Th } from "@/components/ui";

export default function LearningPage() {
  const { t } = useLanguage();
  const [summary, setSummary] = useState<LearningSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<{ tone: "danger"; message: string } | null>(null);

  async function load() {
    setLoading(true);
    try {
      setSummary(await api.learningSummary());
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Không tải được learning memory." });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load().catch(console.error); }, []);

  return (
    <>
      <PageHeader title={t("learningTitle")} description={t("learningHelp")} action={<Button type="button" variant="secondary" onClick={() => load()} disabled={loading}>{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw size={16} />}{t("refresh")}</Button>} />
      {notice ? <Notice tone={notice.tone}>{notice.message}</Notice> : null}
      <div className="mb-5 grid gap-4 md:grid-cols-4">
        <Metric label="Runs" value={String(summary?.total_runs ?? "-")} />
        <Metric label="Avg quality" value={String(summary?.average_quality_score ?? "-")} />
        <Metric label="Release candidates" value={String(summary?.release_candidates ?? "-")} />
        <Metric label="Human review" value={String(summary?.needs_human_review ?? "-")} />
      </div>
      <div className="grid gap-5 xl:grid-cols-2">
        <Card>
          <h2 className="mb-3 text-base font-semibold">Lỗi thường gặp</h2>
          <Table><thead><tr><Th>Taxonomy</Th><Th>Count</Th><Th>Last reason</Th></tr></thead><tbody>{summary?.common_failures.map((item) => <tr key={item.taxonomy}><Td><Badge>{item.taxonomy}</Badge></Td><Td>{item.count}</Td><Td className="max-w-md text-muted-foreground">{item.last_reason ?? "-"}</Td></tr>)}</tbody></Table>
        </Card>
        <Card>
          <h2 className="mb-3 text-base font-semibold">Learning rules đang bật</h2>
          <div className="space-y-3">{summary?.active_rules.map((rule) => <div key={rule.rule_key} className="rounded-md border border-border bg-background p-3"><div className="mb-1 flex items-center gap-2"><Badge>{rule.rule_key}</Badge><Badge tone="success">{rule.confidence_score}</Badge></div><p className="text-sm text-muted-foreground">{rule.description}</p></div>)}{!summary?.active_rules.length ? <p className="text-sm text-muted-foreground">Chưa có rule nào. Chạy thêm pipeline để ForgeTrend học từ kết quả.</p> : null}</div>
        </Card>
      </div>
    </>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <Card><div className="text-sm text-muted-foreground">{label}</div><div className="mt-2 text-2xl font-semibold">{value}</div></Card>;
}
