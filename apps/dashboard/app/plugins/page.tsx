"use client";

import { PlugZap } from "lucide-react";
import { useLanguage } from "@/lib/i18n";
import { Badge, Card, PageHeader, Table, Td, Th } from "@/components/ui";

const plugins = [
  { id: "deterministic_research", name: "Deterministic Research", type: "research_provider", enabled: true, capabilities: ["offline evidence", "fallback ideas"], missing: [] },
  { id: "web_research", name: "Web Research", type: "research_provider", enabled: true, capabilities: ["allowlisted URLs", "evidence links"], missing: ["RESEARCH_ALLOWED_URLS when web mode is enabled"] },
  { id: "education_archetype", name: "Education Archetype", type: "app_archetype", enabled: true, capabilities: ["lessons", "review cards", "progress"], missing: [] },
  { id: "productivity_archetype", name: "Productivity Archetype", type: "app_archetype", enabled: true, capabilities: ["tasks", "priority", "history"], missing: [] },
  { id: "codex_provider", name: "Codex CLI Provider", type: "code_provider", enabled: true, capabilities: ["coding pass", "repair loop"], missing: ["codex login when enabled"] },
  { id: "quality_gate", name: "Product Quality Gate", type: "quality_gate", enabled: true, capabilities: ["banned copy", "journey", "ASO", "product score"], missing: [] },
  { id: "store_assets", name: "Store Asset Generator", type: "store_asset_generator", enabled: true, capabilities: ["listing drafts", "keywords", "screenshot plan"], missing: [] },
];

export default function PluginsPage() {
  const { t } = useLanguage();
  return (
    <>
      <PageHeader title={t("pluginRegistryTitle")} description={t("pluginRegistryHelp")} />
      <Card className="mb-5">
        <div className="flex items-start gap-3">
          <PlugZap className="mt-0.5 h-5 w-5 text-primary" />
          <p className="text-sm text-muted-foreground">Plugin registry hiện là registry khai báo trong code/docs. Bước sau có thể chuyển sang API-backed registry và UI configure từng plugin.</p>
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
              <Td className="text-muted-foreground">{plugin.missing.length ? plugin.missing.join(", ") : "-"}</Td>
            </tr>
          ))}
        </tbody>
      </Table>
    </>
  );
}
