import { expect, test } from "@playwright/test";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const runTimeout = Number(process.env.E2E_UI_TIMEOUT_MS ?? 10 * 60 * 1000);

async function apiRequest(path: string, init?: RequestInit) {
  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}: ${text.slice(0, 1000)}`);
  }
  return text ? JSON.parse(text) : null;
}

async function waitForApi<T>(label: string, fn: () => Promise<{ ok: boolean; value?: T; detail?: string }>, timeoutMs = runTimeout): Promise<T> {
  const started = Date.now();
  let lastDetail = "not checked yet";
  while (Date.now() - started < timeoutMs) {
    const result = await fn();
    if (result.ok) return result.value as T;
    lastDetail = result.detail ?? "condition not met";
    await new Promise((resolve) => setTimeout(resolve, 4000));
  }
  throw new Error(`${label} timed out. Last detail: ${lastDetail}`);
}

test("factory brief can be created and opened from dashboard", async ({ page }, testInfo) => {
  const consoleMessages: string[] = [];
  page.on("console", (message) => consoleMessages.push(`[${message.type()}] ${message.text()}`));
  page.on("pageerror", (error) => consoleMessages.push(`[pageerror] ${error.message}`));

  try {
    const health = await apiRequest("/health");
    expect(health.status).toBe("ok");

    await page.goto("/factory");
    await expect(page.getByRole("heading", { name: "Factory" })).toBeVisible();

    const prompt = `HSK local-first learning app UI E2E ${new Date().toISOString()}`;
    await page.getByLabel("Instruction").fill(prompt);
    await page.getByLabel("Mode").selectOption("auto_trend");
    await page.getByLabel("Category").fill("Education");
    await page.getByLabel("Monetization").selectOption("subscription");
    await page.locator('input[name="iap_enabled"]').check();
    await page.getByLabel("Backend").selectOption("none");
    await page.getByRole("button", { name: /Create brief/i }).click();

    await expect(page.getByText(prompt)).toBeVisible({ timeout: 30_000 });
    await page.getByText(prompt, { exact: true }).click();
    await page.getByRole("button", { name: /^Start$/ }).click();

    const brief = await waitForApi<any>("brief appears", async () => {
      const briefs = await apiRequest("/factory-briefs");
      const item = briefs.find((candidate: any) => candidate.raw_prompt === prompt);
      return { ok: Boolean(item), value: item, detail: `${briefs.length} brief(s)` };
    });

    await waitForApi("factory timeline", async () => {
      const events = await apiRequest(`/factory-briefs/${brief.id}/events`);
      const titles = new Set(events.map((event: any) => event.title));
      const hasQueued = titles.has("brief_queued");
      const hasResearch = titles.has("research_started");
      const hasCandidates = titles.has("candidates_created");
      const hasProject = titles.has("project_created");
      const hasPipelineQueued = titles.has("pipeline_queued");
      return {
        ok: hasQueued && hasResearch && hasCandidates && hasProject && hasPipelineQueued,
        detail: [...titles].join(", "),
        value: events,
      };
    });

    const detail = await waitForApi<any>("project creation", async () => {
      const current = await apiRequest(`/factory-briefs/${brief.id}`);
      return { ok: Boolean(current.selected_project_id), value: current, detail: current.status };
    });

    await page.reload();
    await page.getByText(prompt, { exact: true }).click();
    await expect(page.getByText("brief_queued")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText("research_started")).toBeVisible();
    await expect(page.getByText("candidates_created")).toBeVisible();
    await expect(page.getByText("project_created")).toBeVisible();
    await expect(page.getByText("pipeline_queued").first()).toBeVisible();

    await page.getByRole("link", { name: /Open project/i }).click();
    await expect(page).toHaveURL(new RegExp(`/projects/${detail.selected_project_id}`));

    for (const tab of ["Research", "Tasks", "Code Agent", "QA", "Policy", "Artifacts"]) {
      await expect(page.getByRole("button", { name: tab })).toBeVisible();
    }

    await waitForApi("artifact appears", async () => {
      const artifacts = await apiRequest(`/projects/${detail.selected_project_id}/artifacts`);
      return { ok: artifacts.length > 0, value: artifacts, detail: `${artifacts.length} artifact(s)` };
    });
    await page.getByRole("button", { name: "Artifacts" }).click();
    await expect(page.getByText(/prd\.md|Flutter app|factory_run_report\.md|app-debug\.apk/)).toBeVisible({ timeout: 30_000 });
  } catch (error) {
    await testInfo.attach("browser-console.log", {
      body: consoleMessages.join("\n") || "No browser console output captured.",
      contentType: "text/plain",
    });
    await page.screenshot({ path: testInfo.outputPath("failure.png"), fullPage: true }).catch(() => undefined);
    throw error;
  }
});
