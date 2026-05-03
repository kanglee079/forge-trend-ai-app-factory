"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Activity, Bot, CheckCircle2, FileText, KeyRound, LayoutDashboard, Lightbulb, Moon, Server, Settings, Stethoscope, Smartphone, Sun } from "lucide-react";
import { api } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { FeedbackProvider } from "@/components/feedback";
import { NotificationCenter } from "@/components/NotificationCenter";
import { Badge, Button } from "@/components/ui";

const navItems = [
  { href: "/", labelKey: "overview", icon: LayoutDashboard },
  { href: "/factory", labelKey: "factory", icon: Bot },
  { href: "/doctor", labelKey: "doctor", icon: Stethoscope },
  { href: "/api-keys", labelKey: "apiKeys", icon: KeyRound },
  { href: "/workers", labelKey: "workers", icon: Server },
  { href: "/ideas", labelKey: "ideas", icon: Lightbulb },
  { href: "/projects", labelKey: "projects", icon: Smartphone },
  { href: "/logs", labelKey: "logs", icon: FileText },
  { href: "/settings", labelKey: "settings", icon: Settings }
] as const;

type HealthState = {
  apiOnline: boolean;
  workerCount: number | null;
  apiKeyCount: number | null;
  ideaCount: number | null;
  projectCount: number | null;
};

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { t } = useLanguage();
  const [theme, setTheme] = useState<"light" | "dark">(() => getInitialTheme());
  const [health, setHealth] = useState<HealthState>({ apiOnline: false, workerCount: null, apiKeyCount: null, ideaCount: null, projectCount: null });

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("forge-theme", theme);
  }, [theme]);

  useEffect(() => {
    let active = true;

    async function loadHealth() {
      try {
        const [apiHealth, workers] = await Promise.all([
          api.health().catch(() => ({ status: "offline" })),
          api.workers().catch(() => [])
        ]);
        const [apiKeys, ideas, projects] = apiHealth.status === "ok"
          ? await Promise.all([api.apiKeys().catch(() => []), api.ideas().catch(() => []), api.projects().catch(() => [])])
          : [[], [], []];
        if (!active) {
          return;
        }
        setHealth({
          apiOnline: apiHealth.status === "ok",
          workerCount: workers.filter((worker) => worker.status === "online").length,
          apiKeyCount: apiKeys.length,
          ideaCount: ideas.length,
          projectCount: projects.length
        });
      } catch {
        if (active) {
          setHealth({ apiOnline: false, workerCount: null, apiKeyCount: null, ideaCount: null, projectCount: null });
        }
      }
    }

    loadHealth();
    const timer = window.setInterval(loadHealth, 10000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  const activeItem = useMemo(() => {
    const exact = navItems.find((item) => item.href === pathname);
    if (exact) {
      return exact;
    }
    return navItems.find((item) => item.href !== "/" && pathname.startsWith(item.href));
  }, [pathname]);

  return (
    <FeedbackProvider>
      <div className="min-h-screen">
        <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-border bg-card px-4 py-5 lg:block">
          <Brand />
          <nav className="space-y-1" aria-label="Primary navigation">
            {navItems.map((item) => (
              <NavItem key={item.href} item={item} active={activeItem?.href === item.href} />
            ))}
          </nav>
        </aside>

        <div className="lg:pl-64">
          <header className="sticky top-0 z-30 border-b border-border bg-background/92 backdrop-blur">
            <div className="mx-auto flex min-h-16 w-full max-w-7xl items-center justify-between gap-3 px-4 py-3 sm:px-6 lg:px-8">
              <div className="min-w-0">
                <div className="flex items-center gap-2 lg:hidden">
                  <Brand compact />
                </div>
                <div className="hidden text-sm text-muted-foreground lg:block">
                  {activeItem ? t(activeItem.labelKey) : "ForgeTrend"}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <SystemBadge label="API" online={health.apiOnline} />
                <Badge tone={health.workerCount ? "success" : "warning"}>{health.workerCount ?? "-"} {t("workerShort")}</Badge>
                <NotificationCenter />
                <Button
                  type="button"
                  variant="secondary"
                  className="h-10 w-10 px-0"
                  onClick={() => setTheme((current) => (current === "dark" ? "light" : "dark"))}
                  aria-label={t("toggleTheme")}
                  title={t("toggleTheme")}
                >
                  {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
                </Button>
              </div>
            </div>
            <nav className="flex gap-1 overflow-x-auto px-4 pb-3 sm:px-6 lg:hidden" aria-label="Mobile navigation">
              {navItems.map((item) => (
                <NavPill key={item.href} item={item} active={activeItem?.href === item.href} />
              ))}
            </nav>
          </header>

          <main>
            <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
              <SetupGuide {...health} />
              {children}
            </div>
          </main>
        </div>
      </div>
    </FeedbackProvider>
  );
}

function getInitialTheme(): "light" | "dark" {
  if (typeof window === "undefined") {
    return "light";
  }
  const stored = window.localStorage.getItem("forge-theme");
  if (stored === "dark" || stored === "light") {
    return stored;
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function SetupGuide({ apiOnline, workerCount, apiKeyCount, ideaCount, projectCount }: HealthState) {
  const { t } = useLanguage();
  const items = [
    { label: "API", complete: apiOnline },
    { label: "Worker", complete: Boolean(workerCount) },
    { label: "Key", complete: Boolean(apiKeyCount) },
    { label: "Idea", complete: Boolean(ideaCount) },
    { label: "Project", complete: Boolean(projectCount) }
  ];

  return (
    <div className="mb-5 rounded-lg border border-border bg-card px-4 py-3 text-sm text-card-foreground shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="font-medium">{t("firstRunPath")}</div>
          <div className="text-xs text-muted-foreground">{t("firstRunHelp")}</div>
        </div>
        <div className="flex flex-wrap gap-2">
          {items.map((item) => (
            <span key={item.label} className="inline-flex min-h-8 items-center gap-2 rounded-sm border border-border bg-background px-2.5 text-xs text-muted-foreground">
              {item.complete ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" /> : <span className="h-2 w-2 rounded-full bg-muted-foreground/45" />}
              {item.label}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <Link href="/" className={cn("mb-8 flex items-center gap-3 px-2", compact && "mb-0 px-0")}>
      <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary text-primary-foreground">
        <Activity size={20} />
      </div>
      <div className={compact ? "hidden sm:block" : undefined}>
        <div className="text-sm font-semibold">ForgeTrend</div>
        <div className="text-xs text-muted-foreground">AI App Factory</div>
      </div>
    </Link>
  );
}

function NavItem({ item, active }: { item: (typeof navItems)[number]; active: boolean }) {
  const { t } = useLanguage();
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      className={cn(
        "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition",
        active ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"
      )}
    >
      <Icon size={17} />
      {t(item.labelKey)}
    </Link>
  );
}

function NavPill({ item, active }: { item: (typeof navItems)[number]; active: boolean }) {
  const { t } = useLanguage();
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      className={cn(
        "inline-flex min-h-10 shrink-0 items-center gap-2 rounded-md px-3 text-sm transition",
        active ? "bg-primary text-primary-foreground" : "border border-border bg-card text-muted-foreground"
      )}
    >
      <Icon size={16} />
      {t(item.labelKey)}
    </Link>
  );
}

function SystemBadge({ label, online }: { label: string; online: boolean }) {
  return (
    <span className="inline-flex min-h-8 items-center gap-2 rounded-sm border border-border bg-card px-2.5 text-xs font-medium text-muted-foreground">
      <span className={cn("h-2 w-2 rounded-full", online ? "bg-emerald-500" : "bg-red-500")} />
      {label}
    </span>
  );
}
