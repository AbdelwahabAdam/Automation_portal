// The controls a request form is made of, one per field type in backend/app/forms/.
import { useMemo, useState } from 'react';
import { FileRow } from '../attachments.jsx';
import { Button, Choice, Combobox, Icon, Select, TextArea, TextInput } from '../../../ds/index.jsx';
import { matchesQuery } from '../../../ds/match.js';
import { localPhone } from '../validation.js';

const ACCEPT = '.jpg,.jpeg,.png,.webp,.heic,.pdf,.mp4,.mov,.doc,.docx';
// Selects with this many options or fewer show as option cards, as in the design
export const CHOICE_MAX_OPTIONS = 3;

// Option cards for a short select (and for multiselect), a drop-down otherwise
export const showsAsChoice = (spec) => spec.type === 'select' && spec.options.length <= CHOICE_MAX_OPTIONS && !spec.dropdown;

export function FileField({ spec, files, busy, invalid, onAdd, onRemove }) {
  // True while a file is being dragged over the box, so it is clear where to let go
  const [over, setOver] = useState(false);

  const add = (list) => {
    const chosen = [...list].filter((file) => file.size > 0);
    if (chosen.length) onAdd(spec.name, chosen);
  };

  function onDrop(e) {
    e.preventDefault();
    setOver(false);
    if (!busy) add(e.dataTransfer.files);
  }

  return (
    <div className="fl-files">
      {files.map((file) => (
        <FileRow key={file.id} file={file}>
          <Button size="sm" variant="ghost" icon="trash" iconOnly label={`حذف ${file.filename}`} onClick={() => onRemove(file)} />
        </FileRow>
      ))}
      {/* One way in: the phone's own file picker offers its camera among the rest */}
      <label
        className={['fl-dropzone', busy && 'fl-dropzone--busy', invalid && 'fl-dropzone--invalid', over && 'fl-dropzone--over'].filter(Boolean).join(' ')}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={onDrop}
      >
        <Icon name={busy ? 'loader' : 'upload'} size={18} />
        {busy ? 'جارٍ الرفع…' : over ? 'أفلت الملفات هنا' : 'إضافة ملف أو إفلاته هنا'}
        <input
          type="file" multiple hidden accept={ACCEPT} disabled={busy} aria-label={spec.label}
          onChange={(e) => { add(e.target.files); e.target.value = ''; }}
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

// Several things picked from a long list, the same way products and packages are picked: search,
// add, and each pick becomes a row that can be removed.
export function MultiSelectPicker({ spec, value, invalid, onChange }) {
  const [query, setQuery] = useState('');
  const chosen = Array.isArray(value) ? value : [];
  // Something already added is not offered again
  const left = spec.options.filter((option) => !chosen.includes(option));
  const matches = query ? left.filter((option) => matchesQuery(query, option)) : left;

  const add = (option) => { onChange(spec.name, [...chosen, option]); setQuery(''); };
  const remove = (option) => onChange(spec.name, chosen.filter((kept) => kept !== option));

  return (
    <div className="fl-stack fl-stack--sm">
      {chosen.length > 0 && (
        <div className="fl-picked">
          {chosen.map((option) => (
            <div key={option} className="fl-picked__item">
              <Icon name="tool" size={18} />
              <bdi className="fl-picked__name">{option}</bdi>
              <Button type="button" size="sm" variant="ghost" icon="trash" iconOnly label={`إزالة ${option}`} onClick={() => remove(option)} />
            </div>
          ))}
        </div>
      )}
      <Combobox
        id={spec.name} value={query} onInput={setQuery} items={matches} itemKey={(option) => option}
        onPick={add} closeOnPick={false} invalid={invalid && !chosen.length}
        placeholder={chosen.length ? 'إضافة جهاز آخر…' : 'ابحث عن الجهاز لإضافته'}
        emptyText={left.length ? 'لا يوجد ما يطابق البحث.' : 'تمت إضافة كل الأجهزة.'}
        renderItem={(option) => <bdi>{option}</bdi>}
      />
    </div>
  );
}

// A field picked from a list, with «أخرى» at the end for anything the list has not got. What is
// saved is the chosen text itself, so nothing downstream has to know a list was involved — and a
// saved value the list does not offer is a custom one, which is how the box comes back on a draft.
// The empty line saves nothing; the backend's blank_value then stands in for it («لا يوجد»).
const OTHER = '__other__';

export function ChoiceOrOther({ spec, value, invalid, onChange }) {
  const chosen = String(value ?? '');
  const known = spec.choices.some((choice) => choice.value === chosen);
  // Kept so «أخرى» stays picked while the box is still empty, and while what is typed into it
  // happens to match a line of the list word for word
  const [other, setOther] = useState(Boolean(chosen) && !known);
  const custom = other || (Boolean(chosen) && !known);
  return (
    <div className="fl-stack fl-stack--sm">
      <Select
        id={spec.name} value={custom ? OTHER : chosen} invalid={invalid}
        onChange={(e) => {
          const picked = e.target.value;
          setOther(picked === OTHER);
          onChange(spec.name, picked === OTHER ? '' : picked);
        }}
      >
        <option value="">{spec.blank_value || 'بدون تحديد'}</option>
        {spec.choices.map((choice) => <option key={choice.label} value={choice.value}>{choice.label}</option>)}
        <option value={OTHER}>{spec.other_label}</option>
      </Select>
      {custom && (
        <TextArea
          id={`${spec.name}-other`} value={chosen} rows={2} invalid={invalid}
          aria-label={spec.other_label} placeholder={`اكتب ${spec.label} حرفيًا`}
          onChange={(e) => onChange(spec.name, e.target.value)}
        />
      )}
    </div>
  );
}

// A field typed freely, offering the suggestions that match what is typed (staff names, areas,
// discount names) in the portal's own list rather than the browser's, which cannot be styled
// onPick: what a name chosen from the list does, when that is more than typing it (an initiative
// fills in its own قيمة الخصم). Without it, picking is the same as typing the name.
export function SuggestInput({ spec, value, invalid, onChange, onPick, onBlur }) {
  const matches = useMemo(
    () => (spec.suggestions || []).filter((text) => matchesQuery(value ?? '', text)).slice(0, 50),
    [spec.suggestions, value],
  );
  return (
    <Combobox
      id={spec.name} value={value} invalid={invalid} icon={spec.type === 'staff' ? 'user' : 'chevron-down'}
      // Nothing matching closes the list: what is typed is kept as it is
      items={matches.length ? matches : null} itemKey={(text) => text} renderItem={(text) => <bdi>{text}</bdi>}
      onInput={(text) => onChange(spec.name, text)} onPick={(text) => (onPick || onChange)(spec.name, text)}
      onBlur={onBlur && (() => onBlur(spec.name, value ?? ''))}
    />
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
        id={id} type="text" inputMode="numeric" className="fl-order-lines__qty fl-stepper__value" aria-label={label}
        value={current} onChange={(e) => set(e.target.value.replace(/[^\d]/g, ''))}
      />
      <Button type="button" icon="plus" iconOnly label={`زيادة ${label}`} disabled={current >= max} onClick={() => set(current + 1)} />
    </div>
  );
}

// A UAE phone number. The country code is fixed and shown rather than typed, so the number beside
// it is only ever the national part — and what the form keeps is the local form the client list and
// Daftra are searched by (0501234567), whichever way it was pasted in.
function PhoneInput({ spec, value, invalid, onChange, onSearch }) {
  const national = localPhone(value).replace(/^0/, '');
  // No more than a UAE number has: nine digits after the code for a mobile (5X XXXXXXX), eight for
  // a landline. Anything beyond that is a typo, and the field stops taking it.
  //
  // The cap is here and not maxLength on the input: that counts the characters as typed, so a
  // pasted «+971 55 183 1536» would be cut to its first nine — country code and all — leaving a
  // number nobody entered. These are the digits left once the code has been taken off.
  const change = (typed) => {
    const kept = localPhone(typed).replace(/^0/, '').slice(0, 9);
    onChange(spec.name, kept ? `0${kept}` : '');
  };
  return (
    <TextInput
      id={spec.name} value={national} invalid={invalid} type="text" inputMode="tel" autoComplete="off"
      start={<span className="fl-box__code" id={`${spec.name}-code`}>+971</span>}
      aria-describedby={`${spec.name}-code`}
      icon="search" iconLabel={onSearch ? `بحث عن العميل بـ${spec.label}` : undefined}
      onIconClick={onSearch && (() => onSearch(spec.name, value ?? ''))}
      enterKeyHint={onSearch ? 'search' : undefined}
      onChange={(e) => change(e.target.value)}
      onKeyDown={onSearch && ((e) => {
        if (e.key !== 'Enter') return;
        e.preventDefault();
        onSearch(spec.name, localPhone(e.target.value));
        e.target.blur();
      })}
    />
  );
}

// The control for one plain field. onSearch: the field looks the client up; both its magnifier and
// the keyboard's own search key run the search
export function Control({ spec, value, invalid, onChange, onPick, onBlur, onSearch }) {
  const common = {
    id: spec.name,
    value: value ?? '',
    invalid,
    // Filled in by something else and not typed into: الإحداثيات come from the map's pin
    readOnly: spec.readonly || undefined,
    placeholder: spec.placeholder,
    onChange: (e) => onChange(spec.name, e.target.value),
    onBlur: onBlur && ((e) => onBlur(spec.name, e.target.value)),
  };
  // A list to pick from with «أخرى» at its end, whatever the field's own type is: what «أخرى»
  // saves is plain text, which is checked and stored as it was before the list existed
  if (spec.choices) {
    return <ChoiceOrOther spec={spec} value={value} invalid={invalid} onChange={onChange} />;
  }
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
      ? <MultiSelectPicker spec={spec} value={value} invalid={invalid} onChange={onChange} />
      : <Choice name={spec.name} multiple options={spec.options} value={value} invalid={invalid} onChange={(v) => onChange(spec.name, v)} />;
  }
  if (spec.type === 'textarea') return <TextArea {...common} rows={3} />;
  if (spec.suggestions && !onSearch) {
    return <SuggestInput spec={spec} value={value} invalid={invalid} onChange={onChange} onPick={onPick} onBlur={onBlur} />;
  }
  if (spec.type === 'date') return <TextInput {...common} type="date" />;
  if (spec.type === 'phone') return <PhoneInput spec={spec} value={value} invalid={invalid} onChange={onChange} onSearch={onSearch} />;
  if (spec.type === 'email') return <TextInput {...common} type="email" dir="ltr" inputMode="email" autoComplete="off" />;
  const inputMode = { number: spec.integer ? 'numeric' : 'decimal', phone: 'tel' }[spec.type];
  // A field the client is looked up by: its keyboard says «بحث», and digits are what gets typed
  const searching = Boolean(onSearch);
  const icon = spec.type === 'phone' || onSearch ? 'search' : undefined;
  return (
    <>
      {/* A phone keeps its number pad, and the client code is digits too; on both, the keyboard's own
          Enter key says «بحث» and runs the search */}
      <TextInput
        {...common} icon={icon} type="text" autoComplete="off"
        /* ltr: a value that is read left to right whatever the page is, e.g. «24.178700, 55.604510» */
        dir={spec.ltr ? 'ltr' : undefined}
        inputMode={inputMode ?? (spec.ltr ? 'decimal' : searching ? 'numeric' : undefined)} enterKeyHint={searching ? 'search' : undefined}
        onIconClick={onSearch && (() => onSearch(spec.name, value ?? ''))} iconLabel={onSearch && `بحث عن العميل بـ${spec.label}`}
        onKeyDown={onSearch && ((e) => {
          if (e.key !== 'Enter') return;
          // Enter searches instead of doing nothing; the form is never sent by a keystroke
          e.preventDefault();
          onSearch(spec.name, e.target.value);
          e.target.blur();
        })}
      />
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
