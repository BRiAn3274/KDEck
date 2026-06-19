// 发送页目标设备切换控件，只负责展示和选择已知发送目标。
import { Focusable } from "@decky/ui";
import { MdSwapHoriz } from "react-icons/md";
import { text } from "../../../i18n";
import { targetDeviceIndex, targetDeviceName } from "../domain/devices";
import { textEllipsisStyle } from "../domain/styles";
import type { TargetDevice } from "../domain/types";

export function DeviceSwitcher({
  devices,
  selectedDevice,
  onCycle,
}: {
  devices: TargetDevice[];
  selectedDevice: string;
  onCycle: () => void;
}) {
  const selected = devices.find((device) => device.id === selectedDevice);
  const disabled = devices.length === 0;
  const label = disabled ? text.noDeviceConnected : targetDeviceName(devices, selectedDevice);
  const selectedIndex = targetDeviceIndex(devices, selectedDevice);
  const status = disabled
    ? ""
    : `${selectedIndex || 1}/${devices.length} · ${selected?.connected ? text.connected : text.disconnected}`;

  return (
    <Focusable
      onActivate={disabled ? undefined : onCycle}
      onClick={disabled ? undefined : onCycle}
      noFocusRing={disabled}
      style={{
        width: "100%",
        maxWidth: "100%",
        minHeight: 34,
        boxSizing: "border-box",
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "7px 12px",
        borderRadius: 4,
        background: "rgba(255,255,255,0.10)",
        color: "rgba(255,255,255,0.94)",
        opacity: disabled ? 0.45 : selected && !selected.connected ? 0.72 : 1,
      }}
    >
      <span
        style={{
          ...textEllipsisStyle,
          minWidth: 0,
          flex: "1 1 auto",
          fontSize: 14,
          lineHeight: "18px",
          fontWeight: 700,
        }}
      >
        <span style={{ display: "block", ...textEllipsisStyle }}>{label}</span>
        {status && (
          <span
            style={{
              display: "block",
              ...textEllipsisStyle,
              marginTop: 1,
              fontSize: 11,
              lineHeight: "14px",
              fontWeight: 500,
              color: "rgba(255,255,255,0.58)",
            }}
          >
            {status}
          </span>
        )}
      </span>
      <MdSwapHoriz
        style={{
          width: 18,
          height: 18,
          flex: "0 0 auto",
          opacity: disabled ? 0.35 : 0.9,
        }}
      />
    </Focusable>
  );
}
