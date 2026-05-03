"use client";

import { useEffect, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import { ApiError, api, Worker } from "@/lib/api";
import { formatDate, isReadyWorker } from "@/lib/utils";
import { Badge, Button, Notice, PageHeader, StatusBadge, Table, Td, Th } from "@/components/ui";

export default function WorkersPage() {
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<{ tone: "success" | "danger" | "warning"; message: string } | null>(null);
  const capabilities = [
    ["has_docker", "Docker"],
    ["has_flutter", "Flutter"],
    ["has_android_sdk", "Android"],
    ["has_xcode", "Xcode"],
    ["has_codex", "Codex"],
    ["has_aider", "Aider"]
  ] as const;

  async function load({ quiet = false } = {}) {
    setLoading(true);
    try {
      setWorkers(await api.workers());
      if (!quiet) {
        setNotice({ tone: "success", message: "Worker status refreshed." });
      }
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Could not load workers." });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load({ quiet: true }).catch(console.error);
    const timer = setInterval(() => load({ quiet: true }).catch(console.error), 5000);
    return () => clearInterval(timer);
  }, []);

  const readyWorker = workers.find(isReadyWorker);

  return (
    <>
      <PageHeader
        title="Workers"
        description="Machine registry, heartbeat status, and local build capabilities."
        action={
          <Button type="button" variant="secondary" onClick={() => load()} disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw size={16} />}
            {loading ? "Refreshing..." : "Refresh"}
          </Button>
        }
      />
      {notice ? <Notice tone={notice.tone}>{notice.message}</Notice> : null}
      {readyWorker ? (
        <Notice tone="success">{readyWorker.machine_name} is ready. {readyWorker.worker_enable_codex ? "Mode: Codex coding mode" : "Mode: Deterministic scaffold mode"}</Notice>
      ) : (
        <Notice tone="warning">No ready local worker is online. Deterministic mode requires Flutter; Codex mode requires Flutter plus Codex CLI auth.</Notice>
      )}
      <Table>
        <thead><tr><Th>Machine</Th><Th>OS</Th><Th>Capabilities</Th><Th>Status</Th><Th>Current job</Th><Th>Heartbeat</Th></tr></thead>
        <tbody>
          {workers.map((worker) => (
            <tr key={worker.id}>
              <Td><div className="font-medium">{worker.machine_name}</div><div className="text-xs text-muted-foreground">{worker.arch}</div></Td>
              <Td>{worker.os}</Td>
              <Td>
                <div className="flex flex-wrap gap-1">
                  {capabilities.map(([key, label]) => <Badge key={key} tone={worker[key] ? "success" : "neutral"}>{label}</Badge>)}
                  <Badge>{worker.worker_enable_codex ? "Mode: Codex coding mode" : "Mode: Deterministic scaffold mode"}</Badge>
                </div>
              </Td>
              <Td><StatusBadge status={worker.status} /></Td>
              <Td>{worker.current_job_id ?? "Idle"}</Td>
              <Td>{formatDate(worker.last_heartbeat_at)}</Td>
            </tr>
          ))}
          {!workers.length ? <tr><Td className="text-muted-foreground" colSpan={6}>{loading ? "Loading workers..." : "No workers registered yet."}</Td></tr> : null}
        </tbody>
      </Table>
    </>
  );
}
