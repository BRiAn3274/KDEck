// 发送页 feature 内部共享类型，避免页面组件重复声明状态结构。
import type { SendJob, SendableFile } from "../../../types";

export type CategoryKey = "screenshots" | "recordings" | "saves" | "logs";

export type TargetDevice = { id: string; name: string; connected: boolean };

export type CategoryState = {
  files: SendableFile[];
  loading: boolean;
  loaded: boolean;
  error?: string;
};

export type RowFeedback = { status: "success"; until: number };

export type SaveGroup = {
  key: string;
  title: string;
  appId: string;
  files: SendableFile[];
  totalSize: number;
  mtime: number;
};

export type SendCategoryPageProps = {
  category: CategoryKey;
  state: CategoryState;
  jobs: SendJob[];
  startingPaths: Record<string, boolean>;
  feedbackByPath: Record<string, RowFeedback>;
  devices: TargetDevice[];
  selectedDevice: string;
  onCycleDevice: () => void;
  onSend: (file: SendableFile) => void;
};
