import type { DoctorResponse, Worker } from "@/lib/api";

type ClassDictionary = Record<string, boolean | null | undefined>;
type ClassValue = string | number | false | null | undefined | ClassDictionary | ClassValue[];

function toClassName(value: ClassValue): string[] {
  if (!value) return [];
  if (typeof value === "string" || typeof value === "number") return [String(value)];
  if (Array.isArray(value)) return value.flatMap(toClassName);
  return Object.entries(value).flatMap(([key, enabled]) => enabled ? [key] : []);
}

export function cn(...inputs: ClassValue[]) {
  return inputs.flatMap(toClassName).join(" ");
}

export function formatDate(value?: string | null) {
  if (!value) return "Never";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

export function statusTone(status: string) {
  const normalized = status.toLowerCase();
  if (["passed", "online", "release_candidate", "succeeded", "active", "ok"].includes(normalized)) return "success";
  if (["failed", "needs_human_review", "disabled", "error"].includes(normalized)) return "danger";
  if (["queued", "running", "busy"].includes(normalized)) return "warning";
  return "neutral";
}

export function workerRequiresCodex(worker: Pick<Worker, "worker_enable_codex">) {
  return worker.worker_enable_codex;
}

export function isReadyWorker(worker: Pick<Worker, "status" | "has_flutter" | "has_codex" | "worker_enable_codex">) {
  return worker.status === "online" && worker.has_flutter && (!workerRequiresCodex(worker) || worker.has_codex);
}

export function modeLabelFromDoctor(doctor: DoctorResponse | null | undefined) {
  return doctor?.worker_mode_label ?? "Mode: unknown";
}
