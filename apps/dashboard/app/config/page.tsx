"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { CheckCircle2, Download, KeyRound, Loader2, Plus, RefreshCw, Save, Upload } from "lucide-react";
import { api, ApiError, ApiKey, ConfigProfile, ProviderProfile, RuntimeConfig } from "@/lib/api";
import { Badge, Button, Card, Input, Label, Notice, PageHeader, Select, Textarea } from "@/components/ui";

const tabs = ["Tổng quan", "Model & Provider", "API Key", "Network", "Plugin / Skill", "Project Trust", "Import / Export", "Kiểm tra cấu hình"] as const;

export default function ConfigStudioPage() {
  const [profiles, setProfiles] = useState<ConfigProfile[]>([]);
  const [selected, setSelected] = useState<ConfigProfile | null>(null);
  const [runtime, setRuntime] = useState<RuntimeConfig | null>(null);
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [tab, setTab] = useState<(typeof tabs)[number]>("Tổng quan");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [importText, setImportText] = useState("");
  const [exportText, setExportText] = useState("");
  const [trustPath, setTrustPath] = useState("");
  const [notice, setNotice] = useState<{ tone: "success" | "danger" | "warning" | "neutral"; message: string } | null>(null);

  const activeProvider = useMemo(() => {
    if (!selected) return null;
    return selected.providers.find((item) => item.id === selected.active_provider_profile_id) ?? selected.providers[0] ?? null;
  }, [selected]);

  async function load(selectId?: string) {
    setLoading(true);
    try {
      const [profileItems, keyItems] = await Promise.all([api.configProfiles(), api.apiKeys().catch(() => [])]);
      const nextSelected = profileItems.find((item) => item.id === (selectId ?? selected?.id)) ?? profileItems.find((item) => item.is_default) ?? profileItems[0] ?? null;
      setProfiles(profileItems);
      setSelected(nextSelected);
      setApiKeys(keyItems);
      setRuntime(nextSelected ? await api.runtimeConfig(nextSelected.id).catch(() => null) : null);
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Không tải được Config Studio." });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load().catch(console.error); }, []);

  function patchSelected(patch: Partial<ConfigProfile>) {
    setSelected((current) => (current ? { ...current, ...patch } : current));
  }

  function patchProvider(patch: Partial<ProviderProfile>) {
    if (!selected || !activeProvider) return;
    patchSelected({
      providers: selected.providers.map((item) => item.id === activeProvider.id ? { ...item, ...patch } : item)
    });
  }

  async function saveProfile() {
    if (!selected || saving) return;
    setSaving(true);
    setNotice(null);
    try {
      const saved = await api.updateConfigProfile(selected.id, {
        name: selected.name,
        description: selected.description,
        model_provider: selected.model_provider,
        model: selected.model,
        review_model: selected.review_model,
        model_reasoning_effort: selected.model_reasoning_effort,
        disable_response_storage: selected.disable_response_storage,
        network_access: selected.network_access,
        model_context_window: Number(selected.model_context_window),
        model_auto_compact_token_limit: Number(selected.model_auto_compact_token_limit),
        active_provider_profile_id: selected.active_provider_profile_id,
      });
      setNotice({ tone: "success", message: "Đã lưu config profile." });
      await load(saved.id);
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Không lưu được profile." });
    } finally {
      setSaving(false);
    }
  }

  async function saveProvider() {
    if (!selected || saving) return;
    setSaving(true);
    setNotice(null);
    try {
      if (activeProvider) {
        await api.updateProviderProfile(activeProvider.id, {
          name: activeProvider.name,
          provider_type: activeProvider.provider_type,
          base_url: activeProvider.base_url,
          wire_api: activeProvider.wire_api,
          requires_openai_auth: activeProvider.requires_openai_auth,
          api_key_id: activeProvider.api_key_id,
          enabled: activeProvider.enabled,
        });
      } else {
        await api.createProviderProfile(selected.id, {
          name: selected.model_provider || "OpenAI",
          provider_type: "openai_compatible",
          base_url: "https://api.openai.com/v1",
          wire_api: "responses",
          requires_openai_auth: true,
          enabled: true,
        });
      }
      setNotice({ tone: "success", message: "Đã lưu provider profile." });
      await load(selected.id);
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Không lưu được provider." });
    } finally {
      setSaving(false);
    }
  }

  async function createProfile() {
    setSaving(true);
    try {
      const created = await api.createConfigProfile({
        name: "Custom Router",
        description: "Profile mới để cấu hình provider/model/plugin từ UI.",
        model_provider: "OpenAI",
        model: "gpt-5.5",
        review_model: "gpt-5.5",
        network_access: "enabled",
        model_context_window: 1000000,
        model_auto_compact_token_limit: 900000,
      });
      setNotice({ tone: "success", message: "Đã tạo profile mới." });
      await load(created.id);
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Không tạo được profile." });
    } finally {
      setSaving(false);
    }
  }

  async function setDefault() {
    if (!selected) return;
    const saved = await api.setDefaultConfigProfile(selected.id);
    setNotice({ tone: "success", message: `${saved.name} đã là profile mặc định.` });
    await load(saved.id);
  }

  async function togglePlugin(pluginId: string, enabled: boolean) {
    if (!selected) return;
    const plugin = selected.plugins.find((item) => item.id === pluginId);
    if (!plugin) return;
    await api.updateConfigPlugin(plugin.id, { enabled });
    await load(selected.id);
  }

  async function addTrustedProject(event: FormEvent) {
    event.preventDefault();
    if (!selected || !trustPath.trim()) return;
    try {
      await api.createTrustedProject(selected.id, { path: trustPath.trim(), trust_level: "trusted" });
      setTrustPath("");
      await load(selected.id);
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Không thêm được project trust." });
    }
  }

  async function importToml() {
    if (!importText.trim()) {
      setNotice({ tone: "warning", message: "Hãy dán nội dung config.toml trước." });
      return;
    }
    try {
      const imported = await api.importConfigToml({ toml_text: importText, set_default: false });
      setImportText("");
      setNotice({ tone: "success", message: "Đã import config.toml thành profile mới. API key chỉ được gắn bằng api_key_ref." });
      await load(imported.id);
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Import TOML thất bại." });
    }
  }

  async function exportToml() {
    if (!selected) return;
    const result = await api.exportConfigToml(selected.id);
    setExportText(result.toml_text);
  }

  async function testProfile() {
    if (!selected) return;
    const result = await api.testConfigProfile(selected.id);
    setNotice({ tone: result.status === "passed" ? "success" : "warning", message: result.detail });
    setRuntime(await api.runtimeConfig(selected.id).catch(() => runtime));
  }

  return (
    <>
      <PageHeader
        title="Config Studio"
        description="Cấu hình provider, base URL, model, API key, network, plugin và project trust mà không cần sửa file config.toml thủ công."
        action={
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="secondary" onClick={() => load()} disabled={loading}>{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw size={16} />}Làm mới</Button>
            <Button type="button" onClick={createProfile} disabled={saving}><Plus size={16} />Profile mới</Button>
          </div>
        }
      />
      {notice ? <Notice tone={notice.tone}>{notice.message}</Notice> : null}

      <div className="grid gap-5 xl:grid-cols-[280px_1fr]">
        <Card>
          <h2 className="mb-3 text-sm font-semibold">Config Profiles</h2>
          <div className="space-y-2">
            {profiles.map((profile) => (
              <button
                key={profile.id}
                type="button"
                onClick={() => load(profile.id)}
                className={`w-full rounded-md border px-3 py-2 text-left text-sm transition hover:bg-muted ${selected?.id === profile.id ? "border-primary bg-background" : "border-border bg-background"}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{profile.name}</span>
                  {profile.is_default ? <Badge tone="success">default</Badge> : null}
                </div>
                <div className="mt-1 text-xs text-muted-foreground">{profile.model_provider} · {profile.model}</div>
              </button>
            ))}
          </div>
        </Card>

        <div className="space-y-5">
          <div className="flex gap-2 overflow-x-auto rounded-lg border border-border bg-card p-2">
            {tabs.map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setTab(item)}
                className={`shrink-0 rounded-md px-3 py-2 text-sm ${tab === item ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}
              >
                {item}
              </button>
            ))}
          </div>

          {!selected ? <Notice tone="warning">Chưa có profile nào. Hãy tạo profile mới hoặc import config.toml.</Notice> : null}
          {selected && tab === "Tổng quan" ? (
            <Card>
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-base font-semibold">{selected.name}</h2>
                  <p className="text-sm text-muted-foreground">{selected.description || "Chưa có mô tả."}</p>
                </div>
                <div className="flex gap-2">
                  <Button type="button" variant="secondary" onClick={setDefault} disabled={selected.is_default}>Đặt mặc định</Button>
                  <Button type="button" onClick={saveProfile} disabled={saving}>{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save size={16} />}Lưu</Button>
                </div>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div><Label>Tên profile</Label><Input value={selected.name} onChange={(event) => patchSelected({ name: event.target.value })} /></div>
                <div><Label>Provider mặc định</Label><Input value={selected.model_provider} onChange={(event) => patchSelected({ model_provider: event.target.value })} /></div>
                <div className="md:col-span-2"><Label>Mô tả</Label><Textarea value={selected.description} onChange={(event) => patchSelected({ description: event.target.value })} /></div>
              </div>
              {runtime ? (
                <div className="mt-5 grid gap-3 md:grid-cols-4">
                  <Metric label="Model" value={runtime.model} />
                  <Metric label="Review model" value={runtime.review_model} />
                  <Metric label="Network" value={runtime.network_access} />
                  <Metric label="Plugin bật" value={String(runtime.enabled_plugins.length)} />
                </div>
              ) : null}
            </Card>
          ) : null}

          {selected && tab === "Model & Provider" ? (
            <Card>
              <div className="grid gap-4 md:grid-cols-2">
                <div><Label>Model chính</Label><Input value={selected.model} onChange={(event) => patchSelected({ model: event.target.value })} /></div>
                <div><Label>Review model</Label><Input value={selected.review_model} onChange={(event) => patchSelected({ review_model: event.target.value })} /></div>
                <div><Label>Reasoning effort</Label><Select value={selected.model_reasoning_effort} onChange={(event) => patchSelected({ model_reasoning_effort: event.target.value })}><option value="low">low</option><option value="medium">medium</option><option value="high">high</option><option value="xhigh">xhigh</option></Select></div>
                <label className="flex min-h-10 items-center gap-2 rounded-md border border-border bg-background px-3 text-sm">
                  <input type="checkbox" checked={selected.disable_response_storage} onChange={(event) => patchSelected({ disable_response_storage: event.target.checked })} />
                  Tắt lưu response provider
                </label>
                <div><Label>Provider name</Label><Input value={activeProvider?.name ?? ""} onChange={(event) => patchProvider({ name: event.target.value })} /></div>
                <div><Label>Provider type</Label><Select value={activeProvider?.provider_type ?? "openai_compatible"} onChange={(event) => patchProvider({ provider_type: event.target.value })}><option value="openai_compatible">OpenAI-compatible router</option><option value="codex_cli">Codex CLI auth</option><option value="deterministic">Deterministic fallback</option></Select></div>
                <div className="md:col-span-2"><Label>Base URL</Label><Input value={activeProvider?.base_url ?? ""} onChange={(event) => patchProvider({ base_url: event.target.value })} placeholder="https://router.example.com/v1" /></div>
                <div><Label>Wire API</Label><Select value={activeProvider?.wire_api ?? "responses"} onChange={(event) => patchProvider({ wire_api: event.target.value })}><option value="responses">responses</option><option value="chat_completions">chat_completions</option></Select></div>
                <label className="flex min-h-10 items-center gap-2 rounded-md border border-border bg-background px-3 text-sm">
                  <input type="checkbox" checked={Boolean(activeProvider?.requires_openai_auth)} onChange={(event) => patchProvider({ requires_openai_auth: event.target.checked })} />
                  Provider cần API key
                </label>
              </div>
              <div className="mt-4 flex gap-2">
                <Button type="button" onClick={saveProfile} disabled={saving}><Save size={16} />Lưu model</Button>
                <Button type="button" variant="secondary" onClick={saveProvider} disabled={saving}><Save size={16} />Lưu provider</Button>
              </div>
            </Card>
          ) : null}

          {selected && tab === "API Key" ? (
            <Card>
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-base font-semibold">Gắn API key vào provider</h2>
                  <p className="text-sm text-muted-foreground">Khoá chỉ hiển thị dạng mask/hint. Export TOML dùng api_key_ref, không xuất raw key.</p>
                </div>
                <Link className="inline-flex min-h-10 items-center gap-2 rounded-md border border-border bg-card px-4 py-2 text-sm font-medium hover:bg-muted" href="/api-keys"><KeyRound size={16} />Quản lý khoá</Link>
              </div>
              <Label>API key cho provider đang chọn</Label>
              <Select value={activeProvider?.api_key_id ?? ""} onChange={(event) => patchProvider({ api_key_id: event.target.value || null })}>
                <option value="">Chưa gắn key</option>
                {apiKeys.map((key) => <option key={key.id} value={key.id}>{key.provider} · {key.label} · {key.key_hint}</option>)}
              </Select>
              <Button type="button" className="mt-4" onClick={saveProvider} disabled={saving}><Save size={16} />Lưu API key ref</Button>
            </Card>
          ) : null}

          {selected && tab === "Network" ? (
            <Card>
              <div className="grid gap-4 md:grid-cols-3">
                <div><Label>Network access</Label><Select value={selected.network_access} onChange={(event) => patchSelected({ network_access: event.target.value })}><option value="enabled">enabled</option><option value="restricted">restricted</option><option value="disabled">disabled</option></Select></div>
                <div><Label>Context window</Label><Input type="number" value={selected.model_context_window} onChange={(event) => patchSelected({ model_context_window: Number(event.target.value) })} /></div>
                <div><Label>Auto compact token limit</Label><Input type="number" value={selected.model_auto_compact_token_limit} onChange={(event) => patchSelected({ model_auto_compact_token_limit: Number(event.target.value) })} /></div>
              </div>
              <Notice tone="neutral" className="mt-4 mb-0">Network enabled chỉ cho phép worker/research dùng phần đã được cấu hình. Scanner bên ngoài vẫn luôn đưa nguồn vào quarantine trước.</Notice>
              <Button type="button" className="mt-4" onClick={saveProfile} disabled={saving}><Save size={16} />Lưu network</Button>
            </Card>
          ) : null}

          {selected && tab === "Plugin / Skill" ? (
            <Card>
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-base font-semibold">Plugin trong profile</h2>
                  <p className="text-sm text-muted-foreground">Skill pack được quản lý riêng ở trang Skill/Prompt, nhưng runtime snapshot sẽ gom cả plugin và skill đang bật.</p>
                </div>
                <Link className="text-sm text-primary" href="/skills">Mở Skill Marketplace</Link>
              </div>
              <div className="grid gap-2 md:grid-cols-2">
                {selected.plugins.map((plugin) => (
                  <label key={plugin.id} className="flex min-h-12 items-center justify-between gap-3 rounded-md border border-border bg-background px-3 text-sm">
                    <span><span className="font-medium">{plugin.name}</span><span className="ml-2 text-xs text-muted-foreground">{plugin.plugin_id}</span></span>
                    <input type="checkbox" checked={plugin.enabled} onChange={(event) => togglePlugin(plugin.id, event.target.checked).catch(console.error)} />
                  </label>
                ))}
              </div>
            </Card>
          ) : null}

          {selected && tab === "Project Trust" ? (
            <Card>
              <form onSubmit={addTrustedProject} className="mb-4 grid gap-3 md:grid-cols-[1fr_auto]">
                <div><Label>Đường dẫn project trusted</Label><Input value={trustPath} onChange={(event) => setTrustPath(event.target.value)} placeholder="/Users/me/project" /></div>
                <Button type="submit" className="self-end"><Plus size={16} />Thêm</Button>
              </form>
              <div className="space-y-2">
                {selected.trusted_projects.map((project) => (
                  <div key={project.id} className="flex items-center justify-between gap-3 rounded-md border border-border bg-background px-3 py-2 text-sm">
                    <span className="break-all">{project.path}</span>
                    <Badge tone="success">{project.trust_level}</Badge>
                  </div>
                ))}
                {!selected.trusted_projects.length ? <div className="rounded-md bg-muted p-4 text-sm text-muted-foreground">Chưa có trusted path nào.</div> : null}
              </div>
            </Card>
          ) : null}

          {selected && tab === "Import / Export" ? (
            <div className="grid gap-5 lg:grid-cols-2">
              <Card>
                <h2 className="mb-3 text-base font-semibold">Import config.toml</h2>
                <Textarea value={importText} onChange={(event) => setImportText(event.target.value)} className="min-h-72 font-mono" placeholder={'model_provider = "OpenAI"\nmodel = "gpt-5.5"\n\n[model_providers.OpenAI]\nbase_url = "https://router.example.com/v1"'} />
                <Button type="button" className="mt-4" onClick={importToml}><Upload size={16} />Import thành profile mới</Button>
              </Card>
              <Card>
                <h2 className="mb-3 text-base font-semibold">Export TOML an toàn</h2>
                <Textarea value={exportText} readOnly className="min-h-72 font-mono" placeholder="Bấm Export để lấy TOML. Raw API key không được xuất." />
                <Button type="button" className="mt-4" onClick={exportToml}><Download size={16} />Export</Button>
              </Card>
            </div>
          ) : null}

          {selected && tab === "Kiểm tra cấu hình" ? (
            <Card>
              <div className="mb-4 flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-primary" />
                <h2 className="text-base font-semibold">Kiểm tra profile trước khi chạy</h2>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <Metric label="Profile" value={selected.name} />
                <Metric label="Provider" value={activeProvider?.name ?? "-"} />
                <Metric label="Auth" value={activeProvider?.api_key_id ? "Dashboard API key" : activeProvider?.provider_type === "codex_cli" ? "Codex CLI auth" : "Chưa gắn key"} />
                <Metric label="Secrets" value="redacted" />
              </div>
              <Button type="button" className="mt-4" onClick={testProfile}><CheckCircle2 size={16} />Kiểm tra cấu hình</Button>
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
      <div className="mt-1 break-words text-sm font-semibold">{value}</div>
    </div>
  );
}
