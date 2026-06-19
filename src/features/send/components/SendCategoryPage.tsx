// 单个发送分类页面，组合设备切换、文件列表和存档分组视图。
import { DialogBody } from "@decky/ui";
import { useCallback, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { SendableFile } from "../../../types";
import { text } from "../../../i18n";
import { groupSaveFiles, latestRunningJobForPath } from "../domain/files";
import type { SendCategoryPageProps } from "../domain/types";
import { DeviceSwitcher } from "./DeviceSwitcher";
import { EmptyState } from "./EmptyState";
import { FileSendRow } from "./FileSendRow";
import { SaveGroupRow } from "./SaveGroupRow";

const LIST_BOTTOM_SAFE_SPACE = 68;

export function SendCategoryPage({
  category,
  state,
  jobs,
  startingPaths,
  feedbackByPath,
  devices,
  selectedDevice,
  onCycleDevice,
  onSend,
}: SendCategoryPageProps) {
  const [expandedSaveGroups, setExpandedSaveGroups] = useState<Record<string, boolean>>({});
  const visibleFiles = useMemo(() => {
    return [...state.files].sort((a, b) => b.mtime - a.mtime);
  }, [state.files]);
  const saveGroups = useMemo(() => groupSaveFiles(visibleFiles), [visibleFiles]);

  const toggleSaveGroup = useCallback((key: string) => {
    setExpandedSaveGroups((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  let content: ReactNode;
  if (state.loading && !state.loaded) {
    content = <EmptyState>{text.scanningFiles}</EmptyState>;
  } else if (state.error) {
    content = <EmptyState>{state.error}</EmptyState>;
  } else if (visibleFiles.length === 0) {
    content = <EmptyState>{text.noFiles}</EmptyState>;
  } else if (category === "saves") {
    content = saveGroups.map((group) => (
      <div key={group.key}>
        <SaveGroupRow
          group={group}
          expanded={!!expandedSaveGroups[group.key]}
          onToggle={toggleSaveGroup}
        />
        {expandedSaveGroups[group.key] && group.files.map((file: SendableFile) => (
          <FileSendRow
            key={file.path}
            file={file}
            category={category}
            job={latestRunningJobForPath(jobs, file.path)}
            starting={!!startingPaths[file.path]}
            feedback={feedbackByPath[file.path]}
            onSend={onSend}
          />
        ))}
      </div>
    ));
  } else {
    content = visibleFiles.map((file) => (
      <FileSendRow
        key={file.path}
        file={file}
        category={category}
        job={latestRunningJobForPath(jobs, file.path)}
        starting={!!startingPaths[file.path]}
        feedback={feedbackByPath[file.path]}
        onSend={onSend}
      />
    ));
  }

  return (
    <DialogBody
      style={{
        height: "100%",
        minHeight: 0,
        boxSizing: "border-box",
        padding: "0 24px",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          height: "100%",
          minHeight: 0,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            flex: "0 0 auto",
            padding: "0 0 8px",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "flex-start",
              minHeight: 40,
            }}
          >
            <div style={{ width: "min(320px, 58%)" }}>
              <DeviceSwitcher
                devices={devices}
                selectedDevice={selectedDevice}
                onCycle={onCycleDevice}
              />
            </div>
          </div>
        </div>
        <div
          style={{
            flex: "1 1 auto",
            minHeight: 0,
            overflowY: "auto",
            paddingRight: 8,
          }}
        >
          {content}
          <div style={{ height: LIST_BOTTOM_SAFE_SPACE }} />
        </div>
      </div>
    </DialogBody>
  );
}
