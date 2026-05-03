"use client";

import { useState } from "react";
import { Bell, Check, Trash2 } from "lucide-react";
import { formatDate } from "@/lib/utils";
import { useFeedback } from "@/components/feedback";
import { Badge, Button } from "@/components/ui";

export function NotificationCenter() {
  const [open, setOpen] = useState(false);
  const { notifications, unreadCount, markAllRead, clearNotifications } = useFeedback();

  return (
    <div className="relative">
      <Button
        type="button"
        variant="secondary"
        className="relative h-10 w-10 px-0"
        onClick={() => {
          setOpen((value) => !value);
          markAllRead();
        }}
        aria-label="Open notifications"
        title="Notifications"
      >
        <Bell size={16} />
        {unreadCount ? (
          <span className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold text-white">
            {unreadCount}
          </span>
        ) : null}
      </Button>

      {open ? (
        <div className="absolute right-0 top-12 z-50 w-[calc(100vw-2rem)] max-w-md rounded-lg border border-border bg-card p-4 text-card-foreground shadow-xl">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <div className="font-semibold">Notifications</div>
              <div className="text-xs text-muted-foreground">{notifications.length} recent event(s)</div>
            </div>
            <div className="flex gap-2">
              <Button type="button" variant="ghost" className="h-9 w-9 px-0" onClick={markAllRead} aria-label="Mark notifications read">
                <Check size={15} />
              </Button>
              <Button type="button" variant="ghost" className="h-9 w-9 px-0" onClick={clearNotifications} aria-label="Clear notifications">
                <Trash2 size={15} />
              </Button>
            </div>
          </div>
          <div className="max-h-96 space-y-2 overflow-auto">
            {notifications.map((item) => (
              <div key={item.id} className="rounded-md border border-border bg-background p-3">
                <div className="mb-1 flex flex-wrap items-center gap-2">
                  <Badge tone={item.tone}>{item.tone}</Badge>
                  {!item.read ? <span className="h-2 w-2 rounded-full bg-primary" /> : null}
                  <span className="text-xs text-muted-foreground">{formatDate(item.createdAt)}</span>
                </div>
                {item.title ? <div className="text-sm font-medium">{item.title}</div> : null}
                <div className="text-sm text-muted-foreground">{item.message}</div>
              </div>
            ))}
            {!notifications.length ? <div className="rounded-md bg-muted p-4 text-center text-sm text-muted-foreground">No notifications yet.</div> : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
