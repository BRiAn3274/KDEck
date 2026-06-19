import { callable } from "@decky/api";
import { SidebarNavigation } from "@decky/ui";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { SendCategoryPage } from "../features/send/components/SendCategoryPage";
import {
  CATEGORIES,
  categoryFromLocation,
  iconForCategory,
  titleForCategory,
} from "../features/send/domain/categories";
import { useSendTargets } from "../features/send/hooks/useSendTargets";
import { useSendableFiles } from "../features/send/hooks/useSendableFiles";
import type {
  CategoryKey,
  RowFeedback,
} from "../features/send/domain/types";
import { useToast } from "../hooks/useToast";
import { text } from "../i18n";
import type {
  ApiResult,
  SendJob,
  SendJobList,
  SendableFile,
} from "../types";
import { sendFailureAdvice } from "../utils";

const startSendFileToPhone = callable<[file_path: string, device_id: string], ApiResult>("start_send_file_to_phone");
const getSendJobs = callable<[limit: number], SendJobList>("get_send_jobs");

declare var __KDECK_VERSION__: string;

type SendPageProps = { initialPage?: CategoryKey };

export default function SendPage({ initialPage }: SendPageProps) {
  const [currentPage, setCurrentPage] = useState<CategoryKey>(initialPage ?? categoryFromLocation());
  const [jobs, setJobs] = useState<SendJob[]>([]);
  const [startingPaths, setStartingPaths] = useState<Record<string, boolean>>({});
  const [feedbackByPath, setFeedbackByPath] = useState<Record<string, RowFeedback>>({});
  const feedbackTimersRef = useRef<Record<string, number>>({});
  const handledJobIdsRef = useRef<Set<string>>(new Set());
  const trackedJobIdsRef = useRef<Set<string>>(new Set());
  const toast = useToast();
  const { devices, selectedDevice, cycleDevice } = useSendTargets(toast);
  const { categoryStates } = useSendableFiles(currentPage);

  const refreshJobs = useCallback(async () => {
    const result = await getSendJobs(20).catch(() => ({ ok: false } as SendJobList));
    if (result.ok && result.jobs) setJobs(result.jobs);
  }, []);

  const showSuccessFeedback = useCallback((path: string) => {
    const timer = feedbackTimersRef.current[path];
    if (timer != null) window.clearTimeout(timer);

    setFeedbackByPath((prev) => ({
      ...prev,
      [path]: { status: "success", until: Date.now() + 1500 },
    }));

    feedbackTimersRef.current[path] = window.setTimeout(() => {
      setFeedbackByPath((prev) => {
        const next = { ...prev };
        delete next[path];
        return next;
      });
      delete feedbackTimersRef.current[path];
    }, 1500);
  }, []);

  const runningPaths = useMemo(() => {
    return new Set(jobs.filter((job) => job.status === "running" && job.file_path).map((job) => job.file_path as string));
  }, [jobs]);
  const hasRunningJobs = runningPaths.size > 0;

  const sendFile = useCallback(async (file: SendableFile) => {
    if (!selectedDevice) {
      toast(text.noDeviceConnected, "no_device");
      return;
    }
    if (runningPaths.has(file.path) || startingPaths[file.path]) return;

    setStartingPaths((prev) => ({ ...prev, [file.path]: true }));
    const result = await startSendFileToPhone(file.path, selectedDevice).catch(() => ({ ok: false } as ApiResult));
    if (result.ok && result.job?.job_id) {
      trackedJobIdsRef.current.add(result.job.job_id);
    } else if (!result.ok) {
      toast(`${file.name} ${text.fileSendFailed}: ${sendFailureAdvice(result)}`, "send_result");
    }
    await refreshJobs();
    setStartingPaths((prev) => {
      const next = { ...prev };
      delete next[file.path];
      return next;
    });
  }, [refreshJobs, runningPaths, selectedDevice, startingPaths, toast]);

  useEffect(() => {
    refreshJobs().catch((error) => console.warn("[KDEck] getSendJobs failed:", error));
    const timer = window.setInterval(() => {
      refreshJobs().catch((error) => console.warn("[KDEck] getSendJobs failed:", error));
    }, hasRunningJobs ? 900 : 3000);
    return () => window.clearInterval(timer);
  }, [hasRunningJobs, refreshJobs]);

  useEffect(() => {
    for (const job of jobs) {
      if (!job.job_id || handledJobIdsRef.current.has(job.job_id)) continue;
      if (!trackedJobIdsRef.current.has(job.job_id)) continue;
      if (job.status === "finished" && job.file_path) {
        handledJobIdsRef.current.add(job.job_id);
        trackedJobIdsRef.current.delete(job.job_id);
        showSuccessFeedback(job.file_path);
      } else if (job.status === "failed") {
        handledJobIdsRef.current.add(job.job_id);
        trackedJobIdsRef.current.delete(job.job_id);
        const name = job.file_name || text.file;
        const reason = sendFailureAdvice(job);
        toast(`${name} ${text.fileSendFailed}: ${reason}`, "send_result");
      }
    }
  }, [jobs, showSuccessFeedback, toast]);

  useEffect(() => {
    return () => {
      Object.values(feedbackTimersRef.current).forEach((timer) => window.clearTimeout(timer));
      feedbackTimersRef.current = {};
    };
  }, []);

  const pages = useMemo(() => CATEGORIES.map((category) => ({
    title: titleForCategory(category),
    icon: iconForCategory(category),
    route: `/kdeck/send/${category}`,
    content: (
      <SendCategoryPage
        category={category}
        state={categoryStates[category]}
        jobs={jobs}
        startingPaths={startingPaths}
        feedbackByPath={feedbackByPath}
        devices={devices}
        selectedDevice={selectedDevice}
        onCycleDevice={cycleDevice}
        onSend={sendFile}
      />
    ),
  })), [
    categoryStates,
    cycleDevice,
    devices,
    feedbackByPath,
    jobs,
    selectedDevice,
    sendFile,
    startingPaths,
  ]);

  return (
    <SidebarNavigation
      title={`KDEck v${__KDECK_VERSION__}`}
      showTitle
      pages={pages}
      page={`/kdeck/send/${currentPage}`}
      onPageRequested={(page) => {
        const next = CATEGORIES.find((category) => page.endsWith(`/${category}`));
        if (next) setCurrentPage(next);
      }}
    />
  );
}
