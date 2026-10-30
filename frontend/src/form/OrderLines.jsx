// The products and packages of a request (field type "order_lines" in backend/app/forms/).
import { Fragment, useMemo, useState } from 'react';
import { Button, Combobox, Field, Icon, Select } from '../ds/index.jsx';
import { formatMoney } from '../formsMeta.js';
import { groupLines, linePrice, packageColors, packageQuantity } from '../validation.js';
import { Control, guessFromProductName, Stepper } from './fields.jsx';

const newGroupId = () => `g${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
// المنتج، الكمية، سعر الوحدة، الإجمالي and the row's buttons: what a details row spans
const COLUMNS = 5;

// A package's (or a standalone product's) own fields: colours, build details, the inscription.
// forPackage: a product picked on its own has its own quantity box instead of «الكمية».
// packageName: the package's (or the product's) name, which decides the cover colours offered.
// A colour field with no colours for this package (or for a product picked on its own) would only
// render as a disabled box saying so, which is a field's worth of space for nothing.
// only_for: a field belonging to certain products (وصف العمل، سعر الوحدة under «أخرى»)
function fieldsOfLine(lineFields, { forPackage, packageName, daftraId }) {
  return lineFields.filter((dspec) => (forPackage || !dspec.package_only)
    && (!dspec.only_for || dspec.only_for.includes(daftraId))
    && (dspec.type !== 'package_color' || packageColors(dspec, packageName).length > 0));
}

function DetailFields({ lineFields, details, errors, keyPrefix, onChange, forPackage, packageName, daftraId }) {
  const shown = fieldsOfLine(lineFields, { forPackage, packageName, daftraId });
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
        <Control spec={{ ...dspec, name: id, dropdown: dspec.type === 'select' }} value={details?.[dspec.name] ?? ''}
          invalid={Boolean(error)} onChange={(_, value) => onChange(dspec.name, value)} />
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
  // items: "maintenance" offers only the catalog's maintenance items (products with a maintenance
  // group); item_ids names the products outright, by their Daftra id (اعمال اضافية)
  const maintenance = spec.items === 'maintenance';
  const only = spec.item_ids;
  const items = useMemo(() => {
    const products = catalog.catalogItems?.filter((item) => item.kind === 'product');
    if (only) {
      return products?.filter((item) => only.includes(item.daftra_id))
        .sort((a, b) => only.indexOf(a.daftra_id) - only.indexOf(b.daftra_id));
    }
    return maintenance ? products?.filter((item) => item.maintenance_group) : catalog.catalogItems;
  }, [catalog.catalogItems, maintenance, only]);
  const priceById = useMemo(() => new Map((catalog.products || []).map((p) => [p.id, p.price || 0])), [catalog.products]);
  // Which product a line is, as Daftra numbers it: what only_for on a line field is matched against
  const daftraById = useMemo(
    () => new Map((catalog.catalogItems || []).filter((item) => item.kind === 'product').map((item) => [item.id, item.daftra_id])),
    [catalog.catalogItems],
  );
  const daftraOf = (line) => daftraById.get(Number(line.product_id));
  // Products whose price is typed on the line, not taken from the catalog («أخرى»): they are
  // offered without a price, and start at nothing rather than at the catalog's stand-in figure
  const typedPrice = useMemo(
    () => new Set(lineFields.filter((dspec) => dspec.line_price).flatMap((dspec) => dspec.only_for || [])),
    [lineFields],
  );
  // item_labels: what this form calls a product, by its Daftra id. Only «أخرى» needs one: the rest
  // are offered under the name Daftra holds them by, which is the name their invoice line carries.
  const labelOf = (item) => spec.item_labels?.[item?.daftra_id] || item?.name || '';
  const lineLabel = (line) => spec.item_labels?.[daftraOf(line)] || line.name;
  const matches = useMemo(() => {
    if (!items) return null;
    const words = query.toLowerCase().split(/\s+/).filter(Boolean);
    const text = (item) => `${item.name} ${item.name_ar || ''} ${item.maintenance_group || ''} ${item.description || ''} ${labelOf(item)}`.toLowerCase();
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
        product_id: item.id, name: labelOf(item), quantity: 1, group_id: null, group_name: '', package_id: null,
        unit_price: typedPrice.has(item.daftra_id) ? 0 : (item.price ?? 0),
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

  // One row of the table: the product, its quantity, what one costs and what the row costs.
  // inPackage: a line that came with a package is indented under it and has no fields of its own.
  function row({ line, index }, inPackage = false) {
    const unit = linePrice(line, priceById, lineFields);
    return (
      <Fragment key={`line-${index}`}>
        <tr className={inPackage ? 'fl-row--child' : undefined}>
          <td className="fl-cell--wrap fl-cell--title"><bdi>{lineLabel(line)}</bdi></td>
          <td className="fl-cell--qty" data-label="الكمية">
            <input
              className="fl-mini fl-order-lines__qty" type="number" min="1" inputMode="numeric"
              aria-label={`الكمية — ${line.name}`} value={line.quantity}
              onChange={(e) => setQuantity(index, Math.max(1, Number(e.target.value) || 1))}
            />
          </td>
          <td className="fl-cell--unit" data-label="سعر الوحدة" data-fl-num><bdi dir="ltr">{formatMoney(unit)}</bdi></td>
          <td className="fl-cell--total" data-label="الإجمالي" data-fl-num><bdi dir="ltr">{formatMoney(unit * (Number(line.quantity) || 0))}</bdi></td>
          <td className="fl-cell--actions">
            <Button type="button" size="sm" variant="ghost" icon="trash" iconOnly label={`إزالة ${line.name}`} onClick={() => removeLine(index)} />
          </td>
        </tr>
        {/* A line inside a package shows no fields of its own — they belong to the package, above */}
        {!line.group_id && fieldsOfLine(lineFields, { forPackage: false, packageName: line.name, daftraId: daftraOf(line) }).length > 0 && (
          <tr className="fl-row--detail">
            <td colSpan={COLUMNS}>
              <DetailFields lineFields={lineFields} details={line.details} errors={lineErrors?.[index]} keyPrefix={`${spec.name}-${index}`}
                onChange={(name, v) => setDetail(index, name, v)} forPackage={false} packageName={line.name}
                daftraId={daftraOf(line)} />
            </td>
          </tr>
        )}
      </Fragment>
    );
  }

  function packageGroup(group) {
    const first = group.rows[0];
    const count = packageQuantity(first.line);
    const total = group.rows.reduce((sum, { line }) => sum + linePrice(line, priceById, lineFields) * (Number(line.quantity) || 0), 0);
    const open = openGroups.has(group.key);
    return (
      <Fragment key={group.key}>
        <tr className="fl-row--group">
          <td className="fl-cell--wrap fl-cell--title">
            <span className="fl-order-lines__package"><Icon name="package" size={18} /><bdi><strong>{group.groupName}</strong></bdi></span>
            <span className="fl-cell__sub">باقة — <span data-fl-num>{group.rows.length}</span> منتجات</span>
          </td>
          {/* The package's own «الكمية» is set by its stepper below; here it is what the number means */}
          <td className="fl-cell--qty" data-label="عدد الباقات" data-fl-num>{count}</td>
          <td className="fl-cell--unit fl-muted" data-label="سعر الوحدة">—</td>
          <td className="fl-cell--total" data-label="الإجمالي" data-fl-num><strong><bdi dir="ltr">{formatMoney(total)}</bdi></strong></td>
          <td className="fl-cell--actions">
            <Button type="button" size="sm" variant="ghost" icon={open ? 'chevron-up' : 'chevron-down'} iconOnly
              aria-expanded={open} label={open ? `إخفاء منتجات ${group.groupName}` : `عرض منتجات ${group.groupName}`}
              onClick={() => toggleGroup(group.key)} />
            <Button type="button" size="sm" variant="ghost" icon="trash" iconOnly label={`إزالة ${group.groupName}`} onClick={() => removeGroup(group.key)} />
          </td>
        </tr>
        <tr className="fl-row--detail">
          <td colSpan={COLUMNS}>
            <DetailFields lineFields={lineFields} details={first.line.details} errors={lineErrors?.[first.index]}
              keyPrefix={`${spec.name}-${group.key}`} onChange={(name, v) => setGroupDetail(group.key, name, v)} forPackage
              packageName={group.groupName} />
          </td>
        </tr>
        {open && group.rows.map((entry) => row(entry, true))}
      </Fragment>
    );
  }

  return (
    <div className="fl-stack fl-stack--sm">
      {groups.length > 0 && (
        <div className="fl-table-wrap fl-order-lines">
          <div className="fl-table-scroll">
            <table className="fl-table">
              <thead>
                <tr>
                  <th>المنتج</th><th>الكمية</th><th>سعر الوحدة (درهم)</th><th>الإجمالي (درهم)</th><th />
                </tr>
              </thead>
              <tbody>
                {groups.map((group) => (group.groupName ? packageGroup(group) : group.rows.map((entry) => row(entry))))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      <Combobox
        id={spec.name} value={query} onInput={setQuery} items={matches} invalid={invalid && !lines.length} closeOnPick={false}
        itemKey={(item) => `${item.kind}-${item.id}`} onPick={addItem} emptyText="لا يوجد ما يطابق البحث."
        placeholder={items
          ? (only ? 'ابحث عن العمل المطلوب لإضافته'
            : maintenance ? 'ابحث عن بند (فلتر، قطعة غيار، خدمة…) لإضافته' : 'ابحث عن منتج أو باقة لإضافتها')
          : catalog.catalogItemsError ? '' : 'جارٍ تحميل المنتجات والباقات…'}
        renderItem={(item) => (
          <>
            <bdi>{labelOf(item)}</bdi>
            <small>
              {only ? [item.name.trim(), item.description].filter(Boolean).join(' · ')
                : maintenance ? [item.name_ar, item.maintenance_group].filter(Boolean).join(' · ')
                  : item.kind === 'package' ? 'باقة' : 'منتج'}
              {item.price && !typedPrice.has(item.daftra_id) ? ` · ${item.price} درهم` : ''}
            </small>
          </>
        )}
      />
    </div>
  );
}
