import {
  ButtonItem,
  PanelSection,
  PanelSectionRow,
  staticClasses,
} from "@decky/ui";
import { callable, definePlugin, toaster } from "@decky/api";
import { type KeyboardEvent, useEffect, useRef, useState } from "react";
import { FaLink } from "react-icons/fa";
import type { ApiResult, ConnectionSummary, ManagedEvent, ManagedFile, ManagedKde, Notebook, SendableFile, SendableFileList } from "./types";
import { text } from "./i18n";
import {
  deviceState,
  formatFileSummary,
  formatIp,
  infoRowStyle,
  infoTextStyle,
  inputStyle,
  resultMessage,
  shortDeviceName,
} from "./utils";
import { DeviceRow, TextRow } from "./components";

const ACTION_COOLDOWN_MS = 700;
const CLIPBOARD_POLL_MS = 3000;
const APP_VERSION = "0.5.4";

const getConnectionSummary = callable<[], ConnectionSummary>("get_connection_summary");
const setClipboard = callable<[text: string], ApiResult>("set_clipboard");
const getNotebook = callable<[], Notebook>("get_notebook");
const saveNotebook = callable<[text: string], Notebook>("save_notebook");
const runHiddenCommand = callable<[command: string], ApiResult>("run_hidden_command");
const startManagedKde = callable<[], ManagedKde>("start_managed_kde");
const listSendableFiles = callable<[category: string], SendableFileList>("list_sendable_files");
const sendFileToPhone = callable<[file_path: string, device_id: string], ApiResult>("send_file_to_phone");

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function Content() {
  const [summary, setSummary] = useState<ConnectionSummary>({ connection: text.checking });
  const [clipboardText, setClipboardText] = useState("");
  const [busy, setBusy] = useState(false);
  const [task, setTask] = useState("");
  const [view, setView] = useState<"main" | "send">("main");
  const [category, setCategory] = useState<"screenshots" | "recordings" | "logs">("screenshots");
  const [files, setFiles] = useState<SendableFile[]>([]);
  const [sendingPath, setSendingPath] = useState("");

  const mountedRef = useRef(false);
  const busyRef = useRef(false);
  const editingRef = useRef(false);
  const lastActionAtRef = useRef(0);
  const clipboardTextRef = useRef("");
  const initializedClipboardRef = useRef(false);
  const lastEventKeyRef = useRef("");
  const lastFileKeyRef = useRef("");
  const skipNextBlurSaveRef = useRef(false);

  const toast = (body: string) => toaster.toast({ title: "KDEck", body });

  const showKeyboard = (target: HTMLInputElement) => {
    target.focus();
    const rect = target.getBoundingClientRect();
    window.SteamClient?.System?.ShowFloatingGamepadTextInput?.(0, rect.x, rect.y, rect.width, rect.height);
    window.SteamClient?.System?.ShowVirtualKeyboard?.();
  };

  const setText = (textStr: string) => {
    clipboardTextRef.current = textStr;
    setClipboardText(textStr);
  };

  const acceptAction = () => {
    const now = Date.now();
    if (now - lastActionAtRef.current < ACTION_COOLDOWN_MS) return false;
    lastActionAtRef.current = now;
    return true;
  };

  const refresh = async () => {
    const next: ConnectionSummary = await getConnectionSummary().catch(() => ({ connection: text.checkFailed }));
    if (!mountedRef.current) return;
    setSummary(next);
    notifyManagedEvents(next.managed_kde?.last_events || []);
    notifyLastFile(next.managed_kde?.last_file);
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

  const run = async (label: string, action: () => Promise<ApiResult | Notebook | ManagedKde>, refreshAfter = false) => {
    if (busyRef.current) {
      toast(text.busy);
      return;
    }
    if (!acceptAction()) return;

    busyRef.current = true;
    setBusy(true);
    setTask(label);

    try {
      const result = await action();
      if (!mountedRef.current) return;
      toast(`${label} ${result.ok ? text.done : `${text.failed}: ${resultMessage(result)}`}`);
      if (refreshAfter) await refresh();
    } catch (error) {
      if (mountedRef.current) toast(`${label} ${text.failed}: ${String(error || text.unknownError)}`);
    } finally {
      busyRef.current = false;
      if (mountedRef.current) {
        setBusy(false);
        setTask("");
      }
    }
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

  useEffect(() => {
    mountedRef.current = true;
    startManagedKde().catch(() => undefined);
    refresh().catch(() => undefined);
    loadSavedClipboard().catch(() => undefined);
    pollReceivedClipboard().catch(() => undefined);

    const statusTimer = window.setInterval(() => refresh().catch(() => undefined), 5000);
    const clipboardTimer = window.setInterval(() => pollReceivedClipboard().catch(() => undefined), CLIPBOARD_POLL_MS);
    return () => {
      mountedRef.current = false;
      window.clearInterval(statusTimer);
      window.clearInterval(clipboardTimer);
    };
  }, []);

  const receiverReady = summary.managed_kde?.running && summary.managed_kde?.udp_working && summary.managed_kde?.tcp_working;
  const managedStatus = summary.managed_kde?.paused
    ? text.desktopPaused
    : receiverReady
      ? text.receiverReady
      : text.receiverStarting;
  const device = deviceState(summary.managed_kde);
  const connection = task || managedStatus;

  if (view === "send") {
    const loadFiles = () => {
      listSendableFiles(category).then((result: SendableFileList) => {
        if (mountedRef.current && result.ok && result.files) setFiles(result.files);
      }).catch(() => undefined);
    };

    useEffect(() => {
      loadFiles();
      const timer = window.setInterval(loadFiles, 5000);
      return () => window.clearInterval(timer);
    }, [category]);

    const handleSend = async (file: SendableFile) => {
      if (sendingPath) return;
      setSendingPath(file.path);
      const trustedKey = Object.keys(summary.managed_kde?.trusted_devices || {})[0] || "";
      const result = await sendFileToPhone(file.path, trustedKey).catch(() => ({ ok: false }));
      toast(result.ok ? text.fileSent : `${text.fileSendFailed}: ${resultMessage(result)}`);
      setSendingPath("");
    };

    const tabs: Array<{ key: typeof category; label: string }> = [
      { key: "screenshots", label: text.tabScreenshots },
      { key: "recordings", label: text.tabRecordings },
      { key: "logs", label: text.tabLogs },
    ];
    const maxFileSize = category === "recordings" ? 500 * 1024 * 1024 : category === "logs" ? 50 * 1024 * 1024 : 0;

    return (
      <>
        <PanelSection title={text.sendFile}>
          <PanelSectionRow>
            <ButtonItem layout="below" onClick={() => setView("main")}>
              {"< " + text.back}
            </ButtonItem>
          </PanelSectionRow>
          <PanelSectionRow>
            <div style={{ display: "flex", gap: "6px", ...infoRowStyle, justifyContent: "center" }}>
              {tabs.map((tab) => (
                <ButtonItem
                  key={tab.key}
                  layout="below"
                  disabled={category === tab.key}
                  onClick={() => setCategory(tab.key)}
                >
                  {tab.label}
                </ButtonItem>
              ))}
            </div>
          </PanelSectionRow>
          {files.length === 0 ? (
            <PanelSectionRow>
              <TextRow label={text.noFiles} />
            </PanelSectionRow>
          ) : (
            files.map((file, idx) => {
              const oversize = maxFileSize > 0 && file.size > maxFileSize;
              return (
                <PanelSectionRow key={idx}>
                  <div style={{ ...infoRowStyle, justifyContent: "space-between" }}>
                    <span style={{ ...infoTextStyle, maxWidth: "55%", color: oversize ? "#e07070" : undefined }} title={file.name}>
                      {file.name}
                    </span>
                    <span style={{ fontSize: "12px", color: oversize ? "#e07070" : "#888" }}>
                      {formatSize(file.size)}
                    </span>
                    <div style={{ marginLeft: "8px" }}>
                      <ButtonItem
                        layout="below"
                        disabled={sendingPath !== "" || oversize}
                        onClick={() => handleSend(file)}
                      >
                        {sendingPath === file.path ? text.sending : text.send}
                      </ButtonItem>
                    </div>
                  </div>
                </PanelSectionRow>
              );
            })
          )}
        </PanelSection>
      </>
    );
  }

  return (
    <>
      <PanelSection title={text.connection}>
        <PanelSectionRow>
          <ButtonItem layout="below" disabled={busy} onClick={() => run(text.refreshConnection, async () => startManagedKde(), true)}>
            {busy ? connection : text.refreshConnection}
          </ButtonItem>
        </PanelSectionRow>
        <DeviceRow label={receiverReady ? device.label : text.disconnected} connected={Boolean(receiverReady && device.connected)} />
        <TextRow label="Deck IP" value={formatIp(summary.deck_ips?.primary)} />
      </PanelSection>

      <PanelSection title={text.clipboard}>
        <PanelSectionRow>
          <input
            aria-label={text.clipboard}
            value={clipboardText}
            disabled={busy}
            style={inputStyle}
            onBlur={() => {
              editingRef.current = false;
              if (skipNextBlurSaveRef.current) {
                skipNextBlurSaveRef.current = false;
                return;
              }
              saveNotebook(clipboardTextRef.current).catch(() => undefined);
            }}
            onFocus={(event) => {
              editingRef.current = true;
              showKeyboard(event.currentTarget);
            }}
            onClick={(event) => showKeyboard(event.currentTarget)}
            onChange={(event) => setText(event.currentTarget.value)}
            onKeyDown={handleClipboardEnter}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            disabled={busy || !clipboardText}
            onClick={() =>
              run(text.syncText, async () => {
                const result = await setClipboard(clipboardText);
                if (result.ok) await saveNotebook(clipboardText);
                return result;
              })
            }
          >
            {text.syncText}
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>
      <PanelSection title={text.receiveFile}>
        <TextRow label={text.file} value={formatFileSummary(summary.managed_kde?.last_file, summary.incoming_directories?.items)} />
        <PanelSectionRow>
          <ButtonItem layout="below" disabled={busy} onClick={() => setView("send")}>
            {text.sendFile}
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>
    </>
  );
}

export default definePlugin(() => ({
  name: "KDEck",
  titleView: <div className={staticClasses.Title}>KDEck v{APP_VERSION}</div>,
  content: <Content />,
  icon: <FaLink />,
}));
