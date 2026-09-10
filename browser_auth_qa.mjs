export default async function run(page, ui) {
  const results = {
    steps: [],
    consoleErrors: [],
    failedRequests: [],
  };

  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      results.consoleErrors.push(msg.text());
    }
  });

  page.on('requestfailed', (req) => {
    results.failedRequests.push(`${req.method()} ${req.url()}: ${req.failure()?.errorText}`);
  });

  try {
    // 1. Visit Register Page
    await page.goto('http://127.0.0.1:5000/register');
    await page.waitForSelector('#department_id', { timeout: 8000 });

    const departmentOptions = await page.locator('#department_id option').allInnerTexts();
    const hasDepartments = departmentOptions.some(opt => opt.includes('CSE'));

    results.steps.push({
      step: '1. Register Page Loaded with Dynamic Departments',
      departmentCount: departmentOptions.length - 1,
      hasCse: hasDepartments,
      ok: hasDepartments,
    });

    // 2. Perform Student Registration
    const testEmail = `student_${Date.now()}@example.com`;
    await page.locator('#name').fill('Rayhan');
    await page.locator('#email').fill(testEmail);

    // Select CSE department
    await page.locator('#department_id').selectOption({ label: 'CSE — Computer Science and Engineering' });

    await page.locator('#password').fill('SecretPass123');
    await page.locator('#confirm_password').fill('SecretPass123');

    await page.locator('#register-submit-btn').click();
    await page.waitForURL('**/login', { timeout: 8000 });

    const loginPageLoaded = page.url().includes('/login');
    const pageTextAfterRegister = await page.innerText('body');
    const flashSuccess = pageTextAfterRegister.includes('Account created successfully');

    results.steps.push({
      step: '2. Student Registration Flow',
      loginPageLoaded,
      flashSuccess,
      ok: loginPageLoaded && flashSuccess,
    });

    // 3. Perform Student Login
    await page.locator('#email').fill(testEmail);
    await page.locator('#password').fill('SecretPass123');
    await page.locator('button[type="submit"]').click();
    await page.waitForURL('http://127.0.0.1:5000/', { timeout: 8000 });

    // 4. Verify Authenticated Navigation Bar
    const navText = await page.locator('nav').innerText();
    const userDisplayed = navText.includes('Rayhan');
    const logoutBtnPresent = await page.locator('#nav-logout-btn').isVisible();
    const loginBtnHidden = (await page.locator('#nav-login-btn').count() === 0);

    results.steps.push({
      step: '3. Authenticated Navbar State',
      userDisplayed,
      logoutBtnPresent,
      loginBtnHidden,
      ok: userDisplayed && logoutBtnPresent && loginBtnHidden,
    });

    // 5. Perform Logout
    await page.locator('#nav-logout-btn').click();
    await page.waitForURL('**/login', { timeout: 8000 });

    const navAfterLogout = await page.locator('nav').innerText();
    const loginLinkVisible = await page.locator('#nav-login-btn').isVisible();
    const registerLinkVisible = await page.locator('#nav-register-btn').isVisible();

    results.steps.push({
      step: '4. Logout Flow and Cleared Navbar State',
      loginLinkVisible,
      registerLinkVisible,
      ok: loginLinkVisible && registerLinkVisible,
    });

    return results;

  } catch (err) {
    results.steps.push({ step: 'Error encountered', error: err.message, ok: false });
    return results;
  }
}
