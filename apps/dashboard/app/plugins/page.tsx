"use client";

import { useEffect, useState } from "react";
import { Loader2, PlugZap, RefreshCw } from "lucide-react";
import { api, ApiError, PluginStatus } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";
import { Badge, Button, Card, Notice, PageHeader, Table, Td, Th } from "@/components/ui";

export default function PluginsPage() {
  const { t } = useLanguage();
  const [plugins, setPlugins] = useState<PluginStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<{ tone: "danger"; message: string } | null>(null);

  async function load() {
    setLoading(true);
    try {
      setPlugins(await api.pluginRegistry());
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Không tải được plugin registry." });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load().catch(console.error); }, []);

  return (
    <>
      <PageHeader title={t("pluginRegistryTitle")} description={t("pluginRegistryHelp")} action={<Button type="button" variant="secondary" onClick={() => load()} disabled={loading}>{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw size={16} />}{t("refresh")}</Button>} />
      {notice ? <Notice tone={notice.tone}>{notice.message}</Notice> : null}
      <Card className="mb-5">
        <div className="flex items-start gap-3">
          <PlugZap className="mt-0.5 h-5 w-5 text-primary" />
          <p className="text-sm text-muted-foreground">Registry đang được đọc từ API backend. Bước sau có thể thêm enable/disable và form cấu hình plugin.</p>
        </div>
      </Card>
      <Table>
        <thead><tr><Th>ID</Th><Th>Name</Th><Th>{t("pluginType")}</Th><Th>{t("enabled")}</Th><Th>Capabilities</Th><Th>{t("missingDependencies")}</Th></tr></thead>
        <tbody>
          {plugins.map((plugin) => (
            <tr key={plugin.id}>
              <Td><code>{plugin.id}</code></Td>
              <Td>{plugin.name}</Td>
              <Td><Badge>{plugin.type}</Badge></Td>
              <Td><Badge tone={plugin.enabled ? "success" : "warning"}>{plugin.enabled ? "on" : "off"}</Badge></Td>
              <Td><div className="flex flex-wrap gap-1">{plugin.capabilities.map((item) => <Badge key={item}>{item}</Badge>)}</div></Td>
              <Td className="text-muted-foreground">{plugin.missing_dependencies.length ? plugin.missing_dependencies.join(", ") : "-"}</Td>
            </tr>
          ))}
        </tbody>
      </Table>
    </>
  );
}
