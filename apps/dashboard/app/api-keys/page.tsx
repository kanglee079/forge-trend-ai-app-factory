"use client";

import { FormEvent, useEffect, useState } from "react";
import { Loader2, Plus } from "lucide-react";
import { ApiError, api, ApiKey } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Badge, Button, Card, Input, Label, Notice, PageHeader, Select, StatusBadge, Table, Td, Th } from "@/components/ui";

export default function ApiKeysPage() {
  const [items, setItems] = useState<ApiKey[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<{ tone: "success" | "error"; message: string } | null>(null);

  async function load() {
    setLoading(true);
    try {
      setItems(await api.apiKeys());
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
      await api.createApiKey({
        provider: form.get("provider"),
        label: form.get("label"),
        key: form.get("key"),
        daily_budget_usd: Number(form.get("daily_budget_usd") || 5),
        monthly_budget_usd: Number(form.get("monthly_budget_usd") || 100)
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
          <tr><Th>Provider</Th><Th>Label</Th><Th>Masked key</Th><Th>Budget</Th><Th>Status</Th><Th>Created</Th></tr>
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
            </tr>
          ))}
          {!items.length ? <tr><Td className="text-muted-foreground" colSpan={6}>{loading ? "Loading..." : "No API keys yet."}</Td></tr> : null}
        </tbody>
      </Table>
    </>
  );
}
