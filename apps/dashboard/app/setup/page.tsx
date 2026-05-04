"use client";

import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Loader2, RefreshCw } from "lucide-react";
import { api, DoctorResponse } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";
import { Badge, Button, Card, Notice, PageHeader } from "@/components/ui";
import { CopyButton } from "@/components/log-viewer";

const steps = [
  { key: "setupDocker", checks: ["docker", "docker_compose"], command: "pnpm doctor" },
  { key: "setupPython", checks: ["python"], command: "pnpm setup:python" },
  { key: "setupNode", checks: ["node", "pnpm"], command: "corepack enable && pnpm install" },
  { key: "setupFlutter", checks: ["flutter", "flutter_doctor"], command: "flutter doctor -v" },
  { key: "setupAndroid", checks: ["android_sdk_env", "adb"], command: "flutter doctor --android-licenses" },
  { key: "setupCodex", checks: ["codex", "codex_auth_smoke"], command: "codex login" },
  { key: "setupE2E", checks: ["api", "redis", "postgres"], command: "WORKER_ENABLE_CODEX=false pnpm e2e:factory:vi" },
  { key: "setupFirstApp", checks: [], command: "pnpm dev" },
] as const;

export default function SetupPage() {
  const { t } = useLanguage();
  const [doctor, setDoctor] = useState<DoctorResponse | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    setDoctor(await api.doctor().catch(() => null));
    setLoading(false);
  }

  useEffect(() => { load().catch(console.error); }, []);

  const checkMap = useMemo(() => new Map((doctor?.checks ?? []).map((check) => [check.id, check])), [doctor]);

  return (
    <>
      <PageHeader title={t("setupTitle")} description={t("setupHelp")} action={<Button type="button" variant="secondary" onClick={() => load()} disabled={loading}>{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw size={16} />}{t("refresh")}</Button>} />
      <Notice tone="neutral">{t("runLocalSimple")}: <code>pnpm reset:local</code> → <code>pnpm dev</code> → <code>WORKER_ENABLE_CODEX=false pnpm e2e:factory:vi</code></Notice>
      <div className="grid gap-4 md:grid-cols-2">
        {steps.map((step) => {
          const checks = step.checks.map((id) => checkMap.get(id)).filter(Boolean);
          const passed = checks.length ? checks.every((check) => check?.status === "passed") : true;
          return (
            <Card key={step.key}>
              <div className="mb-3 flex items-center justify-between gap-3">
                <h2 className="font-semibold">{t(step.key)}</h2>
                <Badge tone={passed ? "success" : "warning"}>{passed ? "OK" : "fix"}</Badge>
              </div>
              <div className="space-y-2">
                {checks.map((check) => check ? (
                  <div key={check.id} className="rounded-md border border-border bg-background p-3 text-sm">
                    <div className="flex items-center gap-2">{check.status === "passed" ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <span className="h-2 w-2 rounded-full bg-amber-500" />}<span className="font-medium">{check.label}</span></div>
                    <p className="mt-1 text-xs text-muted-foreground">{check.detail}</p>
                  </div>
                ) : null)}
              </div>
              <div className="mt-4 flex items-center justify-between gap-3 rounded-md bg-muted p-3 text-sm">
                <span>{t("fixCommand")}: <code>{step.command}</code></span>
                <CopyButton value={step.command} label="Copy" />
              </div>
            </Card>
          );
        })}
      </div>
    </>
  );
}
