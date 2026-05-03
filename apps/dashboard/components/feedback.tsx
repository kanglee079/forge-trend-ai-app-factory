"use client";

import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui";

type ToastTone = "success" | "warning" | "danger" | "neutral";

type Toast = {
  id: number;
  title?: string;
  message: string;
  tone: ToastTone;
};

export type NotificationItem = Toast & {
  createdAt: string;
  read: boolean;
};

type ConfirmOptions = {
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: "danger" | "neutral";
};

type FeedbackContextValue = {
  notify: (toast: Omit<Toast, "id">) => void;
  confirm: (options: ConfirmOptions) => Promise<boolean>;
  notifications: NotificationItem[];
  unreadCount: number;
  markAllRead: () => void;
  clearNotifications: () => void;
};

const FeedbackContext = createContext<FeedbackContextValue | null>(null);

export function FeedbackProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [confirmState, setConfirmState] = useState<ConfirmOptions | null>(null);
  const confirmResolver = useRef<((confirmed: boolean) => void) | null>(null);

  const notify = useCallback((toast: Omit<Toast, "id">) => {
    const id = Date.now() + Math.random();
    setToasts((current) => [...current, { ...toast, id }]);
    setNotifications((current) => [{ ...toast, id, createdAt: new Date().toISOString(), read: false }, ...current].slice(0, 50));
    window.setTimeout(() => {
      setToasts((current) => current.filter((item) => item.id !== id));
    }, 5200);
  }, []);

  const confirm = useCallback((options: ConfirmOptions) => {
    setConfirmState(options);
    return new Promise<boolean>((resolve) => {
      confirmResolver.current = resolve;
    });
  }, []);

  const closeConfirm = useCallback((confirmed: boolean) => {
    confirmResolver.current?.(confirmed);
    confirmResolver.current = null;
    setConfirmState(null);
  }, []);

  const markAllRead = useCallback(() => {
    setNotifications((current) => current.map((item) => ({ ...item, read: true })));
  }, []);

  const clearNotifications = useCallback(() => {
    setNotifications([]);
  }, []);

  const unreadCount = notifications.filter((item) => !item.read).length;
  const value = useMemo(
    () => ({ notify, confirm, notifications, unreadCount, markAllRead, clearNotifications }),
    [notify, confirm, notifications, unreadCount, markAllRead, clearNotifications]
  );

  return (
    <FeedbackContext.Provider value={value}>
      {children}
      <ToastViewport toasts={toasts} onDismiss={(id) => setToasts((current) => current.filter((item) => item.id !== id))} />
      {confirmState ? <ConfirmDialog options={confirmState} onClose={closeConfirm} /> : null}
    </FeedbackContext.Provider>
  );
}

export function useFeedback() {
  const value = useContext(FeedbackContext);
  if (!value) {
    throw new Error("useFeedback must be used inside FeedbackProvider");
  }
  return value;
}

function ToastViewport({ toasts, onDismiss }: { toasts: Toast[]; onDismiss: (id: number) => void }) {
  return (
    <div className="fixed right-4 top-4 z-50 flex w-[calc(100vw-2rem)] max-w-sm flex-col gap-3" aria-live="polite">
      {toasts.map((toast) => (
        <ToastCard key={toast.id} toast={toast} onDismiss={() => onDismiss(toast.id)} />
      ))}
    </div>
  );
}

function ToastCard({ toast, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  const Icon = toast.tone === "success" ? CheckCircle2 : toast.tone === "danger" ? XCircle : toast.tone === "warning" ? AlertTriangle : Info;
  return (
    <div
      className={cn(
        "flex items-start gap-3 rounded-lg border bg-card p-4 text-sm text-card-foreground shadow-lg",
        toast.tone === "success" && "border-emerald-200",
        toast.tone === "warning" && "border-amber-200",
        toast.tone === "danger" && "border-red-200",
        toast.tone === "neutral" && "border-border"
      )}
      role="status"
    >
      <Icon
        className={cn(
          "mt-0.5 h-4 w-4 shrink-0",
          toast.tone === "success" && "text-emerald-600",
          toast.tone === "warning" && "text-amber-600",
          toast.tone === "danger" && "text-red-600",
          toast.tone === "neutral" && "text-primary"
        )}
      />
      <div className="min-w-0 flex-1">
        {toast.title ? <div className="font-medium">{toast.title}</div> : null}
        <div className="text-muted-foreground">{toast.message}</div>
      </div>
      <button
        type="button"
        onClick={onDismiss}
        className="rounded-md p-1 text-muted-foreground transition hover:bg-muted hover:text-foreground"
        aria-label="Dismiss notification"
      >
        <X size={15} />
      </button>
    </div>
  );
}

function ConfirmDialog({ options, onClose }: { options: ConfirmOptions; onClose: (confirmed: boolean) => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 px-4" role="presentation">
      <div className="w-full max-w-md rounded-lg border border-border bg-card p-5 text-card-foreground shadow-xl" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
        <div className="flex items-start gap-3">
          <div
            className={cn(
              "flex h-9 w-9 shrink-0 items-center justify-center rounded-md",
              options.tone === "danger" ? "bg-red-100 text-red-700" : "bg-muted text-primary"
            )}
          >
            <AlertTriangle size={18} />
          </div>
          <div>
            <h2 id="confirm-title" className="text-base font-semibold">
              {options.title}
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">{options.description}</p>
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={() => onClose(false)}>
            {options.cancelLabel ?? "Cancel"}
          </Button>
          <Button type="button" variant={options.tone === "danger" ? "danger" : "primary"} onClick={() => onClose(true)}>
            {options.confirmLabel ?? "Confirm"}
          </Button>
        </div>
      </div>
    </div>
  );
}
