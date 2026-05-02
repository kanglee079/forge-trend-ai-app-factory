"use client";

import { useEffect, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import { AgentEvent, api, ApiError, Project } from "@/lib/api";
import { useFeedback } from "@/components/feedback";
import { LogViewer } from "@/components/log-viewer";
import { Button, Notice, PageHeader, Skeleton } from "@/components/ui";

export default function LogsPage() {
  const feedback = useFeedback();
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [notice, setNotice] = useState<{ tone: "success" | "danger"; message: string } | null>(null);

  async function load({ quiet = false } = {}) {
    setLoading(true);
    try {
      const [eventItems, projectItems] = await Promise.all([api.allEvents({ limit: 300 }), api.projects()]);
      setEvents(eventItems);
      setProjects(projectItems);
      if (!quiet) setNotice({ tone: "success", message: "Logs refreshed." });
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Could not load logs." });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load({ quiet: true }).catch(console.error);
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;
    const timer = window.setInterval(() => load({ quiet: true }).catch(console.error), 5000);
    return () => window.clearInterval(timer);
  }, [autoRefresh]);

  async function clearVisible() {
    const projectIds = Array.from(new Set(events.map((event) => event.project_id)));
    if (!projectIds.length) return;
    const confirmed = await feedback.confirm({
      title: "Clear visible project logs?",
      description: `This clears agent event logs for ${projectIds.length} project(s). QA, policy, and artifacts remain.`,
      confirmLabel: "Clear logs",
      tone: "danger",
    });
    if (!confirmed) return;
    try {
      await Promise.all(projectIds.map((projectId) => api.clearEvents(projectId)));
      setEvents([]);
      feedback.notify({ tone: "success", message: "Visible project logs cleared." });
    } catch (error) {
      feedback.notify({ tone: "danger", message: error instanceof ApiError ? error.detail : "Could not clear logs." });
    }
  }

  return (
    <>
      <PageHeader
        title="Logs"
        description="Search, filter, copy, export, and clear agent events without opening a terminal."
        action={
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant={autoRefresh ? "primary" : "secondary"} onClick={() => setAutoRefresh((value) => !value)}>
              {autoRefresh ? "Auto refresh on" : "Auto refresh off"}
            </Button>
            <Button type="button" variant="secondary" onClick={() => load()} disabled={loading}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw size={16} />}
              {loading ? "Refreshing..." : "Refresh"}
            </Button>
          </div>
        }
      />
      {notice ? <Notice tone={notice.tone}>{notice.message}</Notice> : null}
      {loading && !events.length ? (
        <div className="space-y-4">
          <Skeleton className="h-24" />
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
        </div>
      ) : (
        <LogViewer events={events} projects={projects} onClear={clearVisible} />
      )}
    </>
  );
}
