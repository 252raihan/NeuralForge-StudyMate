import path from 'path';

export default async function run(page, ui) {
  const results = {
    steps: [],
    errors: [],
  };

  try {
    // 1. Initial state checks
    const initialSnapshot = await ui.snapshot();
    results.steps.push({ step: 'Initial page load', ok: true });

    // 2. Select the sample PDF file
    const samplePdfPath = path.resolve(process.cwd(), 'sample_study_guide.pdf');
    const fileInput = page.locator('#pdf-file-input');
    await fileInput.setInputFiles(samplePdfPath);

    // Wait a brief moment for change event to fire
    await page.waitForTimeout(300);

    // Verify selected file badge is visible and button is enabled
    const badgeText = await page.locator('#selected-file-name').innerText();
    const isUploadEnabled = await page.locator('#upload-btn').isEnabled();
    results.steps.push({
      step: 'File selected',
      badgeText,
      uploadButtonEnabled: isUploadEnabled,
      ok: badgeText === 'sample_study_guide.pdf' && isUploadEnabled,
    });

    // 3. Click "Extract Text" button
    await page.locator('#upload-btn').click();

    // 4. Wait for preview area or success message
    await page.waitForSelector('#preview-area:not(.hidden)', { timeout: 10000 });

    const statusText = await page.locator('#status-area').innerText();
    const extractedContent = await page.locator('#extracted-text-content').innerText();
    const pageBadge = await page.locator('#meta-page-badge').innerText();
    const charsBadge = await page.locator('#meta-chars-badge').innerText();

    results.steps.push({
      step: 'Extraction completed',
      statusMessage: statusText,
      pageCountBadge: pageBadge,
      charsBadge: charsBadge,
      extractedContentSnippet: extractedContent.slice(0, 150),
      ok: extractedContent.includes('NeuralForge StudyMate - Chapter 1') && pageBadge.includes('1 page'),
    });

    // 5. Test Copy button
    await page.locator('#copy-text-btn').click();
    await page.waitForTimeout(200);
    const copyLabel = await page.locator('#copy-btn-label').innerText();
    results.steps.push({
      step: 'Copy to clipboard clicked',
      buttonLabelAfterClick: copyLabel,
      ok: copyLabel === 'Copied!' || copyLabel === 'Copy Text',
    });

    // 6. Test invalid file rejection flow in UI
    const fakeTxtPath = path.resolve(process.cwd(), 'test_invalid.txt');
    await fileInput.setInputFiles(fakeTxtPath);
    await page.waitForTimeout(300);
    const errorStatusText = await page.locator('#status-area').innerText();
    const isUploadDisabledAfterInvalid = await page.locator('#upload-btn').isDisabled();

    results.steps.push({
      step: 'Invalid non-PDF file handling',
      errorMessage: errorStatusText,
      uploadDisabled: isUploadDisabledAfterInvalid,
      ok: errorStatusText.includes('Invalid file type') && isUploadDisabledAfterInvalid,
    });

    results.allPassed = results.steps.every(s => s.ok);
  } catch (err) {
    results.errors.push(err.message || String(err));
    results.allPassed = false;
  }

  return results;
}
