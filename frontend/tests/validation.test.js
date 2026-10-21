// node --test tests/  (npm test). The browser-side checks in src/validation.js and the search
// helpers in src/formsMeta.js; the backend repeats the form checks (backend/tests/test_forms.py).
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { formatAmount, formatDay, localDay, matchesQuery, normalize } from '../src/formsMeta.js';
import {
  coordinatesFromLink, evaluateForm, groupLines, initialValues, linePrice, normalizePhone, packageColors, packageQuantity, today,
} from '../src/validation.js';

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

test('normalizePhone accepts UAE numbers written any way', () => {
  assert.equal(normalizePhone('050 123 4567'), '0501234567');
  assert.equal(normalizePhone('٠٥٠١٢٣٤٥٦٧'), '0501234567');
  assert.equal(normalizePhone('+971501234567'), '+971501234567');
  assert.equal(normalizePhone('12345'), null);
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
