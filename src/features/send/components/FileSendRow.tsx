// 发送页文件行，负责单个文件的选择、发送入口和任务状态展示。
import { Field, Spinner } from "@decky/ui";
import { useCallback, useState } from "react";
import type { MouseEvent } from "react";
import { FaCheck } from "react-icons/fa";
import { MdSend } from "react-icons/md";
import type { SendJob, SendableFile } from "../../../types";
import { fileMetaFor } from "../domain/files";
import { textEllipsisStyle } from "../domain/styles";
import type { CategoryKey, RowFeedback } from "../domain/types";
import { FileThumbnail } from "./FileThumbnail";

const ROW_PROGRESS_HEIGHT = 2;

function ActionIcon({
  sending,
  success,
}: {
  sending: boolean;
  success: boolean;
}) {
  if (sending) {
    return <Spinner style={{ width: 16, height: 16 }} />;
  }
  if (success) {
    return <FaCheck style={{ width: 14, height: 14 }} />;
  }
  return <MdSend style={{ width: 17, height: 17 }} />;
}

export function FileSendRow({
  file,
  category,
  job,
  starting,
  feedback,
  onSend,
}: {
  file: SendableFile;
  category: CategoryKey;
  job?: SendJob;
  starting: boolean;
  feedback?: RowFeedback;
  onSend: (file: SendableFile) => void;
}) {
  const [focused, setFocused] = useState(false);
  const sending = starting || !!job;
  const success = feedback?.status === "success" && feedback.until > Date.now();
  const total = job?.total_bytes || 0;
  const sent = Math.min(job?.bytes_sent || 0, total);
  const progress = success ? 1 : total > 0 ? Math.max(0, Math.min(1, sent / total)) : 0;
  const thumbnailSize = focused ? 72 : 48;
  const rowMinHeight = focused ? 96 : 68;

  const handleSend = useCallback(() => {
    if (sending) return;
    onSend(file);
  }, [file, onSend, sending]);

  const handleActionClick = useCallback((event: MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    handleSend();
  }, [handleSend]);

  return (
    <div
      style={{
        position: "relative",
        background: success ? "rgba(255,255,255,0.04)" : "rgba(255,255,255,0.015)",
        border: "1px solid rgba(255,255,255,0.055)",
        borderRadius: 8,
        marginBottom: 6,
        overflow: "hidden",
        transition: "background-color 120ms ease, border-color 120ms ease",
      }}
    >
      <Field
        focusable
        highlightOnFocus
        onGamepadFocus={() => setFocused(true)}
        onGamepadBlur={() => setFocused(false)}
        padding="none"
        bottomSeparator="none"
        onActivate={handleSend}
        onClick={handleSend}
        label={
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              minHeight: rowMinHeight,
              padding: "10px 12px",
              boxSizing: "border-box",
              width: "100%",
              minWidth: 0,
              overflow: "hidden",
              transition: "min-height 120ms ease",
            }}
          >
            <FileThumbnail file={file} category={category} size={thumbnailSize} />
            <div style={{ flex: "1 1 auto", minWidth: 0, overflow: "hidden" }}>
              <div
                style={{
                  ...textEllipsisStyle,
                  fontSize: 14,
                  fontWeight: 600,
                  lineHeight: "18px",
                  color: "rgba(255,255,255,0.96)",
                }}
              >
                {file.name}
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
                {fileMetaFor(file, category)}
              </div>
            </div>
            <button
              type="button"
              tabIndex={-1}
              disabled={sending}
              onClick={handleActionClick}
              style={{
                width: 36,
                height: 36,
                border: "none",
                borderRadius: "50%",
                flex: "0 0 36px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: success ? "#ffffff" : "rgba(255,255,255,0.94)",
                background: success ? "rgba(68,211,106,0.38)" : "rgba(255,255,255,0.10)",
                opacity: sending ? 0.86 : 1,
              }}
            >
              <ActionIcon sending={sending} success={success} />
            </button>
          </div>
        }
      />
      {(sending || success) && (
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            bottom: 0,
            height: ROW_PROGRESS_HEIGHT,
            background: "rgba(255,255,255,0.08)",
          }}
        >
          <div
            style={{
              width: total > 0 || success ? `${progress * 100}%` : "42%",
              height: "100%",
              background: success ? "#44d36a" : "#66c0f4",
              transition: "width 160ms ease",
            }}
          />
        </div>
      )}
    </div>
  );
}
