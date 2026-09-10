import path from 'path';

export default async function run(page, ui) {
  const samplePdfPath = path.resolve(process.cwd(), 'sample_study_guide.pdf');
  const fileInput = page.locator('#pdf-file-input');
  await fileInput.setInputFiles(samplePdfPath);
  await page.waitForTimeout(300);

  // Click Extract Text
  await page.locator('#upload-btn').click();

  // Wait for preview area
  await page.waitForSelector('#preview-area:not(.hidden)', { timeout: 10000 });
  await page.waitForTimeout(500);

  return { success: true };
}
