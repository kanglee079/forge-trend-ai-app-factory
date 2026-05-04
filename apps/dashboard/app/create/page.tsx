"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, Loader2, Play, Sparkles } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";
import { Badge, Button, Card, Input, Label, Notice, PageHeader, Select, Textarea } from "@/components/ui";

const steps = ["stepIdea", "stepGoal", "stepMoney", "stepTech", "stepConfirm"] as const;

const initialForm = {
  mode: "manual_idea",
  raw_prompt: "",
  title: "",
  target_category: "Education",
  target_user: "",
  target_country: "VN",
  target_language: "vi",
  complexity: "medium",
  monetization_mode: "none",
  backend_mode: "offline_first",
};

export default function CreateAppPage() {
  const router = useRouter();
  const { t } = useLanguage();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState(initialForm);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<{ tone: "success" | "danger" | "warning"; message: string } | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("mode") === "auto_trend") {
      setForm((current) => ({ ...current, mode: "auto_trend" }));
    }
  }, []);

  const summaryPrompt = useMemo(() => {
    const target = form.target_user ? `\nNgười dùng mục tiêu: ${form.target_user}` : "";
    return `${form.raw_prompt.trim()}${target}\nDanh mục: ${form.target_category}. Quốc gia: ${form.target_country}. Ngôn ngữ: ${form.target_language}. Kiếm tiền: ${form.monetization_mode}. Backend: ${form.backend_mode}.`;
  }, [form]);

  function update(name: keyof typeof form, value: string) {
    setForm((current) => ({ ...current, [name]: value }));
  }

  function next() {
    if (step === 0 && !form.raw_prompt.trim()) {
      setNotice({ tone: "warning", message: "Hãy nhập ý tưởng app trước khi tiếp tục." });
      return;
    }
    setNotice(null);
    setStep((current) => Math.min(steps.length - 1, current + 1));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (saving) return;
    setSaving(true);
    setNotice(null);
    try {
      const brief = await api.createFactoryBrief({
        mode: form.mode,
        title: form.title.trim() || defaultTitle(form.raw_prompt),
        raw_prompt: summaryPrompt,
        target_category: form.target_category,
        target_platforms: ["android"],
        target_country: form.target_country,
        target_language: form.target_language,
        monetization_mode: form.monetization_mode,
        iap_enabled: form.monetization_mode === "iap" || form.monetization_mode === "hybrid",
        subscription_enabled: form.monetization_mode === "subscription" || form.monetization_mode === "hybrid",
        ads_enabled: form.monetization_mode === "ads" || form.monetization_mode === "hybrid",
        backend_mode: form.backend_mode,
        complexity: form.complexity,
        max_cost_usd: 5,
        max_runtime_minutes: form.complexity === "large" ? 120 : 60,
        quality_threshold: 75,
        policy_strictness: "standard",
      });
      await api.startFactoryBrief(brief.id);
      setNotice({ tone: "success", message: t("appQueued") });
      router.push("/factory");
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Không thể tạo app." });
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <PageHeader title={t("createWizardTitle")} description={t("createWizardDescription")} />
      {notice ? <Notice tone={notice.tone}>{notice.message}</Notice> : null}
      <Notice tone="neutral">{t("createHelper")}</Notice>

      <div className="mb-5 grid gap-2 md:grid-cols-5">
        {steps.map((key, index) => (
          <button
            key={key}
            type="button"
            onClick={() => setStep(index)}
            className={`flex min-h-11 items-center gap-2 rounded-md border px-3 text-sm ${step === index ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card"}`}
          >
            {index < step ? <CheckCircle2 size={16} /> : <span className="flex h-5 w-5 items-center justify-center rounded-full border text-xs">{index + 1}</span>}
            {t(key)}
          </button>
        ))}
      </div>

      <form onSubmit={submit} className="grid gap-5 xl:grid-cols-[1fr_0.75fr]">
        <Card>
          {step === 0 ? (
            <div className="space-y-4">
              <div>
                <Label>{t("ideaQuestion")}</Label>
                <Textarea value={form.raw_prompt} onChange={(event) => update("raw_prompt", event.target.value)} placeholder={t("ideaPlaceholder")} className="min-h-40" required />
              </div>
              <div>
                <Label>{t("appTitle")}</Label>
                <Input value={form.title} onChange={(event) => update("title", event.target.value)} placeholder="ForgeTrend sẽ tự đặt tên nếu bỏ trống" />
              </div>
              <div>
                <Label>Mode</Label>
                <Select value={form.mode} onChange={(event) => update("mode", event.target.value)}>
                  <option value="manual_idea">{t("startModeManual")}</option>
                  <option value="auto_trend">{t("startModeTrend")}</option>
                </Select>
              </div>
            </div>
          ) : null}

          {step === 1 ? (
            <div className="grid gap-4 md:grid-cols-2">
              <FieldSelect label={t("category")} value={form.target_category} onChange={(value) => update("target_category", value)} options={["Education", "Productivity", "Utility", "Health", "Finance", "Lifestyle", "Other"]} />
              <div>
                <Label>{t("targetUser")}</Label>
                <Input value={form.target_user} onChange={(event) => update("target_user", event.target.value)} placeholder={t("targetUserPlaceholder")} />
              </div>
              <FieldSelect label={t("country")} value={form.target_country} onChange={(value) => update("target_country", value)} options={["VN", "US"]} />
              <FieldSelect label={t("appLanguage")} value={form.target_language} onChange={(value) => update("target_language", value)} options={["vi", "en"]} />
              <FieldSelect label={t("complexity")} value={form.complexity} onChange={(value) => update("complexity", value)} options={["small", "medium", "large"]} />
            </div>
          ) : null}

          {step === 2 ? <FieldSelect label={t("monetization")} value={form.monetization_mode} onChange={(value) => update("monetization_mode", value)} options={["none", "iap", "subscription", "ads", "hybrid"]} /> : null}
          {step === 3 ? <FieldSelect label={t("backendMode")} value={form.backend_mode} onChange={(value) => update("backend_mode", value)} options={["offline_first", "firebase", "supabase", "none"]} /> : null}

          {step === 4 ? (
            <div className="space-y-4">
              <h2 className="text-base font-semibold">{t("wizardSummary")}</h2>
              <p className="whitespace-pre-line text-sm text-muted-foreground">{summaryPrompt}</p>
              <div className="grid gap-2 md:grid-cols-2">
                <CheckLine>{t("willCreate")}</CheckLine>
                <CheckLine>{t("appWillTest")}</CheckLine>
                <CheckLine>{t("codexMaybe")}</CheckLine>
                <CheckLine>{t("researchMaybe")}</CheckLine>
                <CheckLine>{t("estimatedTime")}</CheckLine>
                <CheckLine>{t("humanApprovalRequired")}</CheckLine>
              </div>
            </div>
          ) : null}

          <div className="mt-6 flex flex-wrap justify-between gap-2">
            <Button type="button" variant="secondary" onClick={() => setStep((current) => Math.max(0, current - 1))} disabled={step === 0 || saving}>{t("back")}</Button>
            {step < steps.length - 1 ? (
              <Button type="button" onClick={next}>{t("next")}</Button>
            ) : (
              <Button type="submit" disabled={saving}>
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play size={16} />}
                {saving ? t("creatingApp") : t("startCreatingApp")}
              </Button>
            )}
          </div>
        </Card>

        <Card>
          <div className="mb-3 flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            <h2 className="text-base font-semibold">{t("wizardSummary")}</h2>
          </div>
          <div className="space-y-3 text-sm">
            <Summary label={t("stepIdea")} value={form.title || defaultTitle(form.raw_prompt)} />
            <Summary label={t("category")} value={form.target_category} />
            <Summary label={t("country")} value={form.target_country} />
            <Summary label={t("appLanguage")} value={form.target_language} />
            <Summary label={t("monetization")} value={form.monetization_mode} />
            <Summary label={t("backendMode")} value={form.backend_mode} />
          </div>
        </Card>
      </form>
    </>
  );
}

function defaultTitle(prompt: string) {
  const compact = prompt.trim().replace(/\s+/g, " ");
  return compact ? compact.slice(0, 58) : "App mới từ ForgeTrend";
}

function FieldSelect({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (value: string) => void }) {
  return (
    <div>
      <Label>{label}</Label>
      <Select value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => <option key={option} value={option}>{option}</option>)}
      </Select>
    </div>
  );
}

function CheckLine({ children }: { children: React.ReactNode }) {
  return <div className="flex gap-2 rounded-md border border-border bg-background p-3 text-sm"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" /><span>{children}</span></div>;
}

function Summary({ label, value }: { label: string; value: string }) {
  return <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-background px-3 py-2"><span className="text-muted-foreground">{label}</span><Badge>{value || "-"}</Badge></div>;
}
