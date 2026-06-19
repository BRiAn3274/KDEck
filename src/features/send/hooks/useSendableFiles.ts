// 发送页文件列表 hook，按分类拉取并缓存可发送文件。
import { callable } from "@decky/api";
import { useCallback, useEffect, useState } from "react";
import { text } from "../../../i18n";
import type { SendableFileList } from "../../../types";
import { makeEmptyCategoryState } from "../domain/categories";
import type { CategoryKey, CategoryState } from "../domain/types";

const listSendableFiles = callable<[category: string], SendableFileList>("list_sendable_files");

export function useSendableFiles(currentPage: CategoryKey) {
  const [categoryStates, setCategoryStates] = useState<Record<CategoryKey, CategoryState>>({
    screenshots: makeEmptyCategoryState(),
    recordings: makeEmptyCategoryState(),
    saves: makeEmptyCategoryState(),
    logs: makeEmptyCategoryState(),
  });

  const refreshCategory = useCallback(async (category: CategoryKey, silent = false) => {
    setCategoryStates((prev) => ({
      ...prev,
      [category]: {
        ...prev[category],
        loading: silent ? prev[category].loading : true,
        error: undefined,
      },
    }));
    try {
      const result = await listSendableFiles(category);
      setCategoryStates((prev) => ({
        ...prev,
        [category]: {
          files: result.ok && result.files ? result.files : [],
          loading: false,
          loaded: true,
          error: result.ok ? undefined : (result.message || text.scanFailed),
        },
      }));
    } catch (error) {
      console.warn("[KDEck] listSendableFiles failed:", error);
      setCategoryStates((prev) => ({
        ...prev,
        [category]: {
          ...prev[category],
          loading: false,
          loaded: true,
          error: text.scanFailed,
        },
      }));
    }
  }, []);

  const currentPageLoaded = categoryStates[currentPage]?.loaded;

  useEffect(() => {
    const silent = currentPageLoaded;
    refreshCategory(currentPage, silent).catch((error) => console.warn("[KDEck] refresh category failed:", error));
    const timer = window.setInterval(() => {
      refreshCategory(currentPage, true).catch((error) => console.warn("[KDEck] refresh category failed:", error));
    }, 5000);
    return () => window.clearInterval(timer);
  }, [currentPage, currentPageLoaded, refreshCategory]);

  return {
    categoryStates,
    refreshCategory,
  };
}
