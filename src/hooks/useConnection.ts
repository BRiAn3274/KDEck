import { callable } from "@decky/api";
import { useEffect, useRef, useState } from "react";
import type { ConnectionSummary, ManagedEvent, ManagedFile, ManagedKde } from "../types";
import { text } from "../i18n";

const getConnectionSummary = callable<[], ConnectionSummary>("get_connection_summary");
const startManagedKde = callable<[], ManagedKde>("start_managed_kde");

const STATUS_POLL_MS = 5000;

export function useConnection(toast: (body: string) => void) {
  const [summary, setSummary] = useState<ConnectionSummary>({ connection: text.checking });
  const mountedRef = useRef(false);
  const lastEventKeyRef = useRef("");
  const lastFileKeyRef = useRef("");
  const timersRef = useRef<{ status?: number }>({});

  const refresh = async () => {
    const next: ConnectionSummary = await getConnectionSummary().catch(() => ({ connection: text.checkFailed }));
    if (!mountedRef.current) return;
    setSummary(next);
    notifyManagedEvents(next.managed_kde?.last_events || []);
    notifyLastFile(next.managed_kde?.last_file);
  };

  const notifyManagedEvents = (events: ManagedEvent[]) => {
    const latest = events[events.length - 1];
    if (!latest?.event || !latest.time) return;
    const key = `${latest.time}:${latest.event}:${latest.file || ""}:${latest.length || ""}`;
    if (key === lastEventKeyRef.current) return;
    lastEventKeyRef.current = key;
    if (latest.event === "file_receive_failed") toast(text.fileReceiveFailed);
  };

  const notifyLastFile = (file?: ManagedFile | null) => {
    if (!file?.time || !file.file) return;
    const key = `${file.time}:${file.status}:${file.file}:${file.size || ""}`;
    if (key === lastFileKeyRef.current) return;
    lastFileKeyRef.current = key;
    if (file.status === "received") toast(`${text.fileReceived}: ${file.file}`);
    if (file.status === "failed") toast(`${text.fileReceiveFailed}: ${file.file}`);
  };

  const startTimers = () => {
    stopTimers();
    timersRef.current.status = window.setInterval(() => refresh().catch(() => undefined), STATUS_POLL_MS);
  };

  const stopTimers = () => {
    if (timersRef.current.status) {
      window.clearInterval(timersRef.current.status);
      timersRef.current.status = undefined;
    }
  };

  useEffect(() => {
    mountedRef.current = true;
    startManagedKde().catch(() => undefined);
    refresh().catch(() => undefined);
    startTimers();

    // Visibility-based polling: stop when hidden, resume when visible
    const handleVisibility = () => {
      if (document.hidden) {
        stopTimers();
      } else {
        refresh().catch(() => undefined);
        startTimers();
      }
    };
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      mountedRef.current = false;
      stopTimers();
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, []);

  return { summary, refresh };
}
