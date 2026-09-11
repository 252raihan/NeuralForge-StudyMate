import { spawn } from "node:child_process";
import { createConnection } from "node:net";
import { fileURLToPath } from "node:url";
import path from "node:path";
const BASE_URL = "http://127.0.0.1:5000";
function waitForServer(host, port, timeoutMs = 20000) { return new Promise((resolve, reject) => { const started = Date.now(); const probe = () => { const socket = createConnection({ host, port }); socket.once("connect", () => { socket.destroy(); resolve(); }); socket.once("error", () => { socket.destroy(); if (Date.now() - started >= timeoutMs) reject(new Error("Flask server readiness timeout")); else setTimeout(probe, 150); }); }; probe(); }); }
export default async function run(page) {
  const result = { steps: [], consoleErrors: [], failedRequests: [] };
  await page.route("https://fonts.googleapis.com/**", route => route.fulfill({ status: 200, contentType: "text/css", body: "" }));
  await page.route("https://fonts.gstatic.com/**", route => route.fulfill({ status: 200, contentType: "font/woff2", body: Buffer.from([]) }));
  page.on("console", msg => { if (msg.type() === "error") result.consoleErrors.push(msg.text()); });
  page.on("requestfailed", req => result.failedRequests.push(`${req.method()} ${req.url()}`));
  const check = (name, ok) => result.steps.push({ name, ok: Boolean(ok) });
  await page.goto(`${BASE_URL}/login`);
  await page.locator("#email").fill("browser_step12@example.com");
  await page.locator("#password").fill("Pass12345");
  await page.locator('button[type="submit"]').click();
  await page.waitForLoadState("domcontentloaded");
  check("student login", !page.url().endsWith("/login"));
  await page.goto(`${BASE_URL}/dashboard`);
  let body = await page.innerText("body");
  check("dashboard loads", body.includes("Student Dashboard"));
  check("summary statistics", body.includes("Materials") && body.includes("Bookmarks") && body.includes("Quizzes") && body.includes("Average"));
  check("dashboard sections", body.includes("Recent Study Materials") && body.includes("Recent Quizzes") && body.includes("Recent Bookmarks") && body.includes("Course Progress"));
  check("dashboard navigation", await page.getByRole("link", { name: /Study Library/ }).count() >= 1 && await page.getByRole("link", { name: /My Bookmarks/ }).count() >= 1);
  const quizLink = page.getByRole("link", { name: /Dashboard Quiz|result|Not attempted/ }).first();
  check("quiz metadata link", await quizLink.count() >= 1);
  await page.getByRole("link", { name: /Study Library/ }).first().click();
  await page.waitForLoadState("domcontentloaded");
  check("Study Library link", page.url().includes("/study-library"));
  await page.goto(`${BASE_URL}/dashboard`);
  await page.getByRole("link", { name: /My Bookmarks/ }).first().click();
  await page.waitForLoadState("domcontentloaded");
  check("My Bookmarks link", page.url().includes("/my-bookmarks"));
  await page.goto(`${BASE_URL}/dashboard`);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  const viewport = await page.evaluate(() => { const root = document.documentElement; const offenders = [...document.querySelectorAll('*')].filter(el => { const rect = el.getBoundingClientRect(); return rect.right > window.innerWidth + 1; }).slice(0, 8).map(el => ({ tag: el.tagName, id: el.id, className: el.className, right: Math.round(el.getBoundingClientRect().right) })); return { width: window.innerWidth, overflow: root.scrollWidth > root.clientWidth, offenders }; });
  result.responsive = viewport;
  check("responsive layout", viewport.width === 390 && viewport.overflow === false);
  await page.goto(`${BASE_URL}/logout`);
  await page.goto(`${BASE_URL}/dashboard`);
  check("dashboard protected after logout", page.url().includes("/login"));
  check("all browser checks passed", result.steps.every(step => step.ok) && result.consoleErrors.length === 0 && result.failedRequests.length === 0);
  return result;
}
async function runStandalone() {
  const root = path.dirname(fileURLToPath(import.meta.url));
  const server = spawn(process.env.PYTHON || "python", ["-c", "from app import app; app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)"], { cwd: root, stdio: "inherit" });
  const cleanup = () => { if (!server.killed) server.kill(); };
  try { await waitForServer("127.0.0.1", 5000); const runner = path.join(process.env.CODEGPT_SKILL_DIR || "C:\\Users\\HP\\.codegpt\\skills\\browser-automation", "browser.mjs"); const child = spawn(process.execPath, [runner, "data:text/html,<title>Step13%20QA</title>", "--script", path.join(root, "browser_step13_qa.mjs")], { cwd: root, stdio: "inherit" }); await new Promise((resolve, reject) => { child.once("exit", code => code === 0 ? resolve() : reject(new Error(`Browser QA exited with ${code}`))); child.once("error", reject); }); } finally { cleanup(); }
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) runStandalone().catch(error => { console.error(error.message); process.exitCode = 1; });
