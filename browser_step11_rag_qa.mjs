// Step 11 browser E2E: RAG-backed Ask StudyMate.
// Verifies retrieval selects the approved source, pending material never appears,
// the no-match state works, and the mobile layout renders. Server: :5001.
export default async function run(page) {
  const result = { steps: [], consoleErrors: [], failedRequests: [] };
  page.on('console', msg => { if (msg.type() === 'error') result.consoleErrors.push(msg.text()); });
  page.on('requestfailed', req => result.failedRequests.push(`${req.method()} ${req.url()}`));

  const BASE = 'http://127.0.0.1:5001';

  // Login (submit button is icon-only, so submit the form directly)
  await page.goto(`${BASE}/login`);
  await page.fill('#email', 'step10_browser@example.com');
  await page.fill('#password', 'Pass12345');
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
    page.locator('form').first().evaluate(f => f.submit()),
  ]);
  result.steps.push({ name: 'login', ok: !page.url().includes('/login') });

  // Ask StudyMate page
  await page.goto(`${BASE}/ask-studymate`);
  await page.waitForSelector('#ask-button');
  result.steps.push({ name: 'page loads', ok: (await page.locator('h1').first().innerText()).includes('Ask StudyMate') });
  result.steps.push({ name: 'empty state', ok: await page.locator('#empty').isVisible() });

  // Realistic academic question -> RAG retrieval + mocked answer
  await page.fill('#question', 'What is database normalization?');
  await page.getByRole('button', { name: 'Ask StudyMate' }).click();
  await page.waitForSelector('#result:visible', { timeout: 10000 });

  const answer = await page.innerText('#answer');
  result.steps.push({ name: 'answer appears', ok: answer.toLowerCase().includes('normalization') });

  const sourcesText = await page.innerText('#sources');
  result.steps.push({ name: 'approved source selected', ok: sourcesText.includes('CSE 221') && sourcesText.includes('Normalization') });
  result.steps.push({ name: 'source cards present', ok: (await page.locator('#sources article').count()) >= 1 });

  const body = await page.innerText('body');
  result.steps.push({ name: 'pending material hidden', ok: !body.includes('Browser Pending Secret') && !body.includes('Pending secret') });

  // No-match state: unrelated question must NOT show sources
  await page.getByRole('button', { name: 'Ask Another Question' }).click();
  await page.fill('#question', 'quantum chromodynamics gluon scattering amplitude');
  await page.getByRole('button', { name: 'Ask StudyMate' }).click();
  await page.waitForSelector('#result:visible', { timeout: 10000 });
  const noMatchAnswer = await page.innerText('#answer');
  const noMatchSources = await page.locator('#sources article').count();
  result.steps.push({ name: 'no-match state', ok: noMatchAnswer.toLowerCase().includes("couldn't find") && noMatchSources === 0 });

  // No filesystem path leakage anywhere
  const finalBody = await page.innerText('body');
  result.steps.push({ name: 'no path leak', ok: !finalBody.includes('F:\\') && !finalBody.includes('uploads/') });

  // Mobile layout
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${BASE}/ask-studymate`);
  await page.waitForSelector('#ask-button');
  result.steps.push({ name: 'mobile layout', ok: await page.locator('#ask-button').isVisible() });

  return result;
}
