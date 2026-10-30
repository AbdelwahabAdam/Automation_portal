// node --test tests/  (npm test). The browser-side checks in modules/requests/validation.js, the
// formatting in lib/format.js and the search helpers in ds/match.js; the backend repeats the form
// checks (backend/tests/modules/form_engine/test_forms.py).
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { matchesQuery, normalize } from '../src/ds/match.js';
import { formatAmount, formatDay, localDay } from '../src/lib/format.js';
import {
  coordinatesFromLink, evaluateForm, groupLines, initialValues, linePrice, normalizePhone, packageColors,
  packageDefault, packageQuantity, today,
} from '../src/modules/requests/validation.js';

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

test('package helpers', () => {
  assert.deepEqual(packageColors({ families }, 'باقة سقيا الخير مدمجة - ذهبي'), ['الابيض', 'الاسود']);
  assert.deepEqual(packageColors({ families }, 'سقيا الخير  3 صنابير'), ['الاسود مقاس طبيعي']);
  assert.deepEqual(packageColors({ families }, 'سقيا الخير ستانلس'), []);
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
  assert.equal(errors.total_amount, 'neg');
  assert.equal(errors.paid_amount, 'all');
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
