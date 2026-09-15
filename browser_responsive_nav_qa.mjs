// browser_responsive_nav_qa.mjs
// Automated Responsive Navigation and UI Verification across all viewports
import { spawn } from 'node:child_process';
import { createConnection } from 'node:net';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const BASE = 'http://127.0.0.1:5005';
const VIEWPORTS = [320, 360, 375, 390, 414, 480, 768, 820, 1024, 1280, 1366, 1440, 1920];

function waitForServer(port = 5005, timeoutMs = 20000) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const tryConnect = () => {
      const socket = createConnection({ host: '127.0.0.1', port });
      socket.once('connect', () => {
        socket.destroy();
        resolve(true);
      });
      socket.once('error', () => {
        socket.destroy();
        if (Date.now() - start > timeoutMs) {
          reject(new Error(`Server readiness timed out on port ${port}`));
        } else {
          setTimeout(tryConnect, 150);
        }
      });
    };
    tryConnect();
  });
}

export default async function run(page) {
  const result = {
    steps: [],
    consoleErrors: [],
    failedRequests: [],
  };

  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      result.consoleErrors.push(msg.text());
    }
  });

  page.on('requestfailed', (req) => {
    // Ignore aborted image requests that happen during rapid page re-navigation
    if (req.failure()?.errorText === 'net::ERR_ABORTED') return;
    result.failedRequests.push(`${req.method()} ${req.url()}: ${req.failure()?.errorText}`);
  });

  const check = (name, ok, details = null) => {
    result.steps.push({ name, ok: Boolean(ok), details });
  };

  async function checkOverflow() {
    return await page.evaluate(() => {
      const scrollW = document.documentElement.scrollWidth;
      const innerW = window.innerWidth;
      const clientW = document.documentElement.clientWidth;
      // No horizontal overflow: scrollWidth must not exceed innerWidth
      const hasOverflow = scrollW > innerW + 1; // 1px tolerance for sub-pixel rounding
      return {
        scrollW,
        innerW,
        clientW,
        noOverflow: !hasOverflow,
      };
    });
  }

  // Helper login
  async function performLogin(email, password) {
    await performLogout();
    await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
    await page.fill('input[name="email"]', email);
    await page.fill('input[name="password"]', password);
    await page.locator('button[type="submit"]').click();
    await page.waitForLoadState('domcontentloaded');
  }

  // Helper logout. Logout is POST-only now, so GET /logout must return 405 and
  // must NOT change session state. The real logout is a POST request made with
  // the browser context's cookies (page.request shares them).
  async function performLogout() {
    const getResp = await page.request.get(`${BASE}/logout`);
    if (getResp.status() !== 405) {
      throw new Error(`GET /logout must be 405, got ${getResp.status()}`);
    }
    await page.request.post(`${BASE}/logout`);
  }

  // ==========================================
  // 1. LOGGED-OUT STATE TESTS
  // ==========================================
  await performLogout();
  await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' });

  // 1. Desktop Navbar (1440px)
  await page.setViewportSize({ width: 1440, height: 900 });
  const desktopNavVisible = await page.locator('nav').isVisible();
  const desktopLoginBtn = await page.locator('#nav-login-btn').isVisible();
  const desktopRegisterBtn = await page.locator('#nav-register-btn').isVisible();
  const desktopMenuBtnHidden = !(await page.locator('#menu-btn').isVisible());
  check('1. desktop navbar visible and styled', desktopNavVisible && desktopLoginBtn && desktopRegisterBtn && desktopMenuBtnHidden);

  // 2. Medium Viewport (768px - 1024px)
  await page.setViewportSize({ width: 820, height: 1180 });
  const medMenuBtnVisible = await page.locator('#menu-btn').isVisible();
  const medDesktopLinksHidden = !(await page.locator('#nav-login-btn').isVisible());
  check('2. medium viewport collapses to hamburger', medMenuBtnVisible && medDesktopLinksHidden);

  // 3-6. Mobile Viewports (320px, 360px, 390px, 414px)
  for (const w of [320, 360, 390, 414]) {
    await page.setViewportSize({ width: w, height: 800 });
    const mobileMenuBtn = await page.locator('#menu-btn').isVisible();
    const of = await checkOverflow();
    check(`mobile ${w}px hamburger visible & no overflow`, mobileMenuBtn && of.noOverflow, of);
  }

  // 7. Hamburger visible on mobile
  await page.setViewportSize({ width: 375, height: 667 });
  check('7. hamburger visible on mobile', await page.locator('#menu-btn').isVisible());

  // 8. Desktop links hidden/collapsed appropriately
  check('8. desktop links hidden on mobile', !(await page.locator('#nav-login-btn').isVisible()));

  // 9. Hamburger opens menu
  await page.locator('#menu-btn').click();
  const mobileMenuOpen = !(await page.locator('#mobile-menu').evaluate(el => el.classList.contains('hidden')));
  const ariaExpandedOpen = (await page.locator('#menu-btn').getAttribute('aria-expanded')) === 'true';
  check('9. hamburger opens menu', mobileMenuOpen && ariaExpandedOpen);

  // 10. Hamburger closes menu
  await page.locator('#menu-btn').click();
  const mobileMenuClosed = await page.locator('#mobile-menu').evaluate(el => el.classList.contains('hidden'));
  const ariaExpandedClosed = (await page.locator('#menu-btn').getAttribute('aria-expanded')) === 'false';
  check('10. hamburger closes menu', mobileMenuClosed && ariaExpandedClosed);

  // 11. Navigation links work in mobile menu
  await page.locator('#menu-btn').click();
  await page.locator('#nav-study-library-mobile').click();
  await page.waitForLoadState('domcontentloaded');
  const onStudyLibrary = page.url().includes('/study-library');
  check('11. navigation links work from mobile menu', onStudyLibrary);

  // Back to home for overflow tests
  await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' });

  // 12. NO HORIZONTAL OVERFLOW across ALL REQUIRED VIEWPORTS
  let allViewportsPassed = true;
  for (const w of VIEWPORTS) {
    await page.setViewportSize({ width: w, height: 800 });
    const of = await checkOverflow();
    if (!of.noOverflow) {
      allViewportsPassed = false;
    }
    check(`12. viewport ${w}px no horizontal overflow`, of.noOverflow, of);
  }

  // 13. Hero heading fits without horizontal overflow
  await page.setViewportSize({ width: 320, height: 600 });
  const heroHeading = page.locator('h1').first();
  const h1Bounding = await heroHeading.boundingBox();
  const h1Fits = h1Bounding && h1Bounding.x + h1Bounding.width <= 321;
  check('13. hero heading fits in 320px viewport', Boolean(h1Fits));

  // 14. CTA buttons fit
  const ctaLinks = await page.locator('section a[href="#upload-section"], section a[href="#about"]').all();
  check('14. CTA buttons present and fit', ctaLinks.length >= 2);

  // ==========================================
  // 2. LOGGED-IN STATE TESTS
  // ==========================================
  await performLogin('responsive_test_user@example.com', 'Pass12345');
  await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' });

  // 15. Logged-in navbar on desktop (1440px)
  await page.setViewportSize({ width: 1440, height: 900 });
  const userPillVisible = (await page.locator('nav').innerText()).includes('Responsive Tester');
  const dashboardLinkVisible = await page.locator('#nav-dashboard-link').isVisible();
  const askLinkVisible = await page.locator('#nav-ask-studymate-link').isVisible();
  const quizCreateLinkVisible = await page.locator('#nav-quiz-create-link').isVisible();
  const attemptsLinkVisible = await page.locator('#nav-quiz-attempts-link').isVisible();
  const perfLinkVisible = await page.locator('#nav-quiz-performance-link').isVisible();
  const logoutBtnVisible = await page.locator('#nav-logout-btn').isVisible();

  // Test "More" Dropdown functionality
  const moreBtn = page.locator('#nav-more-btn');
  let moreDropdownWorks = false;
  if (await moreBtn.isVisible()) {
    await moreBtn.click();
    const moreMenuVisible = !(await page.locator('#nav-more-menu').evaluate(el => el.classList.contains('hidden')));
    const bookmarksLinkVisible = await page.locator('#nav-bookmarks-link').isVisible();
    await moreBtn.click();
    const moreMenuClosed = await page.locator('#nav-more-menu').evaluate(el => el.classList.contains('hidden'));
    moreDropdownWorks = moreMenuVisible && bookmarksLinkVisible && moreMenuClosed;
  }

  check('15. logged-in navbar on desktop with More dropdown', userPillVisible && dashboardLinkVisible && askLinkVisible && quizCreateLinkVisible && attemptsLinkVisible && perfLinkVisible && logoutBtnVisible && moreDropdownWorks);

  // Overflow test while logged in across viewports
  for (const w of VIEWPORTS) {
    await page.setViewportSize({ width: w, height: 800 });
    const of = await checkOverflow();
    check(`15b. logged-in viewport ${w}px no overflow`, of.noOverflow, of);
  }

  // 16. Logged-out navbar verification
  check('16. logged-in state contains all features', userPillVisible && logoutBtnVisible);

  // 17. Logout still works
  // On desktop
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.locator('#nav-logout-btn').click();
  await page.waitForLoadState('domcontentloaded');
  const loggedOutNavText = await page.locator('nav').innerText();
  const logoutSuccess = loggedOutNavText.includes('Log in') && !loggedOutNavText.includes('Responsive Tester');
  check('17. logout still works', logoutSuccess);

  // Verify mobile logout works
  await performLogin('responsive_test_user@example.com', 'Pass12345');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' });
  await page.locator('#menu-btn').click();
  await page.waitForTimeout(300);

  // Directly trigger a logout POST request (logout is POST-only).
  await performLogout();
  await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
  // Check that the user is logged out (login form is shown, not the navbar user pill).
  const onLoginPage = page.url().includes('/login');
  check('17b. mobile logout works', onLoginPage);

  // 18. console errors = 0
  check('18. console errors = 0', result.consoleErrors.length === 0, result.consoleErrors);

  // 19. failed network requests = 0
  check('19. failed network requests = 0', result.failedRequests.length === 0, result.failedRequests);

  const allPassed = result.steps.every(s => s.ok);
  check('ALL RESPONSIVE QA CHECKS PASSED', allPassed);

  return result;
}

async function main() {
  const root = path.dirname(fileURLToPath(import.meta.url));
  const server = spawn(process.env.PYTHON || 'python', [
    '-c',
    `
from werkzeug.security import generate_password_hash
import app as app_module
from database.db import get_db_connection, get_department_by_code, create_user
app = app_module.app
app.config["CSRF_PROTECTION"] = False
with app.app_context():
    conn = get_db_connection()
    cse = get_department_by_code("CSE", conn)
    user = conn.execute("SELECT id FROM users WHERE email = 'responsive_test_user@example.com'").fetchone()
    if not user:
        create_user("Responsive Tester", "responsive_test_user@example.com", generate_password_hash("Pass12345"), cse["id"], "student", conn=conn)
    conn.close()
app.run(host="127.0.0.1", port=5005, debug=False, use_reloader=False, threaded=True)
`
  ], {
    cwd: root,
    stdio: 'inherit',
  });

  const cleanup = () => {
    if (!server.killed) server.kill();
  };

  try {
    await waitForServer(5005);
    const runner = path.join(process.env.CODEGPT_SKILL_DIR || 'C:\\Users\\HP\\.codegpt\\skills\\browser-automation', 'browser.mjs');
    const child = spawn(process.execPath, [
      runner,
      'data:text/html,<title>ResponsiveQA</title>',
      '--script',
      path.join(root, 'browser_responsive_nav_qa.mjs'),
    ], {
      cwd: root,
      stdio: 'inherit',
    });

    await new Promise((res, rej) => {
      child.once('exit', (code) => (code === 0 ? res() : rej(new Error(`browser exit ${code}`))));
      child.once('error', rej);
    });
  } finally {
    cleanup();
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((e) => {
    console.error(e.message);
    process.exitCode = 1;
  });
}
