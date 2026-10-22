// Browser check of the local stack (see run.sh): every page renders, the sales form works, every
// field of every visible form is on the screen, and nothing logs an error. Writes are blocked.
// Env: BASE, TOKEN (an admin's JWT), PHONE (a client's phone), OUT (screenshot folder), TAG
import { chromium } from 'playwright';

const { BASE, TOKEN, PHONE, OUT, TAG = 'run' } = process.env;
const problems = [];
const log = (...args) => console.log(...args);

async function newPage(browser, viewport) {
  const touch = viewport.width < 900;
  const context = await browser.newContext({ viewport, locale: 'ar-AE', timezoneId: 'Asia/Dubai', hasTouch: touch, isMobile: touch });
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
    // Pressing Enter searches; the magnifier is not the only way
    await page.locator('#phone').fill(PHONE);
    await page.locator('#phone').press('Enter');
    await expectText(page, 'عميل مسجل', 'client lookup after pressing Enter');
  }
  // Finding a client fills التصنيف from Daftra, and المنطقة and الإمارة come from its address.
  // التصنيف and الإمارة are buttons showing what is chosen; المنطقة is typed, so it has a value.
  const picked = (id) => page.locator(id).evaluate((el) => ((el.tagName === 'INPUT' ? el.value : el.textContent) || '').trim());
  // Daftra answers a moment after the client is found; wait for التصنيف before reading the three
  await page.locator('#category').filter({ hasNotText: 'اختر…' }).waitFor({ timeout: 12000 }).catch(() => {});
  const afterLookup = { category: await picked('#category'), area: await picked('#area'), emirate: await picked('#emirate') };
  log(`${prefix} after finding the client: ${JSON.stringify(afterLookup)}`);
  const empty = (text) => !text || text.includes('اختر') || text.includes('بدون تحديد');
  if (!empty(afterLookup.category) && (empty(afterLookup.area) || empty(afterLookup.emirate))) {
    problems.push(`[client] التصنيف «${afterLookup.category}» came with المنطقة «${afterLookup.area}» and الإمارة «${afterLookup.emirate}»`);
  }

  // التصنيف is a long list, so its drop-down opens with a search box; picking one fills المنطقة and الإمارة
  const category = page.locator('#category');
  if (await category.count()) {
    await category.click();
    const box = page.locator('.fl-picklist__input');
    if (!(await box.count())) problems.push('[dropdown] التصنيف has no search box');
    else {
      await box.fill('العين');
      await page.waitForTimeout(400);
      await shot(page, `${prefix}-dropdown`, false);
      const matches = page.locator('.fl-picklist__option');
      const found = await matches.count();
      const first = (await matches.first().textContent()) || '';
      if (!found || !first.includes('العين')) problems.push(`[dropdown] searching «العين» gave ${found} rows, first «${first}»`);
      else {
        await matches.first().click();
        await page.waitForTimeout(400);
        const chosen = (await category.textContent()) || '';
        if (!chosen.includes('العين')) problems.push(`[dropdown] after picking, التصنيف reads «${chosen}»`);
        // المنطقة is filled by التصنيف only while it is empty; the client's own address keeps it otherwise
        const area = await picked('#area');
        if (!area) problems.push('[dropdown] المنطقة is empty after picking a التصنيف');
        log(`${prefix} category search: ${found} match(es), picked «${first.trim()}», area «${area.trim()}»`);
      }
    }
  }
  // Asking for a new address empties the whole service address, التصنيف and the coordinates included
  const addressPick = page.locator('.fl-lookup__actions .fl-pick').first();
  if (await addressPick.count()) {
    await page.locator('#coordinates').fill('24.1787, 55.6045');
    await addressPick.click();
    const newAddress = page.getByRole('option', { name: /عنوان جديد/ });
    if (!(await newAddress.count())) problems.push('[address] «عنوان جديد» is not offered');
    else {
      await newAddress.first().click();
      await page.waitForTimeout(400);
      const category = await picked('#category');
      const area = await picked('#area');
      const street = await page.locator('#street').inputValue();
      const coordinates = await page.locator('#coordinates').inputValue();
      log(`${prefix} new address: category «${category}», area «${area}», street «${street}», coordinates «${coordinates}»`);
      if (!category.includes('اختر')) problems.push(`[address] التصنيف kept «${category}»`);
      if (area) problems.push(`[address] المنطقة kept «${area}»`);
      if (street) problems.push(`[address] الشارع kept «${street}»`);
      if (coordinates) problems.push(`[address] الإحداثيات kept «${coordinates}»`);

      // Going back to one of the client's own addresses fills it in again
      await addressPick.click();
      const saved = page.getByRole('option').first();
      const label = ((await saved.textContent()) || '').trim();
      await saved.click();
      await page.waitForTimeout(400);
      const back = await picked('#area');
      const emirate = await picked('#emirate');
      const filled = [back, emirate, await page.locator('#street').inputValue(), await page.locator('#house').inputValue()]
        .filter((part) => part && !part.includes('بدون تحديد')).join(' · ');
      log(`${prefix} back to «${label}»: ${filled || 'nothing filled'}`);
      // Whatever that address holds must come back; «بلا عنوان مسجل» is the one that holds nothing
      if (!label.includes('بلا عنوان') && !filled) problems.push(`[address] going back to «${label}» filled nothing in`);
    }
  }
  await page.evaluate(() => document.querySelector('.fl-main-col')?.scrollTo(0, 0));
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
  await keyboardRoom(page, prefix);
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

// While the phone's keyboard is open, nothing may float over it
async function keyboardRoom(page, prefix) {
  await page.evaluate(() => document.body.classList.add('fl-keyboard'));
  await page.waitForTimeout(200);
  const bottomNav = await page.locator('.fl-bottomnav').isVisible().catch(() => false);
  const barPosition = await page.locator('.fl-actionbar').evaluate((el) => getComputedStyle(el).position).catch(() => 'none');
  if (bottomNav) problems.push(`[keyboard] ${prefix}: the bottom bar still shows over the keyboard`);
  if (barPosition === 'sticky') problems.push(`[keyboard] ${prefix}: the action bar is still stuck over the keyboard`);
  log(`${prefix} with the keyboard open: bottom bar ${bottomNav ? 'VISIBLE' : 'hidden'}, action bar ${barPosition}`);
  await shot(page, `${prefix}-keyboard`, false);
  await page.evaluate(() => document.body.classList.remove('fl-keyboard'));
}

// Staff names (who approved the discount, who collected the cash) are offered in the portal's own
// list, not the browser's unstyled one, and a pick fills the field
async function staffPickers(page, prefix) {
  await page.goto(`${BASE}/sales/new_request`);
  await page.getByText('طلب بيع لعميل جديد').first().click();
  await expectText(page, 'تفاصيل الطلب', 'new sale form');
  await page.getByRole('button', { name: 'فتح كل الأقسام' }).click();
  if (await page.locator('datalist').count()) problems.push("[staff] the form still uses the browser's own suggestion list");
  for (const name of ['discount_approved_by', 'collector_name']) {
    const box = page.locator(`#${name}`);
    await box.scrollIntoViewIfNeeded();
    await box.click();
    await page.waitForTimeout(400);
    const items = page.locator(`#field-${name} .fl-suggest__item`);
    const found = await items.count();
    if (!found) { problems.push(`[staff] ${name}: no themed list of staff names opened`); continue; }
    const first = (await items.first().innerText()).trim();
    await items.first().click();
    const value = await box.inputValue();
    if (value !== first) problems.push(`[staff] ${name}: picked «${first}» but the field holds «${value}»`);
    log(`${prefix} ${name}: ${found} staff name(s) offered, picked «${first}»`);
  }
  await shot(page, `${prefix}-staff`, false);
}

// نوع الجهاز is picked the same way products are: search, add, and a row per pick
async function devicePicker(page, prefix) {
  await page.goto(`${BASE}/sales/new_request`);
  await page.getByText('طلب صيانة وتبديل').first().click();
  await expectText(page, 'تفاصيل الطلب', 'maintenance form');
  const box = page.locator('#devices');
  await box.click();
  await box.fill('سقيا');
  await page.waitForTimeout(400);
  const matches = page.locator('.fl-suggest__item');
  const found = await matches.count();
  if (!found) { problems.push('[devices] searching «سقيا» found nothing'); return; }
  await matches.first().click();
  await page.waitForTimeout(300);
  // A second one, to be sure the list stays open for more
  await box.fill('فلتر');
  await page.waitForTimeout(400);
  if (await page.locator('.fl-suggest__item').count()) await page.locator('.fl-suggest__item').first().click();
  await page.waitForTimeout(300);
  const rows = await page.locator('#field-devices .fl-picked__item').count();
  log(`${prefix} devices: ${found} match(es) for «سقيا», ${rows} picked`);
  if (rows !== 2) problems.push(`[devices] expected 2 rows after two picks, found ${rows}`);
  await shot(page, `${prefix}-devices`, false);
  // Removing one takes its row away
  await page.locator('#field-devices .fl-picked__item button').first().click();
  await page.waitForTimeout(300);
  if (await page.locator('#field-devices .fl-picked__item').count() !== 1) problems.push('[devices] removing a device did not take its row away');
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
    await devicePicker(page, prefix);
    await staffPickers(page, prefix);
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
