import { staticClasses } from "@decky/ui";
import { definePlugin, routerHook } from "@decky/api";
import { FaLink } from "react-icons/fa";
import MainPanel from "./pages/MainPanel";
import SendPage from "./pages/SendPage";

declare var __KDECK_VERSION__: string;

export default definePlugin(() => {
  routerHook.addRoute("/kdeck/send", () => <SendPage initialPage="screenshots" />);
  routerHook.addRoute("/kdeck/send/screenshots", () => <SendPage initialPage="screenshots" />);
  routerHook.addRoute("/kdeck/send/recordings", () => <SendPage initialPage="recordings" />);
  routerHook.addRoute("/kdeck/send/logs", () => <SendPage initialPage="logs" />);
  routerHook.addRoute("/kdeck/send/saves", () => <SendPage initialPage="saves" />);

  return {
    name: "KDEck",
    titleView: <div className={staticClasses.Title}>KDEck v{__KDECK_VERSION__}</div>,
    content: <MainPanel />,
    icon: <FaLink />,
  };
});
