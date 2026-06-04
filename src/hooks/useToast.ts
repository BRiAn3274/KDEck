import { toaster } from "@decky/api";

export function useToast() {
  return (body: string) => toaster.toast({ title: "KDEck", body });
}
