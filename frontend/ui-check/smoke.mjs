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

// On a phone nothing may run past the page or its card, and no table may need a sideways scroll: one
// field too wide drags the whole page with it. Checked at the narrowest phones too, then put back.
async function fitsThePhone(page, prefix, what) {
  if (prefix !== 'phone') return;
  const size = page.viewportSize();
  for (const width of [size.width, 320]) {
    await page.setViewportSize({ ...size, width });
    await page.waitForTimeout(200);
    const found = await page.evaluate(() => {
      const edge = document.documentElement.clientWidth;
      const main = document.querySelector('.fl-main-col');
      const named = (el) => `${el.tagName.toLowerCase()}.${String(el.className).split(' ')[0]} «${(el.innerText || '').trim().slice(0, 24)}»`;
      const shown = (el) => el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden' && !el.closest('.fl-sr-only');
      const problems = [];
      if (main && main.scrollWidth > main.clientWidth + 1) problems.push(`the page is ${main.scrollWidth - main.clientWidth}px too wide`);
      for (const el of document.querySelectorAll('.fl-main-col *')) {
        if (!shown(el) || el.closest('.fl-tabs')) continue;
        const box = el.getBoundingClientRect();
        const card = el.parentElement.closest('.fl-card, .fl-section, .fl-rowcard, .fl-summary');
        const limit = card ? card.getBoundingClientRect() : { left: 0, right: edge };
        if (box.right > limit.right + 1 || box.left < limit.left - 1) problems.push(`${named(el)} runs past the edge`);
        const { overflowX } = getComputedStyle(el);
        if (['auto', 'scroll'].includes(overflowX) && el !== main && el.scrollWidth > el.clientWidth + 1
          && !['INPUT', 'TEXTAREA'].includes(el.tagName)) problems.push(`${named(el)} scrolls sideways`);
      }
      return [...new Set(problems)].slice(0, 3);
    });
    for (const problem of found) problems.push(`[phone ${width}px] ${what}: ${problem}`);
  }
  await page.setViewportSize(size);
  log(`${prefix} ${what}: fits the phone`);
}

async function expectText(page, text, what) {
  try {
    // A visible one: on a phone the sidebar (with every page's name) is hidden
    await page.getByText(text, { exact: false }).locator('visible=true').first().waitFor({ timeout: 15000 });
  } catch {
    problems.push(`[missing] ${what}: «${text}»`);
  }
}

// The location is a link pasted from خرائط جوجل, and الإحداثيات fill in from it when it carries a
// point. Returns what was filled in, so a later step can tell whether clearing the address cleared it.
async function pasteTheLocation(page, problems, prefix, link = 'https://www.google.com/maps?q=25.200000,55.270000') {
  if (await page.locator('.fl-map__canvas').count()) problems.push(`[${prefix}] the removed map is still on the form`);
  const box = page.locator('#location_url');
  if (!(await box.count())) { problems.push(`[${prefix}] موقع العميل is not on the form`); return ''; }
  await box.scrollIntoViewIfNeeded();
  await box.fill(link);
  await page.waitForTimeout(500);
  const field = page.locator('#coordinates');
  const coordinates = await field.inputValue();
  if (!/-?\d+\.\d+,\s*-?\d+\.\d+/.test(coordinates)) problems.push(`[location] pasting a link left الإحداثيات «${coordinates}»`);
  if (await field.evaluate((el) => el.readOnly)) problems.push('[location] الإحداثيات cannot be typed into');
  log(`${prefix} location: pasted a link, الإحداثيات «${coordinates}»`);
  await shot(page, `${prefix}-address`, false);
  return coordinates;
}

// Every path of §9 opens from a fresh tab, the old ones redirect, and a form the user may not
// fill shows the no-access page rather than the form.
async function urls(page, prefix) {
  const REDIRECTS = [
    ['/sales/new_request', '/forms'],
    ['/sales/my_requests', '/requests/mine'],
    ['/sales/review', '/review'],
    ['/admin/permissions', '/admin/roles'],
    ['/admin/daftra_sync', '/admin/sync'],
    ['/admin/order_sources', '/admin/order-sources'],
  ];
  for (const [from, to] of REDIRECTS) {
    await page.goto(`${BASE}${from}`);
    await page.waitForTimeout(500);
    const landed = new URL(page.url()).pathname;
    if (landed !== to) problems.push(`[${prefix}] ${from} went to ${landed}, not ${to}`);
  }
  console.log(`${prefix} redirects: ${REDIRECTS.length} old paths still land on the new ones`);

  // One form, straight from its own URL
  await page.goto(`${BASE}/forms/new_sale`);
  await expectText(page, 'بيانات العميل', 'a form opened by URL');
  // A form that does not exist: the no-access page, not a broken screen
  await page.goto(`${BASE}/forms/no_such_form`);
  await expectText(page, 'غير متاح', 'the no-access page for an unknown form');
  console.log(`${prefix} a form opens from its own URL, and an unknown one says so`);
}

async function salesForm(page, prefix) {
  await page.goto(`${BASE}/forms`);
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
      // A word from the list as this client's address narrows it, whichever emirate they are in
      const word = ((await page.locator('.fl-picklist__option').allInnerTexts())
        .find((text) => !text.includes('اختر')) || '').trim().split(/\s+/)[0];
      await box.fill(word);
      await page.waitForTimeout(400);
      await shot(page, `${prefix}-dropdown`, false);
      const matches = page.locator('.fl-picklist__option');
      const found = await matches.count();
      const first = (await matches.first().textContent()) || '';
      if (!found || !first.includes(word)) problems.push(`[dropdown] searching «${word}» gave ${found} rows, first «${first}»`);
      else {
        await matches.first().click();
        await page.waitForTimeout(400);
        const chosen = (await category.textContent()) || '';
        if (!chosen.includes(word)) problems.push(`[dropdown] after picking, التصنيف reads «${chosen}»`);
        // Picked by hand, so it sets المنطقة and الإمارة (addressLinks checks them closely)
        const area = await picked('#area');
        if (!area) problems.push('[dropdown] المنطقة is empty after picking a التصنيف');
        log(`${prefix} category search: ${found} match(es), picked «${first.trim()}», area «${area.trim()}»`);
      }
    }
  }
  // Asking for a new address empties the whole service address, التصنيف and the coordinates included
  const addressPick = page.locator('.fl-lookup__actions .fl-pick').first();
  if (await addressPick.count()) {
    // الإحداثيات come from the pasted link
    await pasteTheLocation(page, problems, prefix);
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
  // Files are added one way only: the phone's own picker offers its camera among the rest
  if (await page.getByText('التقاط صورة').count()) problems.push(`[${prefix}] the removed camera button is still on the form`);
  const dropzones = await page.locator('.fl-dropzone').count();
  if (!dropzones) problems.push(`[${prefix}] no box to add a file to`);
  log(`${prefix} attachments: ${dropzones} box(es) to add a file, no camera button`);
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

// نوع العميل, الجنس and البريد appear once the phone search finds nobody, and go again for a known client
// التصنيف, المنطقة and الإمارة follow and narrow each other, and changing the client empties the address
async function addressLinks(page, prefix) {
  const categories = await page.evaluate(async (token) => (await fetch('/api/daftra/client_categories', {
    headers: { Authorization: `Bearer ${token}` },
  })).json(), TOKEN);
  await page.goto(`${BASE}/forms/new_sale`);
  await expectText(page, 'عنوان الخدمة', 'the address section');
  await page.locator('#category').waitFor({ timeout: 15000 });
  await page.waitForTimeout(800);
  const read = (id) => page.locator(id).evaluate((el) => ((el.tagName === 'INPUT' ? el.value : el.textContent) || '').trim());
  const expectThat = (holds, what) => { if (!holds) problems.push(`[address links] ${what}`); };
  const pick = async (id, name) => {
    await page.locator(id).click();
    await page.getByRole('option', { name, exact: false }).first().click();
    await page.waitForTimeout(300);
  };
  const offered = async () => {
    await page.locator('#category').click();
    await page.waitForTimeout(250);
    const names = (await page.locator('.fl-picklist__option').allInnerTexts()).filter((text) => !text.includes('اختر'));
    await page.keyboard.press('Escape');
    await page.waitForTimeout(150);
    return names;
  };
  const inside = (test) => categories.filter(test).length;

  await pick('#emirate', 'الشارقة');
  const ofEmirate = (await offered()).length;
  expectThat(ofEmirate === inside((row) => row.emirate === 'الشارقة'), `الشارقة offers ${ofEmirate} categories`);

  await page.locator('#area').fill('منطقة العين');
  await page.waitForTimeout(300);
  expectThat((await read('#emirate')).includes('أبوظبي'), 'an area did not set its emirate');
  const ofArea = await offered();
  expectThat(ofArea.length === inside((row) => row.area === 'منطقة العين'), `منطقة العين offers ${ofArea.length} categories`);

  await pick('#category', ofArea[0]);
  await page.locator('#area').fill('مدينة دبي');
  await page.waitForTimeout(300);
  expectThat((await read('#emirate')).includes('دبي'), 'moving the area did not move the emirate');
  expectThat((await read('#category')).includes('اختر'), 'a category of another area was kept');

  // A neighbourhood is replaced when a category is picked by hand
  const dubai = categories.find((row) => row.area === 'مدينة دبي');
  await page.locator('#area').fill('الخوانيج 2');
  await page.waitForTimeout(300);
  expectThat((await offered()).length === inside((row) => row.emirate === 'دبي'), 'a neighbourhood narrowed the list');
  await pick('#category', dubai.name);
  expectThat((await read('#area')) === 'مدينة دبي', `picking a category left المنطقة «${await read('#area')}»`);

  // Another emirate takes the category and the region with it
  await pick('#emirate', 'عجمان');
  expectThat((await read('#category')).includes('اختر'), 'a category of another emirate was kept');
  expectThat(!(await read('#area')), 'a region of another emirate was kept');

  // Changing the client empties everything they brought, by either field they can be found by. The
  // code goes with the phone because the search filled it in; a phone that was typed stays.
  for (const [cleared, others] of [['#phone', ['#client_code']], ['#client_code', []]]) {
    await page.goto(`${BASE}/forms/new_sale`);
    await page.locator('#phone').waitFor({ timeout: 15000 });
    await page.locator('#phone').fill(PHONE);
    await page.locator('#phone').press('Enter');
    await expectText(page, 'عميل مسجل', 'a client found to change');
    await page.locator('#category').filter({ hasNotText: 'اختر…' }).waitFor({ timeout: 12000 }).catch(() => {});
    await page.waitForTimeout(800);
    const found = { code: await read('#client_code'), area: await read('#area'), name: await read('#customer_name') };
    expectThat(found.code && found.name, `no client was found to clear (${JSON.stringify(found)})`);
    await page.locator(cleared).fill('');
    await page.waitForTimeout(1500);
    for (const id of ['#area', '#street', '#house', '#location_url', '#coordinates', '#customer_name', ...others]) {
      expectThat(!(await read(id)), `clearing ${cleared} left ${id} «${await read(id)}»`);
    }
    expectThat((await read('#category')).includes('اختر'), `clearing ${cleared} kept التصنيف`);
    expectThat((await read('#emirate')).includes('بدون تحديد'), `clearing ${cleared} kept الإمارة`);
    expectThat(!(await page.getByText('عميل مسجل').count()), `clearing ${cleared} left the found client's note`);
    log(`${prefix} address links: clearing ${cleared} emptied client ${found.code}'s address (${found.area})`);
  }
  log(`${prefix} address links: ${ofEmirate} categories in الشارقة, ${ofArea.length} in منطقة العين`);
}

async function newClient(page, prefix) {
  await page.goto(`${BASE}/forms`);
  await page.getByText('طلب بيع لعميل جديد').first().click();
  await expectText(page, 'بيانات العميل', 'new sale form');
  const fields = ['customer_type', 'gender', 'email'];
  const visible = async () => (await Promise.all(fields.map((name) => page.locator(`#field-${name}`).isVisible()))).filter(Boolean).length;
  if (await visible()) problems.push('[new client] its fields show before any search');
  // A client code nobody has shows them as well
  const code = page.locator('#client_code');
  await code.fill('987654');
  await code.press('Enter');
  await expectText(page, 'لا يوجد عميل بهذا الكود', 'no client with that code');
  await page.waitForTimeout(400);
  const shownForCode = await visible();
  if (shownForCode !== fields.length) problems.push(`[new client] ${shownForCode} of ${fields.length} fields shown after a code nobody has`);
  await code.fill('');
  const phone = page.locator('#phone');
  // A valid number no client has
  await phone.fill('0589990001');
  await phone.press('Enter');
  await expectText(page, 'لا يوجد عميل بهذا الرقم', 'no client with that number');
  await page.waitForTimeout(400);
  const shownForNew = await visible();
  if (shownForNew !== fields.length) problems.push(`[new client] ${shownForNew} of ${fields.length} fields shown for a new client`);
  await page.locator('#email').fill('not-an-email');
  await shot(page, `${prefix}-new-client`, false);
  await phone.fill(PHONE);
  await phone.press('Enter');
  await expectText(page, 'عميل مسجل', 'known client found');
  await page.waitForTimeout(400);
  const shownForKnown = await visible();
  if (shownForKnown) problems.push(`[new client] ${shownForKnown} of its fields still shown for a known client`);
  log(`${prefix} new client fields: ${shownForCode} shown for an unknown code, ${shownForNew} for a new number, ${shownForKnown} for a known client`);
}

// مدة التركيب takes any whole number of days, typed in, not picked from a short list
async function installationDays(page, prefix) {
  await page.goto(`${BASE}/forms`);
  await page.getByText('طلب بيع لعميل جديد').first().click();
  await page.getByRole('button', { name: 'فتح كل الأقسام' }).click();
  const box = page.locator('#installation_days');
  await box.scrollIntoViewIfNeeded();
  const tag = await box.evaluate((el) => el.tagName.toLowerCase());
  if (tag !== 'input') { problems.push(`[installation days] is a ${tag}, not a box to type the days into`); return; }
  await box.fill('17');
  if (await box.inputValue() !== '17') problems.push('[installation days] typing 17 did not stay');
  log(`${prefix} installation days: typed 17, placeholder «${await box.getAttribute('placeholder')}»`);
  await shot(page, `${prefix}-installation-days`, false);
}

// The manager's «المسودات» tab: a count per employee with drafts, filtering by one, and a draft opened read-only
async function managerDrafts(page, prefix) {
  await page.goto(`${BASE}/review?tab=draft`);
  await expectText(page, 'مراجعة الطلبات', 'review page');
  await page.waitForTimeout(1200);
  const chips = page.locator('.fl-draftcounts button');
  const employees = await chips.count();
  if (!employees) {
    await expectText(page, 'لا توجد مسودات', 'no drafts message');
    log(`${prefix} drafts: none`);
    return;
  }
  const label = (await chips.first().innerText()).trim();
  const count = Number((label.match(/\((\d+)\)/) || [])[1]);
  await chips.first().click();
  await page.waitForTimeout(400);
  const results = await page.locator('.fl-results').innerText();
  if (!results.includes(`النتائج: ${count} `)) problems.push(`[drafts] «${label}» but the list says «${results}»`);
  await shot(page, `${prefix}-drafts`);
  await page.getByRole('button', { name: 'عرض المسودة' }).first().click();
  await expectText(page, 'مسودة لم تُرسل بعد', 'draft opened read-only');
  if (await page.getByRole('button', { name: 'اعتماد الطلب' }).count()) problems.push('[drafts] a draft offers to be approved');
  await shot(page, `${prefix}-draft-view`, false);
  log(`${prefix} drafts: ${employees} employee(s) with drafts, first «${label}», ${results}`);
}

// Picking an initiative in «اسم الخصم كما يظهر في الفاتورة» fills قيمة الخصم with its own amount,
// over anything typed there, and the amount can still be changed afterwards
async function discountInitiative(page, prefix) {
  await page.goto(`${BASE}/forms`);
  await page.getByText('طلب بيع لعميل جديد').first().click();
  await page.getByRole('button', { name: 'فتح كل الأقسام' }).click();
  const amount = page.locator('#discount_amount');
  await amount.scrollIntoViewIfNeeded();
  await amount.fill('300');
  const box = page.locator('#discount_label');
  await box.click();
  await page.waitForTimeout(400);
  const options = page.locator('.fl-suggest__item');
  const names = await options.allInnerTexts();
  if (!names.length) { problems.push('[discount] no names are offered for اسم الخصم'); return; }
  const wanted = names.findIndex((name) => name.includes('سقيا الخير'));
  if (wanted < 0) { problems.push(`[discount] «مبادرة دعم سقيا الخير» is not offered, only ${names.join(' / ')}`); return; }
  await options.nth(wanted).click();
  await page.waitForTimeout(300);
  const filled = await amount.inputValue();
  if (filled !== '1750') problems.push(`[discount] picking «${names[wanted].trim()}» left قيمة الخصم «${filled}», not 1750`);
  // It is a starting point, not a locked value
  if (await amount.evaluate((el) => el.readOnly)) problems.push('[discount] قيمة الخصم cannot be changed after picking');
  await amount.fill('900');
  if (await amount.inputValue() !== '900') problems.push('[discount] قيمة الخصم could not be changed after picking');
  log(`${prefix} discount: ${names.length} name(s) offered, picking «${names[wanted].trim()}» filled ${filled}`);
  await shot(page, `${prefix}-discount`, false);
}

// Every field each visible form defines is on the screen
async function everyField(page, prefix) {
  const types = await page.evaluate(async (token) => (await fetch('/api/form-types', { headers: { Authorization: `Bearer ${token}` } })).json(), TOKEN);
  for (const type of types.filter((t) => !t.hidden)) {
    await page.goto(`${BASE}/forms`);
    await page.getByText(type.label).first().click();
    await page.getByRole('button', { name: 'فتح كل الأقسام' }).click();
    await page.waitForTimeout(500);
    // A new client's fields (نوع العميل, الجنس, البريد) wait for a phone search that finds nobody: newClient()
    const expected = type.sections.flatMap((section) => section.fields.filter((f) => !f.new_client).map((f) => f.name));
    const shown = await page.$$eval('[id^="field-"]', (els) => els.filter((el) => el.offsetParent !== null).map((el) => el.id.slice(6)));
    const missing = expected.filter((name) => !shown.includes(name));
    log(`${prefix} ${type.key}: ${shown.length} of ${expected.length} fields shown`);
    if (missing.length) problems.push(`[missing fields] ${type.key}: ${missing.join(', ')}`);
    await shot(page, `${prefix}-form-${type.key}`);
    await fitsThePhone(page, prefix, `the ${type.key} form`);
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
  await page.goto(`${BASE}/forms`);
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
  await page.goto(`${BASE}/forms`);
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
    ['/requests/mine', 'طلباتي', 'my-requests'],
    ['/review', 'مراجعة الطلبات', 'review'],
    ['/admin/users', 'المستخدمون', 'users'],
    ['/admin/roles', 'الأدوار والصلاحيات', 'roles'],
    ['/admin/audit', 'سجل النشاط', 'audit'],
    ['/admin/catalog', 'المنتجات والباقات', 'products'],
    ['/admin/sync', 'المزامنة مع دفترة', 'daftra-sync'],
    ['/admin/order-sources', 'مصادر الطلب', 'order-sources'],
    ['/admin/mail', 'اختبار البريد', 'mail'],
    ['/account', 'حسابي', 'account'],
  ];
  for (const [path, title, name] of visits) {
    await page.goto(`${BASE}${path}`);
    await expectText(page, title, path);
    await page.waitForTimeout(1200);
    await shot(page, `${prefix}-${name}`);
    await fitsThePhone(page, prefix, path);
  }
  // A request opened from the review list
  await page.goto(`${BASE}/review?tab=all`);
  const open = page.getByRole('button', { name: /عرض الطلب|مراجعة الطلب/ }).first();
  await open.waitFor({ timeout: 15000 }).catch(() => {});
  if (await open.count().catch(() => 0)) {
    await open.click();
    await expectText(page, 'سجل الطلب', 'request view history');
    await page.waitForTimeout(800);
    await shot(page, `${prefix}-request-view`);
    await fitsThePhone(page, prefix, 'a request opened from the review list');
  }
  // A product drawer in the catalog
  await page.goto(`${BASE}/admin/catalog`);
  await expectText(page, 'المنتجات والباقات', 'catalog again');
  await page.getByRole('button', { name: 'تعديل' }).first().click().catch(() => problems.push('[click] product edit'));
  await page.waitForTimeout(500);
  await shot(page, `${prefix}-product-drawer`);
}

// Each document approving a request made in Daftra can be handed to another app, WhatsApp among
// them. Only an approved request has any, so the list is walked until one shows its دفترة card.
async function daftraDocuments(page, prefix) {
  const rows = page.getByRole('button', { name: /عرض الطلب|مراجعة الطلب/ });
  let tried = 0;
  for (let i = 0; i < 8; i += 1) {
    await page.goto(`${BASE}/review?tab=all`);
    await page.waitForTimeout(1000);
    if (i >= await rows.count()) break;
    tried += 1;
    await rows.nth(i).click();
    await expectText(page, 'سجل الطلب', 'request opened from the review list');
    await page.waitForTimeout(600);
    const docs = await page.locator('.fl-doc').count();
    if (!docs) continue;
    const shares = await page.getByRole('button', { name: /^مشاركة / }).count();
    if (docs !== shares) problems.push(`[${prefix}] ${docs} Daftra document(s) but ${shares} share button(s)`);
    // This browser cannot hand a file to another app (that needs HTTPS and a device with apps to
    // share with), so the document is saved instead and the portal says so rather than doing nothing
    await page.getByRole('button', { name: /^مشاركة / }).first().click();
    await expectText(page, 'تم تنزيل الملف', 'what the share button says where sharing is impossible');
    log(`${prefix} daftra documents: ${docs}, each with a share button`);
    await shot(page, `${prefix}-daftra-documents`, false);
    return;
  }
  problems.push(`[${prefix}] none of the ${tried} request(s) opened carries the دفترة documents to share`);
}

// تفاصيل الطلب offers packages or single products, never both at once: the toggle says which,
// and it opens on باقات. Forms that offer products alone (صيانة وتبديل) have no toggle.
async function packagesOrProducts(page, prefix) {
  // The toggle appears once the products and packages are in: before that there is nothing to
  // choose between, and the search box says it is still loading
  const waitForCatalog = async () => {
    const search = page.locator('#order_lines');
    await search.waitFor({ timeout: 15000 });
    await page.waitForFunction(
      () => !(document.getElementById('order_lines')?.placeholder || '').includes('جارٍ تحميل'),
      null, { timeout: 15000 },
    );
  };

  const kindsListed = async () => {
    const search = page.locator('#order_lines');
    await search.scrollIntoViewIfNeeded();
    await search.click();
    await page.waitForTimeout(400);
    const subs = await page.locator('.fl-suggest__item small').allInnerTexts();
    return [...new Set(subs.map((text) => text.split('·')[0].trim()))];
  };

  for (const form of ['new_sale', 'quotation']) {
    await page.goto(`${BASE}/forms/${form}`);
    await expectText(page, 'تفاصيل الطلب', `${form} order details`);
    await waitForCatalog();
    const on = page.locator('.fl-choice__item--on', { hasText: 'باقات' });
    if (!(await on.count())) { problems.push(`[${prefix}] ${form}: the picker does not open on باقات`); continue; }
    const asPackages = await kindsListed();
    if (asPackages.join() !== 'باقة') problems.push(`[${prefix}] ${form}: باقات lists ${asPackages.join(' + ') || 'nothing'}`);
    await page.getByText('منتجات', { exact: true }).first().click();
    const asProducts = await kindsListed();
    if (asProducts.join() !== 'منتج') problems.push(`[${prefix}] ${form}: منتجات lists ${asProducts.join(' + ') || 'nothing'}`);
    log(`${prefix} ${form} picker: باقات → ${asPackages.join(', ')}, منتجات → ${asProducts.join(', ')}`);
    await shot(page, `${prefix}-${form}-products`, false);
  }
  // A form whose picker has one kind has nothing to choose between
  await page.goto(`${BASE}/forms/maintenance`);
  await expectText(page, 'تفاصيل الطلب', 'maintenance order details');
  await waitForCatalog();
  if (await page.locator('.fl-choice__item', { hasText: 'باقات' }).count()) {
    problems.push(`[${prefix}] صيانة وتبديل offers a باقات toggle, though it has no packages`);
  }
  console.log(`${prefix} صيانة وتبديل: items only, no toggle`);
}

// صيانة وتبديل settles what each part costs per visit: the five fixed items start at their price,
// everything else starts empty, and both سعر الوحدة and الكمية can be changed on every line.
async function maintenancePrices(page, prefix) {
  await page.goto(`${BASE}/forms/maintenance`);
  await expectText(page, 'تفاصيل الطلب', 'maintenance order details');
  const search = page.locator('#order_lines');
  await search.waitFor({ timeout: 15000 });
  const pick = async (text) => {
    await search.scrollIntoViewIfNeeded();
    await search.fill(text);
    await page.waitForTimeout(600);
    const first = page.locator('.fl-suggest__item').first();
    if (!(await first.count())) { problems.push(`[${prefix}] صيانة وتبديل: nothing matches «${text}»`); return false; }
    await first.click();
    await page.waitForTimeout(400);
    return true;
  };
  const prices = page.locator('.fl-order-lines__price');

  // One of the five: it comes with its price, which is still a box to type in
  if (!(await pick('GRAVEL SIZE 1-3'))) return;
  const fixed = await prices.first().inputValue();
  if (fixed !== '150') problems.push(`[${prefix}] GRAVEL SIZE 1-3 started at «${fixed}», not 150`);
  // Anything else comes with none, for the salesperson to fill in
  if (!(await pick('شمعة CTO مقاس 10'))) return;
  const empty = await prices.nth(1).inputValue();
  if (empty !== '') problems.push(`[${prefix}] a filter started at «${empty}» instead of empty`);

  // Both boxes are the salesperson's: 200 x 2 + 60 x 1
  await prices.first().fill('200');
  await prices.nth(1).fill('60');
  const quantity = page.locator('.fl-order-lines__qty').first();
  await quantity.fill('2');
  await page.waitForTimeout(500);
  const subtotal = await page.locator('#subtotal_amount').inputValue();
  if (!String(subtotal).replace(/[^\d]/g, '').startsWith('460')) {
    problems.push(`[${prefix}] typed prices 200x2 + 60 came to «${subtotal}», not 460`);
  }
  log(`${prefix} maintenance prices: GRAVEL starts at ${fixed}, a filter at «${empty}», typed total ${subtotal}`);
  await shot(page, `${prefix}-maintenance-prices`, false);
}

// The discount reads name, amount, then who approved it, on every form that names one, and picking
// an initiative on طلب صيانة وتبديل fills the amount as it does on a sale
async function discountOrder(page, prefix) {
  for (const form of ['new_sale', 'contract_renewal', 'maintenance']) {
    await page.goto(`${BASE}/forms/${form}`);
    await page.getByRole('button', { name: 'فتح كل الأقسام' }).click();
    await page.waitForTimeout(500);
    const order = await page.$$eval('[id^="field-"]', (els) => els.filter((el) => el.offsetParent !== null).map((el) => el.id.slice(6)));
    const seen = ['discount_label', 'discount_amount', 'paid_amount', 'discount_approved_by'].map((name) => order.indexOf(name));
    if (seen.includes(-1) || seen.some((at, i) => i && at <= seen[i - 1])) problems.push(`[discount order] ${form}: ${seen}`);
  }
  await page.locator('#discount_label').scrollIntoViewIfNeeded();
  await page.locator('#discount_label').click();
  await page.waitForTimeout(300);
  await page.getByRole('option', { name: 'مبادرة دعم سقيا الخير' }).first().click();
  await page.waitForTimeout(300);
  const filled = await page.locator('#discount_amount').inputValue();
  if (filled !== '1750') problems.push(`[discount order] the maintenance form filled قيمة الخصم with «${filled}»`);
  await shot(page, `${prefix}-maintenance-discount`, false);
  log(`${prefix} discount order: name, amount, paid, approver on 3 forms; maintenance filled ${filled}`);
}

// اعمال اضافية offers its four works at the form's own prices. The catalog is answered at 150 here,
// so a price of 6 on the line can only have come from the form.
async function techWorks(page, prefix) {
  await page.route('**/api/catalog/picker', async (route) => {
    const response = await route.fetch();
    const rows = (await response.json()).map((row) => (row.daftra_id === 212 ? { ...row, price: 150 } : row));
    await route.fulfill({ response, json: rows });
  });
  await page.goto(`${BASE}/forms/tech_extra_works`);
  await expectText(page, 'الأعمال المطلوبة', 'the works of اعمال اضافية');
  const search = page.locator('#order_lines');
  await search.waitFor({ timeout: 15000 });
  await page.waitForFunction(() => !(document.getElementById('order_lines')?.placeholder || '').includes('جارٍ تحميل'),
    null, { timeout: 15000 });
  await search.scrollIntoViewIfNeeded();
  await search.click();
  await page.waitForTimeout(400);
  const offered = (await page.locator('.fl-suggest__item').allInnerTexts()).map((text) => text.replace(/\s+/g, ' ').trim());
  for (const [work, price] of [['تمديد المياة', '6 درهم'], ['تمديد الكهرباء', '7 درهم'], ['اعمال باسكو', '10 درهم']]) {
    const row = offered.find((text) => text.includes(work));
    if (!row) problems.push(`[tech works] «${work}» is not offered`);
    else if (!row.includes(price)) problems.push(`[tech works] «${work}» reads «${row}», not ${price}`);
  }
  if (offered.length !== 4) problems.push(`[tech works] ${offered.length} works offered, not 4`);
  await page.locator('.fl-suggest__item', { hasText: 'تمديد المياة' }).first().click({ force: true });
  await page.waitForTimeout(300);
  const unit = ((await page.locator('.fl-order-lines .fl-cell--unit').first().textContent()) || '').trim();
  if (!unit.includes('6') || unit.includes('150')) problems.push(`[tech works] a line reads «${unit}», not 6`);
  await page.unroute('**/api/catalog/picker');
  log(`${prefix} tech works: ${offered.length} offered, a line priced «${unit}» with the catalog at 150`);
}

// ملحقات التركيب comes filled in from the package picked, and stays a box the salesperson can
// change or empty. A package nothing is written for leaves it empty.
async function installationWork(page, prefix) {
  await page.goto(`${BASE}/forms/new_sale`);
  await expectText(page, 'تفاصيل الطلب', 'new sale order details');
  const search = page.locator('#order_lines');
  await search.waitFor({ timeout: 15000 });
  const pick = async (text) => {
    await search.scrollIntoViewIfNeeded();
    await search.fill(text);
    await page.waitForTimeout(600);
    const first = page.locator('.fl-suggest__item').first();
    if (!(await first.count())) { problems.push(`[${prefix}] nothing matches «${text}»`); return false; }
    await first.click();
    await page.waitForTimeout(500);
    return true;
  };
  const boxes = page.locator('textarea[id$="-installation_accessories"]');

  // A water cooler, a food cooler (whose name carries «نبع المزن» too and must not take its text),
  // a stainless one, and a package nothing is written for
  const WANTED = [
    ['نبع المزن - 3 صنابير', 'تمديد مياه وكهرباء كامل للبرادة'],
    ['حفظ الطعام - غطاء نبع المزن', 'تمديد كهرباء كامل للبرادة'],
    ['ستانلس ستيل - 2', 'فلتر 3 مراحل + عمل التمديدات'],
    ['باب خلفي جرار', ''],
  ];
  const filled = [];
  for (const [search, expected] of WANTED) {
    if (!(await pick(search))) return;
    const index = filled.length;
    if (await boxes.count() <= index) { problems.push(`[${prefix}] ملحقات التركيب is not on the line`); return; }
    const value = (await boxes.nth(index).inputValue()).trim();
    filled.push(value);
    if (expected ? !value.startsWith(expected) : value !== '') {
      problems.push(`[${prefix}] «${search}» filled ملحقات التركيب with «${value.slice(0, 40)}»`);
    }
  }
  // It is a starting point, not a locked value
  const box = boxes.first();
  if (await box.evaluate((el) => el.readOnly)) problems.push(`[${prefix}] ملحقات التركيب cannot be changed`);
  await box.fill(`${filled[0]} + فحص الضغط`);
  if (!(await box.inputValue()).endsWith('فحص الضغط')) {
    problems.push(`[${prefix}] ملحقات التركيب did not keep what was added to it`);
  }
  log(`${prefix} installation work: ${filled.map((v) => `«${v.slice(0, 22)}»`).join(', ')}`);
  await shot(page, `${prefix}-installation-work`, false);
}

// «استكمال» in طلباتي opens the draft in its own form, and so does the bare URL of that page:
// the form is never guessed from the URL alone.
async function continuingADraft(page, prefix) {
  await page.goto(`${BASE}/requests/mine?tab=draft`);
  await expectText(page, 'طلباتي', 'my requests');
  await page.waitForTimeout(1500);
  const carry = page.getByRole('button', { name: 'استكمال' }).first();
  if (!(await carry.count())) {
    console.log(`${prefix} drafts of my own: none to carry on with`);
    return;
  }
  await carry.click();
  await page.waitForTimeout(1200);
  const shown = await page.locator('.fl-alert, .fl-empty').allInnerTexts().catch(() => []);
  const refused = shown.find((text) => text.includes('لم يعد متاحًا') || text.includes('غير متاح'));
  if (refused) problems.push(`[${prefix}] استكمال said «${refused.slice(0, 60).trim()}»`);
  await expectText(page, 'إرسال للمراجعة', 'the draft opened in its form');
  const url = new URL(page.url());
  if (!url.pathname.endsWith('/edit')) problems.push(`[${prefix}] استكمال went to ${url.pathname}`);
  log(`${prefix} استكمال: opened ${url.pathname}${url.search}`);
  await shot(page, `${prefix}-draft-edit`, false);

  // The same page without the hint the button adds: the request itself says which form it is
  await page.goto(`${BASE}${url.pathname}`);
  await expectText(page, 'إرسال للمراجعة', 'the draft opened from its bare URL');
  const bare = await page.locator('.fl-alert, .fl-empty').allInnerTexts().catch(() => []);
  if (bare.some((text) => text.includes('لم يعد متاحًا'))) {
    problems.push(`[${prefix}] ${url.pathname} without ?form could not tell which form it is`);
  }
  console.log(`${prefix} استكمال: the bare URL opens the same form`);
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
    await addressLinks(page, prefix);
    await devicePicker(page, prefix);
    await staffPickers(page, prefix);
    await newClient(page, prefix);
    await installationDays(page, prefix);
    await discountInitiative(page, prefix);
    await managerDrafts(page, prefix);
    await continuingADraft(page, prefix);
    await everyField(page, prefix);
    await pages(page, prefix);
    await urls(page, prefix);
    await daftraDocuments(page, prefix);
    await packagesOrProducts(page, prefix);
    await maintenancePrices(page, prefix);
    await installationWork(page, prefix);
    await techWorks(page, prefix);
    await discountOrder(page, prefix);
    await page.context().close();
  }
} finally {
  await browser.close();
}
const real = problems.filter((p) => !p.startsWith('[blocked write]') || !p.includes('/auth/logout'));
log(real.length ? `PROBLEMS:\n${real.join('\n')}` : 'NO PROBLEMS');
process.exit(real.some((p) => !p.startsWith('[blocked write]')) ? 1 : 0);
