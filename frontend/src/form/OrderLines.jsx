// The products and packages of a request (field type "order_lines" in backend/app/forms/).
import { useMemo, useState } from 'react';
import { Button, Combobox, Field, Icon, Select, TextInput } from '../ds/index.jsx';
import { formatMoney } from '../formsMeta.js';
import { groupLines, linePrice, packageColors, packageQuantity } from '../validation.js';
import { Control, guessFromProductName, Stepper } from './fields.jsx';

const newGroupId = () => `g${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;

// A package's (or a standalone product's) own fields: colours, build details, the inscription.
// forPackage: a product picked on its own has its own quantity box instead of «الكمية».
// packageName: the package's (or the product's) name, which decides the cover colours offered.
function DetailFields({ lineFields, details, errors, keyPrefix, onChange, forPackage, packageName }) {
  const shown = lineFields.filter((dspec) => forPackage || !dspec.package_only);
  if (!shown.length) return null;
  // A field with a partner (one marked "beside" it) shares a full line with it: two thirds and one third
  const besides = Object.fromEntries(shown.filter((dspec) => dspec.beside).map((dspec) => [dspec.beside, dspec]));
  const colorChoices = (dspec) => packageColors(dspec, packageName);

  const fieldOf = (dspec) => {
    const id = `${keyPrefix}-${dspec.name}`;
    const error = errors?.[dspec.name];
    const required = dspec.type === 'package_color' ? colorChoices(dspec).length > 0 && !dspec.optional : dspec.required;
    let control;
    if (dspec.type === 'package_color') {
      const choices = colorChoices(dspec);
      control = (
        <Select id={id} value={details?.[dspec.name] ?? ''} invalid={Boolean(error)} disabled={!choices.length}
          onChange={(e) => onChange(dspec.name, e.target.value)}>
          <option value="">{choices.length ? 'اختر اللون…' : 'لا توجد ألوان لهذه الباقة'}</option>
          {choices.map((option) => <option key={option}>{option}</option>)}
        </Select>
      );
    } else if (dspec.stepper) {
      control = (
        <Stepper id={id} label={dspec.label} min={dspec.min ?? 1} max={dspec.max ?? 99} value={details?.[dspec.name]}
          onChange={(value) => onChange(dspec.name, value)} />
      );
    } else {
      // A package's details are always drop-downs, however few their options
      control = (
        <Control spec={{ ...dspec, name: id, dropdown: true }} value={details?.[dspec.name] ?? ''} invalid={Boolean(error)}
          onChange={(_, value) => onChange(dspec.name, value)} />
      );
    }
    return <Field key={dspec.name} label={dspec.label} htmlFor={id} error={error} required={required}>{control}</Field>;
  };

  const wide = (dspec) => ['textarea', 'multiselect'].includes(dspec.type) || dspec.stepper;
  return (
    <div className="fl-order-lines__details fl-grid">
      {shown.filter((dspec) => !dspec.beside || !shown.some((other) => other.name === dspec.beside)).map((dspec) => (
        <div key={dspec.name} className={besides[dspec.name] ? 'fl-pair fl-wide' : (wide(dspec) ? 'fl-wide' : undefined)}>
          {fieldOf(dspec)}
          {besides[dspec.name] && fieldOf(besides[dspec.name])}
        </div>
      ))}
    </div>
  );
}

// A repeatable list of products/packages for one request. Picking a package keeps its name
// as a group the user can fold or open; picking a product adds it as its own row. Lines keep
// a group_id/group_name so the grouping survives a saved draft.
export default function OrderLines({ spec, value, invalid, catalog, onChange, lineErrors }) {
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
    if (!items) return null;
    const words = query.toLowerCase().split(/\s+/).filter(Boolean);
    const text = (item) => `${item.name} ${item.name_ar || ''} ${item.maintenance_group || ''}`.toLowerCase();
    return items.filter((item) => words.every((word) => text(item).includes(word))).slice(0, 40);
  }, [items, query]);
  const groups = useMemo(() => groupLines(lines), [lines]);
  const set = (next) => onChange(spec.name, next);

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
      const groupId = newGroupId();
      const details = { package_quantity: '1', ...guessedDetails(item.name, item.items.map((line) => line.name)) };
      // Each line keeps the package it came from and the price it has there (the server checks it again)
      // base_quantity: how many the package itself holds; «الكمية» multiplies it into quantity
      const added = item.items.map((line) => ({
        product_id: line.product_id, name: line.name, quantity: line.quantity, base_quantity: line.quantity, group_id: groupId,
        group_name: item.name, package_id: item.id, unit_price: line.unit_price, details: { ...details },
      }));
      set([...lines, ...added]);
      setOpenGroups((current) => new Set([...current, groupId]));
    } else {
      set([...lines, {
        product_id: item.id, name: item.name, quantity: 1, group_id: null, group_name: '', package_id: null, unit_price: item.price ?? 0,
        details: guessedDetails('', [item.name]),
      }]);
    }
    setQuery('');
  }

  const setQuantity = (index, quantity) => set(lines.map((line, i) => (i === index ? { ...line, quantity } : line)));
  const removeLine = (index) => set(lines.filter((_, i) => i !== index));
  const removeGroup = (groupId) => {
    set(lines.filter((line) => line.group_id !== groupId));
    setOpenGroups((current) => { const next = new Set(current); next.delete(groupId); return next; });
  };
  // A standalone product's details live on its one line; a package's live on every line in its
  // group (kept in sync here), since they describe the package as a whole, not one item inside it.
  const setDetail = (index, name, fieldValue) => set(lines.map((line, i) => (
    i === index ? { ...line, details: { ...line.details, [name]: fieldValue } } : line
  )));
  // Changing a package's «الكمية» changes how many of each of its products there are
  const setGroupDetail = (groupId, name, fieldValue) => set(lines.map((line) => {
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
        {!line.group_id && (
          <DetailFields lineFields={lineFields} details={line.details} errors={lineErrors?.[index]} keyPrefix={`${spec.name}-${index}`}
            onChange={(name, v) => setDetail(index, name, v)} forPackage={false} packageName={line.name} />
        )}
      </div>
    );
  }

  function packageGroup(group) {
    const first = group.rows[0];
    const count = packageQuantity(first.line);
    const total = group.rows.reduce((sum, { line }) => sum + linePrice(line, priceById) * (Number(line.quantity) || 0), 0);
    const open = openGroups.has(group.key);
    return (
      <div key={group.key} className="fl-order-lines__group">
        <div className="fl-order-lines__row fl-order-lines__group-head">
          <Icon name="package" size={18} />
          <bdi className="fl-order-lines__name">{group.groupName}</bdi>
          <span className="fl-small fl-muted fl-cell--nowrap" data-fl-num>
            {count > 1 && `× ${count} · `}
            {formatMoney(total)} درهم
          </span>
          <Button type="button" size="sm" variant="ghost" icon={open ? 'chevron-up' : 'chevron-down'} aria-expanded={open}
            onClick={() => toggleGroup(group.key)}>
            <span data-fl-num>{group.rows.length}</span> منتجات
          </Button>
          <Button type="button" size="sm" variant="ghost" icon="trash" iconOnly label={`إزالة ${group.groupName}`} onClick={() => removeGroup(group.key)} />
        </div>
        <DetailFields lineFields={lineFields} details={first.line.details} errors={lineErrors?.[first.index]}
          keyPrefix={`${spec.name}-${group.key}`} onChange={(name, v) => setGroupDetail(group.key, name, v)} forPackage
          packageName={group.groupName} />
        {open && <div className="fl-order-lines__group-items">{group.rows.map(row)}</div>}
      </div>
    );
  }

  return (
    <div className="fl-stack fl-stack--sm">
      {groups.length > 0 && (
        <div className="fl-order-lines">
          {groups.map((group) => (group.groupName ? packageGroup(group) : group.rows.map(row)))}
        </div>
      )}
      <Combobox
        id={spec.name} value={query} onInput={setQuery} items={matches} invalid={invalid && !lines.length} closeOnPick={false}
        itemKey={(item) => `${item.kind}-${item.id}`} onPick={addItem} emptyText="لا يوجد ما يطابق البحث."
        placeholder={items
          ? (maintenance ? 'ابحث عن بند (فلتر، قطعة غيار، خدمة…) لإضافته' : 'ابحث عن منتج أو باقة لإضافتها')
          : catalog.catalogItemsError ? '' : 'جارٍ تحميل المنتجات والباقات…'}
        renderItem={(item) => (
          <>
            <bdi>{item.name}</bdi>
            <small>
              {maintenance ? [item.name_ar, item.maintenance_group].filter(Boolean).join(' · ') : item.kind === 'package' ? 'باقة' : 'منتج'}
              {item.price ? ` · ${item.price} درهم` : ''}
            </small>
          </>
        )}
      />
    </div>
  );
}
