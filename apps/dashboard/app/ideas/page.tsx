"use client";

import { FormEvent, useEffect, useState } from "react";
import { Loader2, Plus, RefreshCw } from "lucide-react";
import { ApiError, api, Idea } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Badge, Button, Card, Input, Label, Notice, PageHeader, StatusBadge, Table, Td, Textarea, Th } from "@/components/ui";

export default function IdeasPage() {
  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<{ tone: "success" | "danger" | "warning"; message: string } | null>(null);

  async function load() {
    setLoading(true);
    try {
      setIdeas(await api.ideas());
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Could not load ideas." });
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
    const target = event.currentTarget;
    setSaving(true);
    setNotice(null);
    try {
      await api.createIdea({
        title: form.get("title"),
        description: form.get("description"),
        opportunity_score: Number(form.get("opportunity_score") || 65),
        source: "manual"
      });
      target.reset();
      setNotice({ tone: "success", message: "Idea created. You can create a project from it now." });
      await load();
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Could not create idea." });
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Ideas"
        description="Create manual app ideas and score the opportunity before generating a project."
        action={<Button type="button" variant="secondary" onClick={() => load()} disabled={loading}><RefreshCw size={16} /> {loading ? "Refreshing..." : "Refresh"}</Button>}
      />
      {notice ? <Notice tone={notice.tone}>{notice.message}</Notice> : null}
      <Card className="mb-6">
        <form onSubmit={submit} className="grid gap-4 md:grid-cols-[1fr_140px]">
          <div>
            <Label>Idea title</Label>
            <Input name="title" placeholder="AI study sprint planner" required />
          </div>
          <div>
            <Label>Score</Label>
            <Input name="opportunity_score" type="number" min="0" max="100" defaultValue="65" />
          </div>
          <div className="md:col-span-2">
            <Label>Description</Label>
            <Textarea name="description" placeholder="Target user, pain point, original angle, and first MVP shape." required />
          </div>
          <div className="md:col-span-2">
            <Button type="submit" disabled={saving}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus size={16} />}
              {saving ? "Creating..." : "Create idea"}
            </Button>
          </div>
        </form>
      </Card>
      <Table>
        <thead><tr><Th>Idea</Th><Th>Opportunity</Th><Th>Source</Th><Th>Status</Th><Th>Created</Th></tr></thead>
        <tbody>
          {ideas.map((idea) => (
            <tr key={idea.id}>
              <Td><div className="font-medium">{idea.title}</div><div className="max-w-xl text-xs text-muted-foreground">{idea.description}</div></Td>
              <Td><Badge tone={idea.opportunity_score >= 70 ? "success" : "warning"}>{idea.opportunity_score}/100</Badge></Td>
              <Td>{idea.source}</Td>
              <Td><StatusBadge status={idea.status} /></Td>
              <Td>{formatDate(idea.created_at)}</Td>
            </tr>
          ))}
          {!ideas.length ? <tr><Td className="text-muted-foreground" colSpan={5}>{loading ? "Loading ideas..." : "No ideas yet."}</Td></tr> : null}
        </tbody>
      </Table>
    </>
  );
}
