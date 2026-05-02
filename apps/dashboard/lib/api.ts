function getApiBaseUrl() {
  if (typeof window === "undefined") {
    return process.env.API_INTERNAL_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
  }
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
}

export type ApiKey = {
  id: string;
  provider: string;
  label: string;
  key_hint: string;
  status: string;
  daily_budget_usd: string;
  monthly_budget_usd: string;
  total_estimated_spend_usd: string;
  assigned_worker_id: string | null;
  created_at: string;
  last_used_at: string | null;
};

export type ActionResponse = {
  status: string;
  detail: string;
};

export type DoctorCheck = {
  id: string;
  label: string;
  status: string;
  detail: string;
  required: boolean;
  guidance: string | null;
};

export type DoctorResponse = {
  status: string;
  generated_at: string;
  checks: DoctorCheck[];
};

export type Worker = {
  id: string;
  machine_name: string;
  os: string;
  arch: string;
  has_docker: boolean;
  has_flutter: boolean;
  has_android_sdk: boolean;
  has_xcode: boolean;
  has_codex: boolean;
  has_aider: boolean;
  status: string;
  last_heartbeat_at: string | null;
  current_job_id: string | null;
  created_at: string;
};

export type Idea = {
  id: string;
  title: string;
  description: string;
  source: string;
  opportunity_score: number;
  status: string;
  evidence_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type Project = {
  id: string;
  name: string;
  slug: string;
  idea_id: string | null;
  status: string;
  target_platforms: string[];
  workspace_path: string | null;
  created_at: string;
  updated_at: string;
};

export type AgentEvent = {
  id: string;
  project_id: string;
  agent_run_id: string | null;
  step: string;
  level: string;
  message: string;
  stdout: string | null;
  stderr: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
};

export type QAResult = {
  id: string;
  project_id: string;
  status: string;
  command: string;
  exit_code: number;
  stdout: string | null;
  stderr: string | null;
  created_at: string;
};

export type PolicyResult = {
  id: string;
  project_id: string;
  risk: string;
  passed: boolean;
  issues: string[];
  required_changes: string[];
  created_at: string;
};

export type Artifact = {
  id: string;
  project_id: string;
  kind: string;
  name: string;
  path: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
};

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function getErrorMessage(body: string, status: number) {
  if (!body) {
    return `Request failed: ${status}`;
  }
  try {
    const parsed = JSON.parse(body) as { detail?: unknown };
    if (typeof parsed.detail === "string") {
      return parsed.detail;
    }
    if (Array.isArray(parsed.detail)) {
      return parsed.detail.map((item) => item.msg ?? item.message ?? JSON.stringify(item)).join("; ");
    }
  } catch {
    return body;
  }
  return body;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });
  if (!response.ok) {
    const text = await response.text();
    throw new ApiError(response.status, getErrorMessage(text, response.status));
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; service: string }>("/health"),
  doctor: () => request<DoctorResponse>("/doctor"),
  apiKeys: () => request<ApiKey[]>("/api-keys"),
  createApiKey: (body: unknown) => request<ApiKey>("/api-keys", { method: "POST", body: JSON.stringify(body) }),
  updateApiKey: (id: string, body: unknown) => request<ApiKey>(`/api-keys/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteApiKey: (id: string) => request<ActionResponse>(`/api-keys/${id}`, { method: "DELETE" }),
  testApiKey: (id: string) => request<{ status: string; provider: string; detail: string }>(`/api-keys/${id}/test`, { method: "POST" }),
  workers: () => request<Worker[]>("/workers"),
  ideas: () => request<Idea[]>("/ideas"),
  createIdea: (body: unknown) => request<Idea>("/ideas", { method: "POST", body: JSON.stringify(body) }),
  projects: () => request<Project[]>("/projects"),
  project: (id: string) => request<Project>(`/projects/${id}`),
  createProject: (body: unknown) => request<Project>("/projects", { method: "POST", body: JSON.stringify(body) }),
  deleteProject: (id: string) => request<ActionResponse>(`/projects/${id}`, { method: "DELETE" }),
  runPipeline: (id: string) => request<{ project_id: string; status: string; queue: string }>(`/projects/${id}/run-pipeline`, { method: "POST" }),
  retryPipeline: (id: string) => request<{ project_id: string; status: string; queue: string }>(`/projects/${id}/retry`, { method: "POST" }),
  stopPipeline: (id: string) => request<ActionResponse>(`/projects/${id}/stop`, { method: "POST" }),
  allEvents: (params?: { project_id?: string; level?: string; search?: string; limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.project_id) search.set("project_id", params.project_id);
    if (params?.level) search.set("level", params.level);
    if (params?.search) search.set("search", params.search);
    if (params?.limit) search.set("limit", String(params.limit));
    const query = search.toString();
    return request<AgentEvent[]>(`/events${query ? `?${query}` : ""}`);
  },
  events: (id: string) => request<AgentEvent[]>(`/projects/${id}/events`),
  clearEvents: (id: string) => request<ActionResponse>(`/projects/${id}/events`, { method: "DELETE" }),
  qa: (id: string) => request<QAResult[]>(`/projects/${id}/qa`),
  policy: (id: string) => request<PolicyResult[]>(`/projects/${id}/policy`),
  artifacts: (id: string) => request<Artifact[]>(`/projects/${id}/artifacts`)
};
