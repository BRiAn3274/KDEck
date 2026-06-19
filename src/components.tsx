import { PanelSectionRow } from "@decky/ui";
import { infoRowStyle, infoTextStyle } from "./utils";

export function TextRow({ label, value }: { label: string; value?: string }) {
  return (
    <PanelSectionRow>
      <div style={infoRowStyle}>
        <span style={infoTextStyle}>{label}: {value || "-"}</span>
      </div>
    </PanelSectionRow>
  );
}
