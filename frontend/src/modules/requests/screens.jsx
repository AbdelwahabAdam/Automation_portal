// Every screen behind a URL of its own, so a request or a form can be opened from a bookmark,
// the back button works, and a refresh keeps the user where they were.
//
// The screens themselves are the components beside this file; these wrappers read the URL and
// hand them what they need.
import { useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import * as requestsApi from '../../api/requests.js';
import { Alert, EmptyState, Loading } from '../../ds/index.jsx';
import { FormsCatalog } from './FormsCatalog.jsx';
import MyRequestsList from './MyRequests.jsx';
import RequestForm from './RequestForm.jsx';
import RequestView from './RequestView.jsx';
import ReviewQueue from './Review.jsx';

/** The forms and the catalog they come from are loaded once, for anyone who has any of them. */
function notReady(sales) {
  if (sales.error) return <Alert tone="error" title="تعذر تحميل النماذج">{sales.error}</Alert>;
  if (!sales.formTypes) return <Loading />;
  return null;
}

const formOf = (sales, key) => sales.formTypes.find((type) => type.key === key);

export function FormsScreen({ sales }) {
  const navigate = useNavigate();
  return notReady(sales) || (
    <FormsCatalog formTypes={sales.formTypes} onChoose={(key) => navigate(`/forms/${key}`)} />
  );
}

export function NewRequestScreen({ user, sales }) {
  const { formKey } = useParams();
  const navigate = useNavigate();
  const waiting = notReady(sales);
  if (waiting) return waiting;
  const form = formOf(sales, formKey);
  // A form this user may not fill, or one that is no longer there
  if (!form || form.may_submit === false) {
    return (
      <EmptyState icon="shield" title="هذا النموذج غير متاح لك">
        تواصل مع مدير النظام إن كنت تحتاج صلاحية تعبئته.
      </EmptyState>
    );
  }
  return (
    <RequestForm
      key={formKey} formType={form} user={user} catalog={sales}
      onBack={() => navigate('/forms')}
      onNew={() => navigate('/forms')}
      onList={() => navigate('/requests/mine')}
    />
  );
}

export function MyRequestsScreen({ sales }) {
  const navigate = useNavigate();
  return notReady(sales) || (
    <MyRequestsList
      formTypes={sales.formTypes}
      onNew={() => navigate('/forms')}
      onEdit={(request) => navigate(`/requests/${request.id}/edit?form=${request.form_type}`)}
      onView={(request) => navigate(`/requests/${request.id}`)}
    />
  );
}

export function RequestScreen({ sales }) {
  const { requestId } = useParams();
  const navigate = useNavigate();
  return notReady(sales) || (
    <RequestView
      requestId={Number(requestId)} formTypes={sales.formTypes}
      onBack={() => navigate('/requests/mine')}
    />
  );
}

export function EditRequestScreen({ user, sales }) {
  const { requestId } = useParams();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  // «استكمال» puts the form in the URL, so it shows at once without waiting for the request.
  // Opened from a bookmark or a typed URL there is no hint, and then the request says which
  // form it is — the form must never be guessed from the URL alone.
  const hinted = params.get('form');
  const [loadedKey, setLoadedKey] = useState('');
  const [error, setError] = useState('');
  useEffect(() => {
    if (hinted) return;
    requestsApi.getRequest(Number(requestId))
      .then((request) => setLoadedKey(request.form_type))
      .catch((err) => setError(err.message));
  }, [requestId, hinted]);

  const waiting = notReady(sales);
  if (waiting) return waiting;
  if (error) return <Alert tone="error">{error}</Alert>;
  const formKey = hinted || loadedKey;
  if (!formKey) return <Loading />;
  const form = formOf(sales, formKey);
  // A request of a form this user may not fill (one taken away since they wrote it)
  if (!form) {
    return (
      <EmptyState icon="shield" title="هذا النموذج غير متاح لك">
        تواصل مع مدير النظام إن كنت تحتاج صلاحية تعبئته.
      </EmptyState>
    );
  }
  return (
    <RequestForm
      key={requestId} formType={form} requestId={Number(requestId)} user={user} catalog={sales}
      onBack={() => navigate('/requests/mine')}
      onNew={() => navigate('/forms')}
      onList={() => navigate('/requests/mine')}
    />
  );
}

export function ReviewScreen({ user, sales }) {
  const navigate = useNavigate();
  return <ReviewQueue user={user} sales={sales} onOpen={(request) => navigate(`/review/${request.id}`)} />;
}

export function ReviewRequestScreen({ user, sales }) {
  const { requestId } = useParams();
  const navigate = useNavigate();
  return notReady(sales) || (
    <RequestView
      requestId={Number(requestId)} formTypes={sales.formTypes}
      onBack={() => navigate('/review')}
      review={{
        own: (request) => request.created_by_id === user.id && !user.is_admin,
        onDone: () => navigate('/review'),
      }}
    />
  );
}
