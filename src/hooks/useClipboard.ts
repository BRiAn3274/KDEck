import { callable } from "@decky/api";
import { type KeyboardEvent, useEffect, useRef, useState } from "react";
import type { ApiResult, Notebook } from "../types";
import { text } from "../i18n";

const getNotebook = callable<[], Notebook>("get_notebook");
const saveNotebook = callable<[text: string], Notebook>("save_notebook");
const setClipboard = callable<[text: string], ApiResult>("set_clipboard");
const runHiddenCommand = callable<[command: string], ApiResult>("run_hidden_command");

const CLIPBOARD_POLL_MS = 3000;

export function useClipboard(toast: (body: string) => void, run: (label: string, action: () => Promise<any>, refreshAfter?: boolean) => void) {
  const [clipboardText, setClipboardText] = useState("");
  const clipboardTextRef = useRef("");
  const editingRef = useRef(false);
  const initializedClipboardRef = useRef(false);
  const skipNextBlurSaveRef = useRef(false);
  const mountedRef = useRef(false);
  const timerRef = useRef<number | undefined>(undefined);

  const setText = (textStr: string) => {
    clipboardTextRef.current = textStr;
    setClipboardText(textStr);
  };

  const loadSavedClipboard = async () => {
    const saved = await getNotebook().catch(() => ({ ok: false, text: "" }));
    if (mountedRef.current && saved.text) setText(saved.text);
  };

  const pollReceivedClipboard = async () => {
    const saved = await getNotebook().catch(() => ({ ok: false, text: "" }));
    const nextText = saved.text || "";
    if (!mountedRef.current || editingRef.current || !saved.ok || !nextText) return;
    if (nextText !== clipboardTextRef.current) {
      setText(nextText);
      if (initializedClipboardRef.current) toast(text.receivedClipboard);
    }
    initializedClipboardRef.current = true;
  };

  const handleClipboardEnter = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== "Enter") return;
    const command = clipboardTextRef.current.trim().toLowerCase();
    if (!command.startsWith(":kdeck")) return;
    event.preventDefault();
    editingRef.current = false;
    skipNextBlurSaveRef.current = true;
    setText("");
    run(command.includes("logs") ? text.exportLogs : text.runCommand, async () => {
      const result = await runHiddenCommand(command);
      if (result.ok && result.message) toast(result.message);
      if (result.ok && result.path && !result.message) toast(`${text.logsExported}: ${result.path}`);
      return result;
    }, true);
  };

  const handleBlur = () => {
    editingRef.current = false;
    if (skipNextBlurSaveRef.current) {
      skipNextBlurSaveRef.current = false;
      return;
    }
    saveNotebook(clipboardTextRef.current).catch(() => undefined);
  };

  const handleFocus = () => { editingRef.current = true; };

  const handleChange = (value: string) => setText(value);

  const syncClipboard = async () => {
    const result = await setClipboard(clipboardTextRef.current);
    if (result.ok) await saveNotebook(clipboardTextRef.current);
    return result;
  };

  const startTimer = () => {
    stopTimer();
    timerRef.current = window.setInterval(() => pollReceivedClipboard().catch(() => undefined), CLIPBOARD_POLL_MS);
  };

  const stopTimer = () => {
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = undefined;
    }
  };

  useEffect(() => {
    mountedRef.current = true;
    loadSavedClipboard().catch(() => undefined);
    pollReceivedClipboard().catch(() => undefined);
    startTimer();

    const handleVisibility = () => {
      if (document.hidden) {
        stopTimer();
      } else {
        pollReceivedClipboard().catch(() => undefined);
        startTimer();
      }
    };
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      mountedRef.current = false;
      stopTimer();
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, []);

  return {
    clipboardText,
    clipboardTextRef,
    setText,
    handleClipboardEnter,
    handleBlur,
    handleFocus,
    handleChange,
    syncClipboard,
  };
}
