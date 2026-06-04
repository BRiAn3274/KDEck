import {
  ButtonItem,
  PanelSection,
  PanelSectionRow,
} from "@decky/ui";
import { callable, toaster } from "@decky/api";
import { useEffect, useState } from "react";
import type { ApiResult, ConnectionSummary, SendableFile, SendableFileList } from "./types";
import { text } from "./i18n";
import { infoRowStyle, infoTextStyle, resultMessage } from "./utils";

const listSendableFiles = callable<[category: string], SendableFileList>("list_sendable_files");
const sendFileToPhone = callable<[file_path: string, device_id: string], ApiResult>("send_file_to_phone");
const getConnectionSummary = callable<[], ConnectionSummary>("get_connection_summary");

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
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
            <div style={{ display: "flex", gap: "6px", justifyContent: "center", padding: "6px 0" }}>
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
              <span style={infoTextStyle}>{text.noFiles}</span>
            </PanelSectionRow>
          ) : (
            files.map((file, idx) => {
              const oversize = maxFileSize > 0 && file.size > maxFileSize;
              return (
                <PanelSectionRow key={idx}>
                  <div style={{ ...infoRowStyle, justifyContent: "space-between", padding: "4px 0" }}>
                    <span style={{ ...infoTextStyle, maxWidth: "60%", color: oversize ? "#e07070" : undefined }} title={file.name}>
                      {file.name}
                    </span>
                    <span style={{ fontSize: "12px", color: oversize ? "#e07070" : "#888", margin: "0 8px" }}>
                      {formatSize(file.size)}
                    </span>
                    <ButtonItem
                      layout="below"
                      disabled={sendingPath !== "" || oversize}
                      onClick={() => handleSend(file)}
                    >
                      {sendingPath === file.path ? text.sending : text.send}
                    </ButtonItem>
                  </div>
                </PanelSectionRow>
              );
            })
          )}
        </>
      )}
    </PanelSection>
  );
}
