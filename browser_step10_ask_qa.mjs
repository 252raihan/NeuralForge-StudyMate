// Step 10 browser E2E: login, ask a question, verify loading + answer + sources,
// error state, and mobile layout. Runs against browser_step10_server.py on :5001.
export default async function run(page) {
  const result = { steps: [], consoleErrors: [], failedRequests: [] };
  page.on('console', msg => { if (msg.type() === 'error') result.consoleErrors.push(msg.text()); });
  page.on('requestfailed', req => result.failedRequests.push(`${req.method()} ${req.url()}`));

  const BASE = 'http://127.0.0.1:5001';

  // Unauth: Ask StudyMate must redirect to login
  await page.goto(`${BASE}/ask-studymate`);
  result.steps.push({ name: 'anon redirect to login', ok: page.url().includes('/login') });

  // Login (submit button is icon-only, so submit the form directly)
  await page.fill('#email', 'step10_browser@example.com');
  await page.fill('#password', 'Pass12345');
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
    page.locator('form').first().evaluate(f => f.submit()),
  ]);
  result.steps.push({ name: 'login succeeded', ok: !page.url().includes('/login') });

  // Open Ask StudyMate via navbar
  await page.goto(`${BASE}/ask-studymate`);
  await page.waitForSelector('#ask-button', { timeout: 10000 });
  const heading = await page.locator('h1').first().innerText();
  const body = await page.innerText('main');
  result.steps.push({ name: 'page loads', ok: heading.includes('Ask StudyMate') && body.includes('approved study materials') });
  result.steps.push({ name: 'empty state visible', ok: await page.locator('#empty').isVisible() });

  // Submit a realistic question
  await page.fill('#question', 'What is normalization?');
  await page.getByRole('button', { name: 'Ask StudyMate' }).click();

  // Loading state may be brief; wait for the answer to render
  await page.waitForSelector('#result:visible', { timeout: 10000 });

  const answerText = await page.innerText('#answer');
  result.steps.push({ name: 'answer rendered', ok: answerText.toLowerCase().includes('normalization') });

  const sourceCards = await page.locator('#sources article').count();
  result.steps.push({ name: 'source materials appear', ok: sourceCards >= 1 });
  const sourcesText = await page.innerText('#sources');
  result.steps.push({ name: 'source metadata', ok: sourcesText.includes('CSE 221') && /Material #\d+/.test(sourcesText) });

  // No filesystem path leakage in the rendered page
  const full = await page.innerText('body');
  result.steps.push({ name: 'no path leak', ok: !full.includes('F:\\') && !full.includes('uploads/') });

  // Ask Another Question resets
  await page.getByRole('button', { name: 'Ask Another Question' }).click();
  result.steps.push({ name: 'ask another resets', ok: await page.locator('#empty').isVisible() });

  // Error state: force a server error via an invalid body shape
  const errResp = await page.evaluate(async () => {
    const r = await fetch('/api/ask-studymate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: '' })
    });
    return { status: r.status, data: await r.json() };
  });
  result.steps.push({ name: 'empty question error', ok: errResp.status === 400 && errResp.data.success === false });

  // Mobile layout
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${BASE}/ask-studymate`);
  result.steps.push({ name: 'mobile layout', ok: await page.locator('#ask-button').isVisible() });

  return result;
}
