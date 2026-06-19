// 发送页分类定义与分类状态的基础构造函数。
import type { CSSProperties, ReactNode } from "react";
import { MdArticle, MdFolderZip, MdMovie, MdScreenshot } from "react-icons/md";
import { text } from "../../../i18n";
import type { CategoryKey, CategoryState } from "./types";

export const CATEGORIES: CategoryKey[] = ["screenshots", "recordings", "saves", "logs"];

export function makeEmptyCategoryState(): CategoryState {
  return { files: [], loading: false, loaded: false };
}

export function titleForCategory(category: CategoryKey): string {
  const map: Record<CategoryKey, string> = {
    screenshots: text.tabScreenshots,
    recordings: text.tabRecordings,
    saves: text.tabSaves,
    logs: text.tabLogs,
  };
  return map[category];
}

export function iconForCategory(category: CategoryKey, style?: CSSProperties): ReactNode {
  if (category === "screenshots") return <MdScreenshot style={style} />;
  if (category === "recordings") return <MdMovie style={style} />;
  if (category === "saves") return <MdFolderZip style={style} />;
  return <MdArticle style={style} />;
}

export function categoryFromLocation(): CategoryKey {
  const path = `${window.location.pathname || ""}${window.location.hash || ""}`;
  if (path.includes("/recordings")) return "recordings";
  if (path.includes("/saves")) return "saves";
  if (path.includes("/logs")) return "logs";
  return "screenshots";
}
