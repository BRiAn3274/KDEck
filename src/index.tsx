import { staticClasses } from "@decky/ui";
import { definePlugin, routerHook } from "@decky/api";
import { FaLink } from "react-icons/fa";
import MainPanel from "./pages/MainPanel";
import SendPage from "./pages/SendPage";

declare var __KDECK_VERSION__: string;

routerHook.addRoute("/kdeck/send", () => <SendPage />);

export default definePlugin(() => ({
  name: "KDEck",
  titleView: <div className={staticClasses.Title}>KDEck v{__KDECK_VERSION__}</div>,
  content: <MainPanel />,
  icon: <FaLink />,
}));
