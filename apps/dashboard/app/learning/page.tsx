"use client";

import { useEffect, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import { api, ApiError, LearningRule, LearningSummary } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";
import { Badge, Button, Card, Notice, PageHeader, Table, Td, Th } from "@/components/ui";

export default function LearningPage() {
  const { t } = useLanguage();
  const [summary, setSummary] = useState<LearningSummary | null>(null);
  const [rules, setRules] = useState<LearningRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<{ tone: "success" | "danger"; message: string } | null>(null);

  async function load() {
    setLoading(true);
    try {
      const [learningSummary, learningRules] = await Promise.all([api.learningSummary(), api.learningRules().catch(() => [])]);
      setSummary(learningSummary);
      setRules(learningRules);
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Không tải được learning memory." });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load().catch(console.error); }, []);

  async function toggleRule(rule: LearningRule) {
    try {
      const updated = await api.updateLearningRule(rule.id, { enabled: !rule.enabled });
      setRules((current) => current.map((item) => item.id === updated.id ? updated : item));
      setNotice({ tone: "success", message: `${updated.rule_key} đã ${updated.enabled ? "bật" : "tắt"}.` });
      setSummary(await api.learningSummary());
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Không cập nhật được learning rule." });
    }
  }

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
          <div className="space-y-3">
            {rules.map((rule) => (
              <div key={rule.id} className="rounded-md border border-border bg-background p-3">
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge>{rule.rule_key}</Badge>
                    <Badge tone={rule.enabled ? "success" : "warning"}>{rule.enabled ? "enabled" : "disabled"}</Badge>
                    <Badge>{rule.confidence_score}</Badge>
                  </div>
                  <Button type="button" variant="secondary" onClick={() => toggleRule(rule)}>
                    {rule.enabled ? "Tắt rule" : "Bật rule"}
                  </Button>
                </div>
                <p className="text-sm text-muted-foreground">{rule.description}</p>
                <details className="mt-2 text-xs text-muted-foreground">
                  <summary>Trigger/action JSON</summary>
                  <pre className="mt-2 overflow-auto rounded-md bg-muted p-2">{JSON.stringify({ trigger: rule.trigger_json, action: rule.action_json }, null, 2)}</pre>
                </details>
              </div>
            ))}
            {!rules.length ? <p className="text-sm text-muted-foreground">Chưa có rule nào. Chạy thêm pipeline để ForgeTrend học từ kết quả.</p> : null}
          </div>
        </Card>
      </div>
    </>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <Card><div className="text-sm text-muted-foreground">{label}</div><div className="mt-2 text-2xl font-semibold">{value}</div></Card>;
}
