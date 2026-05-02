"use client";

import { useMemo, useState } from "react";
import { Copy, Download, Search, Trash2 } from "lucide-react";
import { AgentEvent, Project } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Badge, Button, Card, Input, Label, Select } from "@/components/ui";

export function CopyButton({ value, label = "Copy" }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  }

  return (
    <Button type="button" variant="secondary" onClick={copy}>
      <Copy size={15} />
      {copied ? "Copied" : label}
    </Button>
  );
}

export function LogViewer({
  events,
  projects = [],
  onClear,
}: {
  events: AgentEvent[];
  projects?: Project[];
  onClear?: () => void;
}) {
  const [query, setQuery] = useState("");
  const [level, setLevel] = useState("");
  const [projectId, setProjectId] = useState("");

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return events.filter((event) => {
      if (level && event.level !== level) return false;
      if (projectId && event.project_id !== projectId) return false;
      if (!normalized) return true;
      return [event.step, event.level, event.message, event.stdout, event.stderr].filter(Boolean).join("\n").toLowerCase().includes(normalized);
    });
  }, [events, level, projectId, query]);

  const exportText = filtered.map((event) => `[${event.created_at}] ${event.project_id} ${event.level} ${event.step}: ${event.message}\n${event.stdout ?? ""}\n${event.stderr ?? ""}`).join("\n\n---\n\n");

  function download(filename: string, value: string, type: string) {
    const blob = new Blob([value], { type });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-4">
      <Card>
        <div className="grid gap-3 lg:grid-cols-[1fr_160px_220px_auto_auto]">
          <div>
            <Label>Search</Label>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input className="pl-9" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search messages, stdout, stderr" />
            </div>
          </div>
          <div>
            <Label>Level</Label>
            <Select value={level} onChange={(event) => setLevel(event.target.value)}>
              <option value="">All levels</option>
              <option value="info">Info</option>
              <option value="warning">Warning</option>
              <option value="error">Error</option>
            </Select>
          </div>
          <div>
            <Label>Project</Label>
            <Select value={projectId} onChange={(event) => setProjectId(event.target.value)}>
              <option value="">All projects</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>{project.name}</option>
              ))}
            </Select>
          </div>
          <div className="flex items-end">
            <Button type="button" variant="secondary" onClick={() => download("forge-logs.txt", exportText, "text/plain")}>
              <Download size={15} />
              Export
            </Button>
          </div>
          {onClear ? (
            <div className="flex items-end">
              <Button type="button" variant="danger" onClick={onClear}>
                <Trash2 size={15} />
                Clear
              </Button>
            </div>
          ) : null}
        </div>
      </Card>

      {filtered.map((event) => (
        <Card key={event.id}>
          <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge>{event.step}</Badge>
                <Badge tone={event.level === "error" ? "danger" : event.level === "warning" ? "warning" : "neutral"}>{event.level}</Badge>
                <span className="text-xs text-muted-foreground">{formatDate(event.created_at)}</span>
              </div>
              <p className="mt-2 text-sm">{event.message}</p>
              <p className="mt-1 text-xs text-muted-foreground">{event.project_id}</p>
            </div>
            <CopyButton value={[event.message, event.stdout, event.stderr].filter(Boolean).join("\n\n")} />
          </div>
          {event.stdout ? <pre className="max-h-72 overflow-auto rounded-md bg-slate-950 p-3 text-xs text-slate-100">{event.stdout}</pre> : null}
          {event.stderr ? <pre className="mt-2 max-h-72 overflow-auto rounded-md bg-red-950 p-3 text-xs text-red-100">{event.stderr}</pre> : null}
        </Card>
      ))}
      {!filtered.length ? <Card className="text-center text-sm text-muted-foreground">No logs match the current filters.</Card> : null}
    </div>
  );
}
