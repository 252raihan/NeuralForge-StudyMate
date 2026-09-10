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
    // 1. Initial Page Load
    results.steps.push({ step: '1. Page Loaded', ok: true });

    // Ensure metadata input elements exist
    const courseNameInput = page.locator('#course-name-input');
    const courseCodeInput = page.locator('#course-code-input');
    const topicInput = page.locator('#topic-input');
    const uploadBtn = page.locator('#upload-btn');
    const statusArea = page.locator('#status-area');
    const fileInput = page.locator('#pdf-file-input');

    const inputsPresent = (await courseNameInput.count() === 1) &&
      (await courseCodeInput.count() === 1) &&
      (await topicInput.count() === 1);

    results.steps.push({
      step: '2. Metadata inputs present in DOM',
      inputsPresent,
      ok: inputsPresent,
    });

    const samplePdfPath = path.resolve(process.cwd(), 'sample_study_guide.pdf');

    // 3. Test Empty Course Name validation
    await fileInput.setInputFiles(samplePdfPath);
    await uploadBtn.click();
    await page.waitForTimeout(300);
    const statusText1 = await statusArea.innerText();
    const courseNameValidated = statusText1.includes('Course Name is required');
    results.steps.push({
      step: '3. Empty Course Name validation check',
      statusText1,
      ok: courseNameValidated,
    });

    // 4. Test Empty Course Code validation
    await courseNameInput.fill('Database Management System');
    await uploadBtn.click();
    await page.waitForTimeout(300);
    const statusText2 = await statusArea.innerText();
    const courseCodeValidated = statusText2.includes('Course Code is required');
    results.steps.push({
      step: '4. Empty Course Code validation check',
      statusText2,
      ok: courseCodeValidated,
    });

    // 5. Test Empty Topic validation
    await courseCodeInput.fill('CSE 221');
    await uploadBtn.click();
    await page.waitForTimeout(300);
    const statusText3 = await statusArea.innerText();
    const topicValidated = statusText3.includes('Topic / Chapter is required');
    results.steps.push({
      step: '5. Empty Topic validation check',
      statusText3,
      ok: topicValidated,
    });

    // 6. Test Valid Submission with Sample PDF and all metadata
    await topicInput.fill('Normalization');
    await uploadBtn.click();

    // Wait for preview area
    await page.waitForSelector('#preview-area:not(.hidden)', { timeout: 12000 });

    const metadataBannerVisible = await page.locator('#metadata-preview-banner').isVisible();
    const courseBadgeText = await page.locator('#preview-course-badge').innerText();
    const codeBadgeText = await page.locator('#preview-code-badge').innerText();
    const topicBadgeText = await page.locator('#preview-topic-badge').innerText();
    const extractedText = await page.locator('#extracted-text-content').innerText();

    const uploadSuccess = metadataBannerVisible &&
      courseBadgeText.includes('Database Management System') &&
      codeBadgeText.includes('CSE 221') &&
      topicBadgeText.includes('Normalization') &&
      extractedText.includes('Normalization');

    results.steps.push({
      step: '6. Valid Upload with Metadata and Extraction',
      courseBadgeText,
      codeBadgeText,
      topicBadgeText,
      extractedSnippet: extractedText.substring(0, 80),
      ok: uploadSuccess,
    });

    // 7. Verify AI Summary button works with extracted text
    // Mock /summarize route to simulate AI summary generation in UI
    await page.route('**/summarize', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          model_used: 'gpt-4o-mini',
          truncated: false,
          original_length: extractedText.length,
          processed_length: extractedText.length,
          summary: [
            '### 1. Overview',
            'This unit covers Database Normalization for CSE 221, focusing on data structuring rules and redundancy reduction.',
            '',
            '### 2. Key Points',
            '- First normal form (1NF) removes repeating groups.',
            '- Second normal form (2NF) resolves partial dependencies.',
            '- Third normal form (3NF) eliminates transitive dependencies.',
            '',
            '### 3. Core Concepts',
            '- **Functional Dependency**: Constraint between two sets of attributes.',
            '- **Lossless Decomposition**: Preservation of relationship data upon table splitting.',
            '',
            '### 4. Practice Questions',
            '- How does BCNF differ from 3NF?',
            '- When is denormalization justified for read performance?'
          ].join('\n')
        }),
      });
    });

    const generateSummaryBtn = page.locator('#generate-summary-btn');
    await generateSummaryBtn.click();
    await page.waitForSelector('#summary-result-area:not(.hidden)', { timeout: 10000 });

    const summaryContent = await page.locator('#summary-content').innerText();
    const summaryModelBadge = await page.locator('#summary-model-badge').innerText();

    const summarySuccess = summaryContent.includes('Database Normalization for CSE 221') &&
      summaryModelBadge.includes('gpt-4o-mini');

    results.steps.push({
      step: '7. Generate AI Summary executed and rendered properly',
      summarySnippet: summaryContent.substring(0, 100),
      summarySuccess,
      ok: summarySuccess,
    });

    return results;

  } catch (err) {
    results.steps.push({ step: 'Error encountered', error: err.message, ok: false });
    return results;
  }
}
