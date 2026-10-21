// React versions of the Future Life design system components (Design/portal/Fl*.dc.html).
// Styling lives in ds.css and uses the tokens in tokens.css only.
import { Children, createContext, isValidElement, useCallback, useContext, useEffect, useId, useRef, useState } from 'react';
import { matchesQuery } from './match.js';
import Icon from './Icon.jsx';

export { Icon };

const cx = (...names) => names.filter(Boolean).join(' ');

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type=hidden]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

// Keeps Tab and Shift+Tab inside a dialog while it is open
function trapTab(e, container) {
  if (e.key !== 'Tab' || !container) return;
  const items = [...container.querySelectorAll(FOCUSABLE)].filter((el) => el.offsetParent !== null || el === document.activeElement);
  if (!items.length) return;
  const first = items[0];
  const last = items[items.length - 1];
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
}

// ---------- Button (FlButton) ----------

export function Button({
  variant = 'secondary', size = 'md', icon, iconEnd, loading, full, iconOnly, label, children, className, type = 'button', ...rest
}) {
  const text = children ?? label;
  return (
    <button
      type={type}
      className={cx('fl-btn', `fl-btn--${variant}`, `fl-btn--${size}`, full && 'fl-btn--full', iconOnly && 'fl-btn--icon', className)}
      aria-busy={loading ? 'true' : undefined}
      aria-label={iconOnly ? label : rest['aria-label']}
      title={iconOnly ? label : rest.title}
      {...rest}
      disabled={rest.disabled || loading}
    >
      {loading ? <Icon name="loader" size={size === 'sm' ? 16 : 18} /> : icon && <Icon name={icon} size={size === 'sm' ? 16 : 18} />}
      {!iconOnly && text != null && <span className="fl-btn__text">{text}</span>}
      {iconEnd && !loading && <Icon name={iconEnd} size={size === 'sm' ? 16 : 18} />}
    </button>
  );
}

// ---------- Field (FlField): label, hint, control box, error ----------

export function Field({ label, htmlFor, required, optional, locked, hint, error, children, className, hideLabel, id }) {
  return (
    <div className={cx('fl-field', error && 'fl-field--invalid', className)} id={id}>
      <div className={cx('fl-field__head', hideLabel && 'fl-sr-only')}>
        <label className="fl-field__label" htmlFor={htmlFor}>
          {label}{required && <span className="fl-field__required" aria-hidden="true"> *</span>}
        </label>
        {optional && <span className="fl-field__aside">(اختياري)</span>}
        {locked && <span className="fl-field__aside"><Icon name="lock" size={13} />{locked}</span>}
      </div>
      {children}
      {/* Under the control, not above it: a hint must not push its own field lower than the one beside it */}
      {hint && <div className="fl-field__hint">{hint}</div>}
      {error && (
        <div className="fl-field__error" role="alert">
          <Icon name="alert-circle" size={15} /><span>{error}</span>
        </div>
      )}
    </div>
  );
}

// The bordered box around an input, with optional icon and trailing button
// onIconClick makes the leading icon a button (e.g. a search field's magnifier that runs the search)
export function InputBox({ icon, onIconClick, iconLabel, end, invalid, readOnly, disabled, children, className }) {
  return (
    <div className={cx('fl-box', invalid && 'fl-box--invalid', readOnly && 'fl-box--readonly', disabled && 'fl-box--disabled', className)}>
      {icon && (onIconClick ? (
        <button type="button" className="fl-box__icon fl-box__icon--button" aria-label={iconLabel} title={iconLabel} disabled={disabled} onClick={onIconClick}>
          <Icon name={icon} size={18} />
        </button>
      ) : <span className="fl-box__icon"><Icon name={icon} size={18} /></span>)}
      {children}
      {end}
    </div>
  );
}

export function TextInput({ icon, onIconClick, iconLabel, invalid, className, ...rest }) {
  return (
    <InputBox icon={icon} onIconClick={onIconClick} iconLabel={iconLabel} invalid={invalid} readOnly={rest.readOnly} disabled={rest.disabled} className={className}>
      <input className="fl-input" aria-invalid={invalid || undefined} {...rest} />
    </InputBox>
  );
}

export function PasswordInput({ invalid, ...rest }) {
  const [shown, setShown] = useState(false);
  return (
    <InputBox
      invalid={invalid}
      end={(
        <button type="button" className="fl-box__btn" onClick={() => setShown(!shown)} aria-pressed={shown}
          aria-label={shown ? 'إخفاء كلمة المرور' : 'إظهار كلمة المرور'}>
          <Icon name={shown ? 'eye-off' : 'eye'} size={18} />
        </button>
      )}
    >
      <input className="fl-input" type={shown ? 'text' : 'password'} aria-invalid={invalid || undefined} {...rest} />
    </InputBox>
  );
}

export function TextArea({ invalid, rows = 3, ...rest }) {
  return (
    <InputBox invalid={invalid} readOnly={rest.readOnly} className="fl-box--area">
      <textarea className="fl-input fl-textarea" rows={rows} aria-invalid={invalid || undefined} {...rest} />
    </InputBox>
  );
}

export function SearchInput({ value, onChange, placeholder, label, ...rest }) {
  return (
    <InputBox
      icon="search"
      end={value ? (
        <button type="button" className="fl-box__btn" aria-label="مسح البحث" onClick={() => onChange('')}><Icon name="x" size={16} /></button>
      ) : null}
    >
      <input className="fl-input" type="search" value={value} placeholder={placeholder} aria-label={label || placeholder}
        onChange={(e) => onChange(e.target.value)} {...rest} />
    </InputBox>
  );
}

// ---------- Combobox: a text box offering matching items in a list below it ----------

// The list opens on focus and typing; ↑ ↓ move through it, Enter picks, Escape closes.
// closeOnPick=false keeps it open after a pick (e.g. adding several products in a row).
export function Combobox({
  id, value, onInput, items, itemKey, renderItem, onPick, placeholder, invalid, emptyText, closeOnPick = true, icon = 'search',
}) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const listId = useId();
  const shown = open && Boolean(items);
  useEffect(() => setActive(-1), [items]);
  useEffect(() => {
    if (active >= 0) document.getElementById(`${listId}-${active}`)?.scrollIntoView({ block: 'nearest' });
  }, [active, listId]);

  function pick(item) {
    onPick(item);
    if (closeOnPick) setOpen(false);
    setActive(-1);
  }

  function onKeyDown(e) {
    if (e.key === 'Escape' && open) {
      e.preventDefault();
      setOpen(false);
    } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (!open) return setOpen(true);
      const count = items?.length || 0;
      if (count) setActive((current) => (current + (e.key === 'ArrowDown' ? 1 : count - 1)) % count);
    } else if (e.key === 'Enter' && shown && items[active]) {
      e.preventDefault();
      pick(items[active]);
    }
  }

  return (
    <div className="fl-suggest">
      <TextInput
        id={id} icon={icon} autoComplete="off" value={value ?? ''} invalid={invalid} placeholder={placeholder}
        role="combobox" aria-expanded={shown} aria-autocomplete="list" aria-controls={listId}
        aria-activedescendant={shown && active >= 0 ? `${listId}-${active}` : undefined}
        onChange={(e) => { onInput(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)} onBlur={() => setOpen(false)} onKeyDown={onKeyDown}
      />
      {shown && (
        <div className="fl-suggest__list" role="listbox" id={listId}>
          {items.map((item, index) => (
            <button
              key={itemKey(item)} id={`${listId}-${index}`} type="button" role="option" aria-selected={index === active}
              className={cx('fl-suggest__item', index === active && 'fl-suggest__item--active')} tabIndex={-1}
              onMouseDown={(e) => e.preventDefault()} onMouseEnter={() => setActive(index)} onClick={() => pick(item)}
            >
              {renderItem(item)}
            </button>
          ))}
          {!items.length && <p className="fl-suggest__empty">{emptyText}</p>}
        </div>
      )}
    </div>
  );
}

// ---------- Select (FlSelect): a drop-down that can be searched ----------

// A list longer than this gets a search box; a short one is quicker to read than to type into
const SEARCH_FROM = 7;

// The text of an <option>, whatever it is written as ({name}, "a — b", a number)
function optionText(node) {
  if (node == null || node === false) return '';
  if (Array.isArray(node)) return node.map(optionText).join('');
  if (typeof node === 'object') return optionText(node.props?.children);
  return String(node);
}

// The <option> children as plain data; an option with an empty value is the "nothing chosen" line
function readOptions(children) {
  return Children.toArray(children)
    .filter((child) => isValidElement(child) && child.type === 'option')
    .map((child) => {
      const label = optionText(child.props.children);
      return { value: child.props.value ?? label, label, disabled: Boolean(child.props.disabled) };
    });
}

// Takes the same props as a plain <select>: value, onChange (e.target.value), disabled, and
// <option> children. Opens a list that can be searched, instead of the browser's own drop-down.
export function Select({ invalid, children, className, value, onChange, disabled, id, ...rest }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(-1);
  const root = useRef(null);
  const search = useRef(null);
  const listId = useId();

  const options = readOptions(children);
  const chosen = options.find((option) => String(option.value) === String(value ?? ''));
  const placeholder = options.find((option) => String(option.value) === '');
  // A saved value the list does not offer (an old client's area, a renamed category). It is shown
  // as it stands rather than silently looking empty, so a refusal to submit makes sense.
  const stray = !chosen && value != null && String(value) !== '' ? String(value) : '';
  const shown = query ? options.filter((option) => matchesQuery(query, option.label)) : options;
  const withSearch = options.length > SEARCH_FROM;

  useEffect(() => {
    if (!open) return undefined;
    setQuery('');
    setActive(shown.findIndex((option) => option === chosen));
    search.current?.focus();
    const close = (e) => { if (!root.current?.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (open && active >= 0) document.getElementById(`${listId}-${active}`)?.scrollIntoView({ block: 'nearest' });
  }, [open, active, listId]);

  function pick(option) {
    if (option.disabled) return;
    onChange?.({ target: { value: String(option.value) } });
    setOpen(false);
    root.current?.querySelector('.fl-pick')?.focus();
  }

  function onKeyDown(e) {
    if (disabled) return;
    if (e.key === 'Escape' && open) {
      e.preventDefault();
      // Closes the list only: a drawer or dialog behind it stays open
      e.stopPropagation();
      setOpen(false);
      root.current?.querySelector('.fl-pick')?.focus();
    } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (!open) return setOpen(true);
      if (shown.length) setActive((current) => (current + (e.key === 'ArrowDown' ? 1 : shown.length - 1) + shown.length) % shown.length);
    } else if ((e.key === 'Enter' || e.key === ' ') && !open) {
      e.preventDefault();
      setOpen(true);
    } else if (e.key === 'Enter' && open) {
      e.preventDefault();
      if (shown[active]) pick(shown[active]);
    }
  }

  return (
    <div className={cx('fl-select-wrap', className)} ref={root} onKeyDown={onKeyDown}>
      <InputBox invalid={invalid} disabled={disabled} className="fl-box--select"
        end={<span className="fl-box__chevron" aria-hidden="true"><Icon name={open ? 'chevron-up' : 'chevron-down'} size={18} /></span>}>
        <button
          type="button" id={id} className="fl-input fl-pick" disabled={disabled} aria-invalid={invalid || undefined}
          role="combobox" aria-expanded={open} aria-haspopup="listbox" aria-controls={listId} {...rest}
          onClick={() => !disabled && setOpen(!open)}
        >
          {chosen && chosen !== placeholder && <span className="fl-pick__value">{chosen.label}</span>}
          {stray && <span className="fl-pick__value fl-pick__stray" title="هذه القيمة ليست من القائمة">{stray}</span>}
          {!stray && (!chosen || chosen === placeholder) && <span className="fl-pick__empty">{placeholder?.label || 'اختر…'}</span>}
        </button>
      </InputBox>
      {open && !disabled && (
        <div className="fl-picklist">
          {withSearch && (
            <div className="fl-picklist__search">
              <Icon name="search" size={16} />
              <input
                ref={search} type="text" value={query} className="fl-picklist__input" placeholder="ابحث…"
                aria-label="ابحث في القائمة" aria-controls={listId} autoComplete="off"
                onChange={(e) => { setQuery(e.target.value); setActive(0); }}
              />
            </div>
          )}
          <div className="fl-picklist__options" role="listbox" id={listId} aria-activedescendant={active >= 0 ? `${listId}-${active}` : undefined}>
            {shown.map((option, index) => (
              <button
                key={`${option.value}-${index}`} id={`${listId}-${index}`} type="button" role="option" tabIndex={-1}
                aria-selected={option === chosen} disabled={option.disabled}
                className={cx('fl-picklist__option', option === chosen && 'fl-picklist__option--on', index === active && 'fl-picklist__option--active')}
                onMouseEnter={() => setActive(index)} onMouseDown={(e) => e.preventDefault()} onClick={() => pick(option)}
              >
                <span>{option.label}</span>
                {option === chosen && <Icon name="check" size={16} />}
              </button>
            ))}
            {!shown.length && <p className="fl-picklist__empty">لا يوجد ما يطابق البحث.</p>}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------- Choice (FlChoice): option cards for radio or checkbox ----------

export function Choice({ name, options, value, multiple, onChange, invalid, columns }) {
  const chosen = multiple ? (Array.isArray(value) ? value : []) : value;
  return (
    <div className={cx('fl-choice', invalid && 'fl-choice--invalid')} role={multiple ? 'group' : 'radiogroup'}
      style={columns ? { '--fl-choice-columns': columns } : undefined}>
      {options.map((option) => {
        const optionValue = typeof option === 'string' ? option : option.value;
        const optionLabel = typeof option === 'string' ? option : option.label;
        const checked = multiple ? chosen.includes(optionValue) : chosen === optionValue;
        return (
          <label key={optionValue} className={cx('fl-choice__item', checked && 'fl-choice__item--on')}>
            <input
              type={multiple ? 'checkbox' : 'radio'} name={name} checked={checked}
              onChange={() => onChange(multiple
                ? (checked ? chosen.filter((v) => v !== optionValue) : [...chosen, optionValue])
                : optionValue)}
            />
            <span>{optionLabel}</span>
          </label>
        );
      })}
    </div>
  );
}

export function Checkbox({ checked, onChange, children, disabled }) {
  return (
    <label className={cx('fl-check', disabled && 'fl-check--disabled')}>
      <input type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      <span>{children}</span>
    </label>
  );
}

// ---------- Badge (FlBadge) and status badges ----------

export function Badge({ tone = 'neutral', icon, children, title }) {
  return (
    <span className={`fl-badge fl-badge--${tone}`} title={title}>
      {icon && <Icon name={icon} size={14} />}
      <span className="fl-badge__text">{children}</span>
    </span>
  );
}

const REQUEST_STATUS = {
  draft: ['neutral', 'edit', 'مسودة'],
  submitted: ['info', 'send', 'قيد المراجعة'],
  returned: ['warning', 'arrow-start', 'تحتاج تعديل'],
  approved: ['success', 'check-circle', 'معتمد'],
};

export function StatusBadge({ status }) {
  const [tone, icon, label] = REQUEST_STATUS[status] || ['neutral', null, status];
  return <Badge tone={tone} icon={icon}>{label}</Badge>;
}

// ---------- Alert (FlAlert) ----------

const ALERT_ICONS = { info: 'info', success: 'check-circle', warning: 'alert-triangle', error: 'alert-circle', neutral: 'info' };

export function Alert({ tone = 'info', title, children, actions, onDismiss }) {
  return (
    <div className={`fl-alert fl-alert--${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      <span className="fl-alert__icon"><Icon name={ALERT_ICONS[tone]} size={20} /></span>
      <div className="fl-alert__body">
        {title && <div className="fl-alert__title">{title}</div>}
        {children && <div className="fl-alert__text">{children}</div>}
        {actions && <div className="fl-alert__actions">{actions}</div>}
      </div>
      {onDismiss && <Button variant="ghost" size="sm" icon="x" iconOnly label="إغلاق" onClick={onDismiss} />}
    </div>
  );
}

// ---------- Tabs (FlTabs) with counts ----------

export function Tabs({ tabs, value, onChange, label }) {
  return (
    <div className="fl-tabs" role="tablist" aria-label={label}>
      {tabs.map((tab) => (
        <button
          key={tab.value} type="button" role="tab" aria-selected={tab.value === value}
          className={cx('fl-tabs__tab', tab.value === value && 'fl-tabs__tab--on')} onClick={() => onChange(tab.value)}
        >
          <span>{tab.label}</span>
          {tab.count != null && <span className="fl-tabs__count" data-fl-num>{tab.count}</span>}
        </button>
      ))}
    </div>
  );
}

// ---------- Page header, empty state, loading ----------

export function PageHeader({ title, subtitle, actions, children }) {
  return (
    <header className="fl-pagehead">
      <div className="fl-pagehead__text">
        <h1 className="fl-pagehead__title" tabIndex={-1}>{title}</h1>
        {subtitle && <p className="fl-pagehead__sub">{subtitle}</p>}
        {children}
      </div>
      {actions && <div className="fl-pagehead__actions">{actions}</div>}
    </header>
  );
}

export function EmptyState({ icon = 'inbox', title, children, action }) {
  return (
    <div className="fl-empty">
      <span className="fl-empty__icon"><Icon name={icon} size={22} /></span>
      <div className="fl-empty__title">{title}</div>
      {children && <p className="fl-empty__text">{children}</p>}
      {action}
    </div>
  );
}

export function Loading({ label = 'جارٍ التحميل…' }) {
  return <p className="fl-loading" role="status"><Icon name="loader" size={18} />{label}</p>;
}

// A thin bar filled to value / max, with its meaning for screen readers
export function ProgressBar({ value, max, label }) {
  const percent = max ? Math.round((value / max) * 100) : 0;
  return (
    <div className="fl-progress" role="progressbar" aria-valuemin={0} aria-valuemax={max} aria-valuenow={value} aria-label={label}>
      <span className="fl-progress__fill" style={{ inlineSize: `${percent}%` }} />
    </div>
  );
}

// ---------- Card and numbered collapsible section ----------

export function Card({ title, actions, children, className }) {
  return (
    <section className={cx('fl-card', className)}>
      {(title || actions) && (
        <div className="fl-card__head">
          {title && <h2 className="fl-card__title">{title}</h2>}
          {actions && <div className="fl-card__actions">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

// A form section that folds away; folded content stays mounted so values and uploads survive.
// state: 'done' shows a tick instead of its number, 'error' marks it as needing corrections
export function Section({ id, number, title, summary, open, onToggle, children, invalid, state }) {
  const bodyId = useId();
  const done = state === 'done' && !invalid;
  return (
    <section id={id} className={cx('fl-section', invalid && 'fl-section--invalid', done && 'fl-section--done', open && 'fl-section--open')}>
      <button type="button" className="fl-section__head" aria-expanded={open} aria-controls={bodyId} onClick={onToggle}>
        {number != null && (
          <span className="fl-section__num" data-fl-num aria-label={done ? `${number} — مكتمل` : undefined}>
            {done ? <Icon name="check" size={16} /> : number}
          </span>
        )}
        <span className="fl-section__titles">
          <span className="fl-section__title">{title}</span>
          {summary && <span className="fl-section__summary">{summary}</span>}
        </span>
        <span className="fl-section__chevron"><Icon name={open ? 'chevron-up' : 'chevron-down'} size={18} /></span>
      </button>
      <div id={bodyId} className="fl-section__body" hidden={!open}>{children}</div>
    </section>
  );
}

// Sticky bar at the bottom of a form. summary: a line of status beside the buttons (e.g. the totals)
export function ActionBar({ children, message, summary }) {
  return (
    <div className="fl-actionbar">
      {message && <div className="fl-actionbar__message">{message}</div>}
      <div className="fl-actionbar__row">
        <div className="fl-actionbar__buttons">{children}</div>
        {summary && <div className="fl-actionbar__summary">{summary}</div>}
      </div>
    </div>
  );
}

// ---------- Filters above a list: the search always, the rest folded behind a button on a phone ----------

// search: the search field; active: how many of the other filters are set (shown on the button)
export function Filters({ search, active = 0, children }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={cx('fl-filters', open && 'fl-filters--open')}>
      <div className="fl-filters__search">
        {search}
        <Button className="fl-filters__toggle" icon="filter" aria-expanded={open} onClick={() => setOpen(!open)}>
          {active ? `الفلاتر (${active})` : 'الفلاتر'}
        </Button>
      </div>
      {children}
    </div>
  );
}

// ---------- Drawer (FlDialog placement="drawer") ----------

export function Drawer({ title, subtitle, onClose, children, footer, width }) {
  const panel = useRef(null);
  useEffect(() => {
    const previous = document.activeElement;
    panel.current?.querySelector('input:not([type=hidden]), select, textarea, button')?.focus();
    const onKey = (e) => {
      // A confirmation open over the drawer answers the keys itself
      if (document.querySelector('.fl-overlay--center')) return;
      if (e.key === 'Escape') onClose();
      trapTab(e, panel.current);
    };
    document.addEventListener('keydown', onKey);
    document.body.classList.add('fl-noscroll');
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.classList.remove('fl-noscroll');
      previous?.focus?.();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="fl-overlay">
      <div className="fl-scrim" onClick={onClose} />
      <aside ref={panel} className="fl-drawer" role="dialog" aria-modal="true" aria-label={title} style={width ? { inlineSize: width } : undefined}>
        <header className="fl-drawer__head">
          <div>
            <h2 className="fl-drawer__title">{title}</h2>
            {subtitle && <p className="fl-drawer__sub">{subtitle}</p>}
          </div>
          <Button variant="ghost" icon="x" iconOnly label="إغلاق" onClick={onClose} />
        </header>
        <div className="fl-drawer__body">{children}</div>
        {footer && <footer className="fl-drawer__foot">{footer}</footer>}
      </aside>
    </div>
  );
}

// ---------- Menu (FlMenu): a button that opens a list of actions ----------

export function Menu({ label, icon, iconOnly, headerTitle, headerSubtitle, items, variant = 'ghost' }) {
  const [open, setOpen] = useState(false);
  const root = useRef(null);
  const menuId = useId();
  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => { if (!root.current?.contains(e.target)) setOpen(false); };
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', onKey); };
  }, [open]);
  return (
    <div className="fl-menu" ref={root}>
      <Button variant={variant} icon={icon} iconEnd={iconOnly ? undefined : 'chevron-down'} iconOnly={iconOnly} label={label}
        aria-haspopup="menu" aria-expanded={open} aria-controls={menuId} onClick={() => setOpen(!open)}>
        {iconOnly ? undefined : label}
      </Button>
      {open && (
        <div className="fl-menu__panel" role="menu" id={menuId}>
          {headerTitle && (
            <div className="fl-menu__header">
              <div className="fl-menu__header-title">{headerTitle}</div>
              {headerSubtitle && <div className="fl-menu__header-sub"><bdi>{headerSubtitle}</bdi></div>}
            </div>
          )}
          {items.map((item) => (
            <button key={item.label} type="button" role="menuitem" className={cx('fl-menu__item', item.danger && 'fl-menu__item--danger')}
              onClick={() => { setOpen(false); item.onSelect(); }}>
              {item.icon && <Icon name={item.icon} size={18} />}<span>{item.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------- Pagination (from FlTable) ----------

export function Pager({ page, pageSize, total, onPage, onPageSize, sizes = [10, 20, 50] }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const first = total ? (page - 1) * pageSize + 1 : 0;
  const last = Math.min(page * pageSize, total);
  const numbers = [];
  for (let n = Math.max(1, page - 2); n <= Math.min(pages, page + 2); n += 1) numbers.push(n);
  return (
    <div className="fl-pager">
      {onPageSize && (
        <label className="fl-pager__size">
          <span>عدد الصفوف</span>
          <select value={pageSize} onChange={(e) => onPageSize(Number(e.target.value))}>
            {sizes.map((size) => <option key={size} value={size}>{size}</option>)}
          </select>
        </label>
      )}
      <span className="fl-pager__count" data-fl-num>عرض <bdi dir="ltr">{first}–{last}</bdi> من {total}</span>
      <div className="fl-pager__pages">
        <Button size="sm" icon="chevron-start" disabled={page <= 1} onClick={() => onPage(page - 1)}>السابق</Button>
        {numbers.map((n) => (
          <button key={n} type="button" className={cx('fl-pager__num', n === page && 'fl-pager__num--on')} aria-current={n === page ? 'page' : undefined}
            onClick={() => onPage(n)}>{n}</button>
        ))}
        <Button size="sm" iconEnd="chevron-end" disabled={page >= pages} onClick={() => onPage(page + 1)}>التالي</Button>
      </div>
    </div>
  );
}

// ---------- Container width (FL.observeWidth): layout follows the element, not the window ----------

// Returns [ref, width]: put ref on the element whose width decides the layout
export function useWidth() {
  const [node, setNode] = useState(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    if (!node) return undefined;
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    observer.observe(node);
    return () => observer.disconnect();
  }, [node]);
  return [setNode, width];
}

// ---------- Dialog (FlDialog): centred confirmation ----------

// altLabel/onAlt: a third choice between confirming and cancelling (e.g. «حفظ والخروج»)
export function Dialog({
  title, children, confirmLabel, cancelLabel = 'إلغاء', tone = 'primary', onConfirm, onCancel, busy, confirmDisabled, altLabel, onAlt,
}) {
  const box = useRef(null);
  // Read by the Escape handler, which is set up once: a dialog that is working cannot be dismissed
  const busyRef = useRef(busy);
  busyRef.current = busy;
  useEffect(() => {
    const previous = document.activeElement;
    (box.current?.querySelector('textarea, input') || box.current?.querySelector('[data-autofocus]'))?.focus();
    const onKey = (e) => {
      if (e.key === 'Escape' && !busyRef.current) onCancel();
      trapTab(e, box.current);
    };
    document.addEventListener('keydown', onKey);
    document.body.classList.add('fl-noscroll');
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.classList.remove('fl-noscroll');
      previous?.focus?.();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="fl-overlay fl-overlay--center">
      <div className="fl-scrim" />
      <div ref={box} className="fl-dialog" role="alertdialog" aria-modal="true" aria-label={title}>
        <h2 className="fl-dialog__title">{title}</h2>
        <div className="fl-dialog__body">{children}</div>
        <div className="fl-dialog__actions">
          <Button variant={tone === 'danger' ? 'destructive' : 'primary'} loading={busy} disabled={confirmDisabled} onClick={onConfirm} data-autofocus>{confirmLabel}</Button>
          {altLabel && <Button onClick={onAlt} disabled={busy}>{altLabel}</Button>}
          <Button variant={altLabel ? 'tertiary' : 'secondary'} onClick={onCancel} disabled={busy}>{cancelLabel}</Button>
        </div>
      </div>
    </div>
  );
}

// ---------- Skeleton: the shape of what is loading, instead of a line of text ----------

// lines: how many grey bars; card wraps them in a surface, as a list of rows is
export function Skeleton({ lines = 3, card = true, label = 'جارٍ التحميل…' }) {
  const bars = Array.from({ length: lines }, (_, index) => <span key={index} className="fl-skeleton__bar" />);
  return (
    <div className={cx('fl-skeleton', card && 'fl-skeleton--card')} role="status" aria-busy="true" aria-label={label}>
      {bars}
    </div>
  );
}

// ---------- Toasts: a short message in the corner, for something that just worked ----------

const ToastContext = createContext(null);
const TOAST_SECONDS = 5;

// Wraps the app once; useToast() below sends the messages
export function ToastHost({ children }) {
  const [toasts, setToasts] = useState([]);
  const remove = (id) => setToasts((current) => current.filter((toast) => toast.id !== id));
  const show = useCallback((message, tone = 'success') => {
    const id = Math.random().toString(36).slice(2);
    setToasts((current) => [...current.filter((toast) => toast.message !== message), { id, message, tone }]);
    setTimeout(() => remove(id), TOAST_SECONDS * 1000);
  }, []);
  return (
    <ToastContext.Provider value={show}>
      {children}
      {toasts.length > 0 && (
        // Announced to a screen reader as it appears, without taking the focus away
        <div className="fl-toasts" role="status" aria-live="polite">
          {toasts.map((toast) => (
            <div key={toast.id} className={`fl-toast fl-toast--${toast.tone}`}>
              <Icon name={toast.tone === 'error' ? 'alert-circle' : 'check-circle'} size={18} />
              <span className="fl-toast__text">{toast.message}</span>
              <button type="button" className="fl-toast__close" aria-label="إغلاق" onClick={() => remove(toast.id)}>
                <Icon name="x" size={16} />
              </button>
            </div>
          ))}
        </div>
      )}
    </ToastContext.Provider>
  );
}

// show(message) for something that worked; show(message, 'error') for something that did not
export function useToast() {
  return useContext(ToastContext) ?? (() => {});
}

// ---------- Confirmation asked in the portal's own dialog (instead of window.confirm) ----------

// const [confirmDialog, confirm] = useConfirm(); … {confirmDialog} …
// if (!(await confirm({ title, body, confirmLabel, tone: 'danger' }))) return;
export function useConfirm() {
  const [asking, setAsking] = useState(null);
  const confirm = (question) => new Promise((resolve) => setAsking({ ...question, resolve }));
  const answer = (yes) => { asking.resolve(yes); setAsking(null); };
  const dialog = asking && (
    <Dialog title={asking.title} confirmLabel={asking.confirmLabel || 'تأكيد'} tone={asking.tone} cancelLabel={asking.cancelLabel}
      onConfirm={() => answer(true)} onCancel={() => answer(false)}>
      {asking.body}
    </Dialog>
  );
  return [dialog, confirm];
}
