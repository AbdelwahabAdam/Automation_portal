import { useEffect, useMemo, useRef, useState } from 'react';
import { api, openAttachment, uploadAttachment } from './api.js';
import {
  ActionBar, Alert, Badge, Button, Choice, Dialog, Field, Icon, InputBox, Loading, PageHeader, Section, Select, TextArea, TextInput,
} from './ds/index.jsx';
import { formatMoney } from './formsMeta.js';
import {
  DAFTRA_LIST_TYPES, allFields, packageColors, evaluateForm, initialValues, linePrice, normalizePhone, packageQuantity,
} from './validation.js';

// Form fields that an existing Daftra client can fill
const CLIENT_FIELDS = ['client_code', 'customer_name', 'phone', 'emirate', 'area', 'street', 'house', 'location_url'];
const ACCEPT = '.jpg,.jpeg,.png,.webp,.heic,.pdf,.mp4,.mov,.doc,.docx';
// Sections open when a form starts; the rest are folded until needed
const OPEN_AT_START = 4;
// Selects with this many options or fewer show as option cards, as in the design
const CHOICE_MAX_OPTIONS = 3;

const sizeText = (bytes) => (bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`);

function FileField({ spec, files, busy, invalid, onAdd, onRemove }) {
  return (
    <div className="fl-files">
      {files.map((file) => (
        <div key={file.id} className="fl-file">
          <Icon name={/^image\//.test(file.content_type) ? 'image' : 'file-text'} size={18} />
          <button type="button" className="fl-link fl-file__name" onClick={() => openAttachment(file.id)}><bdi>{file.filename}</bdi></button>
          <span className="fl-file__size" data-fl-num>{sizeText(file.size)}</span>
          <Button size="sm" variant="ghost" icon="trash" iconOnly label={`حذف ${file.filename}`} onClick={() => onRemove(file)} />
        </div>
      ))}
      <label className={busy ? 'fl-dropzone fl-dropzone--busy' : 'fl-dropzone'} style={invalid ? { borderColor: 'var(--fl-color-border-error)' } : undefined}>
        <Icon name={busy ? 'loader' : 'upload'} size={18} />
        {busy ? 'جارٍ الرفع…' : 'إضافة ملف'}
        <input
          type="file" multiple hidden accept={ACCEPT} disabled={busy} aria-label={spec.label}
          onChange={(e) => { onAdd(spec.name, [...e.target.files]); e.target.value = ''; }}
        />
      </label>
    </div>
  );
}

// What a product name says about the cooler, e.g. "WATER COOLER BLACK 3 T"
function guessFromProductName(name) {
  const guess = {};
  if (/black|[اأ]سود/i.test(name)) guess.cooler_color = 'أسود';
  else if (/white|[اأ]بيض/i.test(name)) guess.cooler_color = 'أبيض';
  else if (/gold|[ذد]هب/i.test(name)) guess.cooler_color = 'ذهبي';
  const outlets = name.match(/(\d)\s*(?:T\b|tap|wolf|ولف)|\bT\s*(\d)\b/i);
  if (outlets) guess.outlets = outlets[1] || outlets[2];
  return guess;
}

function ProductPicker({ spec, value, invalid, catalog, onType, onPick }) {
  const [open, setOpen] = useState(false);
  const { products } = catalog;
  const matches = useMemo(() => {
    if (!products) return [];
    const words = (value ?? '').toLowerCase().split(/\s+/).filter(Boolean);
    return products
      .filter((p) => words.every((word) => p.name.toLowerCase().includes(word) || p.name_ar.includes(word)))
      .slice(0, 40);
  }, [products, value]);
  const placeholder = products ? 'ابحث باسم المنتج' : catalog.productsError ? '' : 'جارٍ تحميل المنتجات…';

  return (
    <div className="fl-suggest">
      <TextInput
        id={spec.name} icon="search" dir="auto" autoComplete="off" value={value ?? ''} invalid={invalid} placeholder={placeholder}
        role="combobox" aria-expanded={open && Boolean(products)} aria-autocomplete="list"
        onChange={(e) => { onType(spec.name, e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}
      />
      {open && products && (
        <div className="fl-suggest__list" role="listbox">
          {matches.map((product) => (
            <button
              key={product.id} type="button" role="option" aria-selected="false" className="fl-suggest__item"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => { onPick(spec.name, product); setOpen(false); }}
            >
              <bdi>{product.name}</bdi>
              <small>{product.name_ar}{product.price ? ` · ${product.price} درهم` : ''}</small>
            </button>
          ))}
          {!matches.length && <p className="fl-suggest__empty">لا يوجد منتج مطابق.</p>}
        </div>
      )}
    </div>
  );
}

// A repeatable list of products/packages for one request. Picking a package keeps its name
// as a group the user can fold or open; picking a product adds it as its own row. Lines keep
// a group_id/group_name so the grouping survives a saved draft.
function OrderLines({ spec, value, invalid, catalog, onChange, lineErrors }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [openGroups, setOpenGroups] = useState(() => new Set());
  const lines = value ?? [];
  const lineFields = spec.line_fields || [];
  // items: "maintenance" offers only the catalog's maintenance items (products with a maintenance group)
  const maintenance = spec.items === 'maintenance';
  const items = useMemo(
    () => (maintenance ? catalog.catalogItems?.filter((item) => item.kind === 'product' && item.maintenance_group) : catalog.catalogItems),
    [catalog.catalogItems, maintenance],
  );
  const priceById = useMemo(() => new Map((catalog.products || []).map((p) => [p.id, p.price || 0])), [catalog.products]);

  const matches = useMemo(() => {
    if (!items) return [];
    const words = query.toLowerCase().split(/\s+/).filter(Boolean);
    const text = (item) => `${item.name} ${item.name_ar || ''} ${item.maintenance_group || ''}`.toLowerCase();
    return items.filter((item) => words.every((word) => text(item).includes(word))).slice(0, 40);
  }, [items, query]);

  // Lines from the same package pick stay together as one group, in the order first added
  const groups = useMemo(() => {
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
  }, [lines]);

  // The colours a pick's names give away, as starting values the user can change: the package
  // name's colour is its cover's (e.g. «… - ذهبي»), the water cooler inside it has its own
  function guessedDetails(packageName, itemNames) {
    const fields = new Set(lineFields.map((d) => d.name));
    // The cooler's colour: that of the water cooler inside the package, else the one in the package's name
    const coolerName = itemNames.find((name) => /water\s*cooler/i.test(name));
    const cooler = (coolerName && guessFromProductName(coolerName).cooler_color) || (packageName && guessFromProductName(packageName).cooler_color);
    // The cover's colour comes from the package's own list; picked here only when there is just one
    const colorSpec = lineFields.find((d) => d.type === 'package_color');
    const choices = colorSpec ? packageColors(colorSpec, packageName || itemNames[0]) : [];
    const cover = choices.length === 1 ? choices[0] : '';
    return Object.fromEntries([['cover_color', cover], ['cooler_color', cooler]].filter(([name, v]) => v && fields.has(name)));
  }

  function addItem(item) {
    if (item.kind === 'package') {
      const groupId = `g${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
      const details = { package_quantity: '1', ...guessedDetails(item.name, item.items.map((line) => line.name)) };
      // Each line keeps the package it came from and the price it has there (the server checks it again)
      // base_quantity: how many the package itself holds; «الكمية» multiplies it into quantity
      const added = item.items.map((line) => ({
        product_id: line.product_id, name: line.name, quantity: line.quantity, base_quantity: line.quantity, group_id: groupId,
        group_name: item.name, package_id: item.id, unit_price: line.unit_price, details: { ...details },
      }));
      onChange(spec.name, [...lines, ...added]);
      setOpenGroups((current) => new Set([...current, groupId]));
    } else {
      onChange(spec.name, [...lines, {
        product_id: item.id, name: item.name, quantity: 1, group_id: null, group_name: '', package_id: null, unit_price: item.price ?? 0,
        details: guessedDetails('', [item.name]),
      }]);
    }
    setQuery('');
  }

  const setQuantity = (index, quantity) => onChange(spec.name, lines.map((line, i) => (i === index ? { ...line, quantity } : line)));
  const removeLine = (index) => onChange(spec.name, lines.filter((_, i) => i !== index));
  const removeGroup = (groupId) => {
    onChange(spec.name, lines.filter((line) => line.group_id !== groupId));
    setOpenGroups((current) => { const next = new Set(current); next.delete(groupId); return next; });
  };
  // A standalone product's details live on its one line; a package's live on every line in its
  // group (kept in sync here), since they describe the package as a whole, not one item inside it.
  const setDetail = (index, name, fieldValue) => onChange(spec.name, lines.map((line, i) => (
    i === index ? { ...line, details: { ...line.details, [name]: fieldValue } } : line
  )));
  // Changing a package's «الكمية» changes how many of each of its products there are
  const setGroupDetail = (groupId, name, fieldValue) => onChange(spec.name, lines.map((line) => {
    if (line.group_id !== groupId) return line;
    const next = { ...line, details: { ...line.details, [name]: fieldValue } };
    if (name === 'package_quantity') next.quantity = (Number(line.base_quantity) || 1) * (Number(fieldValue) || 1);
    return next;
  }));
  const toggleGroup = (groupId) => setOpenGroups((current) => {
    const next = new Set(current);
    if (next.has(groupId)) next.delete(groupId); else next.add(groupId);
    return next;
  });
  const placeholder = items
    ? (maintenance ? 'ابحث عن بند (فلتر، قطعة غيار، خدمة…) لإضافته' : 'ابحث عن منتج أو باقة لإضافتها')
    : catalog.catalogItemsError ? '' : 'جارٍ تحميل المنتجات والباقات…';

  // forPackage: a package's details; a product picked on its own has its own quantity box instead of «الكمية»
  // packageName: the package's (or the product's) name, which decides the cooler colours offered
  function detailFields(details, errors, keyPrefix, onDetailChange, forPackage, packageName) {
    const shown = lineFields.filter((dspec) => forPackage || !dspec.package_only);
    if (!shown.length) return null;
    const besides = Object.fromEntries(shown.filter((dspec) => dspec.beside).map((dspec) => [dspec.beside, dspec]));
    // A field with a partner (one marked "beside" it) shares a full line with it: two thirds and one third
    const cell = (dspec) => (
      <div key={dspec.name} className={besides[dspec.name] ? 'fl-pair fl-wide' : (['textarea', 'multiselect'].includes(dspec.type) || dspec.stepper ? 'fl-wide' : undefined)}>
        {fieldOf(dspec)}
        {besides[dspec.name] && fieldOf(besides[dspec.name])}
      </div>
    );
    const colorChoices = (dspec) => packageColors(dspec, packageName);
    const fieldOf = (dspec) => (
            <Field
              key={dspec.name} label={dspec.label} htmlFor={`${keyPrefix}-${dspec.name}`} error={errors?.[dspec.name]}
              required={dspec.type === 'package_color' ? colorChoices(dspec).length > 0 && !dspec.optional : dspec.required}
            >
              {dspec.type === 'package_color' ? (
                <Select
                  id={`${keyPrefix}-${dspec.name}`} value={details?.[dspec.name] ?? ''} invalid={Boolean(errors?.[dspec.name])}
                  disabled={!colorChoices(dspec).length} onChange={(e) => onDetailChange(dspec.name, e.target.value)}
                >
                  <option value="">{colorChoices(dspec).length ? 'اختر اللون…' : 'لا توجد ألوان لهذه الباقة'}</option>
                  {colorChoices(dspec).map((option) => <option key={option}>{option}</option>)}
                </Select>
              ) : dspec.stepper ? (
                <Stepper
                  id={`${keyPrefix}-${dspec.name}`} label={dspec.label} min={dspec.min ?? 1} max={dspec.max ?? 99}
                  value={details?.[dspec.name]} onChange={(fieldValue) => onDetailChange(dspec.name, fieldValue)}
                />
              ) : (
                <Control
                  // A package's details are always drop-downs, however few their options
                  spec={{ ...dspec, name: `${keyPrefix}-${dspec.name}`, dropdown: true }}
                  value={details?.[dspec.name] ?? ''} invalid={Boolean(errors?.[dspec.name])}
                  onChange={(_, fieldValue) => onDetailChange(dspec.name, fieldValue)}
                />
              )}
            </Field>
    );
    return (
      <div className="fl-order-lines__details fl-grid">
        {shown.filter((dspec) => !dspec.beside || !shown.some((other) => other.name === dspec.beside)).map(cell)}
      </div>
    );
  }

  function row({ line, index }) {
    return (
      <div key={index} className="fl-order-lines__item">
        <div className="fl-order-lines__row">
          <bdi className="fl-order-lines__name">{line.name}</bdi>
          <span className="fl-small fl-muted fl-cell--nowrap" data-fl-num>{formatMoney(linePrice(line, priceById))} درهم</span>
          <TextInput
            dir="ltr" type="number" min="1" inputMode="numeric" className="fl-order-lines__qty"
            aria-label={`الكمية — ${line.name}`} value={line.quantity}
            onChange={(e) => setQuantity(index, Math.max(1, Number(e.target.value) || 1))}
          />
          <Button type="button" size="sm" variant="ghost" icon="trash" iconOnly label={`إزالة ${line.name}`} onClick={() => removeLine(index)} />
        </div>
        {/* A line inside a package shows no fields of its own — they belong to the package, below */}
        {!line.group_id && detailFields(line.details, lineErrors?.[index], `${spec.name}-${index}`, (name, v) => setDetail(index, name, v), false, line.name)}
      </div>
    );
  }

  return (
    <div className="fl-stack fl-stack--sm">
      {groups.length > 0 && (
        <div className="fl-order-lines">
          {groups.map((group) => (group.groupName ? (
            <div key={group.key} className="fl-order-lines__group">
              <div className="fl-order-lines__row fl-order-lines__group-head">
                <Icon name="package" size={18} />
                <bdi className="fl-order-lines__name">{group.groupName}</bdi>
                <span className="fl-small fl-muted fl-cell--nowrap" data-fl-num>
                  {packageQuantity(group.rows[0].line) > 1 && `× ${packageQuantity(group.rows[0].line)} · `}
                  {formatMoney(group.rows.reduce((sum, { line }) => sum + linePrice(line, priceById) * (Number(line.quantity) || 0), 0))} درهم
                </span>
                <Button type="button" size="sm" variant="ghost" icon={openGroups.has(group.key) ? 'chevron-up' : 'chevron-down'} onClick={() => toggleGroup(group.key)}>
                  <span data-fl-num>{group.rows.length}</span> منتجات
                </Button>
                <Button type="button" size="sm" variant="ghost" icon="trash" iconOnly label={`إزالة ${group.groupName}`} onClick={() => removeGroup(group.key)} />
              </div>
              {detailFields(
                group.rows[0]?.line.details, lineErrors?.[group.rows[0]?.index], `${spec.name}-${group.key}`,
                (name, v) => setGroupDetail(group.key, name, v), true, group.groupName,
              )}
              {openGroups.has(group.key) && <div className="fl-order-lines__group-items">{group.rows.map(row)}</div>}
            </div>
          ) : group.rows.map(row)))}
        </div>
      )}
      <div className="fl-suggest">
        <TextInput
          id={spec.name} icon="search" dir="auto" autoComplete="off" value={query} invalid={invalid && !lines.length} placeholder={placeholder}
          role="combobox" aria-expanded={open && Boolean(items)} aria-autocomplete="list"
          onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}
        />
        {open && items && (
          <div className="fl-suggest__list" role="listbox">
            {matches.map((item) => (
              <button
                key={`${item.kind}-${item.id}`} type="button" role="option" aria-selected="false" className="fl-suggest__item"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => addItem(item)}
              >
                <bdi>{item.name}</bdi>
                <small>
                  {maintenance ? [item.name_ar, item.maintenance_group].filter(Boolean).join(' · ') : item.kind === 'package' ? 'باقة' : 'منتج'}
                  {item.price ? ` · ${item.price} درهم` : ''}
                </small>
              </button>
            ))}
            {!matches.length && <p className="fl-suggest__empty">لا يوجد ما يطابق البحث.</p>}
          </div>
        )}
      </div>
    </div>
  );
}

// A drop-down where several options can be ticked; shows the chosen ones, opens a list with a tick box each
function MultiSelectDropdown({ spec, value, invalid, onChange }) {
  const [open, setOpen] = useState(false);
  const box = useRef(null);
  const chosen = Array.isArray(value) ? value : [];
  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => { if (box.current && !box.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [open]);
  const toggle = (option) => onChange(spec.name, chosen.includes(option) ? chosen.filter((v) => v !== option) : [...chosen, option]);
  return (
    <div className="fl-suggest" ref={box}>
      <InputBox invalid={invalid} className="fl-box--select"
        end={<span className="fl-box__chevron" aria-hidden="true"><Icon name={open ? 'chevron-up' : 'chevron-down'} size={18} /></span>}>
        <button
          type="button" id={spec.name} className="fl-input" aria-haspopup="listbox" aria-expanded={open}
          style={{ textAlign: 'start', background: 'none', border: 0, cursor: 'pointer', minBlockSize: '2.5rem' }}
          onClick={() => setOpen(!open)}
        >
          {chosen.length ? chosen.join('، ') : <span className="fl-muted">اختر جهازًا أو أكثر…</span>}
        </button>
      </InputBox>
      {open && (
        <div className="fl-suggest__list" role="listbox" aria-multiselectable="true">
          {spec.options.map((option) => (
            <label key={option} className="fl-suggest__item" style={{ display: 'flex', gap: 'var(--fl-space-3)', alignItems: 'center', cursor: 'pointer' }}>
              <input type="checkbox" checked={chosen.includes(option)} onChange={() => toggle(option)} />
              <span>{option}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  );
}

// A whole number changed with − and + (or typed), kept between min and max
function Stepper({ id, label, min, max, value, onChange }) {
  const current = Math.min(max, Math.max(min, Math.round(Number(value)) || min));
  const set = (next) => onChange(String(Math.min(max, Math.max(min, Math.round(Number(next)) || min))));
  return (
    <div className="fl-row" style={{ flexWrap: 'nowrap' }}>
      <Button type="button" icon="minus" iconOnly label={`إنقاص ${label}`} disabled={current <= min} onClick={() => set(current - 1)} />
      <TextInput
        id={id} dir="ltr" type="text" inputMode="numeric" className="fl-order-lines__qty" aria-label={label}
        value={current} onChange={(e) => set(e.target.value.replace(/[^\d]/g, ''))} style={{ textAlign: 'center' }}
      />
      <Button type="button" icon="plus" iconOnly label={`زيادة ${label}`} disabled={current >= max} onClick={() => set(current + 1)} />
    </div>
  );
}

// onSearch: the field looks the client up; its magnifier runs the search right away
function Control({ spec, value, invalid, onChange, onBlur, onSearch }) {
  const common = {
    id: spec.name,
    value: value ?? '',
    invalid,
    onChange: (e) => onChange(spec.name, e.target.value),
    onBlur: onBlur && ((e) => onBlur(spec.name, e.target.value)),
  };
  if (spec.type === 'select' && spec.options.length <= CHOICE_MAX_OPTIONS && !spec.dropdown) {
    return <Choice name={spec.name} options={spec.options} value={value ?? ''} invalid={invalid} onChange={(v) => onChange(spec.name, v)} />;
  }
  if (spec.type === 'select') {
    return (
      <Select {...common}>
        <option value="">بدون تحديد</option>
        {spec.options.map((option) => <option key={option}>{option}</option>)}
      </Select>
    );
  }
  if (spec.type === 'multiselect' && spec.dropdown) {
    return <MultiSelectDropdown spec={spec} value={value} invalid={invalid} onChange={onChange} />;
  }
  if (spec.type === 'multiselect') {
    return <Choice name={spec.name} multiple options={spec.options} value={value} invalid={invalid} onChange={(v) => onChange(spec.name, v)} />;
  }
  if (spec.type === 'textarea') return <TextArea {...common} rows={3} />;
  if (spec.type === 'date') return <TextInput {...common} type="date" dir="ltr" />;
  const inputMode = { number: spec.integer ? 'numeric' : 'decimal', phone: 'tel' }[spec.type];
  const list = spec.type === 'staff' ? 'staff-list' : spec.suggestions ? `${spec.name}-suggestions` : undefined;
  const icon = spec.type === 'phone' || onSearch ? 'search' : undefined;
  return (
    <>
      <TextInput
        {...common} icon={icon} type="text" inputMode={inputMode} dir={inputMode ? 'ltr' : 'auto'} list={list} autoComplete="off"
        onIconClick={onSearch && (() => onSearch(spec.name, value ?? ''))} iconLabel={onSearch && `بحث عن العميل بـ${spec.label}`}
      />
      {spec.suggestions && <datalist id={list}>{spec.suggestions.map((text) => <option key={text} value={text} />)}</datalist>}
    </>
  );
}

// A field picking a row of a Daftra list (an order source, a treasury); keeps the row's id, and its name for display.
// unavailable: shown instead of the list when there are no rows to pick from yet, and why
function DaftraListSelect({ spec, value, invalid, rows, unavailable, onChange }) {
  if (!rows || unavailable) {
    // Still a drop-down, so it is clear what will appear here, with the reason it is empty
    return (
      <Select id={spec.name} value="" invalid={invalid} disabled onChange={() => {}}>
        <option value="">{unavailable || 'تعذر تحميل القائمة من دفترة — حدّث الصفحة'}</option>
      </Select>
    );
  }
  return (
    <Select
      id={spec.name} value={value == null ? '' : String(value)} invalid={invalid}
      onChange={(e) => onChange(e.target.value, rows.find((row) => String(row.id) === e.target.value)?.name || '')}
    >
      <option value="">اختر…</option>
      {rows.map((row) => <option key={row.id} value={String(row.id)}>{row.name}</option>)}
    </Select>
  );
}

export default function RequestForm({ formType, requestId, user, catalog, onBack, onNew, onList }) {
  const [id, setId] = useState(requestId ?? null);
  const [values, setValues] = useState(() => (formType && !requestId ? initialValues(formType) : {}));
  const [attachments, setAttachments] = useState([]);
  // { status, returned_reason } of a saved request
  const [saved, setSaved] = useState({ status: 'draft', returned_reason: null });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(Boolean(requestId));
  const [busy, setBusy] = useState('');
  const [uploading, setUploading] = useState('');
  const [message, setMessage] = useState(null);
  const [submitted, setSubmitted] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [open, setOpen] = useState(() => new Set((formType?.sections || []).slice(0, OPEN_AT_START).map((s) => s.title)));
  // Result of the last client search: { field, status: 'loading' | 'found' | 'many' | 'none' | 'error', ... }
  const [lookup, setLookup] = useState(null);
  // id of the found client's address currently filled in, or 'new' while typing one to save
  const [addressChoice, setAddressChoice] = useState(null);
  const [addressBusy, setAddressBusy] = useState(false);
  // The found client as Daftra has them now: { status: 'loading' | 'ready' | 'error', category, open_invoices }
  const [clientInfo, setClientInfo] = useState(null);
  const lastLookup = useRef('');
  const autoFilled = useRef({});

  useEffect(() => {
    if (!requestId) return;
    api(`/requests/${requestId}`)
      .then((request) => { setValues(request.data); setAttachments(request.attachments); setSaved({ status: request.status, returned_reason: request.returned_reason }); })
      .catch((err) => setMessage({ error: err.message }))
      .finally(() => setLoading(false));
  }, [requestId]);

  const fileCounts = useMemo(() => {
    const counts = {};
    for (const file of attachments) counts[file.field] = (counts[file.field] || 0) + 1;
    return counts;
  }, [attachments]);
  const evaluation = useMemo(
    () => (formType ? evaluateForm(formType, values, fileCounts, catalog) : null),
    [formType, values, fileCounts, catalog],
  );

  // Forms with a field only Daftra can fill for the found client (their التصنيف, their open invoices)
  const needsClientInfo = Boolean(formType) && allFields(formType).some((spec) => ['daftra_client_category', 'daftra_client_invoice'].includes(spec.type));

  // A saved draft looks its client up again, so those fields have their choices back
  const lookedUpDraft = useRef(false);
  useEffect(() => {
    if (loading || lookedUpDraft.current || !needsClientInfo) return;
    lookedUpDraft.current = true;
    if (values.client_code) lookupClient('client_code', String(values.client_code));
    else if (values.phone) lookupClient('phone', String(values.phone));
  });

  if (!formType) return <Alert tone="error">نوع هذا النموذج لم يعد متاحًا.</Alert>;
  const fieldNames = new Set(allFields(formType).map((spec) => spec.name));
  if (loading) return <Loading />;

  async function loadClientInfo(daftraId) {
    setClientInfo({ status: 'loading' });
    try {
      const info = await api(`/daftra/clients/${daftraId}`);
      setClientInfo({ status: 'ready', ...info });
      setValues((current) => {
        const next = { ...current };
        // Their current التصنيف, unless one was already picked
        if (fieldNames.has('category') && info.category && !current.category) {
          next.category = String(info.category.id);
          next.category_name = info.category.name;
        }
        // An invoice picked for a different client is dropped
        if (fieldNames.has('invoice') && current.invoice && !info.open_invoices.some((i) => String(i.id) === String(current.invoice))) {
          next.invoice = '';
          next.invoice_name = '';
        }
        return next;
      });
    } catch (err) {
      setClientInfo({ status: 'error', message: err.message });
    }
  }

  // What the invoice drop-down says while it has nothing to offer
  function invoicesUnavailable() {
    if (!clientInfo) return 'ابحث عن العميل أولًا برقم الهاتف أو الكود';
    if (clientInfo.status === 'loading') return 'جارٍ تحميل فواتير العميل من دفترة…';
    if (clientInfo.status === 'error') return clientInfo.message;
    if (!clientInfo.open_invoices.length) return 'لا توجد فواتير عليها مبلغ متبقٍ لهذا العميل';
    return null;
  }

  // Fills fields that are empty or still hold what an earlier search or pick filled in
  function autoFill(current, next, name, value, force = false) {
    const untouched = !current[name] || current[name] === autoFilled.current[name];
    if (!fieldNames.has(name) || !value || !(untouched || force)) return;
    next[name] = value;
    autoFilled.current[name] = value;
  }

  // Typing in a product field drops the picked product until one is chosen from the list again
  function typeProduct(name, text) {
    setValues((current) => ({ ...current, [name]: text, [name + '_id']: '' }));
    setMessage(null);
  }

  function pickProduct(name, product) {
    setValues((current) => {
      const next = { ...current, [name]: product.name, [name + '_id']: product.id };
      for (const [field, value] of Object.entries(guessFromProductName(product.name))) autoFill(current, next, field, value);
      return next;
    });
    setMessage(null);
    setErrors(({ [name]: _, ...rest }) => rest);
  }

  const pickedProduct = (name) => catalog.products?.find((product) => product.id === values[name + '_id']);

  // A product must come from our catalog (unless the list could not be loaded)
  function productErrors() {
    const found = {};
    if (!catalog.products) return found;
    for (const spec of allFields(formType)) {
      if (spec.type === 'product' && (values[spec.name] ?? '').trim() && !pickedProduct(spec.name)) {
        found[spec.name] = 'اختر المنتج من القائمة';
      }
    }
    return found;
  }

  function productHint(name) {
    const product = pickedProduct(name);
    if (catalog.productsError && !catalog.products) return `${catalog.productsError} — اكتب اسم المنتج يدويًا.`;
    if (!product) return null;
    return [product.name_ar, product.price && `${product.price} درهم`, product.description].filter(Boolean).join(' — ');
  }

  function change(name, value) {
    setValues((current) => {
      const next = { ...current, [name]: value };
      // A field whose usual value follows this one (e.g. the treasury of a payment method) is filled in,
      // unless the user has already picked something else
      for (const spec of allFields(formType)) {
        // A Google Maps link that carries the coordinates ("…@24.17870,55.60451…", "?q=24.17870,55.60451")
        if (spec.coordinates_from === name) {
          const found = String(value ?? '').match(/(-?\d{1,2}\.\d{3,})\s*,\s*(-?\d{1,3}\.\d{3,})/);
          if (found) autoFill(current, next, spec.name, `${found[1]}, ${found[2]}`);
        }
        const suggested = spec.default_from?.field === name ? spec.default_from.values[value] : undefined;
        if (suggested === undefined) continue;
        const id = String(suggested);
        autoFill(current, next, spec.name, id);
        if (next[spec.name] === id) {
          next[`${spec.name}_name`] = catalog.daftraLists?.[spec.type]?.find((row) => String(row.id) === id)?.name || '';
        }
      }
      return next;
    });
    setMessage(null);
    if (errors[name]) setErrors(({ [name]: _, ...rest }) => rest);
  }

  function chooseFromList(name, id, label) {
    const spec = allFields(formType).find((s) => s.name === name);
    // A client category knows where its clients live: picking it picks المنطقة and الإمارة too
    const located = spec?.type === 'daftra_client_category'
      ? catalog.daftraLists?.daftra_client_category?.find((row) => String(row.id) === String(id))
      : null;
    const place = located?.area && located?.emirate && fieldNames.has('area') ? { area: located.area, emirate: located.emirate } : {};
    setValues((current) => ({ ...current, [name]: id, [`${name}_name`]: label, ...place }));
    autoFilled.current[name] = undefined;
    setMessage(null);
    setErrors(({ [name]: _, ...rest }) => (place.area ? Object.fromEntries(Object.entries(rest).filter(([k]) => k !== 'area' && k !== 'emirate')) : rest));
  }

  // الإمارة and المنطقة stay in sync: picking one narrows or fills in the other
  function chooseEmirate(value) {
    const areaSpec = formType ? allFields(formType).find((s) => s.name === 'area') : null;
    const allowed = areaSpec?.areas_by_emirate?.[value];
    setValues((current) => (
      allowed && current.area && !allowed.includes(current.area)
        ? { ...current, emirate: value, area: '' }
        : { ...current, emirate: value }
    ));
    setMessage(null);
    setErrors(({ emirate: _, ...rest }) => rest);
  }

  function chooseArea(value) {
    const areaSpec = formType ? allFields(formType).find((s) => s.name === 'area') : null;
    const areasByEmirate = areaSpec?.areas_by_emirate || {};
    const matchedEmirate = Object.keys(areasByEmirate).find((emirate) => areasByEmirate[emirate].includes(value));
    setValues((current) => (
      matchedEmirate && current.emirate !== matchedEmirate
        ? { ...current, area: value, emirate: matchedEmirate }
        : { ...current, area: value }
    ));
    setMessage(null);
    setErrors(({ area: _a, emirate: _e, ...rest }) => rest);
  }

  // Fills the client fields that are empty or still hold what a previous search filled in
  function applyClient(client, field) {
    setValues((current) => {
      const next = { ...current };
      for (const name of CLIENT_FIELDS) autoFill(current, next, name, client[name], name === 'client_code');
      return next;
    });
    setErrors((current) => Object.fromEntries(Object.entries(current).filter(([name]) => !CLIENT_FIELDS.includes(name))));
    setLookup({ field, status: 'found', client });
    if (needsClientInfo) loadClientInfo(client.daftra_id);
    const last = client.addresses?.[client.addresses.length - 1];
    setAddressChoice(last ? String(last.id) : null);
  }

  const ADDRESS_FIELDS = ['emirate', 'area', 'street', 'house', 'location_url'];

  // Switches the address fields to one of the client's saved addresses, or clears them to type a new one
  function chooseAddress(choice) {
    setAddressChoice(choice);
    if (choice === 'new') {
      setValues((current) => ({ ...current, ...Object.fromEntries(ADDRESS_FIELDS.map((f) => [f, ''])) }));
      return;
    }
    const address = lookup.client.addresses.find((a) => String(a.id) === choice);
    if (address) setValues((current) => ({ ...current, ...Object.fromEntries(ADDRESS_FIELDS.map((f) => [f, address[f]])) }));
  }

  async function saveNewAddress() {
    const client = lookup.client;
    setAddressBusy(true);
    try {
      const address = await api(`/clients/${client.daftra_id}/addresses`, {
        method: 'POST', body: Object.fromEntries(ADDRESS_FIELDS.map((f) => [f, values[f] || ''])),
      });
      setLookup((current) => ({ ...current, client: { ...current.client, addresses: [...current.client.addresses, address] } }));
      setAddressChoice(String(address.id));
      setMessage({ ok: 'تم حفظ العنوان الجديد لهذا العميل.' });
    } catch (err) {
      setMessage({ error: err.message });
    } finally {
      setAddressBusy(false);
    }
  }

  async function lookupClient(field, raw) {
    const phone = field === 'phone' ? normalizePhone(raw) : null;
    const code = field === 'client_code' && /^[\d٠-٩۰-۹]{1,6}$/.test(raw.trim()) ? raw.trim() : null;
    const query = phone ? `phone=${encodeURIComponent(phone)}` : code ? `code=${encodeURIComponent(code)}` : null;
    if (!query || query === lastLookup.current) return;
    // A code that a search just filled in does not need searching again
    if (field === 'client_code' && raw === autoFilled.current.client_code) return;
    lastLookup.current = query;
    setLookup({ field, status: 'loading' });
    try {
      const { matches } = await api(`/clients/lookup?${query}`);
      if (lastLookup.current !== query) return;
      if (matches.length === 1) applyClient(matches[0], field);
      else setLookup({ field, status: matches.length ? 'many' : 'none', matches });
    } catch (err) {
      lastLookup.current = '';
      setLookup({ field, status: 'error', message: err.message });
    }
  }

  // The search icon runs the search again even for the same number, e.g. after a failed attempt
  function searchNow(field, raw) {
    lastLookup.current = '';
    lookupClient(field, String(raw));
  }

  function addressLabel(address) {
    return [address.emirate, address.area, address.street, address.house].filter(Boolean).join('، ') || 'بلا عنوان مسجل';
  }

  function lookupNote(name) {
    if (lookup?.field !== name) return null;
    if (lookup.status === 'loading') return <p className="fl-field__hint">جارٍ البحث عن العميل…</p>;
    if (lookup.status === 'found') {
      const addresses = lookup.client.addresses || [];
      return (
        <Alert tone="success" title="عميل مسجل">
          <p>{lookup.client.customer_name} — كود <bdi dir="ltr">{lookup.client.client_code}</bdi>. تم تعبئة بياناته.</p>
          <div className="fl-row" style={{ marginTop: 'var(--fl-space-2)' }}>
            {addresses.length > 0 && (
              <Select value={addressChoice ?? ''} onChange={(e) => chooseAddress(e.target.value)} aria-label="عنوان العميل">
                {addresses.map((address) => (
                  <option key={address.id} value={String(address.id)}>
                    {addressLabel(address)}{address.is_default ? ' (الأساسي)' : ''}
                  </option>
                ))}
                <option value="new">+ عنوان جديد</option>
              </Select>
            )}
            {!addresses.length && addressChoice !== 'new' && (
              <Button type="button" size="sm" variant="tertiary" icon="plus" onClick={() => chooseAddress('new')}>
                إضافة عنوان لهذا العميل
              </Button>
            )}
            {addressChoice === 'new' && (
              <Button type="button" size="sm" loading={addressBusy} onClick={saveNewAddress}>
                حفظ هذا العنوان للعميل
              </Button>
            )}
          </div>
        </Alert>
      );
    }
    if (lookup.status === 'none') {
      return <p className="fl-field__hint">{name === 'phone' ? 'لا يوجد عميل بهذا الرقم (عميل جديد).' : 'لا يوجد عميل بهذا الكود.'}</p>;
    }
    if (lookup.status === 'error') return <Alert tone="warning">{lookup.message}</Alert>;
    return (
      <Alert tone="info" title="يوجد أكثر من عميل بهذا الرقم، اختر العميل">
        <div className="fl-row">
          {lookup.matches.map((client) => (
            <Button key={client.daftra_id} size="sm" onClick={() => applyClient(client, name)}>
              {client.customer_name} — <bdi dir="ltr">{client.client_code}</bdi>
            </Button>
          ))}
        </div>
      </Alert>
    );
  }

  async function save(action) {
    const body = { form_type: formType.key, data: values, action };
    const saved = id
      ? await api(`/requests/${id}`, { method: 'PUT', body })
      : await api('/requests', { method: 'POST', body });
    setId(saved.id);
    return saved;
  }

  async function run(name, action) {
    setBusy(name);
    setMessage(null);
    try {
      await action();
    } catch (err) {
      if (err.fieldErrors) showErrors(err.fieldErrors);
      else setMessage({ error: err.message });
    } finally {
      setBusy('');
    }
  }

  // Opens the sections that hold errors and brings the first one into view
  function showErrors(found) {
    setErrors(found);
    const withErrors = formType.sections.filter((section) => section.fields.some((spec) => found[spec.name]));
    setOpen((current) => new Set([...current, ...withErrors.map((section) => section.title)]));
    const first = allFields(formType).find((spec) => found[spec.name]);
    setTimeout(() => document.getElementById('field-' + first?.name)?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 50);
  }

  const saveDraft = () => run('draft', async () => {
    await save('draft');
    setErrors({});
    setMessage({ ok: saved.status === 'returned' ? 'تم حفظ التعديلات. أعد إرسال الطلب عندما تنتهي.' : 'تم حفظ المسودة. يمكنك العودة إليها من «طلباتي».' });
  });

  function askSubmit() {
    const found = { ...evaluation.errors, ...productErrors() };
    if (Object.keys(found).length) return showErrors(found);
    setConfirming(true);
  }

  const submit = () => run('submit', async () => {
    await save('submit');
    setConfirming(false);
    setSubmitted(true);
  }).finally(() => setConfirming(false));

  // A file needs a saved request to attach to, so the first upload saves a draft
  async function addFiles(field, files) {
    setUploading(field);
    setMessage(null);
    try {
      const requestIdToUse = id ?? (await save('draft')).id;
      for (const file of files) {
        const attachment = await uploadAttachment(requestIdToUse, field, file);
        setAttachments((current) => [...current, attachment]);
      }
      if (errors[field]) setErrors(({ [field]: _, ...rest }) => rest);
    } catch (err) {
      setMessage({ error: err.message });
    } finally {
      setUploading('');
    }
  }

  async function removeFile(file) {
    try {
      await api(`/attachments/${file.id}`, { method: 'DELETE' });
      setAttachments((current) => current.filter((a) => a.id !== file.id));
    } catch (err) {
      setMessage({ error: err.message });
    }
  }

  if (submitted) {
    return (
      <div className="fl-narrow fl-stack">
        <Alert tone="success" title={saved.status === 'returned' ? `تمت إعادة إرسال الطلب رقم ${id}` : `تم إرسال الطلب رقم ${id}`}>
          {formType.label} — أُرسل إلى مدير المبيعات للمراجعة ولا يمكن تعديله.
        </Alert>
        <div className="fl-row">
          <Button variant="primary" icon="plus" onClick={onNew}>طلب جديد</Button>
          <Button icon="inbox" onClick={onList}>طلباتي</Button>
        </div>
      </div>
    );
  }

  const toggle = (title) => setOpen((current) => {
    const next = new Set(current);
    if (next.has(title)) next.delete(title); else next.add(title);
    return next;
  });
  const allOpen = formType.sections.every((section) => open.has(section.title));
  const errorCount = Object.keys(errors).length;

  function summary(section) {
    const inputs = section.fields.filter((spec) => spec.type !== 'auto_user' && !spec.computed);
    const sectionErrors = section.fields.filter((spec) => errors[spec.name]).length;
    if (sectionErrors) return `${sectionErrors} حقل يحتاج تصحيحًا`;
    const filled = inputs.filter((spec) => (spec.type === 'files' ? fileCounts[spec.name] : values[spec.name] != null && values[spec.name] !== '' && !(Array.isArray(values[spec.name]) && !values[spec.name].length))).length;
    return filled ? `${filled} من ${inputs.length} مُعبأ` : 'لم تُعبأ بعد';
  }

  return (
    <form className="fl-narrow fl-stack" onSubmit={(e) => e.preventDefault()} noValidate>
      <datalist id="staff-list">{catalog.staff.map((name) => <option key={name} value={name} />)}</datalist>
      <Button className="fl-back" variant="tertiary" icon="arrow-start" onClick={onBack}>رجوع</Button>
      <PageHeader title={formType.label}>
        <div className="fl-row fl-small fl-muted">
          <span>رقم الطلب:</span>
          <strong data-fl-num>{id ?? 'لم يُحفظ بعد'}</strong>
          {saved.status === 'returned' ? <Badge tone="warning" icon="arrow-start">تحتاج تعديل</Badge> : <Badge tone="neutral" icon="edit">مسودة</Badge>}
        </div>
      </PageHeader>
      {saved.status === 'returned' && saved.returned_reason && (
        <Alert tone="warning" title="أُعيد الطلب للتعديل">{saved.returned_reason}</Alert>
      )}
      <div>
        <Button variant="tertiary" size="sm" iconEnd={allOpen ? 'chevron-up' : 'chevron-down'}
          onClick={() => setOpen(allOpen ? new Set() : new Set(formType.sections.map((s) => s.title)))}>
          {allOpen ? 'طي كل الأقسام' : 'فتح كل الأقسام'}
        </Button>
      </div>

      {formType.sections.map((section, index) => (
        <Section
          key={section.title} number={index + 1} title={section.title} summary={summary(section)}
          open={open.has(section.title)} onToggle={() => toggle(section.title)}
          invalid={section.fields.some((spec) => errors[spec.name])}
        >
          {section.note && <Alert tone="info">{section.note}</Alert>}
          <div className="fl-grid">
            {section.fields.map((spec) => {
              const wide = ['textarea', 'files', 'multiselect', 'order_lines'].includes(spec.type)
                || (spec.type === 'select' && spec.options.length <= CHOICE_MAX_OPTIONS);
              const invalid = Boolean(errors[spec.name]);
              let control;
              let locked;
              let hint = spec.type === 'product' ? productHint(spec.name) : null;
              if (spec.type === 'files') {
                control = (
                  <FileField
                    spec={spec} files={attachments.filter((a) => a.field === spec.name)} invalid={invalid}
                    busy={uploading === spec.name} onAdd={addFiles} onRemove={removeFile}
                  />
                );
              } else if (spec.type === 'auto_user') {
                locked = 'للقراءة فقط';
                control = <TextInput id={spec.name} value={user.full_name || user.username} readOnly />;
              } else if (spec.computed) {
                locked = 'يُحسب تلقائيًا';
                control = <TextInput id={spec.name} dir="ltr" value={evaluation.clean[spec.name] ?? ''} readOnly placeholder="—" />;
              } else if (spec.type === 'product') {
                control = (
                  <ProductPicker
                    spec={spec} value={values[spec.name]} invalid={invalid}
                    catalog={catalog} onType={typeProduct} onPick={pickProduct}
                  />
                );
              } else if (spec.type === 'order_lines') {
                control = (
                  <OrderLines
                    spec={spec} value={values[spec.name]} invalid={invalid} catalog={catalog} onChange={change}
                    lineErrors={typeof errors[spec.name] === 'object' ? errors[spec.name]?.lines : null}
                  />
                );
              } else if (DAFTRA_LIST_TYPES.includes(spec.type)) {
                const perClient = spec.type === 'daftra_client_invoice';
                control = (
                  <DaftraListSelect
                    spec={spec} value={values[spec.name]} invalid={invalid}
                    rows={perClient ? clientInfo?.open_invoices || [] : catalog.daftraLists?.[spec.type]}
                    unavailable={perClient ? invoicesUnavailable() : null}
                    onChange={(id, label) => chooseFromList(spec.name, id, label)}
                  />
                );
              } else if (spec.name === 'emirate') {
                control = <Control spec={spec} value={values.emirate} invalid={invalid} onChange={(_, v) => chooseEmirate(v)} />;
              } else if (spec.name === 'area') {
                const options = (values.emirate && spec.areas_by_emirate?.[values.emirate]) || spec.options;
                // Always a drop-down, even when the emirate has only two or three areas
                control = <Control spec={{ ...spec, options, dropdown: true }} value={values.area} invalid={invalid} onChange={(_, v) => chooseArea(v)} />;
              } else {
                const searchable = spec.name === 'phone' || spec.name === 'client_code';
                if (searchable) hint = 'يُبحث عن العميل بعد الكتابة، أو اضغط أيقونة البحث.';
                control = (
                  <Control
                    spec={spec} value={values[spec.name]} invalid={invalid}
                    onChange={change} onBlur={searchable ? lookupClient : undefined} onSearch={searchable ? searchNow : undefined}
                  />
                );
              }
              // A computed field shows its error live (e.g. paid more than the total); order_lines
              // keeps its per-line errors inside the field itself, not as one message here
              const rawError = errors[spec.name] || (spec.computed && evaluation.errors[spec.name]);
              const error = spec.type === 'order_lines' && rawError && typeof rawError === 'object'
                ? 'بعض البنود تحتاج إلى تعديل، انظر التفاصيل أدناه' : rawError;
              return (
                <div key={spec.name} className={wide ? 'fl-wide' : undefined}>
                  <Field
                    id={'field-' + spec.name} label={spec.label} htmlFor={spec.type === 'files' ? undefined : spec.name}
                    required={evaluation.required.has(spec.name)} locked={locked} hint={hint} error={error}
                  >
                    {control}
                  </Field>
                  {lookupNote(spec.name)}
                </div>
              );
            })}
          </div>
        </Section>
      ))}

      <ActionBar
        message={(errorCount > 0 || message) && (
          <>
            {errorCount > 0 && <Alert tone="error">يوجد {errorCount} حقل يحتاج إلى تصحيح قبل الإرسال.</Alert>}
            {message?.error && <Alert tone="error">{message.error}</Alert>}
            {message?.ok && <Alert tone="success">{message.ok}</Alert>}
          </>
        )}
      >
        <Button variant="primary" icon="send" onClick={askSubmit} loading={busy === 'submit'} disabled={Boolean(busy) && busy !== 'submit'}>
          {saved.status === 'returned' ? 'إعادة الإرسال' : 'إرسال للمراجعة'}
        </Button>
        <Button icon="file" onClick={saveDraft} loading={busy === 'draft'} disabled={Boolean(busy) && busy !== 'draft'}>
          {saved.status === 'returned' ? 'حفظ التعديلات' : 'حفظ المسودة'}
        </Button>
      </ActionBar>

      {confirming && (
        <Dialog
          title={saved.status === 'returned' ? 'إعادة إرسال الطلب للمراجعة؟' : 'إرسال الطلب للمراجعة؟'}
          confirmLabel="إرسال" busy={busy === 'submit'}
          onConfirm={submit} onCancel={() => setConfirming(false)}
        >
          بعد الإرسال لا يمكن تعديل الطلب، ويصل إلى مدير المبيعات للمراجعة.
        </Dialog>
      )}
    </form>
  );
}
