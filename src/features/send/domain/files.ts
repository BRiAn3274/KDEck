// 发送页文件展示、过滤、分组和任务匹配的纯函数。
import type { SendJob, SendableFile } from "../../../types";
import { text } from "../../../i18n";
import { formatShortDate, formatSize } from "./format";
import type { CategoryKey, SaveGroup } from "./types";

export function fileMetaFor(file: SendableFile, category: CategoryKey): string {
  const size = formatSize(file.size);
  const time = formatShortDate(file.mtime);
  if (category === "logs") return [file.source, size, time].filter(Boolean).join(" · ");
  if (category === "saves") {
    return [file.app_name || (file.app_id ? `App ${file.app_id}` : file.source), size, time].filter(Boolean).join(" · ");
  }
  return [size, time].filter(Boolean).join(" · ");
}

export function saveGroupTitle(file: SendableFile): string {
  return file.app_name || (file.app_id ? `App ${file.app_id}` : text.otherSaves);
}

export function groupSaveFiles(files: SendableFile[]): SaveGroup[] {
  const groups = new Map<string, SaveGroup>();
  for (const file of files) {
    const key = file.app_id || file.source || text.otherSaves;
    const group = groups.get(key) || {
      key,
      title: saveGroupTitle(file),
      appId: file.app_id || "",
      files: [],
      totalSize: 0,
      mtime: 0,
    };
    group.files.push(file);
    group.totalSize += file.size || 0;
    group.mtime = Math.max(group.mtime, file.mtime || 0);
    if (!group.appId && file.app_id) group.appId = file.app_id;
    if (group.title.startsWith("App ") && file.app_name) group.title = file.app_name;
    groups.set(key, group);
  }
  return Array.from(groups.values())
    .map((group) => ({
      ...group,
      files: [...group.files].sort((a, b) => b.mtime - a.mtime),
    }))
    .sort((a, b) => b.mtime - a.mtime || a.title.localeCompare(b.title));
}

export function latestRunningJobForPath(jobs: SendJob[], path: string): SendJob | undefined {
  return jobs.find((job) => job.file_path === path && job.status === "running");
}
