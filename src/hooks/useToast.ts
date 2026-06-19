import { toaster } from "@decky/api";
import { useRef } from "react";

type ToastNotification = { dismiss(): void };

const COOLDOWN_MS = 3000;

/**
 * Returns a toast function with built-in cooldown and deduplication.
 * - Same `category` within COOLDOWN_MS is silently ignored.
 * - A new toast of the same category dismisses the previous one.
 */
export function useToast() {
  const lastRef = useRef<Record<string, { time: number; notification: ToastNotification }>>({});

  return (body: string, category?: string) => {
    const key = category || body;
    const now = Date.now();
    const prev = lastRef.current[key];

    // Cooldown: suppress duplicate toasts within the window
    if (prev && now - prev.time < COOLDOWN_MS) return;

    // Dismiss the previous toast of the same category
    prev?.notification?.dismiss();

    const notification = toaster.toast({ title: "KDEck", body });
    lastRef.current[key] = { time: now, notification };
  };
}
