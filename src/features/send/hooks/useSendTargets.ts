// 发送目标 hook，负责读取目标设备、首选目标和用户切换结果。
import { callable } from "@decky/api";
import { useCallback, useEffect, useState } from "react";
import { text } from "../../../i18n";
import type { ApiResult, SendTargetList } from "../../../types";
import { chooseDefaultDevice, shortName } from "../domain/devices";
import type { TargetDevice } from "../domain/types";

const setPreferredDevice = callable<[device_id: string], ApiResult>("set_preferred_device");
const getSendTargets = callable<[], SendTargetList>("get_send_targets");

export function useSendTargets(toast: (body: string, category?: string) => void) {
  const [selectedDevice, setSelectedDevice] = useState("");
  const [devices, setDevices] = useState<TargetDevice[]>([]);

  const cycleDevice = useCallback(() => {
    if (devices.length === 0) {
      toast(text.noDeviceConnected, "no_device");
      return;
    }
    const connected = devices.filter((device) => device.connected);
    const pool = connected.length > 0 ? connected : devices;
    if (pool.length <= 1 && pool[0]?.id === selectedDevice) return;

    const currentIndex = pool.findIndex((device) => device.id === selectedDevice);
    const next = currentIndex < 0 ? pool[0] : pool[(currentIndex + 1) % pool.length];
    setSelectedDevice(next.id);
    setPreferredDevice(next.id).catch((error) => console.warn("[KDEck] setPreferredDevice failed:", error));
  }, [devices, selectedDevice, toast]);

  useEffect(() => {
    let cancelled = false;
    const refreshDevices = async () => {
      const targets = await getSendTargets().catch(() => ({} as SendTargetList));
      if (cancelled) return;
      const nextDevices = (targets.devices || []).map((device) => ({
        id: device.id,
        name: shortName(device.name || device.id.slice(0, 8)),
        connected: !!device.connected,
      }));
      setDevices(nextDevices);
      setSelectedDevice((current) => {
        const currentDevice = nextDevices.find((device) => device.id === current);
        if (currentDevice?.connected) return current;
        const connectedDevice = nextDevices.find((device) => device.connected);
        if (connectedDevice) return connectedDevice.id;
        if (currentDevice) return current;
        return chooseDefaultDevice(nextDevices, targets.preferred_device_id || undefined);
      });
    };
    refreshDevices().catch((error) => console.warn("[KDEck] refresh target devices failed:", error));
    const timer = window.setInterval(() => {
      refreshDevices().catch((error) => console.warn("[KDEck] refresh target devices failed:", error));
    }, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  return {
    devices,
    selectedDevice,
    cycleDevice,
  };
}
