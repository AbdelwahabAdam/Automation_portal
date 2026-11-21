// node --test tests/  (npm test). The browser-side checks in modules/requests/validation.js, the
// formatting in lib/format.js and the search helpers in ds/match.js; the backend repeats the form
// checks (backend/tests/modules/form_engine/test_forms.py).
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { matchesQuery, normalize, samePerson } from '../src/ds/match.js';
import { formatAmount, formatDay, localDay } from '../src/lib/format.js';
import {
  changedDetails, chargeApplies, coordinatesFromLink, discountFromPercent, packageFields, packageProfile, evaluateForm, groupLines, initialValues, linePrice, normalizePhone, packageColors,
  packageDefault, packageQuantity, today,
} from '../src/modules/requests/validation.js';
import { afterCategory, afterEmirate, categoriesFor } from '../src/modules/requests/address.js';
import { balanceView, clientCredit } from '../src/modules/requests/form/balance.js';

const families = [
  { match: ['سقيا الخير مدمجة'], exclude: [], colors: ['الابيض', 'الاسود'] },
  { match: ['سقيا الخير'], exclude: ['ستانلس'], colors: ['الاسود مقاس طبيعي'] },
];

const form = {
  key: 'test',
  sections: [
    {
      title: 'a',
      fields: [
        { name: 'request_date', type: 'date', required: true, default: 'today', not_future: true },
        { name: 'phone', type: 'phone', required: true },
        { name: 'code', type: 'text', required: false, pattern: '^\\d{1,6}$', pattern_message: 'أرقام فقط' },
        { name: 'kind', type: 'select', required: true, options: ['x', 'y'] },
        { name: 'treasury', type: 'daftra_treasury', required: true },
        {
          name: 'order_lines', type: 'order_lines', required: true, subtotal_field: 'subtotal_amount',
          line_fields: [{ name: 'inscription_price', type: 'number', charge: true }],
        },
        { name: 'subtotal_amount', type: 'number', computed: [] },
        { name: 'total_amount', type: 'number', computed: ['subtotal_amount', 'discount_amount'], negative_message: 'neg' },
        { name: 'discount_amount', type: 'number', min: 0 },
        { name: 'approved_by', type: 'staff', required_if: { field: 'discount_amount', gt: 0 } },
        { name: 'paid_amount', type: 'number', required: true, min: 0, must_equal: 'total_amount', must_equal_message: 'all' },
        { name: 'proof', type: 'files', required: true },
      ],
    },
  ],
};

const lines = [
  { product_id: 1, quantity: 2, unit_price: 2000, group_id: 'g', details: { package_quantity: '2', inscription_price: '300' } },
  { product_id: 2, quantity: 2, unit_price: 800, group_id: 'g', details: { package_quantity: '2', inscription_price: '300' } },
  { product_id: 3, quantity: 1, group_id: null, details: {} },
];

test('normalizePhone reduces a UAE number written any way to the one form we keep', () => {
  for (const written of ['050 123 4567', '٠٥٠١٢٣٤٥٦٧', '+971 50 123 4567', '00971501234567', '971501234567']) {
    assert.equal(normalizePhone(written), '0501234567', written);
  }
  // A landline is as good a number: 4 دبي, 3 العين, 2 أبوظبي…
  assert.equal(normalizePhone('04 123 4567'), '041234567');
});

test('normalizePhone refuses what is not a UAE number', () => {
  for (const no of ['12345', '0591234567', '0101234567', '05012345', '05012345678', '+44 20 7946 0000']) {
    assert.equal(normalizePhone(no), null, no);
  }
});

// What installing a package involves, as the form's field carries it (INSTALLATION_WORK)
const work = [
  { match: ['حفظ الطعام'], exclude: [], text: 'كهرباء وقاعدة سيراميك' },
  { match: ['ستانلس', '6 صنابير'], exclude: [], text: 'فلتر وتمديدات' },
  { match: ['نبع المزن', 'سقيا الخير'], exclude: ['حفظ الطعام', 'ستانلس'], text: 'مياه وكهرباء كامل' },
];

test('the package picked fills in what installing it involves', () => {
  const spec = { default_by_package: work };
  assert.equal(packageDefault(spec, 'باقة برادة نبع المزن - 3 صنابير - أبيض'), 'مياه وكهرباء كامل');
  assert.equal(packageDefault(spec, 'باقة سقيا الخير مدمجة - برادتا مياه 3 صنابير وبرادة طعام - أسود'), 'مياه وكهرباء كامل');
  // حفظ الطعام and ستانلس carry سقيا الخير / نبع المزن in their names and must not take their text
  assert.equal(packageDefault(spec, 'باقة برادة حفظ الطعام - غطاء نبع المزن'), 'كهرباء وقاعدة سيراميك');
  assert.equal(packageDefault(spec, 'باقة برادة سقيا الخير ستانلس ستيل - 2 صنبور'), 'فلتر وتمديدات');
  assert.equal(packageDefault(spec, 'باقة برادة مياه - 6 صنابير - أبيض'), 'فلتر وتمديدات');
  // Nothing is written for the rest, and a field without the rules is left alone
  assert.equal(packageDefault(spec, 'باب خلفي جرار لبرادة مدمجة'), '');
  assert.equal(packageDefault({}, 'باقة برادة نبع المزن - 3 صنابير - أبيض'), '');
});

// The inscription a package starts with, as the form's field carries it (PACKAGE_INSCRIPTIONS)
const VERSE = 'وجعلنا من الماء';
const NAMED = `104 - ${VERSE}`;
const inscribing = [
  { name: 'inscription', work_field: 'work', price_field: 'price',
    default_by_package: [{ match: ['سقيا الخير'], exclude: [], text: VERSE, price: '0', work: NAMED }] },
  { name: 'work' }, { name: 'price' },
];
const SAQYA = 'باقة برادة سقيا الخير - 2 صنبور - أبيض';
const change = (details, value, name = 'inscription', pack = SAQYA) => changedDetails(inscribing, pack, name, details, value);

test('a package starting with an inscription prices it and names it in ملحقات التركيب', () => {
  const picked = change({ work: 'تمديد • فلتر' }, VERSE);
  assert.deepEqual(picked, { work: `تمديد • فلتر • ${NAMED}`, inscription: VERSE, price: '0' });
  assert.equal(change({}, VERSE).work, NAMED);
});

test('another inscription takes it out of ملحقات التركيب, and picking it again puts it back', () => {
  const picked = change({ work: 'تمديد • فلتر' }, VERSE);
  const other = change(picked, 'نص آخر');
  assert.equal(other.work, 'تمديد • فلتر');
  const none = change(picked, '');
  assert.equal(none.work, 'تمديد • فلتر');
  const again = change(other, VERSE);
  assert.deepEqual(again, picked);
});

test('what the salesperson wrote around it stays when it goes', () => {
  assert.equal(change({ inscription: VERSE, work: `تمديد • ${NAMED} • زيادة`, price: '0' }, 'نص آخر').work, 'تمديد • زيادة');
  assert.equal(change({ inscription: VERSE, work: NAMED, price: '0' }, 'نص آخر').work, '');
});

test('the free price does not follow another inscription, and a typed one is kept', () => {
  assert.equal(change({ inscription: VERSE, work: NAMED, price: '0' }, 'نص آخر').price, '');
  assert.equal(change({ inscription: VERSE, work: NAMED, price: '150' }, 'نص آخر').price, '150');
});

test('changing one other inscription for another leaves ملحقات التركيب and the price alone', () => {
  assert.deepEqual(change({ inscription: 'نص', work: 'تمديد', price: '50' }, 'نص ثان'),
    { inscription: 'نص ثان', work: 'تمديد', price: '50' });
});

test('other fields, and a package with no inscription of its own, change only themselves', () => {
  assert.deepEqual(change({ inscription: VERSE, work: NAMED, price: '0' }, 'نص', 'other'),
    { inscription: VERSE, work: NAMED, price: '0', other: 'نص' });
  assert.deepEqual(change({ work: 'تمديد', price: '50' }, VERSE, 'inscription', 'باقة برادة نبع المزن - 3 صنابير'),
    { work: 'تمديد', price: '50', inscription: VERSE });
});

// التصنيف, المنطقة and الإمارة: the only link left is between the first and the last
const CATEGORIES = [
  { id: 1, name: 'البطين العين', area: 'منطقة العين', emirate: 'العين' },
  { id: 2, name: 'الخوانيج', area: 'مدينة دبي', emirate: 'دبي' },
  { id: 3, name: 'تصنيف بلا مكان', area: null, emirate: null },
];

test('المنطقة is the التصنيف, and الإمارة follows it', () => {
  // Picking a التصنيف: المنطقة is its own name, never its area
  assert.deepEqual(afterCategory(CATEGORIES[0]), { area: 'البطين العين', emirate: 'العين' });
  // One that says nothing about where its clients are still names المنطقة
  assert.deepEqual(afterCategory(CATEGORIES[2]), { area: 'تصنيف بلا مكان' });
  assert.deepEqual(afterCategory(undefined), {});
  // Picking an الإمارة keeps a التصنيف of that الإمارة and drops one of another, المنطقة with it
  assert.deepEqual(afterEmirate({ category: 1, area: 'البطين العين' }, 'العين', { categories: CATEGORIES }),
    { emirate: 'العين' });
  assert.deepEqual(afterEmirate({ category: 1, area: 'البطين العين' }, 'دبي', { categories: CATEGORIES }),
    { emirate: 'دبي', category: '', category_name: '', area: '' });
  // The categories offered are those of the الإمارة, and all of them until one is chosen
  assert.deepEqual(categoriesFor(CATEGORIES, { emirate: 'العين' }).map((c) => c.id), [1]);
  assert.deepEqual(categoriesFor(CATEGORIES, {}).map((c) => c.id), [1, 2, 3]);
  // The one already chosen is always in the list, even when it belongs elsewhere
  assert.deepEqual(categoriesFor(CATEGORIES, { emirate: 'دبي' }, 1).map((c) => c.id), [1, 2]);
});

test('package helpers', () => {
  assert.deepEqual(packageColors({ families }, 'باقة سقيا الخير مدمجة - ذهبي'), ['الابيض', 'الاسود']);
  assert.deepEqual(packageColors({ families }, 'سقيا الخير  3 صنابير'), ['الاسود مقاس طبيعي']);
  assert.deepEqual(packageColors({ families }, 'سقيا الخير ستانلس'), []);
  // لون الغطاء is asked on every package: one no family matches offers the field's own six
  const six = ['اللون الابيض', 'اللون الاسود', 'اللون الدهبي', 'اللون الخشبي', 'اللون العيناوي', 'اللون الازرق'];
  assert.deepEqual(packageColors({ families, default_colors: six }, 'سقيا الخير ستانلس'), six);
  assert.deepEqual(packageColors({ families, default_colors: six }, 'باب خلفي جرار لبرادة مدمجة'), six);
  // A package with its own list keeps it, the six are only the fallback
  assert.deepEqual(packageColors({ families, default_colors: six }, 'سقيا الخير  3 صنابير'), ['الاسود مقاس طبيعي']);
  assert.equal(packageQuantity({ group_id: 'g', details: { package_quantity: '3' } }), 3);
  assert.equal(packageQuantity({ group_id: null, details: { package_quantity: '3' } }), 1);
  assert.equal(linePrice({ unit_price: 5 }, new Map()), 5);
  assert.equal(linePrice({ product_id: '3' }, new Map([[3, 50]])), 50);
});

test('evaluateForm works out the totals like the server', () => {
  const values = {
    request_date: today(), phone: '0501234567', kind: 'x', treasury: '13', order_lines: lines,
    discount_amount: '200', approved_by: 'M', paid_amount: '6050',
  };
  const { clean, errors, required } = evaluateForm(form, values, { proof: 1 }, { products: [{ id: 3, price: 50 }] });
  // (2000 + 800) x 2 + 50, plus the inscription once per package x 2
  assert.equal(clean.subtotal_amount, 6250);
  assert.equal(clean.total_amount, 6050);
  assert.deepEqual(errors, {});
  assert.ok(required.has('approved_by'));
});

test('evaluateForm reports what is missing or wrong', () => {
  const tomorrow = new Date(Date.now() + 86400000 * 2).toISOString().slice(0, 10);
  const values = { request_date: tomorrow, phone: '12', code: '12a', kind: 'z', treasury: 'abc', discount_amount: '5', paid_amount: '1' };
  const { errors } = evaluateForm(form, values, {}, {});
  assert.equal(errors.request_date, 'التاريخ لا يمكن أن يكون في المستقبل');
  assert.equal(errors.phone, 'أدخل رقم هاتف إماراتي صحيح');
  assert.equal(errors.code, 'أرقام فقط');
  assert.equal(errors.kind, 'اختر من القائمة');
  assert.equal(errors.treasury, 'اختر من القائمة');
  assert.equal(errors.order_lines, 'مطلوب');
  assert.equal(errors.approved_by, 'مطلوب');
  assert.equal(errors.proof, 'أرفق ملفًا واحدًا على الأقل');
  // No products is the missing field: the totals worked out from it are not marked as well
  assert.equal(errors.total_amount, undefined);
  assert.equal(errors.paid_amount, undefined);
});

test('evaluateForm still reports a wrong total once nothing it is worked out from is missing', () => {
  const values = {
    request_date: today(), phone: '0501234567', kind: 'x', treasury: '13', order_lines: lines,
    discount_amount: '999999', approved_by: 'M', paid_amount: '1',
  };
  const { errors } = evaluateForm(form, values, { proof: 1 }, { products: [{ id: 3, price: 50 }] });
  assert.deepEqual(errors, { total_amount: 'neg' });
});

test('a required field left empty is the only one marked', () => {
  const complete = {
    request_date: today(), phone: '0501234567', kind: 'x', treasury: '13', order_lines: lines,
    discount_amount: '200', approved_by: 'M', paid_amount: '6050',
  };
  const catalog = { products: [{ id: 3, price: 50 }] };
  assert.deepEqual(evaluateForm(form, complete, { proof: 1 }, catalog).errors, {});
  for (const name of ['request_date', 'phone', 'kind', 'treasury', 'order_lines', 'approved_by', 'paid_amount']) {
    const values = { ...complete, [name]: name === 'order_lines' ? [] : '' };
    assert.deepEqual(Object.keys(evaluateForm(form, values, { proof: 1 }, catalog).errors), [name], name);
  }
  assert.deepEqual(Object.keys(evaluateForm(form, complete, {}, catalog).errors), ['proof']);
});

test('initialValues fills the defaults', () => {
  assert.deepEqual(initialValues(form), { request_date: today() });
});

test('search forgives Arabic spelling variants', () => {
  assert.equal(normalize('أبوظبي'), normalize('ابوظبى'));
  assert.ok(matchesQuery('مدرسة', 'المدرسه الكبرى'));
  assert.ok(matchesQuery('١٢٣', 'request 123'));
  assert.ok(!matchesQuery('دبي', 'الشارقة'));
  assert.ok(matchesQuery('', 'anything'));
});

test('a number that is no amount is refused', () => {
  const spec = { key: 'n', sections: [{ title: 's', fields: [{ name: 'paid', type: 'number', required: true, min: 0 }] }] };
  for (const typed of ['Infinity', '-Infinity', 'abc', '1e400']) {
    assert.equal(evaluateForm(spec, { paid: typed }).errors.paid, 'أدخل رقمًا صحيحًا', typed);
  }
});

test('localDay gives the local date of an ISO time', () => {
  assert.equal(localDay(''), '');
  assert.match(localDay('2026-10-21T10:00:00Z'), /^2026-10-2[01]$/);
});

test('groupLines keeps a package together and each product on its own', () => {
  const groups = groupLines([
    { name: 'a', group_id: 'g', group_name: 'Pack' }, { name: 'b', group_id: 'g', group_name: 'Pack' },
    { name: 'x', group_id: null }, { name: 'x', group_id: null },
  ]);
  assert.deepEqual(groups.map((g) => [g.groupName, g.rows.map((r) => r.index)]), [['Pack', [0, 1]], [null, [2]], [null, [3]]]);
});

test('amounts and dates are written the way the portal reads them', () => {
  assert.equal(formatAmount(8600), '8,600 درهم');
  assert.equal(formatAmount(1234.5), '1,234.5 درهم');
  assert.equal(formatDay('2026-10-21'), '21/10/2026');
  assert.equal(formatDay(''), '');
  assert.equal(formatDay('soon'), '');
});

test('coordinates are read out of a map link', () => {
  assert.equal(coordinatesFromLink('https://maps.google.com/?q=24.17870,55.60451'), '24.17870, 55.60451');
  assert.equal(coordinatesFromLink('https://www.google.com/maps/@25.2048,55.2708,15z'), '25.2048, 55.2708');
  assert.equal(coordinatesFromLink('https://maps.app.goo.gl/T3hGmfZLFvtmhrdT9'), '');
  assert.equal(coordinatesFromLink(''), '');
  assert.equal(coordinatesFromLink(null), '');
});

test('a new client is asked for type and gender, and an email only has to look like one', () => {
  const clientForm = {
    key: 'client',
    sections: [{
      title: 'c',
      fields: [
        { name: 'customer_type', type: 'select', required: true, options: ['شركة', 'فرد'], new_client: true },
        { name: 'gender', type: 'select', required: true, options: ['ذكر', 'أنثى'], new_client: true },
        { name: 'email', type: 'email', required: false, new_client: true },
      ],
    }],
  };
  // Until the phone search finds nobody, the client is not known to be new: nothing is asked
  assert.deepEqual(evaluateForm(clientForm, {}).errors, {});
  assert.deepEqual(evaluateForm(clientForm, { new_client: false, email: 'nope' }).errors, {});
  const asked = evaluateForm(clientForm, { new_client: true });
  assert.deepEqual(asked.errors, { customer_type: 'مطلوب', gender: 'مطلوب' });
  assert.ok(!asked.required.has('email'));
  for (const bad of ['name@', 'name example.com', 'name@example', '@example.com']) {
    assert.match(evaluateForm(clientForm, { new_client: true, email: bad }).errors.email, /بريدًا إلكترونيًا صحيحًا/, bad);
  }
  const done = evaluateForm(clientForm, { new_client: true, customer_type: 'شركة', gender: 'أنثى', email: ' Office@Example.COM ' });
  assert.deepEqual(done.errors, {});
  assert.equal(done.clean.email, 'office@example.com');
});

test('samePerson: a name written differently is the same person, someone else is not', () => {
  // Request 162: a new client's name against the client whose second number was his
  assert.equal(samePerson('حمد يوسف محمد السناني', 'محمد سعيد سهيل'), false);
  assert.equal(samePerson('فهد سعيد العطر', 'محمد سعيد العطر'), false);
  assert.equal(samePerson('محمد سعيد', 'محمد سعيد سهيل'), true);
  assert.equal(samePerson('حمد السنانى', 'حمد السناني'), true);
  assert.equal(samePerson('عبدالله احمد', 'عبد الله احمد'), true);
  assert.equal(samePerson('مُحمّد علي', 'محمد علي'), true);
  assert.equal(samePerson('Qaiser nadeem', 'QAISER NADEEM Mohd Latif'), true);
  assert.equal(samePerson('', 'محمد'), true);
});

// سعر الكتابة as the real form sends it: charged only while الكتابة المطلوبة is not «لا يوجد»,
// because the invoice carries a line for it only then (request 176, invoice 06629)
const NO_INSCRIPTION = ['لا يوجد', 'لايوجد', 'لا توجد', 'لاتوجد'];
const charging = [
  { name: 'inscription', blank_value: 'لا يوجد' },
  { name: 'inscription_price', charge: true, required_if: { field: 'inscription', not_in: NO_INSCRIPTION } },
];
const charge = (details, value) => changedDetails(charging, SAQYA, 'inscription', details, value);

test('a price does not apply to an inscription of «لا يوجد», and goes with it', () => {
  const price = charging[1];
  assert.equal(chargeApplies(charging, price, { inscription: 'بسم الله' }), true);
  assert.equal(chargeApplies(charging, price, { inscription: 'لا يوجد' }), false);
  // An empty الكتابة المطلوبة stands for «لا يوجد», as the server reads it before anything else
  assert.equal(chargeApplies(charging, price, {}), false);
  // Choosing «لا يوجد» empties the price with it, so none is sent with nothing to charge it for
  assert.equal(charge({ inscription: 'بسم الله', inscription_price: '300' }, 'لا يوجد').inscription_price, '');
  // A real inscription keeps what was typed
  assert.equal(charge({ inscription: 'لا يوجد', inscription_price: '' }, 'بسم الله').inscription, 'بسم الله');
  assert.equal(charge({ inscription: 'بسم الله', inscription_price: '300' }, 'نص آخر').inscription_price, '300');
});

// The package profiles as the order_lines field carries them (options.PACKAGE_PROFILES): the same
// shape, cut down to what these tests need. The backend's tests check the real table's contents.
const PROFILES = [
  { match: ['فلتر دش'], fields: ['cooler_color'], labels: { cooler_color: 'اللون' }, options: { cooler_color: ['أبيض', 'أسود'] } },
  { match: ['باب خلفي'], fields: ['cooler_color', 'w_direction', 'manufacturing_notes'], labels: { cooler_color: 'لون الباب' } },
  { match: ['نبع المزن'], needs: ['مدمج'], fields: ['cooler_color', 'front_design', 'design_version', 'inscription'] },
  { match: ['نبع المزن'], fields: ['cooler_color', 'front_design', 'inscription'] },
];
const LINE = [
  { name: 'package_quantity', package_only: true },
  { name: 'cooler_color', label: 'لون البرادة', type: 'select', options: ['أبيض', 'أسود', 'ذهبي', 'أخرى'] },
  { name: 'front_design' }, { name: 'design_version' }, { name: 'w_direction' },
  { name: 'inscription' }, { name: 'inscription_price', beside: 'inscription', charge: true },
  { name: 'manufacturing_notes' },
  { name: 'item_price', open_price_only: true },
];
const names = (fields) => fields.map((d) => d.name);

test('a package takes the first profile its name matches, and none means every field', () => {
  assert.equal(packageProfile(PROFILES, 'باب خلفي مفصلي لبرادة خاصة (Special)').labels.cooler_color, 'لون الباب');
  assert.ok(packageProfile(PROFILES, 'باقة نبع المزن مدمجه - برادة مياه').fields.includes('design_version'));
  assert.ok(!packageProfile(PROFILES, 'باقة برادة نبع المزن - 3 صنابير').fields.includes('design_version'));
  assert.equal(packageProfile(PROFILES, '  باب   خلفي جرار '), PROFILES[1]);
  assert.equal(packageProfile(PROFILES, 'لوح خلفي ثابت لبرادة مدمجة'), null);
  assert.equal(packageProfile(undefined, 'باب خلفي جرار'), null);
  assert.deepEqual(packageFields(LINE, 'لوح خلفي ثابت لبرادة مدمجة', PROFILES), LINE);
});

test('a door shows its colour as لون الباب, its W direction and notes, and nothing to inscribe', () => {
  const door = packageFields(LINE, 'باب خلفي جرار لبرادة مدمجة', PROFILES);
  assert.deepEqual(names(door), ['package_quantity', 'cooler_color', 'w_direction', 'manufacturing_notes', 'item_price']);
  const colour = door.find((d) => d.name === 'cooler_color');
  assert.equal(colour.label, 'لون الباب');
  assert.deepEqual(colour.options, LINE[1].options);
  // The field list itself is left as it was
  assert.equal(LINE[1].label, 'لون البرادة');
});

test('the shower filter offers one colour of two, and سعر الكتابة goes with الكتابة', () => {
  const colour = packageFields(LINE, 'فلتر دش Future Life', PROFILES).find((d) => d.name === 'cooler_color');
  assert.deepEqual([colour.label, colour.options], ['اللون', ['أبيض', 'أسود']]);
  const naba = names(packageFields(LINE, 'باقة برادة نبع المزن - 3 صنابير', PROFILES));
  assert.ok(naba.includes('inscription') && naba.includes('inscription_price'));
});

test('the subtotal counts only the charges the package asks for, as the server does', () => {
  // evaluateForm itself, on a form with one order_lines field carrying the profiles
  const form = { sections: [{ fields: [
    { name: 'order_lines', type: 'order_lines', subtotal_field: 'subtotal', line_fields: LINE, package_profiles: PROFILES },
  ] }] };
  const subtotal = (group_name) => evaluateForm(form, { order_lines: [{
    product_id: '1', quantity: 1, unit_price: 100, group_id: 'g', group_name,
    details: { inscription: 'بسم الله', inscription_price: '300' },
  }] }, {}, {}).clean.subtotal;
  // نبع المزن asks for an inscription, so its 300 counts; a door does not, so it does not
  assert.equal(subtotal('باقة برادة نبع المزن - 3 صنابير'), 400);
  assert.equal(subtotal('باب خلفي جرار لبرادة مدمجة'), 100);
  // A form with no profiles counts every charge, as before
  const plain = { sections: [{ fields: [{ ...form.sections[0].fields[0], package_profiles: undefined }] }] };
  assert.equal(evaluateForm(plain, { order_lines: [{ product_id: '1', quantity: 1, unit_price: 100, group_id: 'g',
    group_name: 'باب خلفي جرار لبرادة مدمجة', details: { inscription_price: '300' } }] }, {}, {}).clean.subtotal, 400);
});

// سقيا الخير's verse as the form carries it now: no «work», so ملحقات التركيب is never touched
const quiet = [
  { name: 'inscription', work_field: 'work', price_field: 'price',
    default_by_package: [{ match: ['سقيا الخير'], exclude: [], text: VERSE, price: '0' }] },
  { name: 'work' }, { name: 'price' },
];
const pickQuiet = (details, value) => changedDetails(quiet, SAQYA, 'inscription', details, value);

test('a package verse with no work leaves ملحقات التركيب as it was, and still brings its price', () => {
  const picked = pickQuiet({ work: 'تمديد مياه وكهرباء • فلتر' }, VERSE);
  assert.deepEqual(picked, { work: 'تمديد مياه وكهرباء • فلتر', inscription: VERSE, price: '0' });
  assert.equal(pickQuiet({}, VERSE).work, undefined);
  // Choosing another one takes the free price away and still leaves the box alone
  const other = pickQuiet(picked, 'نص آخر');
  assert.equal(other.work, 'تمديد مياه وكهرباء • فلتر');
  assert.equal(other.price, '');
});

// نسبة الخصم beside قيمة الخصم, as the shared amounts section declares them
const PERCENT = { name: 'discount_percent', type: 'number', min: 0, max: 100, percent_of: 'subtotal_amount', amount_field: 'discount_amount' };

test('a percentage typed gives the amount in whole dirhams; an amount gives the percentage to two places', () => {
  const byPercent = { subtotal_amount: 7537, discount_percent: 10 };
  discountFromPercent([PERCENT], { discount_percent_basis: 'percent' }, byPercent);
  assert.equal(byPercent.discount_amount, 754);               // 753.7, to the dirham
  const half = { subtotal_amount: 1000, discount_percent: 12.55 };
  discountFromPercent([PERCENT], { discount_percent_basis: 'percent' }, half);
  assert.equal(half.discount_amount, 126);                    // 125.5: a half goes up, as on the server
  const byAmount = { subtotal_amount: 6200, discount_amount: 200 };
  discountFromPercent([PERCENT], {}, byAmount);               // no basis: the amount was typed
  assert.equal(byAmount.discount_percent, 3.23);
});

test('the one typed stays, the other is replaced, and emptying it empties both', () => {
  const stale = { subtotal_amount: 6200, discount_percent: 10, discount_amount: 999 };
  discountFromPercent([PERCENT], { discount_percent_basis: 'percent' }, stale);
  assert.equal(stale.discount_amount, 620);
  const keptAmount = { subtotal_amount: 6200, discount_percent: 50, discount_amount: 620 };
  discountFromPercent([PERCENT], { discount_percent_basis: 'amount' }, keptAmount);
  assert.equal(keptAmount.discount_percent, 10);
  const emptied = { subtotal_amount: 6200, discount_amount: 620 };
  discountFromPercent([PERCENT], { discount_percent_basis: 'percent' }, emptied);
  assert.ok(!('discount_amount' in emptied));
  // With no subtotal yet there is nothing to work from: what was typed is left as it is
  const early = { discount_percent: 10 };
  discountFromPercent([PERCENT], { discount_percent_basis: 'percent' }, early);
  assert.ok(!('discount_amount' in early));
});

test('the total on the form takes off the amount a percentage works out to', () => {
  const form = { sections: [{ fields: [
    { name: 'subtotal_amount', type: 'number', money: true, required: true },
    { name: 'discount_amount', type: 'number', money: true },
    PERCENT,
    { name: 'total_amount', type: 'number', money: true, computed: ['subtotal_amount', 'discount_amount'], negative_message: 'x' },
  ] }] };
  const { clean } = evaluateForm(form, { subtotal_amount: '6200', discount_percent: '10', discount_percent_basis: 'percent' }, {}, {});
  assert.deepEqual([clean.discount_amount, clean.total_amount], [620, 5580]);
  // And a percentage that grows with the order, which an amount typed would not
  const bigger = evaluateForm(form, { subtotal_amount: '8000', discount_percent: '10', discount_percent_basis: 'percent' }, {}, {}).clean;
  assert.equal(bigger.discount_amount, 800);
  const fixed = evaluateForm(form, { subtotal_amount: '8000', discount_amount: '620', discount_percent: '10' }, {}, {}).clean;
  assert.deepEqual([fixed.discount_amount, fixed.discount_percent], [620, 7.75]);
});

// ---------- paying beyond the total, and the client's balance ----------

const PAYING = { sections: [{ fields: [
  { name: 'total_amount', type: 'number', money: true, required: true },
  { name: 'paid_amount', type: 'number', money: true, min: 0 },
  { name: 'remaining_amount', type: 'number', money: true, computed: ['total_amount', 'paid_amount'], floor: 0 },
  { name: 'overpaid_amount', type: 'number', money: true, computed: ['paid_amount', 'total_amount'], floor: 0, hide_when_zero: true },
] }] };

test('what is paid beyond the total is worked out, and nothing is left to pay', () => {
  const { clean, errors } = evaluateForm(PAYING, { total_amount: '6000', paid_amount: '6300' }, {}, {});
  assert.deepEqual([clean.remaining_amount, clean.overpaid_amount], [0, 300]);
  assert.deepEqual(errors, {});
});

test('an order paid no more than its total holds no extra at all', () => {
  const exact = evaluateForm(PAYING, { total_amount: '6000', paid_amount: '6000' }, {}, {}).clean;
  assert.equal(exact.remaining_amount, 0);
  assert.ok(!('overpaid_amount' in exact));
  const part = evaluateForm(PAYING, { total_amount: '6000', paid_amount: '1000' }, {}, {}).clean;
  assert.equal(part.remaining_amount, 5000);
  assert.ok(!('overpaid_amount' in part));
  // What the browser may still hold from an earlier amount is not kept
  const stale = evaluateForm(PAYING, { total_amount: '6000', paid_amount: '1000', overpaid_amount: '300' }, {}, {}).clean;
  assert.ok(!('overpaid_amount' in stale));
});

test('a form that does not take more than its total still refuses it', () => {
  const strict = { sections: [{ fields: [
    ...PAYING.sections[0].fields.slice(0, 2),
    { name: 'remaining_amount', type: 'number', money: true, computed: ['total_amount', 'paid_amount'], negative_message: 'أكبر' },
  ] }] };
  const { errors } = evaluateForm(strict, { total_amount: '6000', paid_amount: '6300' }, {}, {});
  assert.equal(errors.remaining_amount, 'أكبر');
});

test('the balance of a found client shows what they owe and what they hold, 0 included', () => {
  const ready = (balance) => ({ status: 'ready', balance });
  const lines = (info) => balanceView(info).lines.map(([, label, amount]) => [label, amount]);
  assert.deepEqual(lines(ready({ owed: 1250, credit: 500 })), [['المستحق عليه', 1250], ['رصيد دائن', 500]]);
  // Nothing either way still shows, so the salesperson sees it was checked
  assert.deepEqual(lines(ready({ owed: 0, credit: 0 })), [['المستحق عليه', 0], ['رصيد دائن', 0]]);
  // Daftra would not say what they hold (null: «غير متاح»): what they owe is still shown
  assert.deepEqual(lines(ready({ owed: 800, credit: null })), [['المستحق عليه', 800], ['رصيد دائن', null]]);
  // An older answer with no balance in it says neither
  assert.deepEqual(lines(ready(undefined)), [['المستحق عليه', null], ['رصيد دائن', null]]);
  // Not answered yet, or failed: the same two lines stand, with no figure in them, so the block is
  // there with the client's note and nothing moves when Daftra answers
  const empty = [['المستحق عليه', null], ['رصيد دائن', null]];
  assert.equal(balanceView({ status: 'loading' }).status, 'loading');
  assert.deepEqual(lines({ status: 'loading' }), empty);
  assert.equal(balanceView({ status: 'error', message: 'x' }).status, 'error');
  assert.deepEqual(lines({ status: 'error', message: 'x' }), empty);
  // A figure left over from another answer is never shown while waiting
  assert.deepEqual(lines({ status: 'loading', balance: { owed: 5, credit: 5 } }), empty);
  // No client found
  assert.equal(balanceView(null), null);
});

test('رصيد سابق is the found client\'s credit, and only when Daftra says they hold some', () => {
  const ready = (balance) => ({ status: 'ready', balance });
  assert.equal(clientCredit(ready({ owed: 0, credit: 500 })), 500);
  assert.equal(clientCredit(ready({ owed: 1250, credit: 0 })), null);
  assert.equal(clientCredit(ready({ owed: 0, credit: null })), null);
  assert.equal(clientCredit(ready(undefined)), null);
  assert.equal(clientCredit({ status: 'loading' }), null);
  assert.equal(clientCredit({ status: 'error' }), null);
  assert.equal(clientCredit(null), null);
});

// ---------- the client's credit taken off what is left to pay ----------

// As the forms define it: رصيد سابق beside المبلغ المدفوع, and what is taken off it before المتبقي
const CREDIT = { sections: [{ fields: [
  PAYING.sections[0].fields[0],
  PAYING.sections[0].fields[1],
  { name: 'previous_credit', label: 'رصيد سابق', type: 'number', money: true, client_credit: true, pair_with: 'paid_amount' },
  { name: 'credit_applied', type: 'number', money: true, computed: ['total_amount', 'paid_amount'], floor: 0, cap: 'previous_credit', hide_when_zero: true },
  { name: 'remaining_amount', type: 'number', money: true, computed: ['total_amount', 'paid_amount', 'credit_applied'], floor: 0 },
  PAYING.sections[0].fields[3],
] }] };
const withCredit = (paid, credit = '500') => evaluateForm(CREDIT, { total_amount: '6000', paid_amount: paid, previous_credit: credit }, {}, {});
const amountsOf = (clean) => ['previous_credit', 'credit_applied', 'remaining_amount', 'overpaid_amount'].map((name) => clean[name]);

test('the client\'s credit pays what the payment leaves, up to all of it', () => {
  // Less than what is left: all of it is used
  assert.deepEqual(amountsOf(withCredit('1000').clean), [500, 500, 4500, undefined]);
  // More than what is left: only that much, and nothing remains
  assert.deepEqual(amountsOf(withCredit('5800').clean), [500, 200, 0, undefined]);
  assert.deepEqual(withCredit('5800').errors, {});
});

test('a payment of the whole total, or more, uses none of the credit', () => {
  const exact = withCredit('6000').clean;
  assert.ok(!('credit_applied' in exact));
  assert.equal(exact.remaining_amount, 0);
  const more = withCredit('6300').clean;
  assert.ok(!('credit_applied' in more));
  assert.deepEqual([more.remaining_amount, more.overpaid_amount], [0, 300]);
});

test('with no credit the amounts are exactly what they were without it', () => {
  for (const paid of ['1000', '6000', '6300', '']) {
    for (const credit of [undefined, '', '0']) {
      const values = { total_amount: '6000', paid_amount: paid, ...(credit === undefined ? {} : { previous_credit: credit }) };
      const before = evaluateForm(PAYING, values, {}, {});
      const now = evaluateForm(CREDIT, values, {}, {});
      assert.ok(!('credit_applied' in now.clean), `paid ${paid}, credit ${credit}`);
      assert.deepEqual(without(now.clean, 'previous_credit'), before.clean);
      assert.deepEqual(now.errors, before.errors);
    }
  }
});

test('رصيد سابق is never asked for, and a credit that is no number is refused', () => {
  const { errors, required } = withCredit('1000', '');
  assert.ok(!required.has('previous_credit'));
  assert.ok(!('previous_credit' in errors));
  assert.equal(withCredit('1000', 'abc').errors.previous_credit, 'أدخل رقمًا صحيحًا');
});

test('nothing paid in cash is enough when the balance pays something, and not otherwise', () => {
  const form = { sections: [{ fields: CREDIT.sections[0].fields.map((spec) => (
    spec.name === 'paid_amount' ? { ...spec, required: true, positive_unless: 'credit_applied' } : spec)) }] };
  const sent = (paid, credit) => evaluateForm(form, { total_amount: '6000', paid_amount: paid, previous_credit: credit }, {}, {});
  const covered = sent('0', '500');
  assert.ok(!('paid_amount' in covered.errors));
  assert.deepEqual([covered.clean.credit_applied, covered.clean.remaining_amount], [500, 5500]);
  assert.equal(sent('0', '').errors.paid_amount, 'يجب أن يكون أكبر من صفر');
  assert.equal(sent('0', '0').errors.paid_amount, 'يجب أن يكون أكبر من صفر');
  assert.ok(!('paid_amount' in sent('1000', '').errors));
  // Left empty it is asked for like any required field, whatever the balance
  assert.ok(sent('', '500').errors.paid_amount);
});

function without(object, ...names) {
  return Object.fromEntries(Object.entries(object).filter(([name]) => !names.includes(name)));
}
