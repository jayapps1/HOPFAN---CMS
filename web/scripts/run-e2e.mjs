import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = fileURLToPath(new URL("..", import.meta.url));
const environment = { ...process.env, HOPFAN_E2E: "1", NEXT_PUBLIC_API_BASE_URL: "http://localhost:8001",
  PLAYWRIGHT_BROWSERS_PATH: path.join(root, ".playwright") };
function run(executable, args, cwd = root) {
  return new Promise((resolve, reject) => {
    const child = spawn(executable, args, { cwd, env: environment, stdio: "inherit", windowsHide: true });
    child.on("error", () => reject(new Error("Unable to start " + path.basename(executable))));
    child.on("exit", code => code === 0 ? resolve() : reject(new Error(path.basename(executable) + " exited with code " + code)));
  });
}
try {
  await run(process.execPath, [path.join(root, "node_modules/next/dist/bin/next"), "build"]);
  await run(process.execPath, [path.join(root, "node_modules/@playwright/test/cli.js"), "test", ...process.argv.slice(2)]);
} catch (error) { console.error("Browser validation failed:", error.message); process.exitCode = 1; }
finally {
  const repo = path.dirname(root);
  const python = process.platform === "win32" ? path.join(repo, ".venv/Scripts/python.exe") : path.join(repo, ".venv/bin/python");
  try { await run(python, ["-m", "tests.portal_preview_api", "cleanup"], repo); }
  catch (error) { console.error("Fixture cleanup failed:", error.message); process.exitCode = 1; }
}
