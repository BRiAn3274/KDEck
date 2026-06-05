import {
  ButtonItem,
  PanelSection,
  PanelSectionRow,
  Router,
  TextField,
} from "@decky/ui";
import { callable } from "@decky/api";
import { useRef, useState } from "react";
import type { ApiResult, ManagedKde, Notebook } from "../types";
import { text } from "../i18n";
import {
  deviceState,
  formatFileSummary,
  formatIp,
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
  const btStatus = summary.managed_kde?.bt_working ? text.btReady
    : summary.managed_kde?.bt_error ? text.btUnavailable
    : text.btDisabled;

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
        <TextRow label="Bluetooth" value={btStatus} />
      </PanelSection>

      <PanelSection title={text.clipboard}>
        <PanelSectionRow>
          <style>{`
            .kdeck-clipboard-input {
              width: 100%; box-sizing: border-box; padding: 7px 10px !important;
              font-size: 15px !important; font-weight: 400 !important;
              line-height: 20px !important; text-align: left !important;
            }
          `}</style>
          <TextField
            {...({ "aria-label": text.clipboard, className: "kdeck-clipboard-input" } as any)}
            value={clipboard.clipboardText}
            disabled={!!busyAction}
            onBlur={clipboard.handleBlur}
            onFocus={clipboard.handleFocus}
            onChange={(e) => clipboard.handleChange(e?.target?.value ?? "")}
            onKeyDown={clipboard.handleClipboardEnter as any}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <div onDoubleClick={() => clipboard.executeHiddenCommand()}>
            <ButtonItem
              layout="below"
              disabled={!!busyAction || !clipboard.clipboardText}
              onClick={() => run(text.syncText, clipboard.syncClipboard)}
            >
              {text.syncText}
            </ButtonItem>
          </div>
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
