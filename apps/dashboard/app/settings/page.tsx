"use client";

import { FormEvent, useEffect, useState } from "react";
import { Loader2, RefreshCw, Save } from "lucide-react";
import { api, ApiError, AppSettings } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { useFeedback } from "@/components/feedback";
import { Badge, Button, Card, Input, Label, Notice, PageHeader, Select, Skeleton } from "@/components/ui";
import { useLanguage } from "@/lib/i18n";

export default function SettingsPage() {
  const feedback = useFeedback();
  const { language, setLanguage, t } = useLanguage();
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<{ tone: "success" | "danger"; message: string } | null>(null);

  async function load() {
    setLoading(true);
    try {
      setSettings(await api.settings());
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Could not load settings." });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load().catch(console.error);
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!settings || saving) return;
    const form = new FormData(event.currentTarget);
    const daily = Number(form.get("daily_budget_usd") || 0);
    const monthly = Number(form.get("monthly_budget_usd") || 0);
    if (daily < 0 || monthly < 0 || daily > monthly) {
      setNotice({ tone: "danger", message: "Budget values must be non-negative, and daily budget cannot exceed monthly budget." });
      return;
    }
    setSaving(true);
    try {
      const updated = await api.updateSettings({
        default_provider: form.get("default_provider"),
        default_model: form.get("default_model"),
        max_fix_iterations: Number(form.get("max_fix_iterations") || 0),
        workspace_root: form.get("workspace_root"),
        auto_refresh_seconds: Number(form.get("auto_refresh_seconds") || 5),
        notifications_enabled: form.get("notifications_enabled") === "on",
        theme: form.get("theme"),
        daily_budget_usd: daily,
        monthly_budget_usd: monthly,
        default_language: form.get("default_language"),
        feature_flags: {
          trend_radar: form.get("trend_radar") === "on",
          provider_key_network_test: form.get("provider_key_network_test") === "on",
          minio_artifacts: form.get("minio_artifacts") === "on",
          release_approval: form.get("release_approval") === "on",
        },
      });
      setSettings(updated);
      const nextLanguage = form.get("default_language");
      if (nextLanguage === "vi" || nextLanguage === "en") setLanguage(nextLanguage);
      feedback.notify({ tone: "success", message: "Settings saved." });
      setNotice({ tone: "success", message: "Settings saved. Worker max fix iterations apply to new pipeline runs." });
    } catch (error) {
      feedback.notify({ tone: "danger", message: error instanceof ApiError ? error.detail : "Could not save settings." });
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Settings"
        description={t("settingsHelpVi")}
        action={
          <Button type="button" variant="secondary" onClick={() => load()} disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw size={16} />}
            Refresh
          </Button>
        }
      />
      {notice ? <Notice tone={notice.tone}>{notice.message}</Notice> : null}
      {!settings && loading ? <SettingsSkeleton /> : null}
      {settings ? (
        <form onSubmit={submit} className="space-y-5">
          <Card>
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="text-base font-semibold">Agent Defaults</h2>
              <Badge>Updated {formatDate(settings.updated_at)}</Badge>
            </div>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <div>
                <Label>Default provider</Label>
                <Select name="default_provider" defaultValue={settings.default_provider}>
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="google">Google</option>
                  <option value="openrouter">OpenRouter</option>
                  <option value="local">Local</option>
                </Select>
              </div>
              <div>
                <Label>Default model</Label>
                <Input name="default_model" defaultValue={settings.default_model} placeholder="gpt-5.2" />
              </div>
              <div>
                <Label>Max fix iterations</Label>
                <Input name="max_fix_iterations" type="number" min="0" max="20" defaultValue={settings.max_fix_iterations} />
              </div>
              <div>
                <Label>Workspace root</Label>
                <Input name="workspace_root" defaultValue={settings.workspace_root} placeholder="workspaces" />
              </div>
            </div>
          </Card>

          <Card>
            <h2 className="mb-4 text-base font-semibold">Dashboard Preferences</h2>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <div>
                <Label>{t("languageSetting")}</Label>
                <Select name="default_language" defaultValue={settings.default_language || language}>
                  <option value="vi">{t("languageVietnamese")}</option>
                  <option value="en">{t("languageEnglish")}</option>
                </Select>
              </div>
              <div>
                <Label>Auto refresh seconds</Label>
                <Input name="auto_refresh_seconds" type="number" min="2" max="60" defaultValue={settings.auto_refresh_seconds} />
              </div>
              <div>
                <Label>Theme preference</Label>
                <Select name="theme" defaultValue={settings.theme}>
                  <option value="system">System</option>
                  <option value="light">Light</option>
                  <option value="dark">Dark</option>
                </Select>
              </div>
              <label className="flex min-h-10 items-center gap-2 self-end rounded-md border border-border bg-background px-3 text-sm">
                <input name="notifications_enabled" type="checkbox" defaultChecked={settings.notifications_enabled} />
                Notifications enabled
              </label>
            </div>
          </Card>

          <Card>
            <h2 className="mb-4 text-base font-semibold">Budgets</h2>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label>Default daily budget</Label>
                <Input name="daily_budget_usd" type="number" min="0" step="0.01" defaultValue={settings.daily_budget_usd} />
              </div>
              <div>
                <Label>Default monthly budget</Label>
                <Input name="monthly_budget_usd" type="number" min="0" step="0.01" defaultValue={settings.monthly_budget_usd} />
              </div>
            </div>
          </Card>

          <Card>
            <h2 className="mb-4 text-base font-semibold">Feature Flags</h2>
            <div className="grid gap-3 md:grid-cols-2">
              {[
                ["trend_radar", "Trend radar"],
                ["provider_key_network_test", "Provider network key test"],
                ["minio_artifacts", "MinIO artifact links"],
                ["release_approval", "Release approval gate"],
              ].map(([key, label]) => (
                <label key={key} className="flex min-h-10 items-center justify-between gap-3 rounded-md border border-border bg-background px-3 text-sm">
                  <span>{label}</span>
                  <input name={key} type="checkbox" defaultChecked={Boolean(settings.feature_flags[key])} />
                </label>
              ))}
            </div>
          </Card>

          <Button type="submit" disabled={saving}>
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save size={16} />}
            {saving ? "Saving..." : "Save settings"}
          </Button>
        </form>
      ) : null}
    </>
  );
}

function SettingsSkeleton() {
  return (
    <div className="space-y-5">
      <Skeleton className="h-40" />
      <Skeleton className="h-32" />
      <Skeleton className="h-32" />
    </div>
  );
}
