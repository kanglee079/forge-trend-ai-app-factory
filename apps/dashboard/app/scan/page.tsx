"use client";

import { FormEvent, useEffect, useState } from "react";
import { ExternalLink, Loader2, RefreshCw, Search, ShieldCheck } from "lucide-react";
import { api, ApiError, SourceItem } from "@/lib/api";
import { Badge, Button, Card, Input, Label, Notice, PageHeader, Select } from "@/components/ui";

const defaultQueries = [
  "ai agent prompts coding workflow",
  "flutter app template store ready",
  "google play policy checklist",
  "app store readiness checklist",
  "aso prompt templates",
  "agent skills prompt library",
];

export default function ScanPage() {
  const [sourceType, setSourceType] = useState("github_search");
  const [query, setQuery] = useState(defaultQueries[0]);
  const [items, setItems] = useState<SourceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [notice, setNotice] = useState<{ tone: "success" | "danger" | "warning" | "neutral"; message: string } | null>(null);

  async function load() {
    setLoading(true);
    try {
      setItems(await api.sourceItems());
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Không tải được source items." });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load().catch(console.error); }, []);

  async function runScan(event: FormEvent) {
    event.preventDefault();
    if (running) return;
    setRunning(true);
    setNotice(null);
    try {
      const result = await api.createScanRun({ source_type: sourceType, query, limit: 6 });
      setNotice({ tone: "success", message: result.summary });
      await load();
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Scan thất bại." });
    } finally {
      setRunning(false);
    }
  }

  async function convert(item: SourceItem) {
    try {
      await api.convertSourceItemToSkill(item.id);
      setNotice({ tone: "success", message: "Đã chuyển source item thành skill pack ở trạng thái tắt/quarantine để review." });
      await load();
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Không chuyển được thành skill." });
    }
  }

  async function updateStatus(item: SourceItem, status: string) {
    await api.updateSourceItem(item.id, { status });
    await load();
  }

  return (
    <>
      <PageHeader
        title="External Scan"
        description="Quét GitHub/web/local để tìm prompt hoặc skill hữu ích. Mọi nguồn ngoài đều vào quarantine, không tự chạy code và không tự trust."
        action={<Button type="button" variant="secondary" onClick={load} disabled={loading}>{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw size={16} />}Làm mới</Button>}
      />
      {notice ? <Notice tone={notice.tone}>{notice.message}</Notice> : null}
      <Notice tone="neutral"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />Scanner chỉ lấy metadata/text template. External resource phải được review trước khi bật thành skill.</Notice>

      <Card className="mb-5">
        <form onSubmit={runScan} className="grid gap-4 md:grid-cols-[180px_1fr_auto]">
          <div>
            <Label>Nguồn</Label>
            <Select value={sourceType} onChange={(event) => setSourceType(event.target.value)}>
              <option value="github_search">GitHub search</option>
              <option value="github_repo">GitHub repo README</option>
              <option value="web_url">Web URL</option>
              <option value="local_folder">Local folder</option>
              <option value="prompt_library">Prompt library</option>
            </Select>
          </div>
          <div>
            <Label>Query</Label>
            <Input value={query} onChange={(event) => setQuery(event.target.value)} />
          </div>
          <Button type="submit" className="self-end" disabled={running}>{running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search size={16} />}Run scan</Button>
        </form>
        <div className="mt-3 flex flex-wrap gap-2">
          {defaultQueries.map((item) => <button key={item} type="button" onClick={() => setQuery(item)} className="rounded-sm border border-border bg-background px-2 py-1 text-xs text-muted-foreground hover:bg-muted">{item}</button>)}
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        {items.map((item) => (
          <Card key={item.id}>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap gap-2">
                <Badge tone={item.status === "enabled" ? "success" : item.status === "rejected" ? "danger" : "warning"}>{item.status}</Badge>
                <Badge>{item.source_type}</Badge>
                <Badge>{item.usefulness_score}/100</Badge>
              </div>
              {item.source_url ? (
                <a className="inline-flex items-center gap-1 text-xs text-primary" href={item.source_url} target="_blank" rel="noreferrer">
                  Source <ExternalLink size={12} />
                </a>
              ) : null}
            </div>
            <h2 className="font-semibold">{item.title}</h2>
            <p className="mt-2 text-sm text-muted-foreground">{item.summary}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button type="button" variant="secondary" onClick={() => convert(item)}>Convert to skill</Button>
              <Button type="button" variant="ghost" onClick={() => updateStatus(item, "reviewed")}>Reviewed</Button>
              <Button type="button" variant="ghost" onClick={() => updateStatus(item, "enabled")}>Mark useful</Button>
              <Button type="button" variant="ghost" onClick={() => updateStatus(item, "rejected")}>Reject</Button>
            </div>
          </Card>
        ))}
        {!items.length && !loading ? <Notice tone="warning">Chưa có source item nào. Hãy chạy scan đầu tiên.</Notice> : null}
      </div>
    </>
  );
}
