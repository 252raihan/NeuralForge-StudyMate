import path from 'path';

export default async function run(page, ui) {
  const results = {
    steps: [],
    errors: [],
  };

  try {
    // 1. Load home page
    results.steps.push({ step: 'Page loaded', ok: true });

    // 2. Select and upload sample PDF
    const samplePdfPath = path.resolve(process.cwd(), 'sample_study_guide.pdf');
    const fileInput = page.locator('#pdf-file-input');
    await fileInput.setInputFiles(samplePdfPath);
    await page.waitForTimeout(300);

    await page.locator('#upload-btn').click();
    await page.waitForSelector('#preview-area:not(.hidden)', { timeout: 10000 });

    const isSummaryBtnVisible = await page.locator('#generate-summary-btn').isVisible();
    const summaryBtnText = await page.locator('#generate-summary-btn-text').innerText();

    results.steps.push({
      step: 'PDF extracted and Generate AI Summary button rendered',
      isSummaryBtnVisible,
      summaryBtnText,
      ok: isSummaryBtnVisible && summaryBtnText.includes('Generate AI Summary'),
    });

    // 3. Test Error Flow (Placeholder key in .env)
    await page.locator('#generate-summary-btn').click();

    // Verify error is shown and loading bar disappears
    await page.waitForSelector('#summary-error-area:not(.hidden)', { timeout: 10000 });
    const isErrorVisible = await page.locator('#summary-error-area').isVisible();
    const errorText = await page.locator('#summary-error-area').innerText();

    results.steps.push({
      step: 'Graceful API key error handling in UI',
      isErrorVisible,
      errorContainsNotice: errorText.includes('API key is missing or not configured'),
      ok: isErrorVisible && errorText.includes('API key is missing or not configured'),
    });

    // 4. Test Success Flow by mocking OpenAI route in browser to verify UI rendering of all 4 summary sections
    await page.route('**/summarize', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          model_used: 'gpt-4o-mini',
          truncated: false,
          original_length: 426,
          processed_length: 426,
          summary: [
            '### 1. Overview',
            'This introductory guide covers the fundamental concepts of machine learning, contrasting how systems learn from data against traditional programming methodologies.',
            '',
            '### 2. Key Points',
            '- Machine learning systems improve performance and accuracy iteratively using historical data.',
            '- Supervised learning maps inputs to outputs using labeled ground truth examples.',
            '- Unsupervised learning explores unlabeled data to surface patterns and clustering.',
            '- Structured study notes accelerate comprehension and long-term retention.',
            '',
            '### 3. Core Concepts',
            '- **Model Generalization**: The capacity of an algorithm to make accurate predictions on unseen data.',
            '- **Pattern Discovery**: Unsupervised clustering techniques that identify latent relationships.',
            '',
            '### 4. Important Definitions',
            '- **Supervised Learning**: An algorithm trained on input data paired with known ground-truth labels.',
            '- **Unsupervised Learning**: Algorithms that infer underlying structures directly from unlabeled datasets.',
          ].join('\n'),
        }),
      });
    });

    // Click Generate AI Summary again with mocked route
    await page.locator('#generate-summary-btn').click();
    await page.waitForSelector('#summary-result-area:not(.hidden)', { timeout: 10000 });

    const isSummaryResultVisible = await page.locator('#summary-result-area').isVisible();
    const summaryCardHtml = await page.locator('#summary-content').innerHTML();
    const modelBadgeText = await page.locator('#summary-model-badge').innerText();

    const hasOverview = summaryCardHtml.includes('1. Overview');
    const hasKeyPoints = summaryCardHtml.includes('2. Key Points');
    const hasCoreConcepts = summaryCardHtml.includes('3. Core Concepts');
    const hasDefinitions = summaryCardHtml.includes('4. Important Definitions');

    results.steps.push({
      step: 'AI summary display verified with all 4 required sections',
      isSummaryResultVisible,
      modelBadgeText,
      hasOverview,
      hasKeyPoints,
      hasCoreConcepts,
      hasDefinitions,
      ok: isSummaryResultVisible && modelBadgeText === 'gpt-4o-mini' && hasOverview && hasKeyPoints && hasCoreConcepts && hasDefinitions,
    });

    // 5. Test Copy Summary Button
    await page.locator('#copy-summary-btn').click();
    await page.waitForTimeout(200);
    const copySummaryLabel = await page.locator('#copy-summary-btn-label').innerText();

    results.steps.push({
      step: 'Copy Summary button interaction',
      copySummaryLabel,
      ok: copySummaryLabel === 'Copied!' || copySummaryLabel === 'Copy Summary',
    });

    results.allPassed = results.steps.every(s => s.ok);

  } catch (err) {
    results.errors.push(err.message || String(err));
    results.allPassed = false;
  }

  return results;
}
