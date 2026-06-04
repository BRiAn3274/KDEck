import {
  ButtonItem,
  PanelSection,
  PanelSectionRow,
} from "@decky/ui";
import { callable, toaster } from "@decky/api";
import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import type { ApiResult, ConnectionSummary, SendableFile, SendableFileList } from "./types";
import { text } from "./i18n";
import { infoTextStyle, resultMessage } from "./utils";

const listSendableFiles = callable<[category: string], SendableFileList>("list_sendable_files");
const sendFileToPhone = callable<[file_path: string, device_id: string], ApiResult>("send_file_to_phone");
const getConnectionSummary = callable<[], ConnectionSummary>("get_connection_summary");

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const tabBarStyle: CSSProperties = {
  display: "flex",
  gap: "2px",
  borderRadius: "3px",
  overflow: "hidden",
};

const tabStyle = (active: boolean): CSSProperties => ({
  flex: 1,
  textAlign: "center",
  padding: "6px 0",
  fontSize: "14px",
  fontWeight: active ? 700 : 400,
  background: active ? "var(--decky-accent, #1a9fff)" : "var(--decky-button, #3e4652)",
  color: active ? "#fff" : "var(--decky-text, #969696)",
  border: "none",
  cursor: "pointer",
  outline: "none",
  transition: "background 0.15s",
});

const fileIcon = (ext: string): string => {
  if (/\.(png|jpg|jpeg|webp|bmp)$/i.test(ext)) return "\u{1F5BC}";
  if (/\.(mp4|mkv|webm|mov)$/i.test(ext)) return "\u{1F3AC}";
  return "\u{1F4C4}";
};

function fileNameParts(full: string): { icon: string; stem: string; ext: string } {
  const lastDot = full.lastIndexOf(".");
  const stem = lastDot > 0 ? full.slice(0, lastDot) : full;
  const ext = lastDot > 0 ? full.slice(lastDot) : "";
  return { icon: fileIcon(ext), stem, ext };
}

export default function SendPage() {
  const [category, setCategory] = useState<"screenshots" | "recordings" | "logs">("screenshots");
  const [files, setFiles] = useState<SendableFile[]>([]);
  const [sendingPath, setSendingPath] = useState("");
  const [trustedKey, setTrustedKey] = useState("");

  const toast = (body: string) => toaster.toast({ title: "KDEck", body });

  useEffect(() => {
    getConnectionSummary().then((s) => {
      const key = Object.keys(s.managed_kde?.trusted_devices || {})[0] || "";
      setTrustedKey(key);
    }).catch(() => undefined);
  }, []);

  useEffect(() => {
    const load = () => {
      listSendableFiles(category).then((result: SendableFileList) => {
        if (result.ok && result.files) setFiles(result.files);
      }).catch(() => undefined);
    };
    load();
    const timer = window.setInterval(load, 5000);
    return () => window.clearInterval(timer);
  }, [category]);

  const handleSend = async (file: SendableFile) => {
    if (sendingPath || !trustedKey) return;
    setSendingPath(file.path);
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
    <PanelSection title={text.sendFile}>
      {!trustedKey ? (
        <PanelSectionRow>
          <span style={infoTextStyle}>{text.noFiles} — {text.disconnected}</span>
        </PanelSectionRow>
      ) : (
        <>
          <PanelSectionRow>
            <div style={tabBarStyle}>
              {tabs.map((tab) => (
                <button
                  key={tab.key}
                  style={tabStyle(category === tab.key)}
                  disabled={category === tab.key}
                  onClick={() => setCategory(tab.key)}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </PanelSectionRow>
          {files.length === 0 ? (
            <PanelSectionRow>
              <span style={infoTextStyle}>{text.noFiles}</span>
            </PanelSectionRow>
          ) : (
            files.map((file, idx) => {
              const oversize = maxFileSize > 0 && file.size > maxFileSize;
              const { icon, stem, ext } = fileNameParts(file.name);
              const isSending = sendingPath === file.path;
              return (
                <PanelSectionRow key={idx}>
                  <ButtonItem
                    layout="below"
                    disabled={sendingPath !== "" || oversize}
                    onClick={() => handleSend(file)}
                  >
                    <span style={{ fontSize: "13px", opacity: oversize ? 0.55 : 1 }}>
                      {icon}{"  "}
                      <span style={{ fontWeight: 600 }}>{stem}</span>
                      <span style={{ opacity: 0.45 }}>{ext}</span>
                      <span style={{ margin: "0 10px", opacity: 0.35 }}>{"·"}</span>
                      <span style={{ fontSize: "12px", opacity: 0.55 }}>{formatSize(file.size)}</span>
                      {oversize && <span style={{ marginLeft: "8px", color: "#e07070", fontSize: "11px" }}>({text.oversize})</span>}
                      {isSending && <span style={{ marginLeft: "8px", opacity: 0.55 }}>{text.sending}...</span>}
                    </span>
                  </ButtonItem>
                </PanelSectionRow>
              );
            })
          )}
        </>
      )}
    </PanelSection>
  );
}
