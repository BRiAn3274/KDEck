import {
  ButtonItem,
  PanelSection,
  PanelSectionRow,
  TextField,
} from "@decky/ui";
import { callable } from "@decky/api";
import { useEffect, useState } from "react";
import type { ApiResult, ConnectionSummary, SendableFile, SendableFileList } from "../types";
import { text } from "../i18n";
import { infoTextStyle, resultMessage } from "../utils";
import { DeviceSelector } from "../components";
import { useToast } from "../hooks/useToast";

const listSendableFiles = callable<[category: string], SendableFileList>("list_sendable_files");
const sendFileToPhone = callable<[file_path: string, device_id: string], ApiResult>("send_file_to_phone");
const getConnectionSummary = callable<[], ConnectionSummary>("get_connection_summary");
const getPreferredDevice = callable<[], ApiResult>("get_preferred_device");
const setPreferredDevice = callable<[device_id: string], ApiResult>("set_preferred_device");

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Inline tab bar — uses ButtonItem for proper gamepad focus. */
function TabBar({
  tabs,
  active,
  onSelect,
  disabled,
}: {
  tabs: Array<{ key: string; label: string }>;
  active: string;
  onSelect: (key: string) => void;
  disabled?: boolean;
}) {
  return (
    <PanelSectionRow>
      <div style={{ display: "flex", gap: "4px", padding: "4px 0" }}>
        {tabs.map((tab) => (
          <ButtonItem
            key={tab.key}
            layout="below"
            disabled={disabled || active === tab.key}
            onClick={() => onSelect(tab.key)}
          >
            {tab.label}
          </ButtonItem>
        ))}
      </div>
    </PanelSectionRow>
  );
}

/** Single file row — entire row is a ButtonItem for gamepad A-button activation. */
function FileItem({
  file,
  oversize,
  sending,
  onSend,
}: {
  file: SendableFile;
  oversize: boolean;
  sending: boolean;
  onSend: () => void;
}) {
  return (
    <PanelSectionRow>
      <ButtonItem
        layout="below"
        disabled={sending || oversize}
        onClick={onSend}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%", padding: "2px 0" }}>
          <span style={{ ...infoTextStyle, flex: 1, color: oversize ? "#e07070" : sending ? "#88cc88" : undefined }}>
            {sending ? `${text.sending}…` : file.name}
          </span>
          <span style={{ fontSize: "12px", color: oversize ? "#e07070" : "#888", flexShrink: 0, marginLeft: "8px" }}>
            {formatSize(file.size)}
          </span>
        </div>
      </ButtonItem>
      {sending && (
        <div style={{ height: "3px", background: "#2a3a4a", borderRadius: "2px", margin: "0 4px", overflow: "hidden" }}>
          <style>{`@keyframes kdeck-progress-slide { 0% { transform: translateX(-100%); } 100% { transform: translateX(250%); } }`}</style>
          <div style={{
            height: "100%", width: "40%", background: "linear-gradient(90deg, transparent, #88cc88, transparent)",
            borderRadius: "2px", animation: "kdeck-progress-slide 1.5s ease-in-out infinite",
          }} />
        </div>
      )}
    </PanelSectionRow>
  );
}

export default function SendPage() {
  const [category, setCategory] = useState<"screenshots" | "recordings" | "logs">("screenshots");
  const [files, setFiles] = useState<SendableFile[]>([]);
  const [sendingPath, setSendingPath] = useState("");
  const [selectedDevice, setSelectedDevice] = useState("");
  const [trustedDevices, setTrustedDevices] = useState<Array<{ id: string; name: string }>>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const toast = useToast();

  useEffect(() => {
    getConnectionSummary().then((s) => {
      const trusted = s.managed_kde?.trusted_devices || {};
      const discovered = s.managed_kde?.discovered_devices || [];
      const devices = Object.keys(trusted).map((id) => {
        const device = discovered.find((d) => d.device_id === id);
        return { id, name: device?.device_name || id.slice(0, 8) };
      });
      setTrustedDevices(devices);

      // Select preferred device or fallback to first
      getPreferredDevice().then((pref) => {
        const deviceId = (pref as any).device_id;
        if (pref.ok && deviceId) {
          setSelectedDevice(deviceId as string);
        } else if (devices.length > 0) {
          setSelectedDevice(devices[0].id);
        }
      }).catch(() => {
        if (devices.length > 0) setSelectedDevice(devices[0].id);
      });
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

  const handleDeviceSelect = (deviceId: string) => {
    setSelectedDevice(deviceId);
    setPreferredDevice(deviceId).catch(() => undefined);
  };

  const handleSend = async (file: SendableFile) => {
    if (sendingPath || !selectedDevice) return;
    // Fresh connectivity check: verify selected device is actually online
    try {
      const freshSummary = await getConnectionSummary();
      const freshManaged = freshSummary.managed_kde;
      const freshTrustedIds = Object.keys(freshManaged?.trusted_devices || {});
      const discovered = freshManaged?.discovered_devices || [];
      const now = Math.floor(Date.now() / 1000);
      const onlineDevice = discovered.find(
        (d) => d.device_id && freshTrustedIds.includes(d.device_id) && d.last_seen && (now - d.last_seen) < 180,
      );
      if (!onlineDevice?.device_id) {
        toast(text.noDeviceConnected);
        return;
      }
    } catch {
      toast(text.noDeviceConnected);
      return;
    }
    setSendingPath(file.path);
    const result = await sendFileToPhone(file.path, selectedDevice).catch(() => ({ ok: false }));
    toast(result.ok ? text.fileSent : `${text.fileSendFailed}: ${resultMessage(result)}`);
    setSendingPath("");
  };

  const tabs: Array<{ key: typeof category; label: string }> = [
    { key: "screenshots", label: text.tabScreenshots },
    { key: "recordings", label: text.tabRecordings },
    { key: "logs", label: text.tabLogs },
  ];
  const maxFileSize = category === "recordings" ? 500 * 1024 * 1024 : category === "logs" ? 50 * 1024 * 1024 : 0;
  const filteredFiles = searchQuery
    ? files.filter((f) => f.name.toLowerCase().includes(searchQuery.toLowerCase()))
    : files;

  return (
    <PanelSection title={text.sendFile}>
      {!selectedDevice ? (
        <PanelSectionRow>
          <span style={infoTextStyle}>{text.noFiles} — {text.disconnected}</span>
        </PanelSectionRow>
      ) : (
        <>
          {/* Multi-device selector */}
          {trustedDevices.length > 1 && (
            <PanelSectionRow>
              <DeviceSelector
                devices={trustedDevices}
                selected={selectedDevice}
                onSelect={handleDeviceSelect}
                disabled={sendingPath !== ""}
              />
            </PanelSectionRow>
          )}

          {/* Tab bar */}
          <TabBar
            tabs={tabs}
            active={category}
            onSelect={(key) => setCategory(key as typeof category)}
            disabled={sendingPath !== ""}
          />

          {/* Search box */}
          <PanelSectionRow>
            <div style={{ display: "flex", justifyContent: "flex-end", padding: "2px 0" }}>
              <TextField
                {...({ placeholder: text.searchPlaceholder, className: "kdeck-search-input" } as any)}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e?.target?.value ?? "")}
              />
            </div>
            <style>{`
              .kdeck-search-input { width: 50%; min-width: 0; }
              .kdeck-search-input input { font-size: 13px !important; padding: 4px 8px !important; }
            `}</style>
          </PanelSectionRow>

          {/* File list — each file is a full ButtonItem for gamepad A-button send */}
          {filteredFiles.length === 0 ? (
            <PanelSectionRow>
              <span style={infoTextStyle}>{text.noFiles}</span>
            </PanelSectionRow>
          ) : (
            filteredFiles.map((file, idx) => {
              const oversize = maxFileSize > 0 && file.size > maxFileSize;
              return (
                <FileItem
                  key={idx}
                  file={file}
                  oversize={oversize}
                  sending={sendingPath === file.path}
                  onSend={() => handleSend(file)}
                />
              );
            })
          )}
        </>
      )}
    </PanelSection>
  );
}
