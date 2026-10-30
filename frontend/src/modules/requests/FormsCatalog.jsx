import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from './api.js';
import { Alert, EmptyState, Icon, Loading, PageHeader, SearchInput } from './ds/index.jsx';
import { formMeta, matchesQuery } from './formsMeta.js';
import MyRequests from './MyRequests.jsx';
import { pagePath } from './paths.js';
import RequestForm from './RequestForm.jsx';
import RequestView from './RequestView.jsx';

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

function FormsCatalog({ formTypes, onChoose }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  // How many of the user's requests are returned for corrections and how many are drafts
  const [counts, setCounts] = useState({ returned: 0, draft: 0 });

  useEffect(() => {
    api('/requests/mine/counts').then(setCounts).catch(() => {});
  }, []);

  // Hidden forms take no new requests (VISIBLE_FORM_TYPES in backend/app/forms/definitions.py)
  const available = formTypes.filter((type) => !type.hidden).length;
  const shown = formTypes.filter((type) => !type.hidden && matchesQuery(query, type.label, formMeta(type.key).desc));
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
          {shown.map((type) => {
            const meta = formMeta(type.key);
            return (
              <li key={type.key}>
                <button type="button" className="fl-catalog-item" onClick={() => onChoose(type.key)}>
                  <span className="fl-tile"><Icon name={meta.icon} size={20} /></span>
                  <span className="fl-catalog-item__text">
                    <span className="fl-catalog-item__title">{type.label}</span>
                    {meta.desc && <span className="fl-catalog-item__desc">{meta.desc}</span>}
                  </span>
                  <span className="fl-catalog-item__chevron"><Icon name="chevron-end" size={18} /></span>
                </button>
              </li>
            );
          })}
        </ul>
      ) : (
        <EmptyState icon="search" title="لا يوجد نموذج مطابق">جرّب كلمة أخرى أو امسح البحث.</EmptyState>
      )}
    </section>
  );
}

export function NewRequestPage({ user, sales }) {
  const [formType, setFormType] = useState(null);
  const navigate = useNavigate();

  if (notReady(sales)) return notReady(sales);
  if (!formType) return <FormsCatalog formTypes={sales.formTypes} onChoose={setFormType} />;
  return (
    <RequestForm
      key={formType}
      formType={sales.formTypes.find((type) => type.key === formType)}
      user={user}
      catalog={sales}
      onBack={() => setFormType(null)}
      onNew={() => setFormType(null)}
      onList={() => navigate(pagePath('sales.my_requests'))}
    />
  );
}

export function MyRequestsPage({ user, sales }) {
  // { name: 'list' } | { name: 'form', formType, requestId } | { name: 'view', requestId }
  const [view, setView] = useState({ name: 'list' });
  const navigate = useNavigate();
  const showList = () => setView({ name: 'list' });

  if (notReady(sales)) return notReady(sales);
  if (view.name === 'form') {
    return (
      <RequestForm
        key={view.requestId}
        formType={sales.formTypes.find((type) => type.key === view.formType)}
        requestId={view.requestId}
        user={user}
        catalog={sales}
        onBack={showList}
        onNew={() => navigate(pagePath('sales.new_request'))}
        onList={showList}
      />
    );
  }
  if (view.name === 'view') {
    return <RequestView requestId={view.requestId} formTypes={sales.formTypes} onBack={showList} />;
  }
  return (
    <MyRequests
      formTypes={sales.formTypes}
      onNew={() => navigate(pagePath('sales.new_request'))}
      onEdit={(request) => setView({ name: 'form', formType: request.form_type, requestId: request.id })}
      onView={(request) => setView({ name: 'view', requestId: request.id })}
    />
  );
}
