import { useEffect, useState } from 'react';
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import Account from './Account.jsx';
import { api, getToken, setToken } from './api.js';
import { BRAND } from './brand.js';
import { Button, Icon, Loading, Menu } from './ds/index.jsx';
import Login from './Login.jsx';
import { PAGE_COMPONENTS, PAGE_ICONS } from './pages.jsx';
import { pagePath } from './paths.js';
import { useSalesData } from './salesData.js';
import SetPassword from './SetPassword.jsx';

// Pages shown in the phone's bottom bar before the rest move to «المزيد»
const BOTTOM_NAV_SIZE = 3;

function Blank({ label }) {
  return (
    <div className="fl-blank">
      <div className="fl-blank__title">{label}</div>
    </div>
  );
}

function NavItem({ page, onNavigate }) {
  return (
    <li>
      <NavLink to={pagePath(page.key)} className="fl-navlink" onClick={onNavigate}>
        <Icon name={PAGE_ICONS[page.key] || 'file'} size={20} />
        <span>{page.label}</span>
      </NavLink>
    </li>
  );
}

// Departments as labelled groups of pages, as in the design's sidebar
function NavGroups({ departments, onNavigate }) {
  return departments.map((department) => (
    <div key={department.key} className="fl-navgroup" role="group" aria-labelledby={`nav-${department.key}`}>
      <h2 id={`nav-${department.key}`} className="fl-navgroup__title">{department.label}</h2>
      <ul className="fl-navlist">
        {department.pages.map((page) => <NavItem key={page.key} page={page} onNavigate={onNavigate} />)}
      </ul>
    </div>
  ));
}

export default function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(Boolean(getToken()));
  const [moreOpen, setMoreOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  // Shown on the login screen, e.g. after setting a password
  const [notice, setNotice] = useState('');

  useEffect(() => {
    if (!getToken()) return;
    api('/auth/me').then(setUser).catch(() => setToken(null)).finally(() => setLoading(false));
  }, []);

  const departments = user?.navigation || [];
  // Form definitions, our product catalog and Daftra's lists, for the sales pages
  const sales = useSalesData(departments.some((department) => department.key === 'sales'));

  useEffect(() => setMoreOpen(false), [location.pathname]);

  async function logout() {
    await api('/auth/logout', { method: 'POST' }).catch(() => {});
    setToken(null);
    setUser(null);
    setNotice('');
  }

  // The link from an invitation or reset email; works whoever is logged in on this browser
  if (location.pathname === '/set-password') {
    return (
      <SetPassword
        onDone={(message) => {
          setToken(null);
          setUser(null);
          setNotice(message);
          navigate('/', { replace: true });
        }}
      />
    );
  }
  if (loading) return <div className="fl-auth"><Loading /></div>;
  if (!user) return <Login onLogin={setUser} notice={notice} />;

  const reloadUser = () => api('/auth/me').then(setUser).catch(() => {});
  const pages = departments.flatMap((department) => department.pages);
  const bottomPages = pages.slice(0, BOTTOM_NAV_SIZE);
  const hasMore = pages.length > BOTTOM_NAV_SIZE;
  const inMore = hasMore && !bottomPages.some((page) => location.pathname === pagePath(page.key));
  const accountMenu = (iconOnly) => (
    <Menu
      label={iconOnly ? 'حسابي' : user.full_name || user.username} icon="user" iconOnly={iconOnly}
      headerTitle={user.full_name || user.username} headerSubtitle={user.email || user.username}
      items={[
        { label: 'حسابي', icon: 'user', onSelect: () => navigate('/account') },
        { label: 'تسجيل الخروج', icon: 'log-out', onSelect: logout },
      ]}
    />
  );

  return (
    <div className="fl-app">
      <nav className="fl-sidenav" aria-label="التنقل الرئيسي">
        <div className="fl-brand">{BRAND}</div>
        <NavGroups departments={departments} />
      </nav>

      <div className="fl-main-col">
        <header className="fl-topbar">
          <div className="fl-brand fl-topbar__brand">{BRAND}</div>
          <div className="fl-topbar__end">
            <span className="fl-topbar__menu-wide">{accountMenu(false)}</span>
            <span className="fl-topbar__menu-narrow">{accountMenu(true)}</span>
          </div>
        </header>

        <main id="main" className="fl-content">
          {location.pathname === '/account' ? (
            <Account onUserChange={reloadUser} />
          ) : pages.length === 0 ? (
            <div className="fl-blank">
              <div>
                <div className="fl-blank__title">لا توجد صفحات متاحة لحسابك</div>
                <p className="fl-muted">تواصل مع مدير النظام لإضافة صلاحيات لحسابك.</p>
              </div>
            </div>
          ) : (
            <Routes>
              {pages.map((page) => {
                const Page = PAGE_COMPONENTS[page.key];
                return (
                  <Route
                    key={page.key}
                    path={pagePath(page.key)}
                    element={Page ? <Page user={user} sales={sales} /> : <Blank label={page.label} />}
                  />
                );
              })}
              <Route path="*" element={<Navigate to={pagePath(pages[0].key)} replace />} />
            </Routes>
          )}
        </main>
      </div>

      {pages.length > 0 && (
        <nav className="fl-bottomnav" aria-label="التنقل الرئيسي">
          {bottomPages.map((page) => (
            <NavLink key={page.key} to={pagePath(page.key)} className="fl-bottomnav__item">
              <Icon name={PAGE_ICONS[page.key] || 'file'} size={22} />
              <span>{page.label}</span>
            </NavLink>
          ))}
          {hasMore && (
            <button type="button" className={inMore ? 'fl-bottomnav__item active' : 'fl-bottomnav__item'}
              aria-expanded={moreOpen} aria-controls="more-sheet" onClick={() => setMoreOpen(!moreOpen)}>
              <Icon name="more" size={22} />
              <span>المزيد</span>
            </button>
          )}
        </nav>
      )}
      {moreOpen && (
        <>
          <div className="fl-scrim fl-scrim--fixed" onClick={() => setMoreOpen(false)} />
          <div id="more-sheet" className="fl-sheet" role="dialog" aria-label="المزيد">
            <div className="fl-sheet__head">
              <h2 className="fl-sheet__title">المزيد</h2>
              <Button variant="ghost" icon="x" iconOnly label="إغلاق" onClick={() => setMoreOpen(false)} />
            </div>
            <NavGroups departments={departments} onNavigate={() => setMoreOpen(false)} />
          </div>
        </>
      )}
    </div>
  );
}
