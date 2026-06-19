// 发送目标设备的展示名、默认选择和在线状态格式化规则。
import { text } from "../../../i18n";
import type { TargetDevice } from "./types";

export function shortName(name?: string): string {
  const clean = (name || "").trim();
  if (!clean) return "";
  return clean.length > 18 ? `${clean.slice(0, 16)}...` : clean;
}

export function chooseDefaultDevice(devices: TargetDevice[], preferred?: string): string {
  if (preferred && devices.some((device) => device.id === preferred)) return preferred;
  return devices.find((device) => device.connected)?.id || devices[0]?.id || "";
}

export function targetDeviceName(devices: TargetDevice[], selectedDevice: string): string {
  const selected = devices.find((device) => device.id === selectedDevice);
  return selected?.name || text.chooseDevice;
}

export function targetDeviceIndex(devices: TargetDevice[], selectedDevice: string): number {
  const index = devices.findIndex((device) => device.id === selectedDevice);
  return index >= 0 ? index + 1 : 0;
}
