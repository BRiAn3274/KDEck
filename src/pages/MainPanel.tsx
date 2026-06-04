import {
  ButtonItem,
  PanelSection,
  PanelSectionRow,
  Router,
} from "@decky/ui";
import { callable } from "@decky/api";
import { useRef, useState } from "react";
import type { ApiResult, ManagedKde, Notebook } from "../types";
import { text } from "../i18n";
import {
  deviceState,
  formatFileSummary,
  formatIp,
  inputStyle,
  resultMessage,
} from "../utils";
import { DeviceRow, TextRow } from "../components";
import { useToast } from "../hooks/useToast";
import { useConnection } from "../hooks/useConnection";
import { useClipboard } from "../hooks/useClipboard";

const startManagedKde = callable<[], ManagedKde>("start_managed_kde");

const ACTION_COOLDOWN_MS = 700;

export default function MainPanel() {
  const toast = useToast();
  const { summary, refresh } = useConnection(toast);
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

  return (
    <>
      <PanelSection title={text.connection}>
        <PanelSectionRow>
          <ButtonItem layout="below" disabled={busyAction === text.refreshConnection} onClick={() => run(text.refreshConnection, async () => startManagedKde(), true)}>
            {busyAction === text.refreshConnection ? connection : text.refreshConnection}
          </ButtonItem>
        </PanelSectionRow>
        <DeviceRow label={receiverReady ? device.label : text.disconnected} connected={Boolean(receiverReady && device.connected)} />
        <TextRow label="Deck IP" value={formatIp(summary.deck_ips?.primary)} />
      </PanelSection>

      <PanelSection title={text.clipboard}>
        <PanelSectionRow>
          <input
            aria-label={text.clipboard}
            value={clipboard.clipboardText}
            disabled={!!busyAction}
            style={inputStyle}
            onBlur={clipboard.handleBlur}
            onFocus={clipboard.handleFocus}
            onChange={(event) => clipboard.handleChange(event.currentTarget.value)}
            onKeyDown={clipboard.handleClipboardEnter}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <span style={{ fontSize: "11px", color: "#888", padding: "2px 10px", display: "block" }}>{text.keyboardHint}</span>
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
      <PanelSection title={text.receiveFile}>
        <TextRow label={text.file} value={formatFileSummary(summary.managed_kde?.last_file, summary.incoming_directories?.items)} />
      </PanelSection>
      <PanelSection title={text.sendFile}>
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={() => { try { Router.Navigate("/kdeck/send"); } catch (_) { window.location.hash = "/kdeck/send"; } }}>
            {text.sendFile}
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>
    </>
  );
}
