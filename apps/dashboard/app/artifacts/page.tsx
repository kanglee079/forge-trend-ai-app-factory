"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { FileText, Loader2, RefreshCw } from "lucide-react";
import { api, ApiError, Artifact, Project } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";
import { formatDate } from "@/lib/utils";
import { Badge, Button, Card, EmptyState, Label, Notice, PageHeader, Select, Table, Td, Th } from "@/components/ui";
import { CopyButton } from "@/components/log-viewer";

type Row = Artifact & { project?: Project };

function purposeFor(item: Artifact) {
  const name = item.name.toLowerCase();
  if (item.kind === "build" || name.endsWith(".apk")) return "cài thử app Android nội bộ sau khi con người review.";
  if (item.kind === "source") return "mở source Flutter để kiểm tra, chỉnh sửa hoặc build lại.";
  if (name.includes("prd")) return "đọc yêu cầu sản phẩm đã tạo từ ý tưởng.";
  if (name.includes("quality") || name.includes("score")) return "xem điểm chất lượng và lý do bị chặn.";
  if (name.includes("store") || item.path.includes("store_assets")) return "review bản nháp listing, screenshot plan và privacy trước khi lên store.";
  return "lưu bằng chứng đầu ra của pipeline.";
}

export default function ArtifactsPage() {
  const { t } = useLanguage();
  const [projects, setProjects] = useState<Project[]>([]);
  const [rows, setRows] = useState<Row[]>([]);
  const [projectId, setProjectId] = useState("all");
  const [kind, setKind] = useState("all");
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<{ tone: "success" | "danger"; message: string } | null>(null);

  async function load() {
    setLoading(true);
    try {
      const projectItems = await api.projects();
      const artifactGroups = await Promise.all(projectItems.map((project) => api.artifacts(project.id).catch(() => [])));
      setProjects(projectItems);
      setRows(artifactGroups.flatMap((items, index) => items.map((item) => ({ ...item, project: projectItems[index] }))));
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Không tải được artifact." });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load().catch(console.error);
  }, []);

  const kinds = useMemo(() => Array.from(new Set(rows.map((item) => item.kind))).sort(), [rows]);
  const filtered = rows.filter((item) => (projectId === "all" || item.project_id === projectId) && (kind === "all" || item.kind === kind));

  return (
    <>
      <PageHeader
        title={t("artifactCenterTitle")}
        description={t("artifactCenterHelp")}
        action={<Button type="button" variant="secondary" onClick={() => load()} disabled={loading}>{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw size={16} />}{t("refresh")}</Button>}
      />
      {notice ? <Notice tone={notice.tone}>{notice.message}</Notice> : null}
      <Card className="mb-5">
        <div className="grid gap-4 md:grid-cols-2">
          <div><Label>{t("filterProject")}</Label><Select value={projectId} onChange={(event) => setProjectId(event.target.value)}><option value="all">{t("allProjects")}</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</Select></div>
          <div><Label>{t("filterType")}</Label><Select value={kind} onChange={(event) => setKind(event.target.value)}><option value="all">{t("allTypes")}</option>{kinds.map((value) => <option key={value} value={value}>{value}</option>)}</Select></div>
        </div>
      </Card>
      {filtered.length ? (
        <Table>
          <thead><tr><Th>Project</Th><Th>Name</Th><Th>Kind</Th><Th>{t("filePurpose")}</Th><Th>Path</Th><Th>Created</Th><Th>Action</Th></tr></thead>
          <tbody>
            {filtered.map((item) => (
              <tr key={item.id}>
                <Td>{item.project ? <Link className="text-primary" href={`/projects/${item.project.id}`}>{item.project.name}</Link> : item.project_id}</Td>
                <Td><div className="flex items-center gap-2"><FileText size={15} />{item.name}</div></Td>
                <Td><Badge>{item.kind}</Badge></Td>
                <Td className="max-w-sm text-muted-foreground">{purposeFor(item)}</Td>
                <Td className="max-w-md truncate">{item.path}</Td>
                <Td>{formatDate(item.created_at)}</Td>
                <Td><CopyButton value={item.path} label={t("copyPath")} /></Td>
              </tr>
            ))}
          </tbody>
        </Table>
      ) : <EmptyState title={t("noArtifacts")} body="Sau khi pipeline chạy, APK/source/report/store assets sẽ hiện ở đây." href="/create" />}
    </>
  );
}
