import { readFileSync } from "fs";
import replace from "@rollup/plugin-replace";
import deckyPlugin from "@decky/rollup";

const pkg = JSON.parse(readFileSync("./package.json", "utf-8"));

export default deckyPlugin({
  plugins: [
    replace({
      preventAssignment: true,
      __KDECK_VERSION__: JSON.stringify(pkg.version),
    }),
  ],
})