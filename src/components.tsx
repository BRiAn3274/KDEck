import { PanelSectionRow } from "@decky/ui";
import { text } from "./i18n";
import { infoRowStyle, infoTextStyle, statusDotStyle } from "./utils";

export function DeviceRow({ label, connected }: { label: string; connected: boolean }) {
  return (
    <PanelSectionRow>
      <div style={infoRowStyle}>
        <span style={infoTextStyle}>{text.device}: {label}</span>
        <span aria-label={text.status} style={statusDotStyle(connected)} />
      </div>
    </PanelSectionRow>
  );
}

export function TextRow({ label, value }: { label: string; value?: string }) {
  return (
    <PanelSectionRow>
      <div style={infoRowStyle}>
        <span style={infoTextStyle}>{label}: {value || "-"}</span>
      </div>
    </PanelSectionRow>
  );
}
