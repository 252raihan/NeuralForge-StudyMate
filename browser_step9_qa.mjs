export default async function run(page) {
  const result = { steps: [], consoleErrors: [], failedRequests: [] };
  page.on('console', msg => { if (msg.type() === 'error') result.consoleErrors.push(msg.text()); });
  page.on('requestfailed', req => result.failedRequests.push(`${req.method()} ${req.url()}`));
  await page.goto('http://127.0.0.1:5000/study-library');
  const body = await page.innerText('body');
  result.steps.push({ name: 'public library', ok: page.url().includes('/study-library') && body.includes('Study Notes Library') && body.includes('Database Normalization') });
  result.steps.push({ name: 'approved-only visible', ok: !body.includes('Pending Secret Topic') && !body.includes('Rejected Circuit Topic') });
  await page.locator('#topic').fill('normalization');
  await page.getByRole('button', { name: 'Search Library' }).click();
  await page.waitForLoadState('domcontentloaded');
  result.steps.push({ name: 'topic filter', ok: (await page.innerText('body')).includes('Database Normalization') });
  const view = page.getByRole('link', { name: 'View' }).first();
  if (await view.count()) {
    const pdfUrl = await view.getAttribute('href');
    const response = await page.request.get(new URL(pdfUrl, page.url()).toString());
    result.steps.push({ name: 'approved PDF view', ok: response.status() === 200 && (response.headers()['content-type'] || '').includes('application/pdf') });
  }
  return result;
}
