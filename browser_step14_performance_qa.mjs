// Step 14 browser E2E: quiz performance analysis.
// Server: browser_step14_perf_server.py on :5002 (deterministic fixtures).
export default async function run(page) {
  const result = { steps: [], consoleErrors: [], failedRequests: [] };
  page.on('console', msg => { if (msg.type() === 'error') result.consoleErrors.push(msg.text()); });
  page.on('requestfailed', req => result.failedRequests.push(`${req.method()} ${req.url()}`));

  const BASE = 'http://127.0.0.1:5002';

  async function login(email, password) {
    // Ensure a fresh, logged-out login form is present.
    // Logout is POST-only now; GET /logout must not change state (returns 405).
    await page.request.post(`${BASE}/logout`);
    await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => !!document.querySelector('input[name="email"]'), { timeout: 30000 });
    // Fill and submit via the form element directly (robust against a headless
    // sandbox that may not settle actionability because of the Tailwind CDN).
    await Promise.all([
      page.waitForFunction(() => !location.pathname.endsWith('/login'), { timeout: 15000 }).catch(() => {}),
      page.evaluate((creds) => {
        const input = document.querySelector('input[name="email"]');
        input.value = creds.email;
        document.querySelector('input[name="password"]').value = creds.password;
        input.form.submit();
      }, { email, password }),
    ]);
    await page.waitForLoadState('domcontentloaded');
  }

  // 1. Login as the student with completed attempts
  await login('step14_perf@example.com', 'Pass12345');
  result.steps.push({ name: 'login', ok: !page.url().includes('/login') });

  // 2. Performance navigation visible
  const navText = await page.innerText('nav');
  result.steps.push({ name: 'performance nav visible', ok: navText.includes('Performance') });

  // 3. Performance page loads
  await page.goto(`${BASE}/quiz/performance`);
  await page.waitForSelector('h1');
  const body = await page.innerText('main');
  result.steps.push({ name: 'performance page loads', ok: body.includes('My Performance') });

  // 4. Overview cards visible with correct metrics
  result.steps.push({ name: 'overview cards visible', ok: body.includes('Quizzes Completed') && body.includes('Overall Accuracy') });
  result.steps.push({ name: 'overview metrics correct', ok: body.includes('80.0%') && body.includes('10') });

  // 5-8. Sections visible
  result.steps.push({ name: 'quiz performance visible', ok: body.includes('Quiz Performance') && body.includes('PerfBrowser Normalization Quiz') });
  result.steps.push({ name: 'course performance visible', ok: body.includes('Course Performance') && body.includes('CSE 221') });
  result.steps.push({ name: 'topic performance visible', ok: body.includes('Topic Performance') && body.includes('PerfBrowser Indexing') });
  result.steps.push({ name: 'recent performance visible', ok: body.includes('Recent Performance') });

  // 9. Data matches completed attempts (100% + 60%)
  result.steps.push({ name: 'data matches attempts', ok: body.includes('100.0%') && body.includes('60.0%') });

  // 10. Active attempt does not affect metrics (2 completed quizzes, not 3)
  const api = await page.evaluate(async () => (await fetch('/api/quiz/performance')).json());
  result.steps.push({ name: 'active attempt excluded', ok: api.overview.completed_quizzes === 2 && api.quiz_performance.length === 2 });

  // 11. Another user's data is not visible
  result.steps.push({ name: 'other user data hidden', ok: !body.includes('SECRET') && !(await page.content()).includes('SECRET') });

  // 13. Mobile layout
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${BASE}/quiz/performance`);
  await page.waitForSelector('h1');
  result.steps.push({ name: 'mobile layout', ok: (await page.locator('h1').first().innerText()).includes('My Performance') });

  // 12. Empty state for a user with no completed attempts (login() logs out first).
  await login('step14_perf_empty@example.com', 'Pass12345');
  await page.goto(`${BASE}/quiz/performance`);
  const emptyBody = await page.innerText('main');
  result.steps.push({ name: 'empty state works', ok: emptyBody.includes('No performance data yet') });

  return result;
}
