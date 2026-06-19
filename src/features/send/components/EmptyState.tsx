// 发送页空态容器，用于统一暂无文件、加载和错误提示的视觉位置。
import type { ReactNode } from "react";

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        minHeight: 68,
        padding: "18px 10px",
        boxSizing: "border-box",
        display: "flex",
        alignItems: "center",
        color: "rgba(255,255,255,0.66)",
        fontSize: 13,
        lineHeight: "18px",
        borderTop: "1px solid rgba(255,255,255,0.06)",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
      }}
    >
      {children}
    </div>
  );
}
