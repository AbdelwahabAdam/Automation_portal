// Mirrors backend/app/forms/validation.py so the user sees errors before submitting.
// The backend validates again and stays the source of truth.

// A UAE number in the local form the portal keeps them in (0501234567): a mobile on 05 and one of
// the operators' own digits, or a landline on its emirate's code — 2 أبوظبي, 3 العين, 4 دبي,
// 6 الشارقة وعجمان وأم القيوين, 7 رأس الخيمة, 9 الفجيرة. Mirrors PHONE_RE in forms/validation.py.
const PHONE_RE = /^0(?:5[024568]\d{7}|[234679]\d{7})$/;

// Any way a number was written, as the portal keeps it: +971 50…, 00971 50…, 50… and ٠٥٠… all
// become 0501234567. This is the form the client list and Daftra are searched by.
export function localPhone(raw) {
  const number = toLatinDigits(String(raw ?? '')).replace(/\D/g, '');
  const national = number.startsWith('00971') ? number.slice(5)
    : number.startsWith('971') ? number.slice(3) : number;
  return !national || national.startsWith('0') ? national : `0${national}`;
}
const ARABIC_DIGITS = '٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹';
// Field types 'product' and 'staff' hold a name picked from a Daftra list
const DEFAULT_MAX_LENGTH = { text: 300, product: 300, staff: 300, textarea: 3000 };
// Mirrors EMAIL_RE in forms/validation.py
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

// A field marked new_client (نوع العميل, الجنس, البريد) belongs on the form only while the phone search
// has found no client (values.new_client, set by form/ClientLookup.jsx); the server decides the same way
export const fieldApplies = (spec, values) => !spec.new_client || values.new_client === true;
// Field types holding the id of a row in a Daftra list (see DAFTRA_LIST_TYPES in backend/app/forms/validation.py)
export const DAFTRA_LIST_TYPES = ['daftra_order_source', 'daftra_treasury', 'daftra_client_category',
  'daftra_client_invoice', 'daftra_staff'];

const toLatinDigits = (text) => text.replace(/[٠-٩۰-۹]/g, (d) => ARABIC_DIGITS.indexOf(d) % 10);

export const allFields = (formType) => formType.sections.flatMap((section) => section.fields);
export const isInput = (spec) => !['files', 'auto_user'].includes(spec.type) && !spec.computed;

// Returns the phone as digits when it is a valid UAE number, otherwise null
export function normalizePhone(raw) {
  const value = localPhone(raw);
  return PHONE_RE.test(value) ? value : null;
}

export function today() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

// Returns [value, error] for one input field; an empty value comes back as null
function cleanValue(spec, raw) {
  if (spec.type === 'multiselect') {
    const chosen = Array.isArray(raw) ? raw.filter((v) => spec.options.includes(v)) : [];
    return [chosen.length ? chosen : null, null];
  }
  if (spec.type === 'order_lines') {
    const lines = Array.isArray(raw) ? raw.filter((l) => l && l.product_id && Number(l.quantity) > 0) : [];
    return [lines.length ? lines : null, null];
  }
  let value = raw == null || typeof raw === 'object' ? '' : String(raw).trim();
  if (value === '') return [null, null];

  if (spec.type === 'number') {
    const number = Number(toLatinDigits(value).replace(/,/g, ''));
    // Infinity reads as a number but is no amount
    if (!Number.isFinite(number)) return [null, 'أدخل رقمًا صحيحًا'];
    if (spec.integer && !Number.isInteger(number)) return [null, 'أدخل عددًا بدون كسور'];
    if (spec.positive && number <= 0) return [null, 'يجب أن يكون أكبر من صفر'];
    if (spec.min !== undefined && number < spec.min) return [null, `الحد الأدنى ${spec.min}`];
    if (spec.max !== undefined && number > spec.max) return [null, `الحد الأقصى ${spec.max}`];
    return [Math.round(number * 100) / 100, null];
  }
  if (spec.type === 'phone') {
    value = localPhone(value);
    return PHONE_RE.test(value) ? [value, null] : [null, 'أدخل رقم هاتف إماراتي صحيح'];
  }
  if (spec.type === 'date') {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || Number.isNaN(Date.parse(value))) return [null, 'أدخل تاريخًا صحيحًا'];
    if (spec.not_future && value > today()) return [null, 'التاريخ لا يمكن أن يكون في المستقبل'];
    return [value, null];
  }
  if (spec.type === 'select') return spec.options.includes(value) ? [value, null] : [null, 'اختر من القائمة'];
  if (DAFTRA_LIST_TYPES.includes(spec.type)) return /^\d+$/.test(value) ? [Number(value), null] : [null, 'اختر من القائمة'];
  if (spec.type === 'email') {
    return value.length <= 200 && EMAIL_RE.test(value)
      ? [value.toLowerCase(), null] : [null, 'أدخل بريدًا إلكترونيًا صحيحًا، مثل name@example.com'];
  }

  const maxLength = spec.max_length ?? DEFAULT_MAX_LENGTH[spec.type];
  if (value.length > maxLength) return [null, `الحد الأقصى ${maxLength} حرفًا`];
  if (spec.pattern) {
    value = toLatinDigits(value);
    if (!new RegExp(spec.pattern).test(value)) return [null, spec.pattern_message || 'صيغة غير صحيحة'];
  }
  return [value, null];
}

// The cooler colours a package's name allows (a "package_color" field's families, from backend/app/forms/options.py
// PACKAGE_COLOR_FAMILIES): the first family whose words the name contains; [] when none matches
export function packageColors(spec, packageName) {
  const name = String(packageName ?? '').split(/\s+/).filter(Boolean).join(' ');
  const family = (spec.families || []).find((f) => f.match.some((w) => name.includes(w)) && !f.exclude.some((w) => name.includes(w)));
  return family ? family.colors : [];
}

// How many of the package a line was picked from (its «الكمية»); 1 for a product picked on its own
export function packageQuantity(line) {
  const value = Number(line.details?.package_quantity);
  return line.group_id && Number.isInteger(value) && value > 0 ? value : 1;
}

// A line's price: what the product costs inside the package it was picked from, else its own price
// lineFields: a field marked line_price holds the price of a line whose product has none of its
// own («أخرى» on اعمال اضافية). The server works it out again the same way.
export function linePrice(line, priceById, lineFields = []) {
  const typed = lineFields.find((dspec) => dspec.line_price);
  const written = typed && line.details?.[typed.name];
  if (written !== undefined && written !== '' && written !== null) return Number(toLatinDigits(String(written))) || 0;
  return typeof line.unit_price === 'number' ? line.unit_price : priceById.get(Number(line.product_id)) || 0;
}

// A Google Maps link that carries the coordinates ("…@24.17870,55.60451…", "?q=24.17870,55.60451");
// '' when it has none
const COORDINATES_IN_LINK = /(-?\d{1,2}\.\d{3,})\s*,\s*(-?\d{1,3}\.\d{3,})/;

export function coordinatesFromLink(url) {
  const found = String(url ?? '').match(COORDINATES_IN_LINK);
  return found ? `${found[1]}, ${found[2]}` : '';
}

// Lines from the same package pick stay together as one group, in the order first added; a product
// picked on its own is a group of its own. Each group: { key, groupName (null for a product), rows: [{ line, index }] }
export function groupLines(lines) {
  const order = [];
  const byKey = new Map();
  lines.forEach((line, index) => {
    const key = line.group_id || `single-${index}`;
    if (!byKey.has(key)) {
      byKey.set(key, { key, groupName: line.group_id ? line.group_name : null, rows: [] });
      order.push(key);
    }
    byKey.get(key).rows.push({ line, index });
  });
  return order.map((key) => byKey.get(key));
}

function conditionMet(condition, clean) {
  const value = clean[condition.field];
  if ('equals' in condition) return value === condition.equals;
  if ('in' in condition) return condition.in.includes(value);
  if ('not_in' in condition) return !condition.not_in.includes(value);
  return typeof value === 'number' && value > condition.gt;
}

// Cleans the typed values and works out computed fields.
// catalog gives the live price of each product, for a field an order_lines field feeds (its "subtotal_field").
// Returns { clean, errors, required } where required is the set of field names needed right now.
export function evaluateForm(formType, values, fileCounts = {}, catalog = {}) {
  const fields = allFields(formType).filter((spec) => fieldApplies(spec, values));
  const clean = {};
  const errors = {};

  for (const spec of fields.filter(isInput)) {
    const [value, error] = cleanValue(spec, values[spec.name]);
    if (error) errors[spec.name] = error;
    else if (value !== null) clean[spec.name] = value;
  }
  for (const spec of fields) {
    if (spec.type !== 'order_lines' || !spec.subtotal_field) continue;
    const priceById = new Map((catalog.products || []).map((p) => [p.id, p.price || 0]));
    const charges = (spec.line_fields || []).filter((d) => d.charge).map((d) => d.name);
    const lines = Array.isArray(values[spec.name]) ? values[spec.name] : [];
    const seenGroups = new Set();
    let total = 0;
    for (const line of lines) {
      // A package's «الكمية» is already in its products' quantities
      total += linePrice(line, priceById, spec.line_fields || []) * (Number(line.quantity) || 0);
      // A package's details sit on each of its lines, so its charges (e.g. the inscription) count once per package
      if (!line.group_id || !seenGroups.has(line.group_id)) {
        total += charges.reduce((sum, name) => sum + (Number(toLatinDigits(String(line.details?.[name] ?? ''))) || 0), 0) * packageQuantity(line);
      }
      if (line.group_id) seenGroups.add(line.group_id);
    }
    clean[spec.subtotal_field] = Math.round(total * 100) / 100;
  }
  for (const spec of fields.filter((s) => s.computed)) {
    if (spec.name in clean || !spec.computed.length) continue;
    const [first, ...rest] = spec.computed.map((name) => clean[name]);
    if (first === undefined) continue;
    const result = Math.round((first - rest.reduce((sum, v) => sum + (v || 0), 0)) * 100) / 100;
    clean[spec.name] = result;
    if (result < 0) errors[spec.name] = spec.negative_message;
  }
  // A field that must equal another (e.g. the amount paid must be the whole total)
  for (const spec of fields.filter((s) => s.must_equal)) {
    if (spec.name in clean && spec.must_equal in clean && !errors[spec.name]
        && Math.abs(clean[spec.name] - clean[spec.must_equal]) > 0.005) {
      errors[spec.name] = spec.must_equal_message || 'القيمتان يجب أن تتساويا';
    }
  }

  const required = new Set();
  for (const spec of fields) {
    if (!(spec.required || (spec.required_if && conditionMet(spec.required_if, clean)))) continue;
    required.add(spec.name);
    if (errors[spec.name]) continue;
    if (spec.type === 'files') {
      if (!fileCounts[spec.name]) errors[spec.name] = 'أرفق ملفًا واحدًا على الأقل';
    } else if (isInput(spec) && !(spec.name in clean)) {
      errors[spec.name] = 'مطلوب';
    }
  }
  return { clean, errors, required };
}

export function initialValues(formType) {
  const values = {};
  for (const spec of allFields(formType)) {
    if (spec.default) values[spec.name] = spec.default === 'today' ? today() : spec.default;
  }
  return values;
}
