import { spawn } from "node:child_process";
import { createConnection } from "node:net";
import { fileURLToPath } from "node:url";
import path from "node:path";
const BASE = "http://127.0.0.1:5000";
function ready() { return new Promise((resolve, reject) => { const started = Date.now(); const probe = () => { const s = createConnection({ host: "127.0.0.1", port: 5000 }); s.once("connect", () => { s.destroy(); resolve() }); s.once("error", () => { s.destroy(); if (Date.now() - started > 20000) reject(new Error("server readiness timeout")); else setTimeout(probe, 150) }); }; probe(); }); }
export default async function run(page) {
  const result = { steps: [], consoleErrors: [], failedRequests: [] };
  await page.route("https://fonts.googleapis.com/**", r => r.fulfill({ status: 200, contentType: "text/css", body: "" }));
  await page.route("https://fonts.gstatic.com/**", r => r.fulfill({ status: 200, contentType: "font/woff2", body: Buffer.from([]) }));
  await page.route("**/static/images/logo.png", r => r.fulfill({ status: 200, contentType: "image/png", body: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=", "base64") }));
  page.on("console", m => { if (m.type() === "error") result.consoleErrors.push(m.text()) });
  page.on("requestfailed", r => result.failedRequests.push(`${r.method()} ${r.url()}`));
  const check = (name, ok) => result.steps.push({ name, ok: Boolean(ok) });
  await page.goto(`${BASE}/login`); await page.locator("#email").fill(process.env.STEP14_EMAIL || "browser_step14@example.com"); await page.locator("#password").fill("Pass12345"); await page.locator('button[type="submit"]').click(); await page.waitForLoadState("domcontentloaded"); check("student login", !page.url().endsWith("/login"));
  await page.goto(`${BASE}/notifications`); let body = await page.innerText("body"); check("notifications list", body.includes("Notifications") && body.includes("Study material approved") && body.includes("Quiz completed")); check("unread count", body.includes("Mark all as"));
  const open = page.getByRole("button", { name: "Open" }).first(); check("notification open action", await open.count() === 1); await open.click(); await page.waitForLoadState("domcontentloaded"); check("related link works", page.url().includes("/dashboard"));
  await page.goto(`${BASE}/notifications`); const markAll = page.getByRole("button", { name: /Mark all as read/ }); if (await markAll.count()) { await markAll.click(); await page.waitForLoadState("domcontentloaded"); } check("mark all read", !(await page.innerText("body")).includes("Mark all as read"));
  await page.setViewportSize({ width: 390, height: 844 }); await page.reload(); const responsive = await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth); check("responsive layout", responsive);
  await page.request.post(`${BASE}/logout`); await page.goto(`${BASE}/login`); await page.locator("#email").fill("browser_step14_b@example.com"); await page.locator("#password").fill("Pass12345"); await page.locator('button[type="submit"]').click(); await page.waitForLoadState("domcontentloaded"); await page.goto(`${BASE}/notifications`); check("student B cannot see student A notifications", !(await page.innerText("body")).includes("Database Notes has been approved")); const getLogout = await page.request.get(`${BASE}/logout`); check("GET /logout rejected (405)", getLogout.status() === 405); await page.request.post(`${BASE}/logout`); await page.goto(`${BASE}/notifications`); check("notifications protected", page.url().includes("/login"));
  check("all browser checks passed", result.steps.every(x => x.ok) && result.consoleErrors.length === 0 && result.failedRequests.length === 0); return result;
}
async function main() { const root = path.dirname(fileURLToPath(import.meta.url)); const server = spawn(process.env.PYTHON || "python", [path.join(root, "browser_step14_server.py")], { cwd: root, stdio: "inherit" }); const cleanup = () => { if (!server.killed) server.kill() }; try { await ready(); const runner = path.join(process.env.CODEGPT_SKILL_DIR || "C:\\Users\\HP\\.codegpt\\skills\\browser-automation", "browser.mjs"); const child = spawn(process.execPath, [runner, "data:text/html,<title>Step14</title>", "--script", path.join(root, "browser_step14_qa.mjs")], { cwd: root, stdio: "inherit" }); await new Promise((res, rej) => { child.once("exit", code => code === 0 ? res() : rej(new Error(`browser exit ${code}`))); child.once("error", rej) }) } finally { cleanup() } }
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main().catch(e => { console.error(e.message); process.exitCode = 1 });
