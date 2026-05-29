import type { CSSProperties } from "react";
import type { ApiResult, DeckIp, IncomingDirectory, ManagedFile, ManagedKde, Notebook } from "./types";
import { text } from "./i18n";

export const resultMessage = (result?: ApiResult | Notebook | ManagedKde) => {
  const code = result?.error?.code;
  if (code && text.errors[code]) return text.errors[code];
  return result?.error?.message || (result?.ok ? text.done : text.failed);
};

export const formatIp = (ip?: DeckIp | null) => {
  if (!ip) return "-";
  return ip.address;
};

export const formatIncomingPath = (items?: IncomingDirectory[]) => {
  if (!items?.length) return "/home/deck/Downloads";
  return items[0].path;
};

export const shortDirectory = (path: string) => {
  const parts = path.replace(/\\/g, "/").split("/").filter(Boolean);
  return parts[parts.length - 1] || path;
};

export const formatFileSummary = (file?: ManagedFile | null, items?: IncomingDirectory[]) => {
  const directory = shortDirectory(formatIncomingPath(items));
  if (!file?.file) return `${text.noFile} → ${directory}`;
  if (file.status === "failed") return `${file.file} ${text.failed}`;
  return `${file.file} → ${directory}`;
};

export const shortDeviceName = (name?: string) => {
  const clean = (name || "").trim();
  if (!clean) return "";
  return clean.length > 18 ? `${clean.slice(0, 16)}...` : clean;
};

export const deviceState = (managed?: ManagedKde) => {
  const trusted = managed?.trusted_devices || {};
  const devices = managed?.discovered_devices || [];
  const trustedDevice = devices.find((device) => device.device_id && trusted[device.device_id]);
  if (trustedDevice?.device_name) return { label: shortDeviceName(trustedDevice.device_name), connected: true };
  if (managed?.paired) return { label: text.disconnected, connected: false };
  const latest = devices[0];
  if (latest?.device_name) return { label: shortDeviceName(latest.device_name), connected: false };
  return { label: text.disconnected, connected: false };
};

export const inputStyle: CSSProperties = {
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

export const statusDotStyle = (connected: boolean): CSSProperties => ({
  ...statusDotBaseStyle,
  display: "inline-block",
  marginLeft: "6px",
  verticalAlign: "middle",
  background: connected ? "#44d36a" : "#59606a",
  opacity: connected ? 1 : 0.45,
});

export const infoRowStyle: CSSProperties = {
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

export const infoTextStyle: CSSProperties = {
  minWidth: 0,
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};
