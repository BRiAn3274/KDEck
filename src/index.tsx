import {
  ButtonItem,
  PanelSection,
  PanelSectionRow,
  staticClasses,
} from "@decky/ui";
import { callable, definePlugin, toaster } from "@decky/api";
import { type CSSProperties, useEffect, useRef, useState } from "react";
import { FaLink } from "react-icons/fa";

const ACTION_COOLDOWN_MS = 700;
const CLIPBOARD_POLL_MS = 3000;
const APP_VERSION = "0.3.8";

type SteamClientLike = {
  System?: {
    ShowFloatingGamepadTextInput?: (
      inputMode: number,
      x: number,
      y: number,
      width: number,
      height: number,
    ) => void;
    ShowVirtualKeyboard?: () => void;
  };
};

declare global {
  interface Window {
    SteamClient?: SteamClientLike;
  }
}

type ApiResult = {
  ok?: boolean;
  error?: {
    code?: string;
    message?: string;
  };
  text?: string;
};

type Status = {
  kdeconnectd?: {
    running?: boolean;
  };
};

type Device = {
  id: string;
  name: string;
  reachable?: boolean | null;
};

type DeviceResult = {
  paired?: Device[];
};

type DeckIp = {
  interface: string;
  address: string;
  prefixlen?: number;
};

type IncomingDirectory = {
  path: string;
};

type ConnectionSummary = {
  connection?: string;
  status?: Status;
  devices?: DeviceResult;
  selected_device?: Device | null;
  deck_ips?: {
    primary?: DeckIp | null;
  };
  incoming_directories?: {
    items?: IncomingDirectory[];
  };
  managed_kde?: ManagedKde;
};

type Notebook = {
  ok?: boolean;
  text?: string;
  error?: {
    message?: string;
  };
};

type ManagedKde = {
  ok?: boolean;
  running?: boolean;
  device_name?: string;
  udp_working?: boolean;
  tcp_working?: boolean;
  paired?: boolean;
  paused?: boolean;
  pause_reason?: string | null;
  discovered_devices?: ManagedDevice[];
  trusted_devices?: Record<string, unknown>;
  last_events?: ManagedEvent[];
  last_file?: ManagedFile | null;
  error?: {
    message?: string;
  };
};

type ManagedDevice = {
  device_id?: string;
  device_name?: string;
  host?: string;
  last_seen?: number;
};

type ManagedEvent = {
  time?: number;
  event?: string;
  file?: string;
  length?: number;
};

type ManagedFile = {
  status?: string;
  file?: string;
  path?: string;
  size?: number;
  time?: number;
};

const getConnectionSummary = callable<[], ConnectionSummary>("get_connection_summary");
const setClipboard = callable<[text: string], ApiResult>("set_clipboard");
const getNotebook = callable<[], Notebook>("get_notebook");
const saveNotebook = callable<[text: string], Notebook>("save_notebook");
const startManagedKde = callable<[], ManagedKde>("start_managed_kde");

const resultMessage = (result?: ApiResult | Notebook | ManagedKde) =>
  result?.error?.message || (result?.ok ? "完成" : "失败");

const formatIp = (ip?: DeckIp | null) => {
  if (!ip) return "-";
  return ip.address;
};

const formatIncomingPath = (items?: IncomingDirectory[]) => {
  if (!items?.length) return "/home/deck/Downloads";
  return items[0].path;
};

const shortDirectory = (path: string) => {
  const parts = path.replace(/\\/g, "/").split("/").filter(Boolean);
  return parts[parts.length - 1] || path;
};

const formatFileSummary = (file?: ManagedFile | null, items?: IncomingDirectory[]) => {
  const directory = shortDirectory(formatIncomingPath(items));
  if (!file?.file) return `暂无 -> ${directory}`;
  if (file.status === "failed") return `${file.file} 接收失败`;
  return `${file.file} -> ${directory}`;
};

const shortDeviceName = (name?: string) => {
  const clean = (name || "").trim();
  if (!clean) return "";
  return clean.length > 18 ? `${clean.slice(0, 16)}...` : clean;
};

const deviceState = (managed?: ManagedKde) => {
  const trusted = managed?.trusted_devices || {};
  const devices = managed?.discovered_devices || [];
  const trustedDevice = devices.find((device) => device.device_id && trusted[device.device_id]);
  if (trustedDevice?.device_name) return { label: shortDeviceName(trustedDevice.device_name), connected: true };
  if (managed?.paired) return { label: "未连接", connected: false };
  const latest = devices[0];
  if (latest?.device_name) return { label: shortDeviceName(latest.device_name), connected: false };
  return { label: "未连接", connected: false };
};

const inputStyle: CSSProperties = {
  width: "100%",
  boxSizing: "border-box",
  padding: "7px 10px",
  fontSize: "15px",
  fontWeight: 400,
  lineHeight: "20px",
  textAlign: "left",
};

const statusDotBaseStyle: CSSProperties = {
  width: "9px",
  height: "9px",
  borderRadius: "50%",
  flex: "0 0 auto",
};

const statusDotStyle = (connected: boolean): CSSProperties => ({
  ...statusDotBaseStyle,
  display: "inline-block",
  marginLeft: "6px",
  verticalAlign: "middle",
  background: connected ? "#44d36a" : "#59606a",
  opacity: connected ? 1 : 0.45,
});

const infoRowStyle: CSSProperties = {
  width: "100%",
  boxSizing: "border-box",
  display: "flex",
  alignItems: "center",
  minHeight: "34px",
  fontSize: "15px",
  fontWeight: 600,
  lineHeight: "20px",
  overflow: "hidden",
};

const infoTextStyle: CSSProperties = {
  minWidth: 0,
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};

function DeviceRow({ label, connected }: { label: string; connected: boolean }) {
  return (
    <PanelSectionRow>
      <div style={infoRowStyle}>
        <span style={infoTextStyle}>设备: {label}</span>
        <span aria-label="连接状态" style={statusDotStyle(connected)} />
      </div>
    </PanelSectionRow>
  );
}

function TextRow({ label, value }: { label: string; value?: string }) {
  return (
    <PanelSectionRow>
      <div style={infoRowStyle}>
        <span style={infoTextStyle}>{label}: {value || "-"}</span>
      </div>
    </PanelSectionRow>
  );
}

function Content() {
  const [summary, setSummary] = useState<ConnectionSummary>({ connection: "检查中" });
  const [clipboardText, setClipboardText] = useState("");
  const [busy, setBusy] = useState(false);
  const [task, setTask] = useState("");

  const mountedRef = useRef(false);
  const busyRef = useRef(false);
  const editingRef = useRef(false);
  const lastActionAtRef = useRef(0);
  const clipboardTextRef = useRef("");
  const initializedClipboardRef = useRef(false);
  const lastEventKeyRef = useRef("");
  const lastFileKeyRef = useRef("");

  const toast = (body: string) => toaster.toast({ title: "KDEck", body });

  const showKeyboard = (target: HTMLInputElement) => {
    target.focus();
    const rect = target.getBoundingClientRect();
    window.SteamClient?.System?.ShowFloatingGamepadTextInput?.(0, rect.x, rect.y, rect.width, rect.height);
    window.SteamClient?.System?.ShowVirtualKeyboard?.();
  };

  const setText = (text: string) => {
    clipboardTextRef.current = text;
    setClipboardText(text);
  };

  const acceptAction = () => {
    const now = Date.now();
    if (now - lastActionAtRef.current < ACTION_COOLDOWN_MS) return false;
    lastActionAtRef.current = now;
    return true;
  };

  const refresh = async () => {
    const next: ConnectionSummary = await getConnectionSummary().catch(() => ({ connection: "检查失败" }));
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
      if (initializedClipboardRef.current) toast("已收到手机剪贴板");
    }
    initializedClipboardRef.current = true;
  };

  const notifyManagedEvents = (events: ManagedEvent[]) => {
    const latest = events[events.length - 1];
    if (!latest?.event || !latest.time) return;
    const key = `${latest.time}:${latest.event}:${latest.file || ""}:${latest.length || ""}`;
    if (key === lastEventKeyRef.current) return;
    lastEventKeyRef.current = key;
    if (latest.event === "file_receive_failed") toast("文件接收失败");
  };

  const notifyLastFile = (file?: ManagedFile | null) => {
    if (!file?.time || !file.file) return;
    const key = `${file.time}:${file.status}:${file.file}:${file.size || ""}`;
    if (key === lastFileKeyRef.current) return;
    lastFileKeyRef.current = key;
    if (file.status === "received") toast(`已接收文件：${file.file}`);
    if (file.status === "failed") toast(`文件接收失败：${file.file}`);
  };

  const run = async (label: string, action: () => Promise<ApiResult | Notebook | ManagedKde>, refreshAfter = false) => {
    if (busyRef.current) {
      toast("正在处理，请稍等");
      return;
    }
    if (!acceptAction()) return;

    busyRef.current = true;
    setBusy(true);
    setTask(label);

    try {
      const result = await action();
      if (!mountedRef.current) return;
      toast(`${label}${result.ok ? "完成" : `失败：${resultMessage(result)}`}`);
      if (refreshAfter) await refresh();
    } catch (error) {
      if (mountedRef.current) toast(`${label}失败：${String(error || "未知错误")}`);
    } finally {
      busyRef.current = false;
      if (mountedRef.current) {
        setBusy(false);
        setTask("");
      }
    }
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
    ? "桌面模式暂停"
    : receiverReady
      ? "KDEck 接收中"
      : "KDEck 启动中";
  const device = deviceState(summary.managed_kde);
  const connection = task || managedStatus;

  return (
    <>
      <PanelSection title="连接">
        <PanelSectionRow>
          <ButtonItem layout="below" disabled={busy} onClick={() => run("刷新连接", async () => startManagedKde(), true)}>
            {busy ? connection : "刷新连接"}
          </ButtonItem>
        </PanelSectionRow>
        <DeviceRow label={receiverReady ? device.label : "未连接"} connected={Boolean(receiverReady && device.connected)} />
        <TextRow label="Deck IP" value={formatIp(summary.deck_ips?.primary)} />
      </PanelSection>

      <PanelSection title="剪贴板">
        <PanelSectionRow>
          <input
            aria-label="剪贴板"
            value={clipboardText}
            disabled={busy}
            style={inputStyle}
            onBlur={() => {
              editingRef.current = false;
              saveNotebook(clipboardTextRef.current).catch(() => undefined);
            }}
            onFocus={(event) => {
              editingRef.current = true;
              showKeyboard(event.currentTarget);
            }}
            onClick={(event) => showKeyboard(event.currentTarget)}
            onChange={(event) => setText(event.currentTarget.value)}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            disabled={busy || !clipboardText}
            onClick={() =>
              run("同步文本框", async () => {
                const result = await setClipboard(clipboardText);
                if (result.ok) await saveNotebook(clipboardText);
                return result;
              })
            }
          >
            同步文本框
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>
      <PanelSection title="接收文件">
        <TextRow label="文件" value={formatFileSummary(summary.managed_kde?.last_file, summary.incoming_directories?.items)} />
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
