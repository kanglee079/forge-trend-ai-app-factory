"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Loader2, RefreshCw } from "lucide-react";
import { api, ApiError, Artifact, PolicyResult, Project } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";
import { formatDate } from "@/lib/utils";
import { Badge, Button, Card, EmptyState, Notice, PageHeader, Table, Td, Th, StatusBadge } from "@/components/ui";
import { CopyButton } from "@/components/log-viewer";

type CandidateRow = {
  project: Project;
  artifacts: Artifact[];
  policy: PolicyResult[];
};

export default function CandidatesPage() {
  const { t } = useLanguage();
  const [rows, setRows] = useState<CandidateRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<{ tone: "success" | "danger"; message: string } | null>(null);

  async function load() {
    setLoading(true);
    try {
      const projects = await api.projects();
      const groups = await Promise.all(projects.map(async (project) => ({
        project,
        artifacts: await api.artifacts(project.id).catch(() => []),
        policy: await api.policy(project.id).catch(() => []),
      })));
      setRows(groups.filter((row) => row.project.status === "release_candidate" || row.project.status === "NEEDS_HUMAN_REVIEW" || row.artifacts.length));
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Không tải được app ứng viên." });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load().catch(console.error);
  }, []);

  const sorted = useMemo(() => [...rows].sort((a, b) => b.project.updated_at.localeCompare(a.project.updated_at)), [rows]);

  return (
    <>
      <PageHeader
        title={t("appCandidatesTitle")}
        description={t("appCandidatesHelp")}
        action={<Button type="button" variant="secondary" onClick={() => load()} disabled={loading}>{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw size={16} />}{t("refresh")}</Button>}
      />
      {notice ? <Notice tone={notice.tone}>{notice.message}</Notice> : null}
      <Card className="mb-5">
        <Notice tone="neutral" className="mb-0">{t("humanApprovalRequired")}</Notice>
      </Card>
      {sorted.length ? (
        <Table>
          <thead><tr><Th>App</Th><Th>Status</Th><Th>{t("qualityScore")}</Th><Th>{t("policyRisk")}</Th><Th>{t("apkPath")}</Th><Th>{t("sourcePath")}</Th><Th>{t("nextAction")}</Th><Th>Updated</Th></tr></thead>
          <tbody>
            {sorted.map(({ project, artifacts, policy }) => {
              const score = artifacts.find((item) => item.name === "product_score_report.json" || item.name === "quality_gate_report.json")?.metadata_json?.score;
              const scoreLabel = typeof score === "string" || typeof score === "number" ? String(score) : "-";
              const apk = artifacts.find((item) => item.kind === "build" || item.name.endsWith(".apk"));
              const source = artifacts.find((item) => item.kind === "source");
              const latestPolicy = policy[0];
              return (
                <tr key={project.id}>
                  <Td><Link className="font-medium text-primary" href={`/projects/${project.id}`}>{project.name}</Link><div className="text-xs text-muted-foreground">{project.slug}</div></Td>
                  <Td><StatusBadge status={project.status} /></Td>
                  <Td><Badge tone={Number(scoreLabel) >= 75 ? "success" : "warning"}>{scoreLabel}</Badge></Td>
                  <Td>{latestPolicy ? <Badge tone={latestPolicy.passed ? "success" : "warning"}>{latestPolicy.risk}</Badge> : "-"}</Td>
                  <Td>{apk ? <CopyButton value={apk.path} label="APK" /> : "-"}</Td>
                  <Td>{source ? <CopyButton value={source.path} label="Source" /> : "-"}</Td>
                  <Td className="max-w-xs text-muted-foreground">{project.status === "release_candidate" ? "Review APK, source, policy, store assets, then decide internal testing." : "Đọc report, sửa blocker, chạy lại pipeline."}</Td>
                  <Td>{formatDate(project.updated_at)}</Td>
                </tr>
              );
            })}
          </tbody>
        </Table>
      ) : <EmptyState title="Chưa có app ứng viên" body="Tạo app đầu tiên bằng Simple Mode để xem ứng viên ở đây." href="/create" />}
    </>
  );
}
