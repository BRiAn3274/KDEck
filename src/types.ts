export type SteamClientLike = {
  System?: {
    ShowFloatingGamepadTextInput?: (
      inputMode: number,
      x: number,
      y: number,
      width: number,
      height: number,
    ) => void;
    ShowVirtualKeyboard?: () => void;
  };
};

declare global {
  interface Window {
    SteamClient?: SteamClientLike;
  }
}

export type ApiResult = {
  ok?: boolean;
  message?: string;
  path?: string;
  error?: {
    code?: string;
    message?: string;
  };
  text?: string;
};

export type Status = {
  kdeconnectd?: {
    running?: boolean;
  };
};

export type Device = {
  id: string;
  name: string;
  reachable?: boolean | null;
};

export type DeviceResult = {
  paired?: Device[];
};

export type DeckIp = {
  interface: string;
  address: string;
  prefixlen?: number;
};

export type IncomingDirectory = {
  path: string;
};

export type ConnectionSummary = {
  connection?: string;
  status?: Status;
  devices?: DeviceResult;
  selected_device?: Device | null;
  deck_ips?: {
    primary?: DeckIp | null;
  };
  incoming_directories?: {
    items?: IncomingDirectory[];
  };
  managed_kde?: ManagedKde;
};

export type Notebook = {
  ok?: boolean;
  text?: string;
  error?: {
    code?: string;
    message?: string;
  };
};

export type PendingPair = {
  device_id?: string;
  device_name?: string;
  host?: string;
  time?: number;
};

export type ManagedKde = {
  ok?: boolean;
  running?: boolean;
  device_name?: string;
  udp_working?: boolean;
  tcp_working?: boolean;
  paired?: boolean;
  paused?: boolean;
  pause_reason?: string | null;
  discovered_devices?: ManagedDevice[];
  trusted_devices?: Record<string, unknown>;
  last_events?: ManagedEvent[];
  last_file?: ManagedFile | null;
  pending_pair?: PendingPair | null;
  error?: {
    code?: string;
    message?: string;
  };
};

export type ManagedDevice = {
  device_id?: string;
  device_name?: string;
  host?: string;
  last_seen?: number;
};

export type ManagedEvent = {
  time?: number;
  event?: string;
  file?: string;
  length?: number;
};

export type ManagedFile = {
  status?: string;
  file?: string;
  path?: string;
  size?: number;
  time?: number;
};

export type SendableFile = {
  path: string;
  name: string;
  size: number;
  mtime: number;
  app_id?: string;
};

export type SendableFileList = {
  ok?: boolean;
  files?: SendableFile[];
  message?: string;
};
