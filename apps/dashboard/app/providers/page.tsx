"use client";

import { Cpu, Loader2, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError, ProviderStatus } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";
import { Badge, Button, Card, Notice, PageHeader } from "@/components/ui";

export default function ProvidersPage() {
  const { t } = useLanguage();
  const [providers, setProviders] = useState<ProviderStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<{ tone: "danger"; message: string } | null>(null);

  async function load() {
    setLoading(true);
    try {
      setProviders(await api.providerStatus());
    } catch (error) {
      setNotice({ tone: "danger", message: error instanceof ApiError ? error.detail : "Không tải được provider router." });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load().catch(console.error); }, []);

  return (
    <>
      <PageHeader title={t("providerRouterTitle")} description={t("providerRouterHelp")} action={<Button type="button" variant="secondary" onClick={() => load()} disabled={loading}>{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw size={16} />}{t("refresh")}</Button>} />
      {notice ? <Notice tone={notice.tone}>{notice.message}</Notice> : null}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {providers.map((provider) => (
          <ProviderCard key={provider.id} provider={provider} />
        ))}
      </div>
      <Card className="mt-5">
        <h2 className="mb-3 text-base font-semibold">Routing policy</h2>
        <div className="grid gap-2 md:grid-cols-2">
          {[t("providerRuleSmoke"), t("providerRuleCode"), t("providerRuleRefine"), t("providerRuleBudget")].map((rule) => <div key={rule} className="rounded-md border border-border bg-background p-3 text-sm">{rule}</div>)}
        </div>
      </Card>
    </>
  );
}

function ProviderCard({ provider }: { provider: ProviderStatus }) {
  const status = provider.available && provider.enabled ? "available" : provider.available ? "optional" : "needs setup";
  return (
    <Card>
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="text-primary"><Cpu size={18} /></div>
        <Badge tone={status === "available" ? "success" : status === "optional" ? "neutral" : "warning"}>{status}</Badge>
      </div>
      <h2 className="font-semibold">{provider.name}</h2>
      <div className="mt-2 text-sm text-muted-foreground">Auth: {provider.auth_status}</div>
      {provider.current_model ? <div className="mt-1 text-sm text-muted-foreground">Model: {provider.current_model}</div> : null}
      <p className="mt-3 text-sm text-muted-foreground">{provider.recommended_action}</p>
    </Card>
  );
}
