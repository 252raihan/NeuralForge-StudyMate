// Step 12 browser E2E: AI Quiz Generator (generation + preview only).
// Server: browser_step10_server.py on :5001 (mocked AI).
export default async function run(page) {
  const result = { steps: [], consoleErrors: [], failedRequests: [] };
  page.on('console', msg => { if (msg.type() === 'error') result.consoleErrors.push(msg.text()); });
  page.on('requestfailed', req => result.failedRequests.push(`${req.method()} ${req.url()}`));

  const BASE = 'http://127.0.0.1:5001';

  // Login (icon-only submit button -> submit the form directly)
  await page.goto(`${BASE}/login`);
  await page.fill('#email', 'step10_browser@example.com');
  await page.fill('#password', 'Pass12345');
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
    page.locator('form').first().evaluate(f => f.submit()),
  ]);
  result.steps.push({ name: 'login', ok: !page.url().includes('/login') });

  // Quiz create page
  await page.goto(`${BASE}/quiz/create`);
  await page.waitForSelector('#generate-btn');
  result.steps.push({ name: 'create page loads', ok: (await page.locator('h1').first().innerText()).includes('Generate a Quiz') });
  result.steps.push({ name: 'course selector works', ok: (await page.locator('#course option').count()) >= 2 });

  // Fill selectors + topic
  const courseValue = await page.locator('#course option').nth(1).getAttribute('value');
  await page.selectOption('#course', courseValue);
  await page.fill('#topic', 'Normalization');
  await page.selectOption('#difficulty', 'medium');
  await page.selectOption('#number_of_questions', '5');
  result.steps.push({ name: 'selectors populated', ok: (await page.inputValue('#topic')) === 'Normalization' && (await page.inputValue('#number_of_questions')) === '5' });

  // Generate quiz -> redirect to preview
  await page.getByRole('button', { name: 'Generate Quiz' }).click();
  await page.waitForURL(/\/quiz\/view\/\d+/, { timeout: 15000 });
  result.steps.push({ name: 'quiz preview appears', ok: /\/quiz\/view\/\d+/.test(page.url()) });

  const body = await page.innerText('main');
  result.steps.push({ name: 'title shown', ok: body.includes('Normalization Quiz') });
  const questionCount = await page.locator('ol > li').count();
  result.steps.push({ name: 'correct question count', ok: questionCount === 5 });
  const firstOptions = await page.locator('ol > li').first().locator('ul li').count();
  result.steps.push({ name: 'four options appear', ok: firstOptions === 4 });
  result.steps.push({ name: 'source materials shown', ok: body.includes('Source materials') });
  result.steps.push({ name: 'no path leak', ok: !body.includes('F:\\') && !body.includes('uploads/') });

  // Mobile layout
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${BASE}/quiz/create`);
  await page.waitForSelector('#generate-btn');
  result.steps.push({ name: 'mobile layout', ok: await page.locator('#generate-btn').isVisible() });

  return result;
}
