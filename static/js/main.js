document.addEventListener('DOMContentLoaded', () => {
  // 1. Mobile navigation toggle
  initMobileMenu();

  // 2. Step 3: PDF Upload and Text Extraction handler
  initPdfUpload();
});

/**
 * Mobile navbar toggle logic & desktop "More" dropdown
 */
function initMobileMenu() {
  const button = document.getElementById('menu-btn');
  const menu = document.getElementById('mobile-menu');
  const openIcon = document.getElementById('icon-open');
  const closeIcon = document.getElementById('icon-close');

  if (button && menu) {
    const toggleMenu = (forceOpen) => {
      const willBeOpen = typeof forceOpen === 'boolean' ? forceOpen : menu.classList.contains('hidden');
      menu.classList.toggle('hidden', !willBeOpen);
      if (openIcon) openIcon.classList.toggle('hidden', willBeOpen);
      if (closeIcon) closeIcon.classList.toggle('hidden', !willBeOpen);
      button.setAttribute('aria-expanded', String(willBeOpen));
    };

    button.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleMenu();
    });

    // Close mobile menu when clicking any link inside (excluding forms/submit buttons)
    menu.querySelectorAll('a').forEach((item) => {
      item.addEventListener('click', () => {
        toggleMenu(false);
      });
    });

    // Close mobile menu when clicking outside or pressing Escape
    document.addEventListener('click', (e) => {
      if (!menu.classList.contains('hidden') && !menu.contains(e.target) && !button.contains(e.target)) {
        toggleMenu(false);
      }
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !menu.classList.contains('hidden')) {
        toggleMenu(false);
        button.focus();
      }
    });
  }

  // Desktop "More" dropdown logic
  const moreBtn = document.getElementById('nav-more-btn');
  const moreMenu = document.getElementById('nav-more-menu');
  if (moreBtn && moreMenu) {
    const toggleMore = (forceOpen) => {
      const willBeOpen = typeof forceOpen === 'boolean' ? forceOpen : moreMenu.classList.contains('hidden');
      moreMenu.classList.toggle('hidden', !willBeOpen);
      moreBtn.setAttribute('aria-expanded', String(willBeOpen));
    };

    moreBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleMore();
    });

    // Close when clicking dropdown links
    moreMenu.querySelectorAll('a').forEach((link) => {
      link.addEventListener('click', () => {
        toggleMore(false);
      });
    });

    // Close dropdown on outside click or escape
    document.addEventListener('click', (e) => {
      if (!moreMenu.classList.contains('hidden') && !moreMenu.contains(e.target) && !moreBtn.contains(e.target)) {
        toggleMore(false);
      }
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !moreMenu.classList.contains('hidden')) {
        toggleMore(false);
        moreBtn.focus();
      }
    });
  }
}

/**
 * PDF Upload & Text Extraction Studio
 */
function initPdfUpload() {
  const uploadForm = document.getElementById('pdf-upload-form');
  const fileInput = document.getElementById('pdf-file-input');
  const dropZone = document.getElementById('drop-zone');
  const selectedFileBadge = document.getElementById('selected-file-badge');
  const selectedFileName = document.getElementById('selected-file-name');
  const selectedFileSize = document.getElementById('selected-file-size');
  const uploadBtn = document.getElementById('upload-btn');
  const uploadBtnText = document.getElementById('upload-btn-text');
  const clearBtn = document.getElementById('clear-btn');
  const progressWrapper = document.getElementById('progress-wrapper');
  const statusArea = document.getElementById('status-area');
  const previewArea = document.getElementById('preview-area');
  const metaPageBadge = document.getElementById('meta-page-badge');
  const metaCharsBadge = document.getElementById('meta-chars-badge');
  const extractedTextContent = document.getElementById('extracted-text-content');
  const copyTextBtn = document.getElementById('copy-text-btn');
  const copyBtnLabel = document.getElementById('copy-btn-label');

  // Metadata Input Elements
  const courseNameInput = document.getElementById('course-name-input');
  const courseCodeInput = document.getElementById('course-code-input');
  const topicInput = document.getElementById('topic-input');

  // Metadata Preview Badges
  const metadataPreviewBanner = document.getElementById('metadata-preview-banner');
  const previewCourseBadge = document.getElementById('preview-course-badge');
  const previewCodeBadge = document.getElementById('preview-code-badge');
  const previewTopicBadge = document.getElementById('preview-topic-badge');

  // Step 4: AI Summarization Elements
  const generateSummaryBtn = document.getElementById('generate-summary-btn');
  const generateSummaryBtnText = document.getElementById('generate-summary-btn-text');
  const summaryLoadingWrapper = document.getElementById('summary-loading-wrapper');
  const summaryErrorArea = document.getElementById('summary-error-area');
  const summaryResultArea = document.getElementById('summary-result-area');
  const summaryModelBadge = document.getElementById('summary-model-badge');
  const summaryTruncationBadge = document.getElementById('summary-truncation-badge');
  const summaryContent = document.getElementById('summary-content');
  const copySummaryBtn = document.getElementById('copy-summary-btn');
  const copySummaryBtnLabel = document.getElementById('copy-summary-btn-label');

  if (!uploadForm || !fileInput || !dropZone) return;

  let currentSelectedFile = null;
  let currentExtractedText = '';
  let rawAiSummaryText = '';

  // Format bytes into human-readable size
  function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  // Validate if a file is a valid PDF
  function isValidPdfFile(file) {
    if (!file) return false;
    const isExtensionPdf = file.name.toLowerCase().endsWith('.pdf');
    const isMimePdf = file.type === 'application/pdf' || file.type === '';
    return isExtensionPdf && isMimePdf;
  }

  // Display status message (error or success). Built with safe DOM APIs so any
  // server-provided text is rendered as text, never interpreted as HTML.
  function showStatus(type, message, details = '') {
    statusArea.replaceChildren();
    statusArea.classList.remove('hidden');

    const isError = type === 'error';
    const bgColor = isError ? 'bg-rose-500/10 border-rose-500/30 text-rose-300' : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300';
    const iconPath = isError
      ? 'M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z'
      : 'M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z';

    const wrapper = document.createElement('div');
    wrapper.className = `rounded-xl border p-4 ${bgColor} flex items-start gap-3`;

    const svgNs = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(svgNs, 'svg');
    svg.setAttribute('class', 'w-5 h-5 shrink-0 mt-0.5');
    svg.setAttribute('fill', 'none');
    svg.setAttribute('stroke', 'currentColor');
    svg.setAttribute('stroke-width', '2');
    svg.setAttribute('viewBox', '0 0 24 24');
    const path = document.createElementNS(svgNs, 'path');
    path.setAttribute('stroke-linecap', 'round');
    path.setAttribute('stroke-linejoin', 'round');
    path.setAttribute('d', iconPath);
    svg.appendChild(path);

    const body = document.createElement('div');
    body.className = 'text-xs sm:text-sm leading-relaxed flex-1';
    const titleEl = document.createElement('p');
    titleEl.className = 'font-semibold';
    titleEl.textContent = message;
    body.appendChild(titleEl);
    if (details) {
      const detailEl = document.createElement('p');
      detailEl.className = 'mt-1 text-xs opacity-90 break-words';
      detailEl.textContent = details;
      body.appendChild(detailEl);
    }

    wrapper.appendChild(svg);
    wrapper.appendChild(body);
    statusArea.appendChild(wrapper);
  }

  function clearStatus() {
    statusArea.replaceChildren();
    statusArea.classList.add('hidden');
  }

  // Handle selected file
  function handleFileSelection(file) {
    clearStatus();
    previewArea.classList.add('hidden');

    if (!file) {
      resetFileSelection();
      return;
    }

    if (!isValidPdfFile(file)) {
      resetFileSelection();
      showStatus('error', 'Invalid file type. Only PDF files (.pdf) are accepted.', 'Please choose a valid PDF document to continue.');
      return;
    }

    // Check file size (16MB max)
    if (file.size > 16 * 1024 * 1024) {
      resetFileSelection();
      showStatus('error', 'File size exceeds 16 MB limit.', 'Please choose a smaller PDF file.');
      return;
    }

    currentSelectedFile = file;
    selectedFileName.textContent = file.name;
    selectedFileSize.textContent = `(${formatBytes(file.size)})`;
    selectedFileBadge.classList.remove('hidden');
    selectedFileBadge.classList.add('inline-flex');
    uploadBtn.disabled = false;
    clearBtn.classList.remove('hidden');
  }

  function resetFileSelection() {
    currentSelectedFile = null;
    currentExtractedText = '';
    rawAiSummaryText = '';
    fileInput.value = '';
    selectedFileBadge.classList.add('hidden');
    selectedFileBadge.classList.remove('inline-flex');
    selectedFileName.textContent = 'No file selected';
    selectedFileSize.textContent = '';
    uploadBtn.disabled = true;
    clearBtn.classList.add('hidden');
    if (metadataPreviewBanner) {
      metadataPreviewBanner.classList.add('hidden');
      metadataPreviewBanner.classList.remove('flex');
    }
    hideAiSummaryState();
  }

  // Click on dropzone opens native file picker
  dropZone.addEventListener('click', () => {
    fileInput.click();
  });

  // Handle file input change
  fileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileSelection(e.target.files[0]);
    }
  });

  // Drag and drop event listeners
  ['dragenter', 'dragover'].forEach((eventName) => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.add('drag-active');
    });
  });

  ['dragleave', 'dragend', 'drop'].forEach((eventName) => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove('drag-active');
    });
  });

  dropZone.addEventListener('drop', (e) => {
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const droppedFile = e.dataTransfer.files[0];
      handleFileSelection(droppedFile);
    }
  });

  // Clear button click
  clearBtn.addEventListener('click', () => {
    resetFileSelection();
    clearStatus();
    previewArea.classList.add('hidden');
    hideAiSummaryState();
  });

  // Copy extracted text
  copyTextBtn.addEventListener('click', async () => {
    const text = extractedTextContent.textContent || '';
    if (!text.trim()) return;

    try {
      await navigator.clipboard.writeText(text);
      copyBtnLabel.textContent = 'Copied!';
      setTimeout(() => {
        copyBtnLabel.textContent = 'Copy Text';
      }, 2000);
    } catch (err) {
      copyBtnLabel.textContent = 'Failed to copy';
      setTimeout(() => {
        copyBtnLabel.textContent = 'Copy Text';
      }, 2000);
    }
  });

  // Form submit: Upload & Extract
  uploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const courseName = courseNameInput ? courseNameInput.value.trim() : '';
    const courseCode = courseCodeInput ? courseCodeInput.value.trim() : '';
    const topic = topicInput ? topicInput.value.trim() : '';

    if (!courseName) {
      showStatus('error', 'Course Name is required.', 'Please enter the course name before submitting.');
      if (courseNameInput) courseNameInput.focus();
      return;
    }

    if (!courseCode) {
      showStatus('error', 'Course Code is required.', 'Please enter the course code (e.g. CSE 221) before submitting.');
      if (courseCodeInput) courseCodeInput.focus();
      return;
    }

    if (!topic) {
      showStatus('error', 'Topic / Chapter is required.', 'Please enter the topic or chapter before submitting.');
      if (topicInput) topicInput.focus();
      return;
    }

    if (!currentSelectedFile) {
      showStatus('error', 'Please select a PDF file first.', 'Choose or drop a PDF file to upload.');
      return;
    }

    if (!isValidPdfFile(currentSelectedFile)) {
      showStatus('error', 'Invalid file type. Only PDF files (.pdf) are accepted.');
      return;
    }

    // Set UI into loading state
    clearStatus();
    previewArea.classList.add('hidden');
    progressWrapper.classList.remove('hidden');
    uploadBtn.disabled = true;
    clearBtn.classList.add('hidden');
    uploadBtnText.textContent = 'Extracting...';

    const formData = new FormData();
    formData.append('course_name', courseName);
    formData.append('course_code', courseCode);
    formData.append('topic', topic);
    formData.append('file', currentSelectedFile, currentSelectedFile.name);
    const csrfInput = uploadForm.querySelector('input[name="csrf_token"]');
    if (csrfInput) formData.append('csrf_token', csrfInput.value);

    try {
      const response = await fetch('/upload', {
        method: 'POST',
        body: formData,
      });

      const result = await response.json().catch(() => null);

      if (!response.ok || !result || !result.success) {
        const errorMsg = result && result.error ? result.error : `Server responded with status ${response.status}`;
        showStatus('error', 'Failed to extract text from PDF.', errorMsg);
        return;
      }

      // Success
      const charCount = result.character_count ?? result.char_count ?? 0;
      showStatus('success', `PDF extracted successfully!`, `Saved to uploads/${result.filename} • ${result.page_count} page(s) • ${charCount.toLocaleString()} characters`);

      // Populate metadata preview badges if available
      if (metadataPreviewBanner && (result.course_name || result.course_code || result.topic)) {
        if (previewCourseBadge) previewCourseBadge.textContent = result.course_name || courseName;
        if (previewCodeBadge) previewCodeBadge.textContent = result.course_code || courseCode;
        if (previewTopicBadge) previewTopicBadge.textContent = result.topic || topic;
        metadataPreviewBanner.classList.remove('hidden');
        metadataPreviewBanner.classList.add('flex');
      }

      // Populate preview area
      metaPageBadge.textContent = `${result.page_count} page${result.page_count === 1 ? '' : 's'}`;
      metaCharsBadge.textContent = `${charCount.toLocaleString()} characters`;

      hideAiSummaryState();

      if (result.text && result.text.trim()) {
        currentExtractedText = result.text.trim();
        extractedTextContent.textContent = result.text;
        if (generateSummaryBtn) {
          generateSummaryBtn.disabled = false;
          generateSummaryBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        }
      } else {
        currentExtractedText = '';
        extractedTextContent.textContent = '[This PDF contains no extractable plain text. It may be scanned or composed entirely of images.]';
        if (generateSummaryBtn) {
          generateSummaryBtn.disabled = true;
          generateSummaryBtn.classList.add('opacity-50', 'cursor-not-allowed');
        }
      }

      previewArea.classList.remove('hidden');
      previewArea.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    } catch (error) {
      showStatus('error', 'Network or server error while uploading.', error.message || 'Please check your Flask server.');
    } finally {
      // Revert loading state
      progressWrapper.classList.add('hidden');
      uploadBtn.disabled = false;
      clearBtn.classList.remove('hidden');
      uploadBtnText.textContent = 'Extract Text';
    }
  });

  // ==========================================
  // Step 4: AI Summarization Logic
  // ==========================================

  function hideAiSummaryState() {
    if (summaryLoadingWrapper) summaryLoadingWrapper.classList.add('hidden');
    if (summaryErrorArea) {
      summaryErrorArea.classList.add('hidden');
      summaryErrorArea.replaceChildren();
    }
    if (summaryResultArea) summaryResultArea.classList.add('hidden');
  }

  function showSummaryError(title, message) {
    if (!summaryErrorArea) return;
    summaryErrorArea.classList.remove('hidden');
    summaryErrorArea.replaceChildren();

    const wrapper = document.createElement('div');
    wrapper.className = 'rounded-xl border-rose-500/30 bg-rose-500/10 p-4 text-rose-300 flex items-start gap-3';

    const svgNs = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(svgNs, 'svg');
    svg.setAttribute('class', 'w-5 h-5 shrink-0 mt-0.5');
    svg.setAttribute('fill', 'none');
    svg.setAttribute('stroke', 'currentColor');
    svg.setAttribute('stroke-width', '2');
    svg.setAttribute('viewBox', '0 0 24 24');
    const path = document.createElementNS(svgNs, 'path');
    path.setAttribute('stroke-linecap', 'round');
    path.setAttribute('stroke-linejoin', 'round');
    path.setAttribute('d', 'M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z');
    svg.appendChild(path);

    const body = document.createElement('div');
    body.className = 'text-xs sm:text-sm leading-relaxed flex-1 min-w-0';
    const titleEl = document.createElement('p');
    titleEl.className = 'font-bold text-rose-200';
    titleEl.textContent = title;
    const messageEl = document.createElement('p');
    messageEl.className = 'mt-1 text-xs opacity-90 break-words';
    messageEl.textContent = message;
    body.appendChild(titleEl);
    body.appendChild(messageEl);

    wrapper.appendChild(svg);
    wrapper.appendChild(body);
    summaryErrorArea.appendChild(wrapper);
    summaryErrorArea.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  /* Legacy inline error markup removed - now built with safe DOM APIs. */

  /**
   * Simple, safe Markdown to HTML renderer for study summaries.
   * Converts headings, bullet lists, bold text, and code spans without external dependencies.
   */
  function renderMarkdownToHtml(markdown) {
    if (!markdown) return '';

    // Sanitize basic tags
    let html = markdown
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');

    // Headings
    html = html.replace(/^### (.*$)/gim, '<h4 class="text-sm font-bold text-brand-300 mt-5 mb-2 flex items-center gap-2"><span class="w-1.5 h-1.5 rounded-full bg-brand-400"></span>$1</h4>');
    html = html.replace(/^## (.*$)/gim, '<h3 class="text-base font-bold text-white mt-6 mb-3 border-b border-white/10 pb-1">$1</h3>');
    html = html.replace(/^# (.*$)/gim, '<h2 class="text-lg font-extrabold text-white mt-6 mb-3">$1</h2>');

    // Bold text
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold text-white">$1</strong>');

    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code class="bg-slate-800 text-brand-200 px-1.5 py-0.5 rounded text-xs font-mono">$1</code>');

    // Split paragraphs and list items
    const lines = html.split('\n');
    let inList = false;
    let formattedLines = [];

    for (let line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
        if (!inList) {
          formattedLines.push('<ul class="space-y-1.5 my-2 pl-2">');
          inList = true;
        }
        const bulletText = trimmed.substring(2);
        formattedLines.push(`<li class="flex items-start gap-2 text-slate-300 text-xs sm:text-sm leading-relaxed"><span class="text-brand-400 font-bold leading-none mt-1.5">•</span><span>${bulletText}</span></li>`);
      } else {
        if (inList) {
          formattedLines.push('</ul>');
          inList = false;
        }
        if (trimmed && !trimmed.startsWith('<h')) {
          formattedLines.push(`<p class="my-2 text-slate-300 text-xs sm:text-sm leading-relaxed">${trimmed}</p>`);
        } else if (trimmed) {
          formattedLines.push(trimmed);
        }
      }
    }

    if (inList) {
      formattedLines.push('</ul>');
    }

    return formattedLines.join('\n');
  }

  // Handle "Generate AI Summary" button click
  if (generateSummaryBtn) {
    generateSummaryBtn.addEventListener('click', async () => {
      const textToSummarize = currentExtractedText || extractedTextContent.textContent.trim();

      if (!textToSummarize) {
        showStatus('error', 'No text found to summarize.', 'Please extract text from a valid PDF first.');
        return;
      }

      // Hide previous results and errors
      if (summaryErrorArea) {
        summaryErrorArea.classList.add('hidden');
        summaryErrorArea.replaceChildren();
      }
      if (summaryResultArea) summaryResultArea.classList.add('hidden');

      // Loading state
      if (summaryLoadingWrapper) summaryLoadingWrapper.classList.remove('hidden');
      generateSummaryBtn.disabled = true;
      generateSummaryBtn.classList.add('opacity-75', 'cursor-wait');
      generateSummaryBtnText.textContent = 'Generating...';

      try {
        const csrfInput = uploadForm ? uploadForm.querySelector('input[name="csrf_token"]') : null;
        const csrfToken = csrfInput ? csrfInput.value : '';
        const response = await fetch('/summarize', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrfToken,
          },
          body: JSON.stringify({
            text: textToSummarize,
          }),
        });

        const result = await response.json().catch(() => null);

        if (!response.ok || !result || !result.success) {
          const errMessage = result && result.error ? result.error : `Server responded with HTTP ${response.status}`;
          showSummaryError('Failed to generate summary', errMessage);
          return;
        }

        // Display results
        rawAiSummaryText = result.summary;
        if (summaryModelBadge) {
          summaryModelBadge.textContent = result.model_used || 'OpenAI';
        }

        if (summaryTruncationBadge) {
          if (result.truncated) {
            summaryTruncationBadge.classList.remove('hidden');
            summaryTruncationBadge.textContent = `Safe limit applied: First ${result.processed_length.toLocaleString()} chars`;
          } else {
            summaryTruncationBadge.classList.add('hidden');
          }
        }

        if (summaryContent) {
          summaryContent.innerHTML = renderMarkdownToHtml(result.summary);
        }

        if (summaryResultArea) {
          summaryResultArea.classList.remove('hidden');
          summaryResultArea.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }

      } catch (err) {
        showSummaryError('Network or server error', err.message || 'Could not reach the summarization endpoint.');
      } finally {
        // Restore button state
        if (summaryLoadingWrapper) summaryLoadingWrapper.classList.add('hidden');
        generateSummaryBtn.disabled = false;
        generateSummaryBtn.classList.remove('opacity-75', 'cursor-wait');
        generateSummaryBtnText.textContent = 'Generate AI Summary';
      }
    });
  }

  // Copy Summary button
  if (copySummaryBtn) {
    copySummaryBtn.addEventListener('click', async () => {
      const summaryToCopy = rawAiSummaryText || (summaryContent ? summaryContent.innerText : '');
      if (!summaryToCopy.trim()) return;

      try {
        await navigator.clipboard.writeText(summaryToCopy);
        copySummaryBtnLabel.textContent = 'Copied!';
        setTimeout(() => {
          copySummaryBtnLabel.textContent = 'Copy Summary';
        }, 2000);
      } catch (err) {
        copySummaryBtnLabel.textContent = 'Failed to copy';
        setTimeout(() => {
          copySummaryBtnLabel.textContent = 'Copy Summary';
        }, 2000);
      }
    });
  }

}

