import { spawn } from "node:child_process";
import { createConnection } from "node:net";
import { fileURLToPath } from "node:url";
import path from "node:path";

const BASE_URL = "http://127.0.0.1:5000";

function waitForServer(host, port, timeoutMs = 20000) {
  return new Promise((resolve, reject) => {
    const started = Date.now();
    const probe = () => {
      const socket = createConnection({ host, port });
      socket.once("connect", () => { socket.destroy(); resolve(); });
      socket.once("error", () => {
        socket.destroy();
        if (Date.now() - started >= timeoutMs) reject(new Error("Flask server readiness timeout"));
        else setTimeout(probe, 150);
      });
    };
    probe();
  });
}

export default async function run(page) {
  const result = { steps: [], consoleErrors: [], failedRequests: [] };
  await page.route("https://fonts.googleapis.com/**", route => route.fulfill({ status: 200, contentType: "text/css", body: "" }));
  await page.route("https://fonts.gstatic.com/**", route => route.fulfill({ status: 200, contentType: "font/woff2", body: Buffer.from([]) }));
  page.on("console", msg => { if (msg.type() === "error") result.consoleErrors.push(msg.text()); });
  page.on("requestfailed", req => result.failedRequests.push(`${req.method()} ${req.url()}`));
  const check = (name, ok) => result.steps.push({ name, ok: Boolean(ok) });

  await page.goto(`${BASE_URL}/study-library`);
  let body = await page.innerText("body");
  check("public approved library", body.includes("Study Notes Library") && body.includes("Database Normalization"));
  check("pending/rejected hidden", !body.includes("Pending Secret Topic") && !body.includes("Rejected Circuit Topic"));

  await page.goto(`${BASE_URL}/login`);
  await page.locator("#email").fill("browser_step12@example.com");
  await page.locator("#password").fill("Pass12345");
  await page.locator('button[type="submit"]').click();
  await page.waitForLoadState("domcontentloaded");
  check("student login", !page.url().endsWith("/login"));

  await page.goto(`${BASE_URL}/study-library?q=normalization`);
  const quizLink = page.getByRole("link", { name: /Generate Quiz/ }).first();
  check("Study Library quiz action", await quizLink.count() === 1);
  await quizLink.click();
  await page.waitForLoadState("domcontentloaded");
  check("quiz creation page", (await page.innerText("body")).includes("AI Quiz Generator"));

  await page.locator("#question_type").selectOption("mcq");
  await page.locator("#difficulty").selectOption("medium");
  await page.locator("#question_count").fill("2");
  await page.getByRole("button", { name: "Generate Quiz" }).click();
  await page.waitForLoadState("domcontentloaded");
  body = await page.innerText("body");
  check("questions rendered", body.includes("Submit Quiz") && (await page.locator('input[type="radio"]').count()) === 8);
  const quizHtml = await page.content();
  check("answer keys protected before submission", !quizHtml.includes("correct_answer") && !quizHtml.includes("expected_answer"));

  const firstAnswer = page.locator('input[type="radio"]').first();
  await firstAnswer.check();
  await page.locator('input[type="radio"]').nth(4).check();
  await page.getByRole("button", { name: "Submit Quiz" }).click();
  await page.waitForLoadState("domcontentloaded");
  body = await page.innerText("body");
  check("result page", body.includes("Quiz Result") || body.includes("Correct"));
  check("server score shown", body.includes("Score") && body.includes("/2"));
  check("answers and explanations after submit", body.includes("Correct answer:") && body.includes("Explanation:"));

  await page.goto(`${BASE_URL}/study-library?q=normalization`);
  const bookmarkAction = page.getByRole("button", { name: /Bookmark/ }).first();
  if (await bookmarkAction.count()) await bookmarkAction.click();
  await page.waitForLoadState("domcontentloaded");
  await page.goto(`${BASE_URL}/my-bookmarks`);
  check("My Bookmarks quiz action", await page.getByRole("link", { name: /Generate Quiz/ }).count() >= 1);

  await page.goto(`${BASE_URL}/quiz/create/47`);
  check("pending material blocked", !page.url().includes("/quiz/create/47") || (await page.innerText("body")).includes("unavailable"));
  await page.goto(`${BASE_URL}/quiz/create/48`);
  check("rejected material blocked", !page.url().includes("/quiz/create/48") || (await page.innerText("body")).includes("unavailable"));
  check("all browser checks passed", result.steps.every(step => step.ok) && result.consoleErrors.length === 0 && result.failedRequests.length === 0);
  return result;
}

async function runStandalone() {
  const root = path.dirname(fileURLToPath(import.meta.url));
  const server = spawn(process.env.PYTHON || "python", [path.join(root, "browser_step10_server.py")], { cwd: root, stdio: "inherit" });
  const cleanup = () => { if (!server.killed) server.kill(); };
  process.once("SIGINT", () => { cleanup(); process.exit(130); });
  process.once("SIGTERM", () => { cleanup(); process.exit(143); });
  try {
    await waitForServer("127.0.0.1", 5000);
    const runner = path.join(process.env.CODEGPT_SKILL_DIR || "C:\\Users\\HP\\.codegpt\\skills\\browser-automation", "browser.mjs");
    const child = spawn(process.execPath, [runner, "data:text/html,<title>Step10%20QA</title>", "--script", path.join(root, "browser_step10_qa.mjs")], { cwd: root, stdio: "inherit" });
    await new Promise((resolve, reject) => { child.once("exit", code => code === 0 ? resolve() : reject(new Error(`Browser QA exited with ${code}`))); child.once("error", reject); });
  } finally { cleanup(); }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) runStandalone().catch(error => { console.error(error.message); process.exitCode = 1; });
