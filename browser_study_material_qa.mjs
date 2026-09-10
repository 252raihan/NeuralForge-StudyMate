import path from 'path';

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
    // 1. Unauthenticated access check
    await page.goto('http://127.0.0.1:5000/study-material/upload');
    await page.waitForTimeout(500);
    const unauthUrl = page.url();
    const redirectedToLogin = unauthUrl.includes('/login');

    results.steps.push({
      step: '1. Unauthenticated access redirects to login',
      unauthUrl,
      ok: redirectedToLogin,
    });

    // 2. Register a new student in CSE department
    await page.goto('http://127.0.0.1:5000/register');
    await page.waitForSelector('#department_id', { timeout: 8000 });

    const studentEmail = `browser_student_${Date.now()}@example.com`;
    await page.locator('#name').fill('Sarah Jenkins');
    await page.locator('#email').fill(studentEmail);
    await page.locator('#department_id').selectOption({ label: 'CSE — Computer Science and Engineering' });
    await page.locator('#password').fill('SecretPass123');
    await page.locator('#confirm_password').fill('SecretPass123');
    await page.locator('#register-submit-btn').click();
    await page.waitForURL('**/login', { timeout: 8000 });

    // 3. Log in as this student
    await page.locator('#email').fill(studentEmail);
    await page.locator('#password').fill('SecretPass123');
    await page.locator('button[type="submit"]').click();
    await page.waitForURL('http://127.0.0.1:5000/', { timeout: 8000 });

    results.steps.push({
      step: '2. Student registered and logged in',
      studentEmail,
      ok: true,
    });

    // 4. Navigate to /study-material/upload
    await page.goto('http://127.0.0.1:5000/study-material/upload');
    await page.waitForSelector('#study-material-form', { timeout: 8000 });

    const courseOptions = await page.locator('#course_id option').allInnerTexts();
    const hasCse221 = courseOptions.some(opt => opt.includes('CSE 221'));

    results.steps.push({
      step: '3. Upload page loaded with departmental courses',
      courseCount: courseOptions.length - 1,
      hasCse221,
      ok: hasCse221,
    });

    // 5. Fill out Study Material upload form
    const samplePdfPath = path.resolve(process.cwd(), 'sample_study_guide.pdf');

    // Select CSE 221
    const cse221Option = await page.locator('#course_id option').filter({ hasText: 'CSE 221' }).first();
    const cse221Val = await cse221Option.getAttribute('value');
    await page.locator('#course_id').selectOption(cse221Val);

    // Select Exam Type: Midterm
    await page.locator('#exam_type').selectOption('midterm');

    // Fill Topic
    await page.locator('#topic').fill('Normalization & 3NF Forms');

    // Attach PDF
    await page.locator('#material-file-input').setInputFiles(samplePdfPath);
    await page.waitForTimeout(300);

    // Submit Form
    await page.locator('#submit-material-btn').click();
    await page.waitForURL('**/my-study-materials', { timeout: 10000 });

    const myMaterialsUrl = page.url();
    const pageText = await page.innerText('body');

    const topicPresent = pageText.includes('Normalization & 3NF Forms');
    const coursePresent = pageText.includes('CSE 221');
    const statusPendingPresent = pageText.includes('Pending Approval');

    results.steps.push({
      step: '4. Form submitted and redirected to My Study Materials',
      myMaterialsUrl,
      topicPresent,
      coursePresent,
      statusPendingPresent,
      ok: topicPresent && coursePresent && statusPendingPresent,
    });

    return results;

  } catch (err) {
    results.steps.push({ step: 'Error encountered', error: err.message, ok: false });
    return results;
  }
}
