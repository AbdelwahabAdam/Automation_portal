// The controls a request form is made of, one per field type in backend/app/forms/.
import { useEffect, useMemo, useRef, useState } from 'react';
import { openAttachment } from '../api.js';
import { Button, Choice, Combobox, Icon, InputBox, Select, TextArea, TextInput } from '../ds/index.jsx';

const ACCEPT = '.jpg,.jpeg,.png,.webp,.heic,.pdf,.mp4,.mov,.doc,.docx';
// Selects with this many options or fewer show as option cards, as in the design
export const CHOICE_MAX_OPTIONS = 3;

const sizeText = (bytes) => (bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`);

// Option cards for a short select (and for multiselect), a drop-down otherwise
export const showsAsChoice = (spec) => spec.type === 'select' && spec.options.length <= CHOICE_MAX_OPTIONS && !spec.dropdown;

export function FileField({ spec, files, busy, invalid, onAdd, onRemove }) {
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
      <label className={['fl-dropzone', busy && 'fl-dropzone--busy', invalid && 'fl-dropzone--invalid'].filter(Boolean).join(' ')}>
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
export function guessFromProductName(name) {
  const guess = {};
  if (/black|[اأ]سود/i.test(name)) guess.cooler_color = 'أسود';
  else if (/white|[اأ]بيض/i.test(name)) guess.cooler_color = 'أبيض';
  else if (/gold|[ذد]هب/i.test(name)) guess.cooler_color = 'ذهبي';
  const outlets = name.match(/(\d)\s*(?:T\b|tap|wolf|ولف)|\bT\s*(\d)\b/i);
  if (outlets) guess.outlets = outlets[1] || outlets[2];
  return guess;
}

// A product picked by name from our catalog; typing drops the pick until one is chosen again
export function ProductPicker({ spec, value, invalid, catalog, onType, onPick }) {
  const { products } = catalog;
  const matches = useMemo(() => {
    if (!products) return null;
    const words = (value ?? '').toLowerCase().split(/\s+/).filter(Boolean);
    return products
      .filter((p) => words.every((word) => p.name.toLowerCase().includes(word) || p.name_ar.includes(word)))
      .slice(0, 40);
  }, [products, value]);
  return (
    <Combobox
      id={spec.name} value={value} invalid={invalid} items={matches} itemKey={(product) => product.id}
      placeholder={products ? 'ابحث باسم المنتج' : catalog.productsError ? '' : 'جارٍ تحميل المنتجات…'}
      onInput={(text) => onType(spec.name, text)} onPick={(product) => onPick(spec.name, product)}
      emptyText="لا يوجد منتج مطابق."
      renderItem={(product) => (
        <>
          <bdi>{product.name}</bdi>
          <small>{product.name_ar}{product.price ? ` · ${product.price} درهم` : ''}</small>
        </>
      )}
    />
  );
}

// A drop-down where several options can be ticked; shows the chosen ones, opens a list with a tick box each
export function MultiSelectDropdown({ spec, value, invalid, onChange }) {
  const [open, setOpen] = useState(false);
  const box = useRef(null);
  const chosen = Array.isArray(value) ? value : [];
  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => { if (box.current && !box.current.contains(e.target)) setOpen(false); };
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', onKey); };
  }, [open]);
  const toggle = (option) => onChange(spec.name, chosen.includes(option) ? chosen.filter((v) => v !== option) : [...chosen, option]);
  return (
    <div className="fl-suggest" ref={box}>
      <InputBox invalid={invalid} className="fl-box--select"
        end={<span className="fl-box__chevron" aria-hidden="true"><Icon name={open ? 'chevron-up' : 'chevron-down'} size={18} /></span>}>
        <button type="button" id={spec.name} className="fl-input fl-multiselect__button" aria-haspopup="listbox" aria-expanded={open}
          onClick={() => setOpen(!open)}>
          {chosen.length ? chosen.join('، ') : <span className="fl-muted">اختر جهازًا أو أكثر…</span>}
        </button>
      </InputBox>
      {open && (
        <div className="fl-suggest__list" role="listbox" aria-multiselectable="true">
          {spec.options.map((option) => (
            <label key={option} className="fl-suggest__item fl-multiselect__option">
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
export function Stepper({ id, label, min, max, value, onChange }) {
  const current = Math.min(max, Math.max(min, Math.round(Number(value)) || min));
  const set = (next) => onChange(String(Math.min(max, Math.max(min, Math.round(Number(next)) || min))));
  return (
    <div className="fl-stepper">
      <Button type="button" icon="minus" iconOnly label={`إنقاص ${label}`} disabled={current <= min} onClick={() => set(current - 1)} />
      <TextInput
        id={id} dir="ltr" type="text" inputMode="numeric" className="fl-order-lines__qty fl-stepper__value" aria-label={label}
        value={current} onChange={(e) => set(e.target.value.replace(/[^\d]/g, ''))}
      />
      <Button type="button" icon="plus" iconOnly label={`زيادة ${label}`} disabled={current >= max} onClick={() => set(current + 1)} />
    </div>
  );
}

// The control for one plain field. onSearch: the field looks the client up, and its magnifier runs the search
export function Control({ spec, value, invalid, onChange, onBlur, onSearch }) {
  const common = {
    id: spec.name,
    value: value ?? '',
    invalid,
    onChange: (e) => onChange(spec.name, e.target.value),
    onBlur: onBlur && ((e) => onBlur(spec.name, e.target.value)),
  };
  if (showsAsChoice(spec)) {
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
  if (spec.type === 'multiselect') {
    return spec.dropdown
      ? <MultiSelectDropdown spec={spec} value={value} invalid={invalid} onChange={onChange} />
      : <Choice name={spec.name} multiple options={spec.options} value={value} invalid={invalid} onChange={(v) => onChange(spec.name, v)} />;
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
export function DaftraListSelect({ spec, value, invalid, rows, unavailable, onChange }) {
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
