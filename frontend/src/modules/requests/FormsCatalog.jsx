import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import * as requestsApi from '../../api/requests.js';
import { Alert, EmptyState, Icon, Loading, PageHeader, SearchInput } from '../../ds/index.jsx';
import { matchesQuery } from '../../ds/match.js';
import { pagePath } from '../../app/nav.js';

// Forms catalog: the search box shows once there are more forms than this
const SEARCH_FROM = 6;

// Shown in place of a sales page until the form definitions have loaded
function notReady(sales) {
  if (sales.error) return <Alert tone="error" title="تعذر تحميل النماذج">{sales.error}</Alert>;
  if (!sales.formTypes) return <Loading />;
  return null;
}

// A status strip above the catalog (FlStrip), e.g. "drafts 3 → continue"
function Strip({ tone, icon, title, count, action, onClick }) {
  return (
    <button type="button" className={tone === 'attention' ? 'fl-strip fl-strip--attention' : 'fl-strip'} onClick={onClick}>
      <span className="fl-strip__main">
        <span className="fl-tile"><Icon name={icon} size={20} /></span>
        <span className="fl-strip__title">{title}</span>
        <span className="fl-strip__count" data-fl-num>{count}</span>
      </span>
      <span className="fl-strip__action">{action}<Icon name="chevron-end" size={16} /></span>
    </button>
  );
}

export function FormsCatalog({ formTypes, onChoose }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  // How many of the user's requests are returned for corrections and how many are drafts
  const [counts, setCounts] = useState({ returned: 0, draft: 0 });

  useEffect(() => {
    requestsApi.myCounts().then(setCounts).catch(() => {});
  }, []);

  // Hidden forms take no new requests (`visible=False` in app/forms/<key>/__init__.py)
  const available = formTypes.filter((type) => !type.hidden).length;
  const shown = formTypes.filter((type) => !type.hidden && matchesQuery(query, type.label, type.description));
  return (
    <section className="fl-stack" aria-labelledby="forms-title">
      <PageHeader title="النماذج" subtitle="اختر النموذج المطلوب لتسجيل طلب جديد" />
      {counts.returned > 0 && (
        <Strip tone="attention" icon="arrow-start" title="طلبات تحتاج تعديل" count={counts.returned} action="عرض وتعديل"
          onClick={() => navigate(`${pagePath('sales.my_requests')}?tab=returned`)} />
      )}
      {counts.draft > 0 && (
        <Strip icon="edit" title="المسودات" count={counts.draft} action="استكمال" onClick={() => navigate(`${pagePath('sales.my_requests')}?tab=draft`)} />
      )}
      {/* A search is worth it only when there are many forms to choose from */}
      {available > SEARCH_FROM && (
        <div className="fl-narrow-search">
          <SearchInput value={query} onChange={setQuery} placeholder="ابحث عن نموذج" />
        </div>
      )}
      {shown.length ? (
        <ul className="fl-catalog" role="list">
          {/* The icon and the description come with the form from the API, so a new form
              needs no change here */}
          {shown.map((type) => (
            <li key={type.key}>
              <button type="button" className="fl-catalog-item" onClick={() => onChoose(type.key)}>
                <span className="fl-tile"><Icon name={type.icon || 'file'} size={20} /></span>
                <span className="fl-catalog-item__text">
                  <span className="fl-catalog-item__title">{type.label}</span>
                  {type.description && <span className="fl-catalog-item__desc">{type.description}</span>}
                </span>
                <span className="fl-catalog-item__chevron"><Icon name="chevron-end" size={18} /></span>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState icon="search" title="لا يوجد نموذج مطابق">جرّب كلمة أخرى أو امسح البحث.</EmptyState>
      )}
    </section>
  );
}
