"use client";

import { FormEvent, useEffect, useState } from "react";
import { Loader2, Plus, Power, TestTube2, Trash2 } from "lucide-react";
import { ApiError, api, ApiKey } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Badge, Button, Card, Input, Label, Notice, PageHeader, Select, StatusBadge, Table, Td, Th } from "@/components/ui";
import { useFeedback } from "@/components/feedback";

export default function ApiKeysPage() {
  const feedback = useFeedback();
  const [items, setItems] = useState<ApiKey[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: "success" | "error"; message: string } | null>(null);

  async function load() {
    setLoading(true);
    try {
      setItems(await api.apiKeys());
    } catch (error) {
      setNotice({ tone: "error", message: error instanceof ApiError ? error.detail : "Could not load API keys." });
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
    const daily = Number(form.get("daily_budget_usd") || 5);
    const monthly = Number(form.get("monthly_budget_usd") || 100);
    const key = String(form.get("key") || "").trim();
    if (key.length < 8) {
      setNotice({ tone: "error", message: "Key must be at least 8 characters." });
      return;
    }
    if (daily < 0 || monthly < 0 || daily > monthly) {
      setNotice({ tone: "error", message: "Budgets must be non-negative, and daily budget cannot exceed monthly budget." });
      return;
    }
    setSaving(true);
    setNotice(null);
    try {
      await api.createApiKey({
        provider: form.get("provider"),
        label: form.get("label"),
        key,
        daily_budget_usd: daily,
        monthly_budget_usd: monthly
      });
      target.reset();
      setOpen(false);
      setNotice({ tone: "success", message: "Key saved. It is encrypted and ready for worker use." });
      await load();
    } catch (error) {
      const message = error instanceof ApiError ? error.detail : "Could not save this key.";
      setNotice({ tone: "error", message });
    } finally {
      setSaving(false);
    }
  }

  async function testKey(item: ApiKey) {
    setBusyId(item.id);
    try {
      const response = await api.testApiKey(item.id);
      feedback.notify({ tone: "success", title: "Key test passed", message: response.detail });
      await load();
    } catch (error) {
      feedback.notify({ tone: "danger", message: error instanceof ApiError ? error.detail : "Could not test key." });
    } finally {
      setBusyId(null);
    }
  }

  async function toggleKey(item: ApiKey) {
    const nextStatus = item.status === "active" ? "disabled" : "active";
    const confirmed = await feedback.confirm({
      title: `${nextStatus === "active" ? "Enable" : "Disable"} key?`,
      description: `${item.provider}/${item.label} will be marked ${nextStatus}. Full key material remains hidden.`,
      confirmLabel: nextStatus === "active" ? "Enable" : "Disable",
      tone: nextStatus === "active" ? "neutral" : "danger",
    });
    if (!confirmed) return;
    setBusyId(item.id);
    try {
      await api.updateApiKey(item.id, { status: nextStatus });
      feedback.notify({ tone: "success", message: `Key ${nextStatus}.` });
      await load();
    } catch (error) {
      feedback.notify({ tone: "danger", message: error instanceof ApiError ? error.detail : "Could not update key." });
    } finally {
      setBusyId(null);
    }
  }

  async function deleteKey(item: ApiKey) {
    const confirmed = await feedback.confirm({
      title: "Delete API key?",
      description: `${item.provider}/${item.label} will be removed. This cannot reveal or recover the full key later.`,
      confirmLabel: "Delete key",
      tone: "danger",
    });
    if (!confirmed) return;
    setBusyId(item.id);
    try {
      const response = await api.deleteApiKey(item.id);
      feedback.notify({ tone: "success", message: response.detail });
      await load();
    } catch (error) {
      feedback.notify({ tone: "danger", message: error instanceof ApiError ? error.detail : "Could not delete key." });
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <PageHeader
        title="API Keys"
        description="Store provider keys encrypted at rest. The dashboard only shows masked hints."
        action={<Button onClick={() => setOpen(true)}><Plus size={16} /> Add key</Button>}
      />
      {notice ? (
        <Notice tone={notice.tone === "success" ? "success" : "danger"}>{notice.message}</Notice>
      ) : null}
      {open ? (
        <Card className="mb-6">
          <form onSubmit={submit} className="grid gap-4 md:grid-cols-5">
            <div>
              <Label>Provider</Label>
              <Select name="provider" defaultValue="openai">
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="google">Google</option>
                <option value="openrouter">OpenRouter</option>
                <option value="other">Other</option>
              </Select>
            </div>
            <div>
              <Label>Label</Label>
              <Input name="label" placeholder="main coding key" required />
            </div>
            <div>
              <Label>Key</Label>
              <Input name="key" type="password" placeholder="Paste key" required />
            </div>
            <div>
              <Label>Daily budget</Label>
              <Input name="daily_budget_usd" type="number" min="0" step="0.01" defaultValue="5" />
            </div>
            <div>
              <Label>Monthly budget</Label>
              <Input name="monthly_budget_usd" type="number" min="0" step="0.01" defaultValue="100" />
            </div>
            <div className="md:col-span-5 flex gap-2">
              <Button type="submit" disabled={saving}>
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                {saving ? "Saving..." : "Save encrypted key"}
              </Button>
              <Button type="button" variant="secondary" onClick={() => setOpen(false)} disabled={saving}>Cancel</Button>
            </div>
          </form>
        </Card>
      ) : null}

      <Table>
        <thead>
          <tr><Th>Provider</Th><Th>Label</Th><Th>Masked key</Th><Th>Budget</Th><Th>Status</Th><Th>Created</Th><Th>Actions</Th></tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <Td><Badge>{item.provider}</Badge></Td>
              <Td>{item.label}</Td>
              <Td><code>{item.key_hint}</code></Td>
              <Td>${item.daily_budget_usd}/day · ${item.monthly_budget_usd}/month</Td>
              <Td><StatusBadge status={item.status} /></Td>
              <Td>{formatDate(item.created_at)}</Td>
              <Td>
                <div className="flex flex-wrap gap-2">
                  <Button type="button" variant="secondary" onClick={() => testKey(item)} disabled={busyId === item.id || item.status !== "active"}>
                    {busyId === item.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <TestTube2 size={15} />}
                    Test
                  </Button>
                  <Button type="button" variant="secondary" onClick={() => toggleKey(item)} disabled={busyId === item.id}>
                    <Power size={15} />
                    {item.status === "active" ? "Disable" : "Enable"}
                  </Button>
                  <Button type="button" variant="danger" onClick={() => deleteKey(item)} disabled={busyId === item.id}>
                    <Trash2 size={15} />
                    Delete
                  </Button>
                </div>
              </Td>
            </tr>
          ))}
          {!items.length ? <tr><Td className="text-muted-foreground" colSpan={7}>{loading ? "Loading..." : "No API keys yet."}</Td></tr> : null}
        </tbody>
      </Table>
    </>
  );
}
