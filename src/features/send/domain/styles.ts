// 发送页跨组件复用的轻量行内样式。
import type { CSSProperties } from "react";

export const textEllipsisStyle: CSSProperties = {
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};
