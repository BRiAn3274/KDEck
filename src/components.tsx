import { ButtonItem, PanelSectionRow } from "@decky/ui";
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

export function DeviceSelector({
  devices,
  selected,
  onSelect,
  disabled,
}: {
  devices: Array<{ id: string; name: string }>;
  selected: string;
  onSelect: (deviceId: string) => void;
  disabled?: boolean;
}) {
  return (
    <div style={{ display: "flex", gap: "4px", flexWrap: "wrap", padding: "4px 0" }}>
      {devices.map((device) => (
        <ButtonItem
          key={device.id}
          layout="below"
          disabled={disabled || selected === device.id}
          onClick={() => onSelect(device.id)}
        >
          {device.name}
        </ButtonItem>
      ))}
    </div>
  );
}
