import { useEffect, useState } from 'react';
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import Account from '../modules/identity/Account.jsx';
import { getToken, setToken } from '../api/http.js';
import * as identityApi from '../api/identity.js';
import { BRAND, LOGO_MARK } from '../lib/brand.js';
import { Button, Icon, Loading, Menu } from '../ds/index.jsx';
import Login from '../modules/identity/Login.jsx';
import { useKeyboardOpen } from '../lib/hooks.js';
import Version from '../modules/system/Version.jsx';
import { PAGE_ICONS } from './nav.js';
import { REDIRECTS, ROUTES } from './routes.jsx';
import { useSalesData } from '../modules/requests/useFormData.js';
import SetPassword from '../modules/identity/SetPassword.jsx';

// Pages shown in the phone's bottom bar before the rest move to «المزيد»
const BOTTOM_NAV_SIZE = 3;

/** A page this user may not open. Shown instead of the screen, never instead of the server's check. */
function NoAccess() {
  return (
    <div className="fl-blank">
      <div>
        <div className="fl-blank__title">هذه الصفحة غير متاحة لك</div>
        <p className="fl-muted">تواصل مع مدير النظام إن كنت تحتاج صلاحيتها.</p>
      </div>
    </div>
  );
}


function NavItem({ page, onNavigate }) {
  return (
    <li>
      <NavLink to={page.path} className="fl-navlink" onClick={onNavigate}>
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
  // While the phone's keyboard is open, the bars at the bottom get out of its way
  useKeyboardOpen();
  const location = useLocation();
  const navigate = useNavigate();
  // Shown on the login screen, e.g. after setting a password
  const [notice, setNotice] = useState('');

  useEffect(() => {
    if (!getToken()) return;
    identityApi.me().then(setUser).catch(() => setToken(null)).finally(() => setLoading(false));
  }, []);

  const departments = user?.navigation || [];
  // Form definitions, our product catalog and Daftra's lists, for the sales pages
  // The «الطلبات» group: loaded once for anyone who has any of its pages
  const sales = useSalesData(departments.some((group) => group.key === 'requests'));

  useEffect(() => setMoreOpen(false), [location.pathname]);

  async function logout() {
    await identityApi.logOut().catch(() => {});
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

  const reloadUser = () => identityApi.me().then(setUser).catch(() => {});
  const pages = departments.flatMap((department) => department.pages);
  // The menu keys this user may open; a route of any other shows the no-access page
  const allowed = new Set(pages.map((page) => page.key));
  const bottomPages = pages.slice(0, BOTTOM_NAV_SIZE);
  const hasMore = pages.length > BOTTOM_NAV_SIZE;
  const inMore = hasMore && !bottomPages.some((page) => location.pathname === page.path);
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
        <div className="fl-brand"><img className="fl-brand__logo" src={LOGO_MARK} alt="" />{BRAND}</div>
        <NavGroups departments={departments} />
      </nav>

      <div className="fl-main-col">
        {/* Nothing is reaching Daftra: say so on every page, so no one takes a made-up
            invoice number for a real one. The backend turns this on with DAFTRA_FAKE. */}
        {user.daftra_fake && (
          <div className="fl-fakebar" role="status">دفترة تجريبية: لا يصل شيء إلى دفترة</div>
        )}
        <header className="fl-topbar">
          <div className="fl-brand fl-topbar__brand"><img className="fl-brand__logo" src={LOGO_MARK} alt="" />{BRAND}</div>
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
              {/* The paths the portal used before; emails already sent link to them */}
              {Object.entries(REDIRECTS).map(([from, to]) => (
                <Route key={from} path={from} element={<Navigate to={to} replace />} />
              ))}
              {ROUTES.map(({ key, path, screen: Screen, open }) => (
                <Route
                  key={path}
                  path={path}
                  element={open || allowed.has(key)
                    ? <Screen user={user} sales={sales} />
                    : <NoAccess />}
                />
              ))}
              <Route path="*" element={<Navigate to={pages[0].path} replace />} />
            </Routes>
          )}
          {/* Only on the الإدارة pages */}
          {location.pathname.startsWith('/admin/') && <Version />}
        </main>
      </div>

      {pages.length > 0 && (
        <nav className="fl-bottomnav" aria-label="التنقل الرئيسي">
          {bottomPages.map((page) => (
            <NavLink key={page.key} to={page.path} className="fl-bottomnav__item">
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
