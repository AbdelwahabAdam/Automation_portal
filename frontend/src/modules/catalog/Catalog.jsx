import { useEffect, useMemo, useState } from 'react';
import * as catalogApi from '../../api/catalog.js';
import {
  Alert, Badge, Button, Checkbox, Drawer, EmptyState, Field, Loading, PageHeader, Pager, SearchInput, Select, Tabs, TextArea, TextInput,
  Skeleton, useConfirm, useToast,
} from '../../ds/index.jsx';
import { formatMoney as money } from '../../lib/format.js';
import { matchesQuery } from '../../ds/match.js';
import { useAction } from '../../lib/hooks.js';

// ---------- Products ----------

const NEW_PRODUCT = {
  name: '', name_ar: '', description: '', unit_price: '', price_includes_tax: true, tax_rate: 0.05, is_active: true,
  product_code: '', barcode: '', buy_price: '', stock_balance: '', category: '', brand: '', daftra_id: '', maintenance_group: '',
};
// The groups طلب صيانة وتبديل lists its items under (Maintenance_Invoice_Items.xlsx)
const MAINTENANCE_GROUPS = ['الفلاتر', 'قطع الغيار', 'الهيد والميديا', 'الخدمات'];

function ProductDrawer({ product, onSaved, onDeleted, onClose }) {
  const [values, setValues] = useState(product ? {
    ...product, tax_percent: product.tax_rate * 100,
    buy_price: product.buy_price ?? '', stock_balance: product.stock_balance ?? '', daftra_id: product.daftra_id ?? '',
  } : { ...NEW_PRODUCT, tax_percent: 5 });
  const { error, busy, run } = useAction();
  const [confirmDialog, confirm] = useConfirm();
  // What is missing before the product can be saved, said here rather than by the server
  const [problem, setProblem] = useState('');
  const set = (name, value) => setValues((current) => ({ ...current, [name]: value }));

  function submit(e) {
    e?.preventDefault();
    if (!values.name.trim()) return setProblem('اكتب اسم المنتج كما يظهر في الفاتورة.');
    if (String(values.unit_price).trim() === '' || Number(values.unit_price) < 0) return setProblem('اكتب سعر الوحدة (صفر أو أكثر).');
    setProblem('');
    run('save', async () => {
      const body = {
        name: values.name, name_ar: values.name_ar, description: values.description, unit_price: Number(values.unit_price),
        price_includes_tax: values.price_includes_tax, tax_rate: Number(values.tax_percent) / 100, is_active: values.is_active,
        product_code: values.product_code, barcode: values.barcode,
        buy_price: values.buy_price === '' ? null : Number(values.buy_price),
        stock_balance: values.stock_balance === '' ? null : Number(values.stock_balance),
        category: values.category, brand: values.brand,
        daftra_id: values.daftra_id === '' || values.daftra_id == null ? null : Number(values.daftra_id),
        maintenance_group: values.maintenance_group || '',
      };
      onSaved(product ? await catalogApi.updateProduct(product.id, body) : await catalogApi.createProduct(body));
    });
  }

  async function remove() {
    const yes = await confirm({ title: `حذف المنتج «${product.name}»؟`, body: 'يُحذف المنتج نهائيًا من الكتالوج.', confirmLabel: 'حذف المنتج', tone: 'danger' });
    if (!yes) return;
    run('delete', async () => {
      await catalogApi.deleteProduct(product.id);
      onDeleted(product);
    });
  }

  return (
    <>
    {confirmDialog}
    <Drawer
      title={product ? 'تعديل منتج' : 'إضافة منتج'}
      subtitle="المنتج وحدة واحدة لا يدخل فيها شيء آخر."
      onClose={onClose}
      footer={(
        <>
          <Button variant="primary" loading={busy === 'save'} disabled={Boolean(busy)} onClick={submit}>حفظ</Button>
          <Button onClick={onClose}>إلغاء</Button>
          {product && (
            <span className="fl-push">
              <Button size="sm" variant="destructive-secondary" icon="trash" loading={busy === 'delete'} onClick={remove}>حذف المنتج</Button>
            </span>
          )}
        </>
      )}
    >
      <form className="fl-stack fl-stack--sm" onSubmit={submit} noValidate>
        {(problem || error) && <Alert tone="error">{problem || error}</Alert>}
        <Field label="الاسم كما يظهر في الفاتورة" htmlFor="p_name" required>
          <TextInput id="p_name" value={values.name} onChange={(e) => set('name', e.target.value)} maxLength={200} />
        </Field>
        <Field label="الاسم بالعربية" htmlFor="p_name_ar">
          <TextInput id="p_name_ar" value={values.name_ar} onChange={(e) => set('name_ar', e.target.value)} maxLength={200} />
        </Field>
        <div className="fl-grid">
          <Field label="سعر الوحدة (درهم)" htmlFor="p_price" required>
            <TextInput id="p_price" type="number" min="0" step="0.01" value={values.unit_price} onChange={(e) => set('unit_price', e.target.value)} />
          </Field>
          <Field label="نسبة الضريبة %" htmlFor="p_tax">
            <TextInput id="p_tax" type="number" min="0" max="100" step="0.01" value={values.tax_percent} onChange={(e) => set('tax_percent', e.target.value)} />
          </Field>
        </div>
        <Field label="الوصف" htmlFor="p_description">
          <TextArea id="p_description" rows={2} value={values.description} onChange={(e) => set('description', e.target.value)} maxLength={2000} />
        </Field>
        <div className="fl-stack fl-stack--sm">
          <Checkbox checked={values.price_includes_tax} onChange={(v) => set('price_includes_tax', v)}>السعر شامل الضريبة</Checkbox>
          <Checkbox checked={values.is_active} onChange={(v) => set('is_active', v)}>مفعّل</Checkbox>
        </div>
        <div className="fl-grid">
          <Field label="كود المنتج (دفترة)" htmlFor="p_code">
            <TextInput id="p_code" value={values.product_code} onChange={(e) => set('product_code', e.target.value)} maxLength={50} />
          </Field>
          <Field label="الباركود" htmlFor="p_barcode">
            <TextInput id="p_barcode" value={values.barcode} onChange={(e) => set('barcode', e.target.value)} maxLength={50} />
          </Field>
        </div>
        <div className="fl-grid">
          <Field label="سعر الشراء (درهم)" htmlFor="p_buy_price">
            <TextInput id="p_buy_price" type="number" min="0" step="0.01" value={values.buy_price} onChange={(e) => set('buy_price', e.target.value)} />
          </Field>
          <Field label="رصيد المخزون" htmlFor="p_stock">
            <TextInput id="p_stock" type="number" min="0" step="1" value={values.stock_balance} onChange={(e) => set('stock_balance', e.target.value)} />
          </Field>
        </div>
        <div className="fl-grid">
          <Field label="التصنيف" htmlFor="p_category">
            <TextInput id="p_category" value={values.category} onChange={(e) => set('category', e.target.value)} maxLength={200} />
          </Field>
          <Field label="الماركة" htmlFor="p_brand">
            <TextInput id="p_brand" value={values.brand} onChange={(e) => set('brand', e.target.value)} maxLength={100} />
          </Field>
        </div>
        <div className="fl-grid">
          <Field label="رقم دفترة" htmlFor="p_daftra_id" hint="رقم المنتج في دفترة؛ تستخدمه الفواتير التي تُنشأ عند اعتماد الطلبات.">
            <TextInput id="p_daftra_id" type="number" min="1" step="1" value={values.daftra_id ?? ''} onChange={(e) => set('daftra_id', e.target.value)} />
          </Field>
          <Field label="بند صيانة — المجموعة" htmlFor="p_maintenance_group" hint="يظهر في «إضافة بند» بطلب الصيانة والتبديل تحت هذه المجموعة.">
            <Select id="p_maintenance_group" value={values.maintenance_group || ''} onChange={(e) => set('maintenance_group', e.target.value)}>
              <option value="">ليس بند صيانة</option>
              {[...new Set([...MAINTENANCE_GROUPS, values.maintenance_group].filter(Boolean))].map((group) => <option key={group}>{group}</option>)}
            </Select>
          </Field>
        </div>
      </form>
    </Drawer>
    </>
  );
}

function Products({ products, onChange, toast }) {
  // null | { product } (product undefined for a new one)
  const [panel, setPanel] = useState(null);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  useEffect(() => setPage(1), [search, pageSize]);

  function done(message) {
    toast(message);
    setPanel(null);
    onChange();
  }

  const shown = products.filter((product) => matchesQuery(search, product.name, product.name_ar, product.maintenance_group || ''));
  // The SKU column only when some product has one (the proposals import leaves it empty)
  const withSku = products.some((product) => product.sku);
  return (
    <>
      <div className="fl-row fl-row--spread">
        <div className="fl-narrow-search"><SearchInput value={search} onChange={setSearch} placeholder="ابحث في المنتجات" /></div>
        <Button variant="primary" icon="plus" onClick={() => setPanel({})}>إضافة منتج</Button>
      </div>
      {!shown.length ? (
        <EmptyState icon="package" title={products.length ? 'لا توجد منتجات مطابقة' : 'لا توجد منتجات بعد'} />
      ) : (
        <div className="fl-table-wrap fl-stacked">
          <div className="fl-table-scroll">
            <table className="fl-table">
              <thead>
                <tr>
                  {withSku && <th>SKU</th>}
                  <th>المنتج</th><th>كود المنتج</th><th>التصنيف</th><th>بند صيانة</th><th>سعر الوحدة</th><th>المخزون</th>
                  <th>في كم باقة</th><th>الحالة</th><th>الإجراء</th>
                </tr>
              </thead>
              <tbody>
                {shown.slice((page - 1) * pageSize, page * pageSize).map((product) => (
                  <tr key={product.id} className={product.is_active ? undefined : 'fl-row--off'}>
                    {withSku && <td className="fl-cell--id" data-label="SKU"><bdi dir="ltr">{product.sku || '—'}</bdi></td>}
                    <td className="fl-cell--wrap">
                      <strong><bdi>{product.name}</bdi></strong>
                      {product.name_ar && <span className="fl-cell__sub">{product.name_ar}</span>}
                    </td>
                    <td className="fl-cell--id" data-label="كود المنتج"><bdi dir="ltr">{product.product_code || '—'}</bdi></td>
                    <td className="fl-cell--wrap fl-cell--minor" data-label="التصنيف">{product.category || '—'}</td>
                    <td className="fl-cell--wrap fl-cell--minor" data-label="بند صيانة">{product.maintenance_group || '—'}</td>
                    <td className="fl-cell--nowrap" data-label="سعر الوحدة" data-fl-num>
                      <bdi dir="ltr">{money(product.unit_price)}</bdi>
                      <span className="fl-cell__sub">{product.price_includes_tax ? 'شامل' : 'غير شامل'} <bdi dir="ltr">{money(product.tax_rate * 100)}%</bdi></span>
                    </td>
                    <td data-label="المخزون" data-fl-num>{product.stock_balance ?? '—'}</td>
                    <td className="fl-cell--minor" data-label="في كم باقة" data-fl-num>{product.package_count}</td>
                    <td data-label="الحالة">{product.is_active ? <Badge tone="success">مفعّل</Badge> : <Badge>موقوف</Badge>}</td>
                    <td className="fl-cell--actions"><Button size="sm" icon="edit" onClick={() => setPanel({ product })}>تعديل</Button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager page={page} pageSize={pageSize} total={shown.length} onPage={setPage} onPageSize={setPageSize} sizes={[20, 50, 100]} />
        </div>
      )}
      {panel && (
        <ProductDrawer
          key={panel.product?.id ?? 'new'} product={panel.product} onClose={() => setPanel(null)}
          onSaved={(saved) => done(`تم حفظ المنتج ${saved.name}.`)}
          onDeleted={(deleted) => done(`تم حذف المنتج ${deleted.name}.`)}
        />
      )}
    </>
  );
}

// ---------- Packages ----------

function lineTotal(line, product) {
  const gross = Number(line.unit_price || 0) * Number(line.quantity || 0) * (line.price_includes_tax ? 1 : 1 + (product?.tax_rate ?? 0));
  return Math.round((gross - Number(line.discount || 0)) * 100) / 100;
}

function PackageDrawer({ pack, products, onSaved, onDeleted, onClose }) {
  const [values, setValues] = useState(pack ? { name: pack.name, code: pack.code, color: pack.color, is_active: pack.is_active } : { name: '', code: '', color: '', is_active: true });
  // Each line gets a key of its own so React keeps the right inputs when one is removed
  const [lines, setLines] = useState(() => (pack ? pack.items.map((item, index) => ({ ...item, key: index })) : []));
  const [nextKey, setNextKey] = useState(pack ? pack.items.length : 0);
  const [adding, setAdding] = useState('');
  const { error, busy, run } = useAction();
  const [confirmDialog, confirm] = useConfirm();
  const [problem, setProblem] = useState('');
  const byId = Object.fromEntries(products.map((product) => [product.id, product]));
  const set = (name, value) => setValues((current) => ({ ...current, [name]: value }));
  const setLine = (key, name, value) => setLines((current) => current.map((line) => (line.key === key ? { ...line, [name]: value } : line)));

  // A new line starts from the product's usual price
  function addLine(productId) {
    const product = byId[productId];
    if (!product) return;
    setLines((current) => [...current, {
      key: nextKey, product_id: product.id, quantity: 1, unit_price: product.unit_price,
      price_includes_tax: product.price_includes_tax, discount: 0,
    }]);
    setNextKey(nextKey + 1);
    setAdding('');
  }

  function submit(e) {
    e?.preventDefault();
    if (!values.name.trim()) return setProblem('اكتب اسم الباقة.');
    const bad = lines.find((line) => !(Number(line.quantity) >= 1) || String(line.unit_price).trim() === '' || Number(line.unit_price) < 0);
    if (bad) return setProblem(`راجع كمية «${byId[bad.product_id]?.name || bad.product_name}» وسعرها: الكمية 1 أو أكثر والسعر صفر أو أكثر.`);
    setProblem('');
    run('save', async () => {
      const body = {
        ...values,
        items: lines.map((line) => ({
          product_id: line.product_id, quantity: Number(line.quantity), unit_price: Number(line.unit_price),
          price_includes_tax: line.price_includes_tax, discount: Number(line.discount || 0),
        })),
      };
      onSaved(pack ? await catalogApi.updatePackage(pack.id, body) : await catalogApi.createPackage(body));
    });
  }

  async function remove() {
    const yes = await confirm({ title: `حذف الباقة «${pack.name}»؟`, body: 'تُحذف الباقة نهائيًا؛ المنتجات نفسها لا تُحذف.', confirmLabel: 'حذف الباقة', tone: 'danger' });
    if (!yes) return;
    run('delete', async () => {
      await catalogApi.deletePackage(pack.id);
      onDeleted(pack);
    });
  }

  const used = new Set(lines.map((line) => line.product_id));
  const available = products.filter((product) => product.is_active && !used.has(product.id));
  const total = lines.reduce((sum, line) => sum + lineTotal(line, byId[line.product_id]), 0);
  return (
    <>
    {confirmDialog}
    <Drawer
      title={pack ? 'تعديل باقة' : 'إضافة باقة'}
      subtitle="الباقة منتج أو أكثر تُباع معًا، ولكل منتج فيها كميته وسعره وخصمه."
      width="min(100%, 760px)"
      onClose={onClose}
      footer={(
        <>
          <Button variant="primary" loading={busy === 'save'} disabled={Boolean(busy) || !lines.length} onClick={submit}>حفظ</Button>
          <Button onClick={onClose}>إلغاء</Button>
          {!lines.length && <span className="fl-field__hint">أضف منتجًا واحدًا على الأقل.</span>}
          {pack && (
            <span className="fl-push">
              <Button size="sm" variant="destructive-secondary" icon="trash" loading={busy === 'delete'} onClick={remove}>حذف الباقة</Button>
            </span>
          )}
        </>
      )}
    >
      <form className="fl-stack fl-stack--sm" onSubmit={submit} noValidate>
        {(problem || error) && <Alert tone="error">{problem || error}</Alert>}
        <div className="fl-grid">
          <Field label="اسم الباقة" htmlFor="k_name" required>
            <TextInput id="k_name" value={values.name} onChange={(e) => set('name', e.target.value)} maxLength={200} />
          </Field>
          <Field label="الكود" htmlFor="k_code">
            <TextInput id="k_code" value={values.code} onChange={(e) => set('code', e.target.value)} maxLength={30} placeholder="FLP-043" />
          </Field>
          <Field label="اللون" htmlFor="k_color">
            <TextInput id="k_color" value={values.color} onChange={(e) => set('color', e.target.value)} maxLength={40} />
          </Field>
        </div>
        <Checkbox checked={values.is_active} onChange={(v) => set('is_active', v)}>مفعّلة</Checkbox>
        <Field label="المنتجات داخل الباقة">
          {lines.length > 0 && (
            <div className="fl-table-wrap fl-lines fl-stacked">
              <div className="fl-table-scroll">
                <table className="fl-table">
                  <thead><tr><th>المنتج</th><th>الكمية</th><th>سعر الوحدة</th><th>شامل الضريبة</th><th>خصم البند</th><th>الإجمالي</th><th /></tr></thead>
                  <tbody>
                    {lines.map((line) => {
                      const product = byId[line.product_id];
                      const label = product?.name || line.product_name;
                      return (
                        <tr key={line.key}>
                          <td className="fl-cell--wrap"><bdi>{label}</bdi>{product?.name_ar && <span className="fl-cell__sub">{product.name_ar}</span>}</td>
                          <td data-label="الكمية"><input className="fl-mini" type="number" min="1" max="9999" step="1" value={line.quantity} onChange={(e) => setLine(line.key, 'quantity', e.target.value)} aria-label={`كمية ${label}`} /></td>
                          <td data-label="سعر الوحدة"><input className="fl-mini" type="number" min="0" step="0.01" value={line.unit_price} onChange={(e) => setLine(line.key, 'unit_price', e.target.value)} aria-label={`سعر ${label}`} /></td>
                          <td data-label="شامل الضريبة"><input type="checkbox" className="fl-mini-check" checked={line.price_includes_tax} onChange={(e) => setLine(line.key, 'price_includes_tax', e.target.checked)} aria-label={`سعر ${label} شامل الضريبة`} /></td>
                          <td data-label="خصم البند"><input className="fl-mini" type="number" min="0" step="0.01" value={line.discount} onChange={(e) => setLine(line.key, 'discount', e.target.value)} aria-label={`خصم ${label}`} /></td>
                          <td data-label="الإجمالي" data-fl-num><bdi dir="ltr">{money(lineTotal(line, product))}</bdi></td>
                          <td className="fl-cell--actions"><Button size="sm" variant="ghost" icon="trash" iconOnly label={`إزالة ${label}`} onClick={() => setLines((current) => current.filter((l) => l.key !== line.key))} /></td>
                        </tr>
                      );
                    })}
                  </tbody>
                  <tfoot><tr><td colSpan={5}>إجمالي الباقة شامل الضريبة</td><td data-fl-num><bdi dir="ltr">{money(total)}</bdi></td><td /></tr></tfoot>
                </table>
              </div>
            </div>
          )}
        </Field>
        <Field label="إضافة منتج إلى الباقة" htmlFor="k_add">
          <Select id="k_add" value={adding} onChange={(e) => addLine(Number(e.target.value))}>
            <option value="">اختر منتجًا…</option>
            {available.map((product) => (
              <option key={product.id} value={product.id}>{product.name}{product.name_ar ? ` — ${product.name_ar}` : ''} ({money(product.unit_price)})</option>
            ))}
          </Select>
        </Field>
      </form>
    </Drawer>
    </>
  );
}

function PackageRow({ pack, open, onToggle, onEdit }) {
  return (
    <>
      <tr className={pack.is_active ? undefined : 'fl-row--off'}>
        <td className="fl-cell--id" data-label="الكود"><bdi dir="ltr">{pack.code || '—'}</bdi></td>
        <td className="fl-cell--wrap"><strong><bdi>{pack.name}</bdi></strong></td>
        <td data-label="اللون">{pack.color || '—'}</td>
        <td data-label="عدد المنتجات" data-fl-num>{pack.items.length}</td>
        <td data-label="الإجمالي شامل الضريبة" data-fl-num><bdi dir="ltr">{money(pack.total)}</bdi></td>
        <td data-label="الحالة">{pack.is_active ? <Badge tone="success">مفعّلة</Badge> : <Badge>موقوفة</Badge>}</td>
        <td className="fl-cell--actions">
          <Button size="sm" variant="tertiary" iconEnd={open ? 'chevron-up' : 'chevron-down'} aria-expanded={open} onClick={onToggle}>{open ? 'إخفاء' : 'المنتجات'}</Button>
          <Button size="sm" icon="edit" onClick={onEdit}>تعديل</Button>
        </td>
      </tr>
      {open && (
        <tr className="fl-row--detail">
          <td colSpan={7}>
            <div className="fl-table-wrap fl-stacked">
              <div className="fl-table-scroll">
                <table className="fl-table">
                  <thead><tr><th>المنتج</th><th>بالعربية</th><th>الكمية</th><th>سعر الوحدة</th><th>خصم البند</th><th>الإجمالي</th></tr></thead>
                  <tbody>
                    {pack.items.map((item) => (
                      <tr key={item.product_id}>
                        <td className="fl-cell--wrap"><bdi>{item.product_name}</bdi></td>
                        <td className="fl-cell--full" data-label="بالعربية">{item.product_name_ar || '—'}</td>
                        <td data-label="الكمية" data-fl-num>{item.quantity}</td>
                        <td data-label="سعر الوحدة"><bdi dir="ltr">{money(item.unit_price)}</bdi> {item.price_includes_tax ? '' : '+ ضريبة'}</td>
                        <td data-label="خصم البند"><bdi dir="ltr">{item.discount ? money(item.discount) : '—'}</bdi></td>
                        <td data-label="الإجمالي" data-fl-num><bdi dir="ltr">{money(item.total)}</bdi></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function Packages({ packages, products, onChange, toast }) {
  const [panel, setPanel] = useState(null);
  const [search, setSearch] = useState('');
  const [openId, setOpenId] = useState(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  useEffect(() => setPage(1), [search, pageSize]);

  function done(message) {
    toast(message);
    setPanel(null);
    onChange();
  }

  const shown = useMemo(() => packages.filter((pack) => matchesQuery(search, pack.name, pack.code, pack.color)), [packages, search]);
  return (
    <>
      <div className="fl-row fl-row--spread">
        <div className="fl-narrow-search"><SearchInput value={search} onChange={setSearch} placeholder="ابحث في الباقات" /></div>
        <Button variant="primary" icon="plus" onClick={() => setPanel({})}>إضافة باقة</Button>
      </div>
      {!shown.length ? (
        <EmptyState icon="layers" title={packages.length ? 'لا توجد باقات مطابقة' : 'لا توجد باقات بعد'} />
      ) : (
        <div className="fl-table-wrap fl-stacked">
          <div className="fl-table-scroll">
            <table className="fl-table">
              <thead><tr><th>الكود</th><th>الباقة</th><th>اللون</th><th>عدد المنتجات</th><th>الإجمالي شامل الضريبة</th><th>الحالة</th><th>الإجراء</th></tr></thead>
              <tbody>
                {shown.slice((page - 1) * pageSize, page * pageSize).map((pack) => (
                  <PackageRow key={pack.id} pack={pack} open={openId === pack.id} onToggle={() => setOpenId(openId === pack.id ? null : pack.id)}
                    onEdit={() => setPanel({ pack })} />
                ))}
              </tbody>
            </table>
          </div>
          <Pager page={page} pageSize={pageSize} total={shown.length} onPage={setPage} onPageSize={setPageSize} sizes={[20, 50, 100]} />
        </div>
      )}
      {panel && (
        <PackageDrawer
          key={panel.pack?.id ?? 'new'} pack={panel.pack} products={products} onClose={() => setPanel(null)}
          onSaved={(saved) => done(`تم حفظ الباقة ${saved.name}.`)}
          onDeleted={(deleted) => done(`تم حذف الباقة ${deleted.name}.`)}
        />
      )}
    </>
  );
}

// ---------- Page ----------

export default function Catalog() {
  const [tab, setTab] = useState('products');
  const toast = useToast();
  const [products, setProducts] = useState(null);
  const [packages, setPackages] = useState(null);
  const [error, setError] = useState('');

  // A change to a product shows in the packages that contain it, so both lists are reloaded together
  function load() {
    Promise.all([catalogApi.listProducts(), catalogApi.listPackages()])
      .then(([loadedProducts, loadedPackages]) => {
        setProducts(loadedProducts);
        setPackages(loadedPackages);
      })
      .catch((err) => setError(err.message));
  }
  useEffect(load, []);

  const header = <PageHeader title="المنتجات والباقات" subtitle="المنتج وحدة واحدة لا يدخل فيها شيء آخر. الباقة منتج أو أكثر تُباع معًا." />;
  if (!products || !packages) return <div className="fl-stack">{header}{error ? <Alert tone="error">{error}</Alert> : <Skeleton lines={6} />}</div>;
  return (
    <div className="fl-stack">
      {header}
      {error && <Alert tone="error">{error}</Alert>}
      <Tabs label="المنتجات والباقات" value={tab} onChange={setTab}
        tabs={[{ value: 'products', label: 'المنتجات', count: products.length }, { value: 'packages', label: 'الباقات', count: packages.length }]} />
      {tab === 'products'
        ? <Products products={products} onChange={load} toast={toast} />
        : <Packages packages={packages} products={products} onChange={load} toast={toast} />}
    </div>
  );
}

