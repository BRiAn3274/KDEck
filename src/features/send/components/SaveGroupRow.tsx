// 存档分类的游戏分组行，负责展开状态和分组摘要展示。
import { Field } from "@decky/ui";
import { useCallback } from "react";
import { MdExpandLess, MdExpandMore } from "react-icons/md";
import { text } from "../../../i18n";
import { formatShortDate, formatSize } from "../domain/format";
import { textEllipsisStyle } from "../domain/styles";
import type { SaveGroup } from "../domain/types";
import { FileThumbnail, PlaceholderIcon } from "./FileThumbnail";

export function SaveGroupRow({
  group,
  expanded,
  onToggle,
}: {
  group: SaveGroup;
  expanded: boolean;
  onToggle: (key: string) => void;
}) {
  const representative = group.files[0];
  const handleToggle = useCallback(() => onToggle(group.key), [group.key, onToggle]);

  return (
    <div
      style={{
        marginBottom: 6,
        borderRadius: 8,
        overflow: "hidden",
        background: "rgba(255,255,255,0.018)",
        border: "1px solid rgba(255,255,255,0.055)",
      }}
    >
      <Field
        focusable
        highlightOnFocus
        padding="none"
        bottomSeparator="none"
        onActivate={handleToggle}
        onClick={handleToggle}
        label={
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              minHeight: 72,
              padding: "10px 12px",
              boxSizing: "border-box",
              width: "100%",
              minWidth: 0,
              overflow: "hidden",
            }}
          >
            {representative ? (
              <FileThumbnail file={representative} category="saves" size={52} />
            ) : (
              <PlaceholderIcon category="saves" size={22} />
            )}
            <div style={{ flex: "1 1 auto", minWidth: 0, overflow: "hidden" }}>
              <div
                style={{
                  ...textEllipsisStyle,
                  fontSize: 15,
                  fontWeight: 700,
                  lineHeight: "19px",
                  color: "rgba(255,255,255,0.96)",
                }}
              >
                {group.title}
              </div>
              <div
                style={{
                  ...textEllipsisStyle,
                  marginTop: 4,
                  fontSize: 12,
                  lineHeight: "16px",
                  color: "rgba(255,255,255,0.58)",
                }}
              >
                {group.files.length} {text.fileCount} · {formatSize(group.totalSize)} · {formatShortDate(group.mtime)}
              </div>
            </div>
            {expanded ? (
              <MdExpandLess style={{ width: 24, height: 24, flex: "0 0 auto", opacity: 0.86 }} />
            ) : (
              <MdExpandMore style={{ width: 24, height: 24, flex: "0 0 auto", opacity: 0.86 }} />
            )}
          </div>
        }
      />
    </div>
  );
}
