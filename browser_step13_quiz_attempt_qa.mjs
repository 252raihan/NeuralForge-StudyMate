// Step 13 browser E2E: quiz attempt, submission, result, and history.
// Server: browser_step10_server.py on :5001 (mocked AI generation).
export default async function run(page) {
  const result = { steps: [], consoleErrors: [], failedRequests: [] };
  page.on('console', msg => { if (msg.type() === 'error') result.consoleErrors.push(msg.text()); });
  page.on('requestfailed', req => result.failedRequests.push(`${req.method()} ${req.url()}`));

  const BASE = 'http://127.0.0.1:5001';

  // Login
  await page.goto(`${BASE}/login`);
  await page.fill('#email', 'step10_browser@example.com');
  await page.fill('#password', 'Pass12345');
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
    page.locator('form').first().evaluate(f => f.submit()),
  ]);
  result.steps.push({ name: 'login', ok: !page.url().includes('/login') });

  // Generate a 5-question quiz (mocked AI)
  await page.goto(`${BASE}/quiz/create`);
  await page.waitForSelector('#generate-btn');
  const courseValue = await page.locator('#course option').nth(1).getAttribute('value');
  await page.selectOption('#course', courseValue);
  await page.fill('#topic', 'Normalization');
  await page.selectOption('#number_of_questions', '5');
  await page.getByRole('button', { name: 'Generate Quiz' }).click();
  await page.waitForURL(/\/quiz\/view\/\d+/, { timeout: 15000 });
  const quizUrl = page.url();
  result.steps.push({ name: 'quiz generated', ok: /\/quiz\/view\/\d+/.test(quizUrl) });

  // Open the take page
  await page.getByRole('link', { name: /Take Quiz/ }).click();
  await page.waitForURL(/\/quiz\/take\/\d+/, { timeout: 15000 });
  await page.waitForSelector('#submit-btn');
  result.steps.push({ name: 'take page loads', ok: /\/quiz\/take\/\d+/.test(page.url()) });

  const totalQuestions = await page.locator('fieldset[data-question-id]').count();
  result.steps.push({ name: 'questions render', ok: totalQuestions === 5 });
  const firstOptions = await page.locator('fieldset[data-question-id]').first().locator('input[type=radio]').count();
  result.steps.push({ name: 'four options render', ok: firstOptions === 4 });

  // SECURITY: correct answer must not be present anywhere in the page HTML/source
  const html = await page.content();
  result.steps.push({ name: 'no answer key in HTML', ok: !/correct_answer/i.test(html) && !/data-correct/i.test(html) && !/"correctAnswer"/.test(html) });

  // Answer: select option B (index 1 = correct in the mock) for all, to score 100%
  const sets = page.locator('fieldset[data-question-id]');
  for (let i = 0; i < totalQuestions; i++) {
    await sets.nth(i).locator('input[type=radio]').nth(1).check();
  }

  // Confirm dialog + submit
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name: 'Submit Quiz' }).click();
  await page.waitForURL(/\/quiz\/result\/\d+/, { timeout: 15000 });
  result.steps.push({ name: 'result appears', ok: /\/quiz\/result\/\d+/.test(page.url()) });

  const reviewBody = await page.innerText('main');
  result.steps.push({ name: 'score appears', ok: /5\/5/.test(reviewBody) && reviewBody.includes('100') });
  result.steps.push({ name: 'review shows correct/wrong', ok: reviewBody.includes('Correct') });
  result.steps.push({ name: 'correct answer shown after submit', ok: reviewBody.includes('correct answer') });
  result.steps.push({ name: 'explanation shown after submit', ok: reviewBody.includes('Explanation') });
  const resultUrl = page.url();

  // Refresh result works (idempotent GET)
  await page.reload({ waitUntil: 'domcontentloaded' });
  result.steps.push({ name: 'refresh result works', ok: /5\/5/.test(await page.innerText('main')) });

  // Attempt history
  await page.goto(`${BASE}/quiz/attempts`);
  const histBody = await page.innerText('main');
  result.steps.push({ name: 'attempt history appears', ok: histBody.includes('Normalization') && histBody.includes('100') });
  await page.getByRole('link', { name: 'View Result' }).first().click();
  await page.waitForURL(/\/quiz\/result\/\d+/, { timeout: 10000 });
  result.steps.push({ name: 'open result from history', ok: /\/quiz\/result\/\d+/.test(page.url()) });

  // Mobile layout
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${BASE}/quiz/attempts`);
  result.steps.push({ name: 'mobile layout', ok: (await page.locator('h1').first().innerText()).includes('My Quiz Attempts') });

  return result;
}
