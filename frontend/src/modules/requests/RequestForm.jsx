import { useEffect, useMemo, useRef, useState } from 'react';
import * as clientsApi from '../../api/clients.js';
import * as requestsApi from '../../api/requests.js';
import {
  ActionBar, Alert, Badge, Button, Dialog, Field, PageHeader, Section, Skeleton, TextInput, useToast,
} from '../../ds/index.jsx';
import { ClientLookupNote, SEARCH_FIELDS, useClientLookup } from './form/ClientLookup.jsx';
import { Control, DaftraListSelect, FileField, ProductPicker, guessFromProductName, showsAsChoice } from './form/fields.jsx';
import FormProgress, { Totals, formTotals } from './form/FormProgress.jsx';
import OrderLines from './form/OrderLines.jsx';
import { formatAmount } from '../../lib/format.js';
import { afterArea, afterCategory, afterEmirate, categoriesFor, categoryById } from './address.js';
import { DAFTRA_LIST_TYPES, allFields, coordinatesFromLink, evaluateForm, fieldApplies, initialValues } from './validation.js';

// Sections open when a form starts; the rest are folded until needed
const OPEN_AT_START = 4;
// Field types that take a whole row of the form's grid
const WIDE_TYPES = ['textarea', 'files', 'multiselect', 'order_lines'];
const hasValue = (value) => value != null && value !== '' && !(Array.isArray(value) && !value.length);
const without = (errors, ...names) => Object.fromEntries(Object.entries(errors).filter(([name]) => !names.includes(name)));

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
  // Asking whether to save before going back, when there are changes not saved yet
  const [leaving, setLeaving] = useState(false);
  // The values as last saved (or as the form started), to tell whether there is anything unsaved
  const [savedSnapshot, setSavedSnapshot] = useState(() => JSON.stringify(formType && !requestId ? initialValues(formType) : {}));
  const [open, setOpen] = useState(() => new Set((formType?.sections || []).slice(0, OPEN_AT_START).map((s) => s.title)));
  // What each field was last filled with by a search or a pick, so a later one may replace it but not the user's typing
  const autoFilled = useRef({});

  const fields = useMemo(() => (formType ? allFields(formType) : []), [formType]);
  const fieldNames = useMemo(() => new Set(fields.map((spec) => spec.name)), [fields]);
  const specOf = (name) => fields.find((spec) => spec.name === name);
  // Forms with a field only Daftra can fill for the found client (their التصنيف, their open invoices)
  const needsClientInfo = fields.some((spec) => ['daftra_client_category', 'daftra_client_invoice'].includes(spec.type));

  // Fills fields that are empty or still hold what an earlier search or pick filled in
  function autoFill(current, next, name, value, force = false) {
    const untouched = !current[name] || current[name] === autoFilled.current[name];
    if (!fieldNames.has(name) || !value || !(untouched || force)) return;
    next[name] = value;
    autoFilled.current[name] = value;
  }

  const toast = useToast();
  const client = useClientLookup({ fieldNames, needsClientInfo, setValues, setErrors, setMessage, autoFill, autoFilled, toast });

  // Where a التصنيف's clients live
  const categories = catalog.daftraLists?.daftra_client_category;
  const addressLists = { areasByEmirate: specOf('area')?.areas_by_emirate, categories };

  // A التصنيف the form did not get from the user — the one Daftra holds for a found client, or a
  // saved draft's — fills المنطقة and الإمارة only while they are empty: the client's own
  // neighbourhood is their address. One picked by hand replaces them (chooseFromList).
  // Runs again if the list of categories arrives later.
  const placedBy = useRef('');
  useEffect(() => {
    const id = values.category;
    if (!id) placedBy.current = '';
    if (!id || placedBy.current === String(id)) return;
    const { area, emirate } = afterCategory(categoryById(categories, id));
    const place = area ? { area, emirate } : null;
    if (!place) return;
    // Decided out here, not inside the update: an update may be run more than once, and reading
    // what was auto-filled while also writing it would make the second run change its mind
    const takeArea = !values.area;
    const takeEmirate = !values.emirate;
    placedBy.current = String(id);
    if (!takeArea && !takeEmirate) return;
    if (takeArea) autoFilled.current.area = place.area;
    if (takeEmirate) autoFilled.current.emirate = place.emirate;
    setValues((current) => ({
      ...current,
      ...(takeArea ? { area: place.area } : {}),
      ...(takeEmirate ? { emirate: place.emirate } : {}),
    }));
  }, [values.category, categories]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!requestId) return;
    requestsApi.getRequest(requestId)
      .then((request) => {
        setValues(request.data);
        setSavedSnapshot(JSON.stringify(request.data));
        setAttachments(request.attachments);
        setSaved({ status: request.status, returned_reason: request.returned_reason });
      })
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

  const dirty = !submitted && JSON.stringify(values) !== savedSnapshot;
  // Closing the tab or reloading with unsaved changes asks first
  useEffect(() => {
    if (!dirty) return undefined;
    const warn = (e) => { e.preventDefault(); e.returnValue = ''; };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);

  // A saved draft looks its client up again, so those fields have their choices back
  const lookedUpDraft = useRef(false);
  useEffect(() => {
    if (loading || lookedUpDraft.current || !needsClientInfo) return;
    lookedUpDraft.current = true;
    if (values.client_code) client.lookupClient('client_code', String(values.client_code));
    else if (values.phone) client.lookupClient('phone', String(values.phone));
  });

  if (!formType) return <Alert tone="error">نوع هذا النموذج لم يعد متاحًا.</Alert>;
  if (loading) return <Skeleton lines={8} />;

  const clearError = (...names) => setErrors((current) => without(current, ...names));

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
    clearError(name);
  }

  const pickedProduct = (name) => catalog.products?.find((product) => product.id === values[name + '_id']);

  // A product must come from our catalog (unless the list could not be loaded)
  function productErrors() {
    const found = {};
    if (!catalog.products) return found;
    for (const spec of fields) {
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
      for (const spec of fields) {
        if (spec.coordinates_from === name) {
          const found = coordinatesFromLink(value);
          if (found) autoFill(current, next, spec.name, found);
        }
        // A field whose usual value follows this one (e.g. the treasury of a payment method) is filled in,
        // unless the user has already picked something else
        const suggested = spec.default_from?.field === name ? spec.default_from.values[value] : undefined;
        if (suggested === undefined) continue;
        const suggestedId = String(suggested);
        autoFill(current, next, spec.name, suggestedId);
        if (next[spec.name] === suggestedId) {
          next[`${spec.name}_name`] = catalog.daftraLists?.[spec.type]?.find((row) => String(row.id) === suggestedId)?.name || '';
        }
      }
      return next;
    });
    setMessage(null);
    if (errors[name]) clearError(name);
  }

  function chooseFromList(name, rowId, label) {
    // A client category knows where its clients live: picking it sets المنطقة and الإمارة, whatever
    // they held. That is the user's choice, so unlike the effect above it replaces a neighbourhood.
    const place = specOf(name)?.type === 'daftra_client_category' && fieldNames.has('area')
      ? afterCategory(categoryById(categories, rowId)) : {};
    setValues((current) => ({ ...current, [name]: rowId, [`${name}_name`]: label, ...place }));
    autoFilled.current[name] = undefined;
    setMessage(null);
    if (place.area) clearError(name, 'area', 'emirate');
    else clearError(name);
  }

  // الإحداثيات follow the link whenever it carries a point; otherwise they are typed in
  function changeLocation(name, value) {
    const point = coordinatesFromLink(value);
    setValues((current) => {
      const next = { ...current, [name]: value };
      if (point) autoFill(current, next, 'coordinates', point);
      return next;
    });
    setMessage(null);
    clearError(name, ...(point ? ['coordinates'] : []));
  }

  // A link shared from a phone (maps.app.goo.gl/…) carries no point, so the server follows it.
  // The browser cannot: reading another site's redirect is not allowed.
  async function resolveLocation(name, value) {
    const link = String(value || '').trim();
    if (!link || coordinatesFromLink(link) || values.coordinates) return;
    try {
      const at = await clientsApi.pointOfLink(link);
      const point = `${at.lat.toFixed(6)}, ${at.lng.toFixed(6)}`;
      setValues((current) => {
        // Unless the link has changed again meanwhile
        if ((current[name] || '').trim() !== link) return current;
        const next = { ...current };
        autoFill(current, next, 'coordinates', point);
        return next;
      });
      clearError('coordinates');
    } catch {
      // The link leads nowhere we can read; الإحداثيات stay to be typed in
    }
  }

  // A name picked from a list that carries an amount of its own: the initiative's own قيمة الخصم
  // goes in, over anything typed there, and can be changed afterwards
  function pickNamed(name, text) {
    const spec = specOf(name);
    const amount = spec?.fills_by_choice?.[text];
    setValues((current) => ({
      ...current, [name]: text, ...(amount === undefined ? {} : { [spec.fills]: String(amount) }),
    }));
    setMessage(null);
    clearError(name, ...(amount === undefined ? [] : [spec.fills]));
  }

  // What each of the three changes in the others is in address.js
  function chooseEmirate(value) {
    setValues((current) => ({ ...current, ...afterEmirate(current, value, addressLists) }));
    setMessage(null);
    clearError('emirate');
  }

  function chooseArea(value) {
    setValues((current) => ({ ...current, ...afterArea(current, value, addressLists) }));
    setMessage(null);
    clearError('area', 'emirate');
  }

  // Changing the number or code a client was found by means another client: what they brought goes
  function changeSearchField(name, value) {
    if (client.lookup?.status === 'found' && values[name] && value !== values[name]) client.forgetClient(name, values);
    change(name, value);
  }

  async function save(action) {
    const body = { form_type: formType.key, data: values, action };
    const result = id
      ? await requestsApi.updateRequest(id, body)
      : await requestsApi.createRequest(body);
    setId(result.id);
    setSavedSnapshot(JSON.stringify(body.data));
    return result;
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
    goToFirstError(found);
  }

  function goToFirstError(found = errors) {
    const first = fields.find((spec) => found[spec.name]);
    setTimeout(() => {
      const target = document.getElementById('field-' + first?.name);
      target?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      target?.querySelector('input, select, textarea, button')?.focus({ preventScroll: true });
    }, 50);
  }

  // Opens a section and brings it into view (from the progress list or a section's «التالي»)
  function jumpTo(index) {
    const section = formType.sections[index];
    setOpen((current) => new Set([...current, section.title]));
    setTimeout(() => document.getElementById(`section-${index}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50);
  }

  // Going back with unsaved changes asks whether to keep them
  function back() {
    if (dirty) setLeaving(true);
    else onBack();
  }

  const saveAndLeave = () => run('draft', async () => {
    await save('draft');
    setLeaving(false);
    onBack();
  });

  const saveDraft = () => run('draft', async () => {
    await save('draft');
    setErrors({});
    toast(saved.status === 'returned' ? 'تم حفظ التعديلات' : 'تم حفظ المسودة — تجدها في «طلباتي»');
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
        const attachment = await requestsApi.addAttachment(requestIdToUse, field, file);
        setAttachments((current) => [...current, attachment]);
      }
      if (errors[field]) clearError(field);
    } catch (err) {
      setMessage({ error: err.message });
    } finally {
      setUploading('');
    }
  }

  async function removeFile(file) {
    try {
      await requestsApi.deleteAttachment(file.id);
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

  const isFilled = (spec) => (spec.type === 'files' ? fileCounts[spec.name] : hasValue(values[spec.name]));
  // A new-client field the server still asks about (e.g. the search was never run) is shown too
  const shown = (spec) => fieldApplies(spec, values) || Boolean(errors[spec.name]);
  const inputsOf = (section) => section.fields.filter((spec) => spec.type !== 'auto_user' && !spec.computed && shown(spec));

  function summary(section) {
    const inputs = inputsOf(section);
    const sectionErrors = section.fields.filter((spec) => errors[spec.name]).length;
    if (sectionErrors) return `${sectionErrors} حقل يحتاج تصحيحًا`;
    const filled = inputs.filter(isFilled).length;
    return filled ? `${filled} من ${inputs.length} مُعبأ` : 'لم تُعبأ بعد';
  }

  // Each section's state: 'error' (corrections asked for), 'done' (nothing required is missing),
  // 'partial', 'todo', or 'optional' (nothing in it is required). Sections with required fields
  // count towards the progress.
  const sectionStates = formType.sections.map((section) => {
    if (section.fields.some((spec) => errors[spec.name])) return 'error';
    const needed = section.fields.some((spec) => evaluation.required.has(spec.name));
    const missing = section.fields.some((spec) => evaluation.errors[spec.name]);
    const filled = inputsOf(section).some(isFilled);
    if (!needed && !missing) return filled ? 'done' : 'optional';
    if (!missing) return 'done';
    return filled ? 'partial' : 'todo';
  });
  const counted = formType.sections.map((section) => section.fields.some((spec) => evaluation.required.has(spec.name)));
  const progress = {
    done: sectionStates.filter((state, index) => counted[index] && state === 'done').length,
    total: counted.filter(Boolean).length,
  };
  const totals = formTotals(fieldNames, evaluation.clean);

  // The control for one field of the form, with what its Field shows around it
  function controlFor(spec) {
    const invalid = Boolean(errors[spec.name]);
    if (spec.type === 'files') {
      return {
        control: <FileField spec={spec} files={attachments.filter((a) => a.field === spec.name)} invalid={invalid}
          busy={uploading === spec.name} onAdd={addFiles} onRemove={removeFile} />,
      };
    }
    if (spec.type === 'auto_user') {
      return { locked: 'للقراءة فقط', control: <TextInput id={spec.name} value={user.full_name || user.username} readOnly /> };
    }
    if (spec.computed) {
      const value = evaluation.clean[spec.name];
      return {
        locked: 'يُحسب تلقائيًا',
        control: (
          <TextInput id={spec.name} dir={spec.money ? 'auto' : 'ltr'} readOnly placeholder="—"
            value={value == null ? '' : (spec.money ? formatAmount(value) : value)} />
        ),
      };
    }
    if (spec.type === 'product') {
      return {
        hint: productHint(spec.name),
        control: <ProductPicker spec={spec} value={values[spec.name]} invalid={invalid} catalog={catalog} onType={typeProduct} onPick={pickProduct} />,
      };
    }
    if (spec.type === 'order_lines') {
      return {
        control: <OrderLines spec={spec} value={values[spec.name]} invalid={invalid} catalog={catalog} onChange={change}
          lineErrors={typeof errors[spec.name] === 'object' ? errors[spec.name]?.lines : null} />,
      };
    }
    if (DAFTRA_LIST_TYPES.includes(spec.type)) {
      const perClient = spec.type === 'daftra_client_invoice';
      const rows = spec.type === 'daftra_client_category'
        ? categoriesFor(categories, values, values[spec.name]) : catalog.daftraLists?.[spec.type];
      return {
        control: <DaftraListSelect spec={spec} value={values[spec.name]} invalid={invalid}
          rows={perClient ? client.clientInfo?.open_invoices || [] : rows}
          unavailable={perClient ? client.invoicesUnavailable() : null}
          onChange={(rowId, label) => chooseFromList(spec.name, rowId, label)} />,
      };
    }
    // الإحداثيات are the pin's own position while the location holds one — which it does whenever
    // the map wrote it, or a pasted link could be followed to a point. A link that holds none
    // (shared from a phone's own position, where Google kept only the place's name) leaves them to
    // be filled in by hand, and they are still required.
    if (spec.coordinates_from) {
      const location = values[spec.coordinates_from];
      return {
        hint: location && !values[spec.name] && !coordinatesFromLink(location)
          ? 'الرابط لا يحمل إحداثيات، اكتبها هنا.' : null,
        control: <Control spec={spec} value={values[spec.name]} invalid={invalid} onChange={change} />,
      };
    }
    if (spec.name === 'location_url') {
      return {
        hint: 'الصق رابط الموقع من خرائط جوجل؛ تُملأ الإحداثيات منه تلقائيًا إن حمَلها.',
        control: <Control spec={spec} value={values[spec.name]} invalid={invalid}
          onChange={changeLocation} onBlur={resolveLocation} />,
      };
    }
    if (spec.name === 'emirate') {
      return { control: <Control spec={spec} value={values.emirate} invalid={invalid} onChange={(_, v) => chooseEmirate(v)} /> };
    }
    if (spec.name === 'area') {
      // Typed freely — a client's neighbourhood is whatever Daftra holds — with the regions of the
      // chosen emirate offered as suggestions
      const suggestions = (values.emirate && spec.areas_by_emirate?.[values.emirate]) || spec.suggestions;
      return { control: <Control spec={{ ...spec, suggestions }} value={values.area} invalid={invalid} onChange={(_, v) => chooseArea(v)} /> };
    }
    if (spec.fills) {
      return {
        hint: 'اختيار اسم المبادرة يملأ قيمة الخصم، ويمكن تعديلها بعدها.',
        control: <Control spec={spec} value={values[spec.name]} invalid={invalid} onChange={change} onPick={pickNamed} />,
      };
    }
    if (spec.type === 'staff') {
      // Daftra's staff names are offered, and a name typed by hand is kept
      return { control: <Control spec={{ ...spec, suggestions: catalog.staff }} value={values[spec.name]} invalid={invalid} onChange={change} /> };
    }
    const searchable = SEARCH_FIELDS.includes(spec.name);
    return {
      hint: searchable ? 'يُبحث عن العميل بعد الكتابة، أو اضغط أيقونة البحث.' : null,
      control: <Control spec={spec} value={values[spec.name]} invalid={invalid} onChange={searchable ? changeSearchField : change}
        onBlur={searchable ? client.lookupClient : undefined} onSearch={searchable ? client.searchNow : undefined} />,
    };
  }

  function fieldRow(spec) {
    const { control, locked, hint } = controlFor(spec);
    // A computed field shows its error live (e.g. paid more than the total); order_lines
    // keeps its per-line errors inside the field itself, not as one message here
    const rawError = errors[spec.name] || (spec.computed && evaluation.errors[spec.name]);
    const error = spec.type === 'order_lines' && rawError && typeof rawError === 'object'
      ? 'بعض البنود تحتاج إلى تعديل، انظر التفاصيل أدناه' : rawError;
    const wide = WIDE_TYPES.includes(spec.type) || showsAsChoice(spec);
    return (
      <div key={spec.name} className={wide ? 'fl-wide' : undefined}>
        <Field
          id={'field-' + spec.name} label={spec.label} htmlFor={spec.type === 'files' ? undefined : spec.name}
          required={evaluation.required.has(spec.name)} locked={locked} hint={hint} error={error}
        >
          {control}
        </Field>
        <ClientLookupNote name={spec.name} client={client} values={values} />
      </div>
    );
  }

  return (
    <div className="fl-formlayout">
      <form className="fl-formlayout__main fl-stack" onSubmit={(e) => e.preventDefault()} noValidate>
      <Button className="fl-back" variant="tertiary" icon="arrow-start" onClick={back}>رجوع</Button>
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
      <div className="fl-form-toolbar">
        <span className="fl-small fl-muted"><span className="fl-field__required" aria-hidden="true">*</span> حقل مطلوب</span>
        <Button variant="tertiary" size="sm" iconEnd={allOpen ? 'chevron-up' : 'chevron-down'}
          onClick={() => setOpen(allOpen ? new Set() : new Set(formType.sections.map((s) => s.title)))}>
          {allOpen ? 'طي كل الأقسام' : 'فتح كل الأقسام'}
        </Button>
      </div>

      {formType.sections.map((section, index) => {
        const next = formType.sections[index + 1];
        return (
          <Section
            key={section.title} id={`section-${index}`} number={index + 1} title={section.title} summary={summary(section)}
            open={open.has(section.title)} onToggle={() => toggle(section.title)} state={sectionStates[index]}
            invalid={section.fields.some((spec) => errors[spec.name])}
          >
            {section.note && <Alert tone="info">{section.note}</Alert>}
            <div className="fl-grid">{section.fields.filter(shown).map(fieldRow)}</div>
            {next && (
              <div className="fl-section__next">
                <Button variant="tertiary" size="sm" iconEnd="chevron-end" onClick={() => jumpTo(index + 1)}>
                  التالي: {next.title}
                </Button>
              </div>
            )}
          </Section>
        );
      })}

      <ActionBar
        summary={(
          <>
            <span className="fl-actionbar__progress" data-fl-num>{progress.done} من {progress.total} أقسام مكتملة</span>
            <Totals totals={totals.filter((total) => total.name !== 'subtotal_amount')} compact />
          </>
        )}
        message={(errorCount > 0 || message) && (
          <>
            {errorCount > 0 && (
              <Alert tone="error" actions={<Button size="sm" variant="secondary" icon="arrow-start" onClick={() => goToFirstError()}>الانتقال إلى أول خطأ</Button>}>
                يوجد {errorCount} حقل يحتاج إلى تصحيح قبل الإرسال.
              </Alert>
            )}
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
      {leaving && (
        <Dialog
          title="لديك تغييرات غير محفوظة" confirmLabel={saved.status === 'returned' ? 'حفظ التعديلات والخروج' : 'حفظ المسودة والخروج'}
          altLabel="الخروج دون حفظ" onAlt={() => { setLeaving(false); onBack(); }} cancelLabel="البقاء في النموذج"
          busy={busy === 'draft'} onConfirm={saveAndLeave} onCancel={() => setLeaving(false)}
        >
          {message?.error || 'احفظ ما كتبته كمسودة لتعود إليه من «طلباتي»، أو اخرج دون حفظ.'}
        </Dialog>
      )}
      </form>
      <FormProgress sections={formType.sections} states={sectionStates} progress={progress} totals={totals} onJump={jumpTo} />
    </div>
  );
}
