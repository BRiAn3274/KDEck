export type ApiResult = {
  ok?: boolean;
  message?: string;
  path?: string;
  job?: SendJob;
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

export type ManagedKde = {
  ok?: boolean;
  running?: boolean;
  device_name?: string;
  udp_working?: boolean;
  tcp_working?: boolean;
  bt_working?: boolean;
  bt_error?: {
    message?: string;
    time?: number;
  } | null;
  paired?: boolean;
  paused?: boolean;
  pause_reason?: string | null;
  discovered_devices?: ManagedDevice[];
  peer_connections?: Record<string, { host?: string }>;
  trusted_devices?: Record<string, ManagedTrustedDevice>;
  last_events?: ManagedEvent[];
  last_state_transition?: ManagedStateTransition | null;
  connection_states?: Record<string, ManagedConnectionState>;
  last_file?: ManagedFile | null;
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

export type ManagedTrustedDevice = {
  device_name?: string;
  device_type?: string;
  last_seen?: number;
  last_connected?: number;
  last_host?: string;
};

export type ManagedEvent = {
  time?: number;
  event?: string;
  stage?: string;
  device_id?: string;
  file?: string;
  length?: number;
};

export type ManagedStateTransition = {
  device_id?: string;
  from?: string;
  to?: string;
  reason?: string;
  time?: number;
};

export type ManagedConnectionState = {
  device_id?: string;
  state?: string;
  reason?: string;
  time?: number;
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
  app_name?: string;
  source?: string;
  summary?: string;
  kind?: string;
  recommended?: boolean;
};

export type SendableFileList = {
  ok?: boolean;
  files?: SendableFile[];
  message?: string;
};

export type ThumbnailResponse = {
  ok?: boolean;
  data?: string;
  mime?: string;
  error?: {
    code?: string;
    message?: string;
  };
};

export type SendTarget = {
  id: string;
  name: string;
  type?: string;
  connected?: boolean;
  last_seen?: number;
};

export type SendTargetList = {
  ok?: boolean;
  preferred_device_id?: string | null;
  devices?: SendTarget[];
  error?: {
    code?: string;
    message?: string;
  };
};

export type SendJob = {
  job_id: string;
  device_id?: string;
  file_path?: string;
  file_name?: string;
  total_bytes?: number;
  bytes_sent?: number;
  phase?: string;
  status?: string;
  speed_bps?: number;
  eta_seconds?: number | null;
  error_code?: string;
  error_message?: string;
  created_at?: number;
  updated_at?: number;
};

export type SendJobList = {
  ok?: boolean;
  jobs?: SendJob[];
};
