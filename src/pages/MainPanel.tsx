import {
  ButtonItem,
  PanelSection,
  PanelSectionRow,
  Router,
  TextField,
} from "@decky/ui";
import { callable, injectCssIntoTab, removeCssFromTab } from "@decky/api";
import { useEffect, useRef, useState } from "react";
import type { ApiResult, ManagedKde, Notebook } from "../types";
import { text } from "../i18n";
import {
  deviceState,
  formatFileSummary,
  formatIp,
  infoRowStyle,
  infoTextStyle,
  resultMessage,
  statusDotStyle,
} from "../utils";
import { TextRow } from "../components";
import { useToast } from "../hooks/useToast";
import { useConnection } from "../hooks/useConnection";
import { useClipboard } from "../hooks/useClipboard";

const startManagedKde = callable<[], ManagedKde>("start_managed_kde");
const broadcastDiscovery = callable<[], ApiResult>("broadcast_discovery");

const ACTION_COOLDOWN_MS = 700;

const clipboardCss = `
  .kdeck-clipboard-input input {
    width: 100%; box-sizing: border-box; text-align: left;
    padding: 7px 10px !important; font-size: 15px !important;
    font-weight: 400; line-height: 20px;
  }
`;

export default function MainPanel() {
  const toast = useToast();
  const { summary, refresh } = useConnection(toast);

  useEffect(() => {
    injectCssIntoTab("kdeck-clipboard", clipboardCss);
    return () => removeCssFromTab("kdeck-clipboard", clipboardCss);
  }, []);

  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [task, setTask] = useState("");
  const lastActionAtRef = useRef(0);

  const acceptAction = () => {
    const now = Date.now();
    if (now - lastActionAtRef.current < ACTION_COOLDOWN_MS) return false;
    lastActionAtRef.current = now;
    return true;
  };

  const run = async (label: string, action: () => Promise<ApiResult | Notebook | ManagedKde>, refreshAfter = false) => {
    if (busyAction) {
      toast(text.busy);
      return;
    }
    if (!acceptAction()) return;

    setBusyAction(label);
    setTask(label);

    try {
      const result = await action();
      toast(`${label} ${result.ok ? text.done : `${text.failed}: ${resultMessage(result)}`}`);
      if (refreshAfter) await refresh();
    } catch (error) {
      toast(`${label} ${text.failed}: ${String(error || text.unknownError)}`);
    } finally {
      setBusyAction(null);
      setTask("");
    }
  };

  const clipboard = useClipboard(toast, run);

  const receiverReady = summary.managed_kde?.running && summary.managed_kde?.udp_working && summary.managed_kde?.tcp_working;
  const managedStatus = summary.managed_kde?.paused
    ? text.desktopPaused
    : receiverReady
      ? text.receiverReady
      : text.receiverStarting;
  const device = deviceState(summary.managed_kde);
  const connection = task || managedStatus;
  const connectedDevices = device.trustedList.filter((d) => d.connected);
  const deviceSummary = connectedDevices.length > 0
    ? connectedDevices.map((d) => d.name).join(" / ")
    : (receiverReady ? device.label : text.disconnected);
  const transferSummary = connectedDevices.length > 0
    ? `${text.targetDevice}: ${connectedDevices.map((d) => d.name).join(" / ")}`
    : text.noDeviceConnected;
  const hasReceiverError = Boolean(
    summary.managed_kde?.paused ||
    summary.managed_kde?.error ||
    !summary.managed_kde?.running ||
    !summary.managed_kde?.udp_working ||
    !summary.managed_kde?.tcp_working
  );

  return (
    <>
      <PanelSection title={text.connection}>
        {hasReceiverError && (
          <PanelSectionRow>
            <ButtonItem layout="below" disabled={busyAction === text.restartReceiver} onClick={() => run(text.restartReceiver, async () => startManagedKde(), true)}>
              {busyAction === text.restartReceiver ? connection : text.restartReceiver}
            </ButtonItem>
          </PanelSectionRow>
        )}
        {!hasReceiverError && (
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              disabled={busyAction === text.broadcastDiscovery}
              onClick={() => run(text.broadcastDiscovery, async () => broadcastDiscovery(), true)}
            >
              {busyAction === text.broadcastDiscovery ? connection : text.broadcastDiscovery}
            </ButtonItem>
          </PanelSectionRow>
        )}
        <PanelSectionRow>
          <div style={{ ...infoRowStyle, gap: "8px" }}>
            <span style={{ ...infoTextStyle, flex: 1 }}>
              {deviceSummary}
            </span>
            <span style={statusDotStyle(Boolean(receiverReady && device.connected))} />
          </div>
        </PanelSectionRow>
        <TextRow label="Deck IP" value={formatIp(summary.deck_ips?.primary)} />
      </PanelSection>

      <PanelSection title={text.clipboard}>
        <PanelSectionRow>
          <TextField
            aria-label={text.clipboard}
            className="kdeck-clipboard-input"
            value={clipboard.clipboardText}
            disabled={!!busyAction}
            onBlur={clipboard.handleBlur}
            onFocus={clipboard.handleFocus}
            onChange={(e) => clipboard.handleChange(e?.target?.value ?? "")}
            onKeyDown={clipboard.handleClipboardEnter}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            disabled={!!busyAction || !clipboard.clipboardText}
            onClick={() => run(text.syncText, clipboard.syncClipboard)}
          >
            {text.syncText}
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>
      <PanelSection title={text.transferFiles}>
        <PanelSectionRow>
          <ButtonItem layout="below" description={transferSummary} onClick={() => {
            try {
              Router.CloseSideMenus();
              Router.Navigate("/kdeck/send/screenshots");
            } catch (_) {
              window.location.hash = "/kdeck/send/screenshots";
            }
          }}>
            {text.sendFile}
          </ButtonItem>
        </PanelSectionRow>
        <TextRow label={text.file} value={formatFileSummary(summary.managed_kde?.last_file, summary.incoming_directories?.items)} />
      </PanelSection>
    </>
  );
}
