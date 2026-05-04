"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Play, Sparkles } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";
import { Badge, Button, Card, Input, Label, Notice, PageHeader, Select, Textarea } from "@/components/ui";

const presets = [
  { label: "App học ngoại ngữ", prompt: "Tạo app học ngoại ngữ cho người Việt, có bài học ngắn, ôn từ vựng, streak và nhắc lại từ khó.", category: "Education" },
  { label: "App quản lý thói quen", prompt: "Tạo app quản lý thói quen hằng ngày, có checklist, streak, biểu đồ tuần và nhắc nhở mô phỏng.", category: "Lifestyle" },
  { label: "App checklist công việc", prompt: "Tạo app checklist công việc theo dự án, có danh mục, trạng thái hoàn thành, lịch sử và reset có xác nhận.", category: "Productivity" },
  { label: "App tính toán tiện ích", prompt: "Tạo app tính toán tiện ích đơn giản, có form nhập liệu, kết quả, lịch sử và cài đặt riêng tư.", category: "Utility" },
  { label: "App theo dõi chi tiêu", prompt: "Tạo app theo dõi chi tiêu cá nhân, có nhập khoản chi, nhóm chi phí, tổng quan tháng và cảnh báo ngân sách.", category: "Finance" },
  { label: "App tạo nội dung AI", prompt: "Tạo app hỗ trợ lên ý tưởng nội dung cho người bán hàng online, có brief, draft, lịch sử và export placeholder.", category: "Productivity" },
  { label: "App dành cho học sinh/sinh viên", prompt: "Tạo app lập kế hoạch học tập cho học sinh sinh viên, có môn học, deadline, tiến độ và lịch sử ôn tập.", category: "Education" },
  { label: "App cho người bán hàng online", prompt: "Tạo app quản lý việc bán hàng online, có checklist đơn, tồn kho đơn giản, ghi chú khách và lịch sử xử lý.", category: "Utility" },
];

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
  max_cost_usd: "5",
  policy_strictness: "standard",
};

export default function CreateAppPage() {
  const router = useRouter();
  const { t } = useLanguage();
  const [form, setForm] = useState(initialForm);
  const [showMore, setShowMore] = useState(false);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<{ tone: "success" | "danger" | "warning"; message: string } | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("mode") === "auto_trend") setForm((current) => ({ ...current, mode: "auto_trend" }));
  }, []);

  const summaryPrompt = useMemo(() => {
    const parts = [
      form.raw_prompt.trim(),
      form.target_user ? `Người dùng mục tiêu: ${form.target_user}` : "",
      `Danh mục: ${form.target_category}`,
      `Quốc gia: ${form.target_country}`,
      `Ngôn ngữ: ${form.target_language}`,
      `Kiếm tiền: ${form.monetization_mode}`,
      `Backend: ${form.backend_mode}`,
    ].filter(Boolean);
    return parts.join("\n");
  }, [form]);

  function update(name: keyof typeof form, value: string) {
    setForm((current) => ({ ...current, [name]: value }));
  }

  function applyPreset(preset: (typeof presets)[number]) {
    setForm((current) => ({ ...current, raw_prompt: preset.prompt, target_category: preset.category, target_language: "vi", target_country: "VN" }));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (saving) return;
    if (!form.raw_prompt.trim()) {
      setNotice({ tone: "warning", message: "Hãy nhập ý tưởng app trước khi tạo." });
      return;
    }
    setSaving(true);
    setNotice(null);
    try {
      const monetized = form.monetization_mode !== "none";
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
        subscription_enabled: form.monetization_mode === "subscription" || form.monetization_mode === "hybrid" || monetized,
        ads_enabled: form.monetization_mode === "ads" || form.monetization_mode === "hybrid",
        backend_mode: form.backend_mode,
        complexity: form.complexity,
        max_cost_usd: Number(form.max_cost_usd || 5),
        max_runtime_minutes: form.complexity === "large" ? 120 : 60,
        quality_threshold: 75,
        policy_strictness: form.policy_strictness,
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
      <PageHeader title={t("createWizardTitle")} description="Chỉ cần nhập ý tưởng. Các tuỳ chọn kỹ thuật đã được ẩn trong phần mở rộng." />
      {notice ? <Notice tone={notice.tone}>{notice.message}</Notice> : null}

      <form onSubmit={submit} className="grid gap-5 xl:grid-cols-[1fr_0.75fr]">
        <Card>
          <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-base font-semibold">{t("basicCreate")}</h2>
              <p className="text-sm text-muted-foreground">Người dùng phổ thông có thể tạo app trong dưới 60 giây.</p>
            </div>
            <Badge tone="success">Simple Mode</Badge>
          </div>

          <div className="space-y-4">
            <div>
              <Label>{t("ideaQuestion")}</Label>
              <Textarea value={form.raw_prompt} onChange={(event) => update("raw_prompt", event.target.value)} placeholder={t("ideaPlaceholder")} className="min-h-40" required />
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <FieldSelect label={t("appLanguage")} value={form.target_language} onChange={(value) => update("target_language", value)} options={[["vi", t("languageVietnamese")], ["en", t("languageEnglish")]]} />
              <FieldSelect label="Có kiếm tiền không?" value={form.monetization_mode === "none" ? "none" : "subscription"} onChange={(value) => update("monetization_mode", value)} options={[["none", t("noMonetization")], ["subscription", "Có, subscription mô phỏng"]]} />
            </div>
            <Button type="submit" disabled={saving}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play size={16} />}
              {saving ? t("creatingApp") : t("startCreatingApp")}
            </Button>
          </div>

          <div className="mt-6">
            <button type="button" className="text-sm font-medium text-primary" onClick={() => setShowMore((current) => !current)}>
              {showMore ? "Ẩn tuỳ chọn thêm" : t("moreOptions")}
            </button>
            {showMore ? (
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <div><Label>{t("appTitle")}</Label><Input value={form.title} onChange={(event) => update("title", event.target.value)} placeholder="ForgeTrend tự đặt tên nếu bỏ trống" /></div>
                <FieldSelect label="Mode" value={form.mode} onChange={(value) => update("mode", value)} options={[["manual_idea", t("startModeManual")], ["auto_trend", t("startModeTrend")]]} />
                <FieldSelect label={t("category")} value={form.target_category} onChange={(value) => update("target_category", value)} options={["Education", "Productivity", "Utility", "Health", "Finance", "Lifestyle", "Other"].map((item) => [item, item])} />
                <div><Label>{t("targetUser")}</Label><Input value={form.target_user} onChange={(event) => update("target_user", event.target.value)} placeholder={t("targetUserPlaceholder")} /></div>
                <FieldSelect label={t("country")} value={form.target_country} onChange={(value) => update("target_country", value)} options={[["VN", t("vietnam")], ["US", t("unitedStates")]]} />
                <FieldSelect label={t("backendMode")} value={form.backend_mode} onChange={(value) => update("backend_mode", value)} options={[["offline_first", t("offlineFirst")], ["firebase", t("firebasePlaceholder")], ["supabase", t("supabasePlaceholder")], ["none", t("noBackend")]]} />
                <FieldSelect label={t("complexity")} value={form.complexity} onChange={(value) => update("complexity", value)} options={[["small", t("simple")], ["medium", t("medium")], ["large", t("advanced")]]} />
                <div><Label>Budget tối đa</Label><Input value={form.max_cost_usd} type="number" min="0" step="0.01" onChange={(event) => update("max_cost_usd", event.target.value)} /></div>
              </div>
            ) : null}
          </div>
        </Card>

        <div className="space-y-5">
          <Card>
            <div className="mb-3 flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" />
              <h2 className="text-base font-semibold">{t("presets")}</h2>
            </div>
            <div className="grid gap-2">
              {presets.map((preset) => (
                <button key={preset.label} type="button" onClick={() => applyPreset(preset)} className="rounded-md border border-border bg-background px-3 py-2 text-left text-sm hover:bg-muted">
                  {preset.label}
                </button>
              ))}
            </div>
          </Card>
          <Card>
            <h2 className="mb-3 text-base font-semibold">{t("wizardSummary")}</h2>
            <div className="space-y-3 text-sm">
              <Summary label={t("stepIdea")} value={form.title || defaultTitle(form.raw_prompt)} />
              <Summary label={t("category")} value={form.target_category} />
              <Summary label={t("appLanguage")} value={form.target_language} />
              <Summary label={t("monetization")} value={form.monetization_mode} />
              <Summary label={t("backendMode")} value={form.backend_mode} />
            </div>
            <Notice tone="neutral" className="mt-4 mb-0">{t("humanApprovalRequired")}</Notice>
          </Card>
        </div>
      </form>
    </>
  );
}

function defaultTitle(prompt: string) {
  const compact = prompt.trim().replace(/\s+/g, " ");
  return compact ? compact.slice(0, 58) : "App mới từ ForgeTrend";
}

function FieldSelect({ label, value, options, onChange }: { label: string; value: string; options: string[][]; onChange: (value: string) => void }) {
  return (
    <div>
      <Label>{label}</Label>
      <Select value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map(([option, text]) => <option key={option} value={option}>{text}</option>)}
      </Select>
    </div>
  );
}

function Summary({ label, value }: { label: string; value: string }) {
  return <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-background px-3 py-2"><span className="text-muted-foreground">{label}</span><Badge>{value || "-"}</Badge></div>;
}
