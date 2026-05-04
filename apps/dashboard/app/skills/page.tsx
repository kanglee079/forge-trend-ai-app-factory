"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2, Play, RefreshCw, ScanSearch } from "lucide-react";
import { api, ApiError, SkillPack } from "@/lib/api";
import { Badge, Button, Card, Label, Notice, PageHeader, Textarea } from "@/components/ui";

export default function SkillsPage() {
  const [skills, setSkills] = useState<SkillPack[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);
  const [renderedPrompt, setRenderedPrompt] = useState("");
  const [contextSummary, setContextSummary] = useState<{ prompt_fragments: Array<Record<string, unknown>>; context_packs: Array<Record<string, unknown>>; token_budget_decision: Record<string, unknown> } | null>(null);
  const [notice, setNotice] = useState<{ tone: "success" | "danger" | "warning" | "neutral"; message: string } | null>(null);

  async function load() {
    setLoading(true);
    try {
      const items = await api.skillPacks();
      setSkills(items);
      setSelectedId((current) => current ?? items[0]?.id ?? null);
      setContextSummary(await api.promptContextSummary().catch(() => null));
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Không tải được Skill Marketplace." });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load().catch(console.error); }, []);

  const selected = useMemo(() => skills.find((item) => item.id === selectedId) ?? skills[0] ?? null, [skills, selectedId]);
  const categories = useMemo(() => Array.from(new Set(skills.map((item) => item.category))).sort(), [skills]);

  async function scanInstalled() {
    setLoading(true);
    try {
      const items = await api.scanInstalledSkills();
      setSkills(items);
      setNotice({ tone: "success", message: "Đã scan skills/ và đồng bộ skill pack built-in." });
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Không scan được skill." });
    } finally {
      setLoading(false);
    }
  }

  async function toggleSkill(skill: SkillPack) {
    const updated = await api.updateSkillPack(skill.id, { enabled: !skill.enabled });
    setSkills((current) => current.map((item) => item.id === updated.id ? updated : item));
  }

  async function testSkill() {
    if (!selected) return;
    setTesting(true);
    try {
      const result = await api.testSkillPack(selected.id, {
        sample_input: {
          app_name: "Học HSK Mỗi Ngày",
          app_context: "App học tiếng Trung cho người Việt, local-first, có subscription mô phỏng.",
          qa_error: "flutter analyze failed",
        },
      });
      setRenderedPrompt(result.rendered_prompt);
      setNotice({ tone: "success", message: `Prompt render khoảng ${result.estimated_tokens} token thô.` });
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Không test được skill." });
    } finally {
      setTesting(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Skill / Prompt Marketplace"
        description="Nơi ForgeTrend chọn prompt ngắn, đúng ngữ cảnh để tiết kiệm token và tạo output ổn định hơn."
        action={
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="secondary" onClick={load} disabled={loading}>{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw size={16} />}Làm mới</Button>
            <Button type="button" onClick={scanInstalled} disabled={loading}><ScanSearch size={16} />Scan installed skills</Button>
          </div>
        }
      />
      {notice ? <Notice tone={notice.tone}>{notice.message}</Notice> : null}

      <div className="grid gap-5 xl:grid-cols-[320px_1fr]">
        <Card>
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="text-sm font-semibold">Skill packs</h2>
            <Badge>{skills.length}</Badge>
          </div>
          <div className="mb-3">
            <Label>Nhóm đang có</Label>
            <div className="flex flex-wrap gap-1">
              {categories.map((category) => <Badge key={category}>{category}</Badge>)}
            </div>
          </div>
          <div className="space-y-2">
            {skills.map((skill) => (
              <button
                key={skill.id}
                type="button"
                onClick={() => setSelectedId(skill.id)}
                className={`w-full rounded-md border px-3 py-2 text-left text-sm transition hover:bg-muted ${selected?.id === skill.id ? "border-primary bg-background" : "border-border bg-background"}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{skill.name}</span>
                  <Badge tone={skill.enabled ? "success" : "warning"}>{skill.enabled ? "on" : "off"}</Badge>
                </div>
                <div className="mt-1 text-xs text-muted-foreground">{skill.category} · {skill.token_budget} token</div>
              </button>
            ))}
          </div>
        </Card>

        {selected ? (
          <div className="space-y-5">
            <Card>
              <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <div className="mb-2 flex flex-wrap gap-2">
                    <Badge>{selected.slug}</Badge>
                    <Badge>{selected.category}</Badge>
                    <Badge tone={selected.quality_score >= 75 ? "success" : "warning"}>{selected.quality_score}/100</Badge>
                  </div>
                  <h2 className="text-lg font-semibold">{selected.name}</h2>
                  <p className="mt-1 text-sm text-muted-foreground">{selected.description}</p>
                </div>
                <Button type="button" variant={selected.enabled ? "secondary" : "primary"} onClick={() => toggleSkill(selected)}>
                  {selected.enabled ? "Tắt skill" : "Bật skill"}
                </Button>
              </div>
              <div className="grid gap-3 md:grid-cols-4">
                <Metric label="Version" value={selected.version} />
                <Metric label="Source" value={selected.source_type} />
                <Metric label="Prompt" value={String(selected.prompts.length)} />
                <Metric label="Token budget" value={String(selected.token_budget)} />
              </div>
            </Card>

            <Card>
              <div className="mb-3 flex items-center justify-between gap-3">
                <h2 className="text-base font-semibold">Prompt templates</h2>
                <Button type="button" variant="secondary" onClick={testSkill} disabled={testing}>{testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play size={16} />}Test sample</Button>
              </div>
              <div className="space-y-3">
                {selected.prompts.map((prompt) => (
                  <div key={prompt.id} className="rounded-md border border-border bg-background p-3">
                    <div className="mb-2 flex flex-wrap gap-2">
                      <Badge>{prompt.name}</Badge>
                      <Badge>{prompt.token_budget} token</Badge>
                    </div>
                    <div className="text-sm font-medium">{prompt.purpose}</div>
                    <p className="mt-1 text-sm text-muted-foreground">{prompt.when_to_use}</p>
                    <pre className="mt-3 max-h-56 overflow-auto rounded-md bg-muted p-3 text-xs whitespace-pre-wrap">{prompt.prompt_template}</pre>
                  </div>
                ))}
              </div>
            </Card>

            {renderedPrompt ? (
              <Card>
                <Label>Rendered prompt sample</Label>
                <Textarea value={renderedPrompt} readOnly className="min-h-56 font-mono" />
              </Card>
            ) : null}

            <Card>
              <div className="mb-3 flex items-center justify-between gap-3">
                <h2 className="text-base font-semibold">Prompt compression / context packs</h2>
                <Badge>{contextSummary?.context_packs.length ?? 0} packs</Badge>
              </div>
              <p className="mb-3 text-sm text-muted-foreground">
                Worker ghi context pack khi research, PRD, UX và code agent chuẩn bị prompt. Token planner dùng summary khi context lớn.
              </p>
              <div className="grid gap-2 md:grid-cols-2">
                {(contextSummary?.prompt_fragments ?? []).slice(0, 8).map((fragment) => (
                  <div key={String(fragment.slug)} className="rounded-md border border-border bg-background p-3 text-sm">
                    <div className="font-medium">{String(fragment.slug)}</div>
                    <div className="mt-1 text-xs text-muted-foreground">{String(fragment.category)} · {String(fragment.token_estimate)} token</div>
                  </div>
                ))}
              </div>
              {contextSummary?.token_budget_decision ? (
                <pre className="mt-3 overflow-auto rounded-md bg-muted p-3 text-xs">{JSON.stringify(contextSummary.token_budget_decision, null, 2)}</pre>
              ) : null}
            </Card>
          </div>
        ) : (
          <Notice tone="warning">Chưa có skill pack nào. Bấm Scan installed skills để tạo built-in pack.</Notice>
        )}
      </div>
    </>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-background p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 break-words text-sm font-semibold">{value}</div>
    </div>
  );
}
