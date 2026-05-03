"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { Bot, CheckCircle2, Loader2, Play, RefreshCw, Rocket, Wand2 } from "lucide-react";
import { api, ApiError, FactoryBrief, FactoryBriefDetail, Notification } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Badge, Button, Card, Input, Label, Notice, PageHeader, Select, Skeleton, StatusBadge, Textarea } from "@/components/ui";
import { useFeedback } from "@/components/feedback";

function defaultTitle(prompt: string) {
  const compact = prompt.trim().replace(/\s+/g, " ");
  if (!compact) return "Autonomous App Opportunity";
  return compact.length > 62 ? `${compact.slice(0, 62).trim()}...` : compact;
}

export default function FactoryPage() {
  const feedback = useFeedback();
  const [briefs, setBriefs] = useState<FactoryBrief[]>([]);
  const [selected, setSelected] = useState<FactoryBriefDetail | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [events, setEvents] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [startingId, setStartingId] = useState<string | null>(null);
  const [finalizingId, setFinalizingId] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: "success" | "danger" | "warning"; message: string } | null>(null);

  async function load(selectId?: string) {
    setLoading(true);
    try {
      const items = await api.factoryBriefs();
      setBriefs(items);
      const targetId = selectId ?? selectedId ?? items[0]?.id;
      if (targetId) {
        const [detail, eventItems] = await Promise.all([api.factoryBrief(targetId), api.factoryBriefEvents(targetId).catch(() => [])]);
        setSelected(detail);
        setEvents(eventItems);
        setSelectedId(targetId);
      } else {
        setSelected(null);
        setEvents([]);
        setSelectedId(null);
      }
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Could not load factory briefs." });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load().catch(console.error);
    const timer = window.setInterval(() => load().catch(console.error), 7000);
    return () => window.clearInterval(timer);
  }, [selectedId]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving) return;
    const form = new FormData(event.currentTarget);
    const prompt = String(form.get("raw_prompt") || "");
    const target = event.currentTarget;
    setSaving(true);
    setNotice(null);
    try {
      const brief = await api.createFactoryBrief({
        mode: form.get("mode"),
        title: String(form.get("title") || defaultTitle(prompt)),
        raw_prompt: prompt,
        target_category: form.get("target_category") || null,
        target_platforms: ["android"],
        target_country: form.get("target_country") || "US",
        target_language: form.get("target_language") || "en",
        monetization_mode: form.get("monetization_mode") || "none",
        iap_enabled: form.get("iap_enabled") === "on",
        subscription_enabled: form.get("subscription_enabled") === "on",
        ads_enabled: form.get("ads_enabled") === "on",
        backend_mode: form.get("backend_mode") || "none",
        complexity: form.get("complexity") || "medium",
        max_cost_usd: Number(form.get("max_cost_usd") || 5),
        max_runtime_minutes: Number(form.get("max_runtime_minutes") || 60),
        quality_threshold: Number(form.get("quality_threshold") || 75),
        policy_strictness: form.get("policy_strictness") || "standard"
      });
      target.reset();
      feedback.notify({ tone: "success", message: "Factory brief created." });
      setNotice({ tone: "success", message: "Factory brief created. Start it to run research, scoring, project creation, and pipeline queueing." });
      await load(brief.id);
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Could not create factory brief." });
    } finally {
      setSaving(false);
    }
  }

  async function startBrief(id: string) {
    if (startingId) return;
    setStartingId(id);
    try {
      const response = await api.startFactoryBrief(id);
      feedback.notify({ tone: "success", message: `Factory brief queued on ${response.queue}.` });
      await load(id);
    } catch (error) {
      feedback.notify({ tone: "danger", message: error instanceof ApiError ? error.detail : "Could not start factory brief." });
    } finally {
      setStartingId(null);
    }
  }

  async function finalize(briefId: string, candidateId: string) {
    if (finalizingId) return;
    setFinalizingId(candidateId);
    try {
      const response = await api.finalizeFactoryBrief(briefId, candidateId, true);
      feedback.notify({ tone: "success", message: `Project queued on ${response.queue}.` });
      await load(briefId);
    } catch (error) {
      feedback.notify({ tone: "danger", message: error instanceof ApiError ? error.detail : "Could not create project from candidate." });
    } finally {
      setFinalizingId(null);
    }
  }

  const selectedCandidate = useMemo(() => selected?.candidates.find((candidate) => candidate.status === "selected"), [selected]);
  const topCandidate = selected?.candidates[0];

  return (
    <>
      <PageHeader
        title="Factory"
        description="Create one brief, then let the factory research, score, select, create a project, and queue the build pipeline."
        action={
          <Button type="button" variant="secondary" onClick={() => load()} disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw size={16} />}
            Refresh
          </Button>
        }
      />
      {notice ? <Notice tone={notice.tone}>{notice.message}</Notice> : null}

      <div className="grid gap-5 xl:grid-cols-[0.95fr_1.25fr]">
        <Card>
          <div className="mb-4 flex items-center gap-2">
            <Wand2 className="h-5 w-5 text-primary" />
            <h2 className="text-base font-semibold">New Factory Brief</h2>
          </div>
          <form onSubmit={submit} className="space-y-4">
            <div>
              <Label>Instruction</Label>
              <Textarea
                name="raw_prompt"
                placeholder="Tự search trend và build app tốt nhất cho người học HSK, có subscription và local-first progress."
                required
                className="min-h-36"
              />
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label>Title</Label>
                <Input name="title" placeholder="Auto-generate if empty" />
              </div>
              <div>
                <Label>Mode</Label>
                <Select name="mode" defaultValue="auto_trend">
                  <option value="auto_trend">Auto trend search</option>
                  <option value="manual_idea">Manual idea</option>
                  <option value="clone_safe_alternative">Safe alternative</option>
                </Select>
              </div>
              <div>
                <Label>Category</Label>
                <Input name="target_category" placeholder="Education, productivity, finance..." />
              </div>
              <div>
                <Label>Country</Label>
                <Input name="target_country" defaultValue="US" />
              </div>
              <div>
                <Label>Language</Label>
                <Select name="target_language" defaultValue="en">
                  <option value="en">English</option>
                  <option value="vi">Vietnamese</option>
                  <option value="zh">Chinese</option>
                  <option value="ja">Japanese</option>
                </Select>
              </div>
              <div>
                <Label>Complexity</Label>
                <Select name="complexity" defaultValue="medium">
                  <option value="small">Small</option>
                  <option value="medium">Medium</option>
                  <option value="large">Large</option>
                </Select>
              </div>
              <div>
                <Label>Backend</Label>
                <Select name="backend_mode" defaultValue="none">
                  <option value="none">Local-first</option>
                  <option value="supabase">Supabase planned</option>
                  <option value="firebase">Firebase planned</option>
                  <option value="custom_api">Custom API planned</option>
                </Select>
              </div>
              <div>
                <Label>Monetization</Label>
                <Select name="monetization_mode" defaultValue="freemium">
                  <option value="none">None</option>
                  <option value="freemium">Freemium</option>
                  <option value="subscription">Subscription</option>
                  <option value="iap">IAP</option>
                  <option value="ads">Ads</option>
                </Select>
              </div>
              <label className="flex min-h-10 items-center gap-2 rounded-md border border-border bg-background px-3 text-sm">
                <input name="iap_enabled" type="checkbox" />
                IAP
              </label>
              <label className="flex min-h-10 items-center gap-2 rounded-md border border-border bg-background px-3 text-sm">
                <input name="subscription_enabled" type="checkbox" defaultChecked />
                Subscription
              </label>
              <label className="flex min-h-10 items-center gap-2 rounded-md border border-border bg-background px-3 text-sm">
                <input name="ads_enabled" type="checkbox" />
                Ads
              </label>
              <div>
                <Label>Policy</Label>
                <Select name="policy_strictness" defaultValue="standard">
                  <option value="standard">Standard</option>
                  <option value="strict">Strict</option>
                </Select>
              </div>
              <div>
                <Label>Max cost</Label>
                <Input name="max_cost_usd" type="number" min="0" step="0.01" defaultValue="5" />
              </div>
              <div>
                <Label>Max runtime minutes</Label>
                <Input name="max_runtime_minutes" type="number" min="5" max="720" defaultValue="60" />
              </div>
              <div>
                <Label>Quality threshold</Label>
                <Input name="quality_threshold" type="number" min="0" max="100" defaultValue="75" />
              </div>
            </div>
            <Button type="submit" disabled={saving}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bot size={16} />}
              {saving ? "Creating..." : "Create brief"}
            </Button>
          </form>
        </Card>

        <div className="space-y-5">
          <Card>
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="text-base font-semibold">Brief Queue</h2>
              <Badge>{briefs.length} brief(s)</Badge>
            </div>
            {loading && !briefs.length ? <Skeleton className="h-40" /> : null}
            <div className="space-y-3">
              {briefs.map((brief) => (
                <button
                  key={brief.id}
                  type="button"
                  onClick={() => {
                    setSelectedId(brief.id);
                    load(brief.id).catch(console.error);
                  }}
                  className={`block w-full rounded-md border p-3 text-left transition hover:bg-muted ${selected?.id === brief.id ? "border-primary bg-background" : "border-border bg-background"}`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="font-medium">{brief.title}</div>
                    <StatusBadge status={brief.status} />
                  </div>
                  <div className="mt-1 text-sm text-muted-foreground">{brief.raw_prompt}</div>
                  <div className="mt-2 text-xs text-muted-foreground">{formatDate(brief.updated_at)}</div>
                </button>
              ))}
              {!briefs.length && !loading ? <div className="rounded-md bg-muted p-4 text-sm text-muted-foreground">No factory briefs yet.</div> : null}
            </div>
          </Card>

          {selected ? (
            <Card>
              <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <div className="mb-2 flex flex-wrap gap-2">
                    <StatusBadge status={selected.status} />
                    <Badge>{selected.mode}</Badge>
                    <Badge>{selected.target_platforms.join(", ")}</Badge>
                  </div>
                  <h2 className="text-lg font-semibold">{selected.title}</h2>
                  <p className="mt-1 text-sm text-muted-foreground">{selected.raw_prompt}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button type="button" onClick={() => startBrief(selected.id)} disabled={startingId === selected.id}>
                    {startingId === selected.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play size={16} />}
                    Start
                  </Button>
                  {selected.selected_project_id ? (
                    <Link className="inline-flex min-h-10 items-center gap-2 rounded-md border border-border bg-card px-4 py-2 text-sm font-medium hover:bg-muted" href={`/projects/${selected.selected_project_id}`}>
                      <Rocket size={16} />
                      Open project
                    </Link>
                  ) : null}
                </div>
              </div>

              <div className="mb-5 grid gap-3 md:grid-cols-4">
                <Metric label="Findings" value={String(selected.findings.length)} />
                <Metric label="Candidates" value={String(selected.candidates.length)} />
                <Metric label="Top score" value={topCandidate ? `${topCandidate.opportunity_score}` : "-"} />
                <Metric label="Selected" value={selectedCandidate ? "yes" : "no"} />
              </div>

              <div className="grid gap-5 xl:grid-cols-[0.8fr_1.2fr]">
                <div>
                  <h3 className="mb-3 text-sm font-semibold">Factory Timeline</h3>
                  <div className="mb-5 space-y-3">
                    {events.map((event) => (
                      <div key={event.id} className="rounded-md border border-border bg-background p-3">
                        <div className="mb-1 flex flex-wrap items-center gap-2">
                          <Badge tone={event.level === "success" ? "success" : event.level === "warning" ? "warning" : event.level === "error" || event.level === "danger" ? "danger" : "neutral"}>{event.level}</Badge>
                          <span className="text-xs text-muted-foreground">{formatDate(event.created_at)}</span>
                        </div>
                        <div className="font-medium">{event.title}</div>
                        <p className="mt-1 text-sm text-muted-foreground">{event.message}</p>
                      </div>
                    ))}
                    {!events.length ? <div className="rounded-md bg-muted p-4 text-sm text-muted-foreground">Timeline events appear as the worker processes this brief.</div> : null}
                  </div>
                  <h3 className="mb-3 text-sm font-semibold">Research Findings</h3>
                  <div className="space-y-3">
                    {selected.findings.map((finding) => (
                      <div key={finding.id} className="rounded-md border border-border bg-background p-3">
                        <div className="mb-2 flex flex-wrap items-center gap-2">
                          <Badge>{finding.source}</Badge>
                          <Badge tone={finding.confidence_score >= 70 ? "success" : "warning"}>{finding.confidence_score}/100</Badge>
                        </div>
                        <div className="font-medium">{finding.title}</div>
                        <p className="mt-1 text-sm text-muted-foreground">{finding.summary}</p>
                      </div>
                    ))}
                    {!selected.findings.length ? <div className="rounded-md bg-muted p-4 text-sm text-muted-foreground">Research has not run yet.</div> : null}
                  </div>
                </div>

                <div>
                  <h3 className="mb-3 text-sm font-semibold">Opportunity Candidates</h3>
                  <div className="space-y-3">
                    {selected.candidates.map((candidate) => (
                      <div key={candidate.id} className="rounded-md border border-border bg-background p-4">
                        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge tone={candidate.status === "selected" ? "success" : "neutral"}>{candidate.status}</Badge>
                            <Badge tone={candidate.opportunity_score >= 75 ? "success" : "warning"}>{candidate.opportunity_score}/100</Badge>
                          </div>
                          <Button type="button" variant="secondary" onClick={() => finalize(selected.id, candidate.id)} disabled={Boolean(finalizingId) || Boolean(selected.selected_project_id)}>
                            {finalizingId === candidate.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 size={15} />}
                            Select
                          </Button>
                        </div>
                        <div className="font-medium">{candidate.title}</div>
                        <p className="mt-1 text-sm text-muted-foreground">{candidate.description}</p>
                        <div className="mt-3 grid gap-2 text-sm md:grid-cols-2">
                          <Score label="Demand" value={candidate.demand_score} />
                          <Score label="Pain" value={candidate.pain_score} />
                          <Score label="Feasibility" value={candidate.build_feasibility_score} />
                          <Score label="Originality" value={candidate.originality_score} />
                        </div>
                      </div>
                    ))}
                    {!selected.candidates.length ? <div className="rounded-md bg-muted p-4 text-sm text-muted-foreground">Candidates appear after the worker processes the brief.</div> : null}
                  </div>
                </div>
              </div>
            </Card>
          ) : null}
        </div>
      </div>
    </>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-background p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-xl font-semibold">{value}</div>
    </div>
  );
}

function Score({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-sm bg-muted px-3 py-2">
      <span>{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}
