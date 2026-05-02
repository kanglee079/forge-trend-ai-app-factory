"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { Loader2, Play, Plus, RefreshCw } from "lucide-react";
import { ApiError, api, Idea, Project, Worker } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Button, Card, Input, Label, Notice, PageHeader, Select, StatusBadge, Table, Td, Th } from "@/components/ui";

function slugify(value: string) {
  return value.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [runningId, setRunningId] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: "success" | "danger" | "warning"; message: string } | null>(null);

  async function load() {
    setLoading(true);
    try {
      const [projectItems, ideaItems, workerItems] = await Promise.all([api.projects(), api.ideas(), api.workers()]);
      setProjects(projectItems);
      setIdeas(ideaItems);
      setWorkers(workerItems);
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Could not load projects." });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load().catch(console.error);
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving) {
      return;
    }
    const form = new FormData(event.currentTarget);
    const name = String(form.get("name") || "");
    const target = event.currentTarget;
    setSaving(true);
    setNotice(null);
    try {
      await api.createProject({
        name,
        slug: String(form.get("slug") || slugify(name)),
        idea_id: form.get("idea_id") || null,
        target_platforms: ["android"]
      });
      target.reset();
      setNotice({ tone: "success", message: "Project created. It is ready for the agent pipeline." });
      await load();
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Could not create project." });
    } finally {
      setSaving(false);
    }
  }

  async function run(projectId: string) {
    if (runningId) {
      return;
    }
    const activeLocalWorker = workers.find((worker) => worker.status === "online" && worker.has_codex && worker.has_flutter);
    if (!activeLocalWorker) {
      setNotice({ tone: "warning", message: "No online local worker with Codex and Flutter is available. Start pnpm dev:worker before running the pipeline." });
      return;
    }
    setRunningId(projectId);
    setNotice(null);
    try {
      const response = await api.runPipeline(projectId);
      setNotice({ tone: "success", message: `Pipeline queued on ${response.queue}. Watch the project detail page for live events.` });
      await load();
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Could not queue pipeline." });
    } finally {
      setRunningId(null);
    }
  }

  const hasReadyWorker = workers.some((worker) => worker.status === "online" && worker.has_codex && worker.has_flutter);

  return (
    <>
      <PageHeader
        title="Projects"
        description="Create app projects from ideas and launch the agent pipeline."
        action={<Button type="button" variant="secondary" onClick={() => load()} disabled={loading}><RefreshCw size={16} /> {loading ? "Refreshing..." : "Refresh"}</Button>}
      />
      {notice ? <Notice tone={notice.tone}>{notice.message}</Notice> : null}
      {!hasReadyWorker ? (
        <Notice tone="warning">Local worker is not ready. Open a terminal, run codex login, then pnpm dev:worker so the pipeline can control Codex and Flutter on this machine.</Notice>
      ) : null}
      <Card className="mb-6">
        <form onSubmit={submit} className="grid gap-4 md:grid-cols-[1fr_1fr_1fr_auto]">
          <div>
            <Label>Name</Label>
            <Input name="name" placeholder="Focus Forge" required />
          </div>
          <div>
            <Label>Slug</Label>
            <Input name="slug" placeholder="focus-forge" />
          </div>
          <div>
            <Label>Idea</Label>
            <Select name="idea_id" defaultValue="">
              <option value="">No idea</option>
              {ideas.map((idea) => <option key={idea.id} value={idea.id}>{idea.title}</option>)}
            </Select>
          </div>
          <div className="flex items-end">
            <Button type="submit" disabled={saving}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus size={16} />}
              {saving ? "Creating..." : "Create"}
            </Button>
          </div>
        </form>
      </Card>
      <Table>
        <thead><tr><Th>Project</Th><Th>Platform</Th><Th>Status</Th><Th>Workspace</Th><Th>Updated</Th><Th>Action</Th></tr></thead>
        <tbody>
          {projects.map((project) => (
            <tr key={project.id}>
              <Td><Link className="font-medium text-primary" href={`/projects/${project.id}`}>{project.name}</Link><div className="text-xs text-muted-foreground">{project.slug}</div></Td>
              <Td>{project.target_platforms.join(", ")}</Td>
              <Td><StatusBadge status={project.status} /></Td>
              <Td className="max-w-xs truncate">{project.workspace_path ?? "Not created"}</Td>
              <Td>{formatDate(project.updated_at)}</Td>
              <Td>
                <Button type="button" variant="secondary" onClick={() => run(project.id)} disabled={runningId === project.id || Boolean(runningId)}>
                  {runningId === project.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play size={15} />}
                  {runningId === project.id ? "Queueing..." : "Run"}
                </Button>
              </Td>
            </tr>
          ))}
          {!projects.length ? <tr><Td className="text-muted-foreground" colSpan={6}>{loading ? "Loading projects..." : "No projects yet."}</Td></tr> : null}
        </tbody>
      </Table>
    </>
  );
}
