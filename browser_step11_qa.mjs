export default async function run(page) {
  const result = { steps: [], consoleErrors: [], failedRequests: [] };
  page.on('console', msg => { if (msg.type() === 'error') result.consoleErrors.push(msg.text()); });
  page.on('requestfailed', req => result.failedRequests.push(`${req.method()} ${req.url()}`));
  await page.goto('http://127.0.0.1:5000/study-library');
  let body = await page.innerText('body');
  result.steps.push({ name: 'public library loaded', ok: body.includes('Study Notes Library') && body.includes('Approved') });
  await page.locator('#q').fill('normalization');
  await page.getByRole('button', { name: 'Search Library' }).click();
  await page.waitForLoadState('domcontentloaded');
  body = await page.innerText('body');
  result.steps.push({ name: 'keyword search', ok: page.url().includes('q=normalization') && body.toLowerCase().includes('normalization') });
  const cseOption = await page.locator('#department_id option').filter({ hasText: 'CSE' }).first();
  await page.locator('#department_id').selectOption(await cseOption.getAttribute('value'));
  await page.waitForLoadState('domcontentloaded');
  result.steps.push({ name: 'department filter', ok: new URL(page.url()).searchParams.has('department_id') });
  await page.locator('#exam_type').selectOption('midterm');
  await page.getByRole('button', { name: 'Search Library' }).click();
  await page.waitForLoadState('domcontentloaded');
  result.steps.push({ name: 'combined filters', ok: new URL(page.url()).searchParams.get('exam_type') === 'midterm' && (await page.innerText('body')).toLowerCase().includes('normalization') });
  await page.locator('#sort').selectOption('title_desc');
  await page.getByRole('button', { name: 'Search Library' }).click();
  await page.waitForLoadState('domcontentloaded');
  result.steps.push({ name: 'sorting preserves query state', ok: new URL(page.url()).searchParams.get('sort') === 'title_desc' && new URL(page.url()).searchParams.get('q') === 'normalization' });
  const clear = page.getByRole('link', { name: 'Clear filters' });
  await clear.click();
  await page.waitForLoadState('domcontentloaded');
  result.steps.push({ name: 'clear filters', ok: !new URL(page.url()).searchParams.has('q') && !new URL(page.url()).searchParams.has('exam_type') });
  const view = page.getByRole('link', { name: /View/ }).first();
  if (await view.count()) {
    const pdfUrl = await view.getAttribute('href');
    const response = await page.request.get(new URL(pdfUrl, page.url()).toString());
    result.steps.push({ name: 'approved PDF access', ok: response.status() === 200 && (response.headers()['content-type'] || '').includes('application/pdf') });
  }
  return result;
}
