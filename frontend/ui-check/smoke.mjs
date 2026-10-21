// Browser check of the local stack (see run.sh): every page renders, the sales form works, every
// field of every visible form is on the screen, and nothing logs an error. Writes are blocked.
// Env: BASE, TOKEN (an admin's JWT), PHONE (a client's phone), OUT (screenshot folder), TAG
import { chromium } from 'playwright';

const { BASE, TOKEN, PHONE, OUT, TAG = 'run' } = process.env;
const problems = [];
const log = (...args) => console.log(...args);

async function newPage(browser, viewport) {
  const context = await browser.newContext({ viewport, locale: 'ar-AE', timezoneId: 'Asia/Dubai' });
  // Only the app's own page: the mail preview is a sandboxed frame without storage
  await context.addInitScript((token) => { if (window === window.top) localStorage.setItem('portal_token', token); }, TOKEN);
  const page = await context.newPage();
  page.on('console', (msg) => { if (msg.type() === 'error') problems.push(`[console] ${msg.text()}`); });
  page.on('pageerror', (err) => problems.push(`[pageerror] ${err.message}`));
  // Block anything that would change data
  await page.route('**/api/**', (route) => {
    const method = route.request().method();
    if (method !== 'GET') { problems.push(`[blocked write] ${method} ${route.request().url()}`); return route.abort(); }
    return route.continue();
  });
  return page;
}

async function shot(page, name, full = true) {
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${OUT}/${TAG}-${name}.png`, fullPage: full });
}

async function expectText(page, text, what) {
  try {
    // A visible one: on a phone the sidebar (with every page's name) is hidden
    await page.getByText(text, { exact: false }).locator('visible=true').first().waitFor({ timeout: 15000 });
  } catch {
    problems.push(`[missing] ${what}: «${text}»`);
  }
}

async function salesForm(page, prefix) {
  await page.goto(`${BASE}/sales/new_request`);
  await expectText(page, 'طلب بيع لعميل جديد', 'forms catalog');
  await shot(page, `${prefix}-catalog`);
  await page.getByText('طلب بيع لعميل جديد').first().click();
  await expectText(page, 'بيانات العميل', 'new sale form');
  await page.waitForTimeout(1500);
  await shot(page, `${prefix}-form-empty`);

  // Client lookup by phone
  if (PHONE) {
    await page.locator('#phone').fill(PHONE);
    await page.locator('#phone').blur();
    await expectText(page, 'عميل مسجل', 'client lookup result');
  }
  // Category picks the area and emirate
  const category = page.locator('#category');
  if (await category.count()) {
    const options = await category.locator('option').all();
    const withArea = options.length > 5 ? 5 : options.length - 1;
    if (withArea > 0) await category.selectOption({ index: withArea });
  }
  await page.evaluate(() => window.scrollTo(0, 0));
  await shot(page, `${prefix}-form-top`, false);
  // Order lines: search, keyboard pick, the package's own fields, the stepper
  const search = page.locator('#order_lines');
  await search.click();
  await search.fill('نبع');
  await page.waitForTimeout(300);
  await search.press('ArrowDown');
  await search.press('Enter');
  await expectText(page, 'الكمية (عدد الباقات)', 'package details after keyboard pick');
  const plus = page.getByRole('button', { name: /زيادة الكمية/ }).first();
  if (await plus.count()) await plus.click();
  await page.getByRole('button', { name: 'فتح كل الأقسام' }).click().catch(() => {});
  await page.locator('#paid_amount').fill('100');
  await page.waitForTimeout(300);
  const subtotal = await page.locator('#subtotal_amount').inputValue().catch(() => '');
  // It reads «8,600 درهم»: the amount with its unit
  const amount = Number(String(subtotal).replace(/[^\d.]/g, ''));
  if (!(amount > 0) || !subtotal.includes('درهم')) problems.push(`[value] subtotal after picking a package: «${subtotal}»`);
  log(`${prefix} subtotal after package x2:`, subtotal);
  await shot(page, `${prefix}-form-filled`);
  await page.locator('#order_lines').scrollIntoViewIfNeeded();
  await shot(page, `${prefix}-form-view`, false);
  // Submitting with missing fields shows the errors (the API call is blocked anyway)
  await page.getByRole('button', { name: 'إرسال للمراجعة' }).click();
  await expectText(page, 'حقل يحتاج إلى تصحيح', 'error summary on submit');
  await shot(page, `${prefix}-form-errors`);
  await page.getByRole('button', { name: 'رجوع' }).first().click();
  await expectText(page, 'لديك تغييرات غير محفوظة', 'unsaved changes dialog on back');
  await shot(page, `${prefix}-form-leave`, false);
  await page.getByRole('button', { name: 'البقاء في النموذج' }).click();
}

// Every field each visible form defines is on the screen
async function everyField(page, prefix) {
  const types = await page.evaluate(async (token) => (await fetch('/api/form-types', { headers: { Authorization: `Bearer ${token}` } })).json(), TOKEN);
  for (const type of types.filter((t) => !t.hidden)) {
    await page.goto(`${BASE}/sales/new_request`);
    await page.getByText(type.label).first().click();
    await page.getByRole('button', { name: 'فتح كل الأقسام' }).click();
    await page.waitForTimeout(500);
    const expected = type.sections.flatMap((section) => section.fields.map((f) => f.name));
    const shown = await page.$$eval('[id^="field-"]', (els) => els.filter((el) => el.offsetParent !== null).map((el) => el.id.slice(6)));
    const missing = expected.filter((name) => !shown.includes(name));
    log(`${prefix} ${type.key}: ${shown.length} of ${expected.length} fields shown`);
    if (missing.length) problems.push(`[missing fields] ${type.key}: ${missing.join(', ')}`);
    await shot(page, `${prefix}-form-${type.key}`);
    // Leave without saving (the form asks first, since nothing was typed it should not)
    await page.getByRole('button', { name: 'رجوع' }).first().click();
  }
}

async function pages(page, prefix) {
  const visits = [
    ['/sales/my_requests', 'طلباتي', 'my-requests'],
    ['/sales/review', 'مراجعة الطلبات', 'review'],
    ['/admin/users', 'المستخدمون', 'users'],
    ['/admin/permissions', 'الأدوار والصلاحيات', 'roles'],
    ['/admin/audit', 'سجل النشاط', 'audit'],
    ['/admin/catalog', 'المنتجات والباقات', 'products'],
    ['/admin/mail', 'اختبار البريد', 'mail'],
    ['/account', 'حسابي', 'account'],
  ];
  for (const [path, title, name] of visits) {
    await page.goto(`${BASE}${path}`);
    await expectText(page, title, path);
    await page.waitForTimeout(1200);
    await shot(page, `${prefix}-${name}`);
  }
  // A request opened from the review list
  await page.goto(`${BASE}/sales/review?tab=all`);
  const open = page.getByRole('button', { name: /عرض الطلب|مراجعة الطلب/ }).first();
  await open.waitFor({ timeout: 15000 }).catch(() => {});
  if (await open.count().catch(() => 0)) {
    await open.click();
    await expectText(page, 'سجل الطلب', 'request view history');
    await page.waitForTimeout(800);
    await shot(page, `${prefix}-request-view`);
  }
  // A product drawer in the catalog
  await page.goto(`${BASE}/admin/catalog`);
  await expectText(page, 'المنتجات والباقات', 'catalog again');
  await page.getByRole('button', { name: 'تعديل' }).first().click().catch(() => problems.push('[click] product edit'));
  await page.waitForTimeout(500);
  await shot(page, `${prefix}-product-drawer`);
}

const browser = await chromium.launch();
try {
  for (const [prefix, viewport] of [['desktop', { width: 1440, height: 900 }], ['phone', { width: 390, height: 844 }]]) {
    const context = await browser.newContext({ viewport, locale: 'ar-AE' });
    const page = await context.newPage();
    page.on('pageerror', (err) => problems.push(`[pageerror login] ${err.message}`));
    await page.goto(BASE);
    await expectText(page, 'تسجيل الدخول', 'login page');
    await shot(page, `${prefix}-login`, false);
    await context.close();
  }
  for (const [prefix, viewport] of [['desktop', { width: 1440, height: 900 }], ['phone', { width: 390, height: 844 }]]) {
    const page = await newPage(browser, viewport);
    await salesForm(page, prefix);
    await everyField(page, prefix);
    await pages(page, prefix);
    await page.context().close();
  }
} finally {
  await browser.close();
}
const real = problems.filter((p) => !p.startsWith('[blocked write]') || !p.includes('/auth/logout'));
log(real.length ? `PROBLEMS:\n${real.join('\n')}` : 'NO PROBLEMS');
process.exit(real.some((p) => !p.startsWith('[blocked write]')) ? 1 : 0);
