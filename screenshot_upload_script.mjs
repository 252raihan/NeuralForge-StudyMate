export default async function run(page, ui) {
  // Login first
  await page.goto('http://127.0.0.1:5000/login');
  await page.locator('#email').fill('student@studymate.local');
  await page.locator('#password').fill('samplepasswordhashforstep5verification'); // or register fresh
  // Let's create a fresh user and navigate to upload
  await page.goto('http://127.0.0.1:5000/register');
  const tempEmail = `screen_${Date.now()}@example.com`;
  await page.locator('#name').fill('Alex Student');
  await page.locator('#email').fill(tempEmail);
  await page.locator('#department_id').selectOption({ label: 'CSE — Computer Science and Engineering' });
  await page.locator('#password').fill('AlexPass123');
  await page.locator('#confirm_password').fill('AlexPass123');
  await page.locator('#register-submit-btn').click();
  await page.waitForURL('**/login');

  await page.locator('#email').fill(tempEmail);
  await page.locator('#password').fill('AlexPass123');
  await page.locator('button[type="submit"]').click();
  await page.waitForURL('http://127.0.0.1:5000/');

  await page.goto('http://127.0.0.1:5000/study-material/upload');
  await page.waitForSelector('#study-material-form');
  return { ok: true };
}
