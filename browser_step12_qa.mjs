export default async function run(page) {
  const result = { steps: [], consoleErrors: [], failedRequests: [] };
  page.on('console', msg => { if (msg.type() === 'error') result.consoleErrors.push(msg.text()); });
  page.on('requestfailed', req => result.failedRequests.push(`${req.method()} ${req.url()}`));
  await page.goto('http://127.0.0.1:5000/study-library?q=normalization');
  const publicBody = await page.innerText('body');
  result.steps.push({ name: 'public library search', ok: publicBody.includes('Study Notes Library') });
  await page.goto('http://127.0.0.1:5000/login');
  await page.locator('#email').fill('browser_step12@example.com');
  await page.locator('#password').fill('Pass12345');
  await page.locator('button[type="submit"]').click();
  await page.waitForTimeout(500);
  await page.goto('http://127.0.0.1:5000/study-library?q=normalization');
  const bookmarkButton = page.getByRole('button', { name: /Bookmark/ }).first();
  if (await bookmarkButton.count()) {
    await bookmarkButton.click();
    await page.waitForTimeout(300);
  }
  result.steps.push({ name: 'bookmark action', ok: (await page.innerText('body')).includes('Bookmarked') });
  await page.goto('http://127.0.0.1:5000/my-bookmarks');
  const savedBody = await page.innerText('body');
  result.steps.push({ name: 'my bookmarks', ok: savedBody.includes('My Bookmarks') && savedBody.toLowerCase().includes('normalization') });
  const view = page.getByRole('link', { name: /View/ }).first();
  if (await view.count()) {
    const pdfUrl = await view.getAttribute('href');
    const pdf = await page.request.get(new URL(pdfUrl, page.url()).toString());
    result.steps.push({ name: 'bookmarked PDF access', ok: pdf.status() === 200 && (pdf.headers()['content-type'] || '').includes('application/pdf') });
  }
  const remove = page.getByRole('button', { name: /Remove Bookmark/ }).first();
  if (await remove.count()) { await remove.click(); await page.waitForTimeout(300); }
  result.steps.push({ name: 'remove bookmark', ok: (await page.innerText('body')).includes('No bookmarks yet') });
  return result;
}
