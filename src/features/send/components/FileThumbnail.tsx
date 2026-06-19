// 文件缩略图与类型占位图标，缩略图加载失败时保持列表稳定。
import { callable } from "@decky/api";
import { useEffect, useState } from "react";
import { FaFileAlt, FaFileArchive, FaImage, FaVideo } from "react-icons/fa";
import type { SendableFile, ThumbnailResponse } from "../../../types";
import type { CategoryKey } from "../domain/types";

const getThumbnailBase64 = callable<[path: string], ThumbnailResponse>("get_thumbnail_base64");
const THUMBNAIL_CONCURRENCY = 3;

const thumbnailCache = new Map<string, string | null>();
let thumbnailActiveCount = 0;
const thumbnailQueue: Array<() => void> = [];

function runThumbnailQueue() {
  while (thumbnailActiveCount < THUMBNAIL_CONCURRENCY && thumbnailQueue.length > 0) {
    const task = thumbnailQueue.shift();
    if (!task) return;
    thumbnailActiveCount += 1;
    task();
  }
}

function enqueueThumbnail(path: string): Promise<ThumbnailResponse> {
  return new Promise((resolve, reject) => {
    thumbnailQueue.push(() => {
      getThumbnailBase64(path)
        .then(resolve)
        .catch(reject)
        .finally(() => {
          thumbnailActiveCount = Math.max(0, thumbnailActiveCount - 1);
          runThumbnailQueue();
        });
    });
    runThumbnailQueue();
  });
}

export function PlaceholderIcon({ category, size = 18 }: { category: CategoryKey; size?: number }) {
  const iconStyle = { width: size, height: size, opacity: 0.78 };
  if (category === "screenshots") return <FaImage style={iconStyle} />;
  if (category === "recordings") return <FaVideo style={iconStyle} />;
  if (category === "saves") return <FaFileArchive style={iconStyle} />;
  return <FaFileAlt style={iconStyle} />;
}

export function FileThumbnail({
  file,
  category,
  size = 48,
}: {
  file: SendableFile;
  category: CategoryKey;
  size?: number;
}) {
  const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(null);
  const canLoadThumbnail = category === "screenshots" || category === "recordings" || category === "saves";
  const placeholderSize = Math.max(18, Math.round(size * 0.38));

  useEffect(() => {
    let cancelled = false;
    setThumbnailUrl(null);
    if (!canLoadThumbnail) return;

    if (thumbnailCache.has(file.path)) {
      setThumbnailUrl(thumbnailCache.get(file.path) || null);
      return;
    }

    enqueueThumbnail(file.path)
      .then((result) => {
        if (cancelled) return;
        if (result.ok && result.data) {
          const url = `data:${result.mime || "image/jpeg"};base64,${result.data}`;
          thumbnailCache.set(file.path, url);
          setThumbnailUrl(url);
        } else {
          thumbnailCache.set(file.path, null);
        }
      })
      .catch((error) => console.warn("[KDEck] get thumbnail failed:", error));

    return () => {
      cancelled = true;
    };
  }, [canLoadThumbnail, file.path]);

  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: 6,
        overflow: "hidden",
        flex: "0 0 auto",
        background: "rgba(255,255,255,0.08)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        color: "rgba(255,255,255,0.74)",
      }}
    >
      {thumbnailUrl ? (
        <img
          src={thumbnailUrl}
          alt={file.name}
          loading="lazy"
          onError={() => setThumbnailUrl(null)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            display: "block",
          }}
        />
      ) : (
        <PlaceholderIcon category={category} size={placeholderSize} />
      )}
    </div>
  );
}
