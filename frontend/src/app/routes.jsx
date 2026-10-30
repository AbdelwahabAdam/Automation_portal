// A URL for every screen, every form and every request.
//
// `key` is the menu key the route belongs to (app/core/permissions.py's MENU): a route whose key
// the user does not hold shows the no-access page. `open: true` means any signed-in user may try
// it and the server decides — a request is readable by its owner and by anyone who may view or
// review that request's form, which only the server can say.
import AuditLog from '../modules/audit/AuditLog.jsx';
import Catalog from '../modules/catalog/Catalog.jsx';
import Roles from '../modules/identity/Roles.jsx';
import Users from '../modules/identity/Users.jsx';
import OrderSources from '../modules/lookups/OrderSources.jsx';
import MailTest from '../modules/notifications/MailTest.jsx';
import {
  EditRequestScreen, FormsScreen, MyRequestsScreen, NewRequestScreen, RequestScreen, ReviewRequestScreen, ReviewScreen,
} from '../modules/requests/screens.jsx';
import Sync from '../modules/system/Sync.jsx';

export const ROUTES = [
  { key: 'forms', path: '/forms', screen: FormsScreen },
  { key: 'forms', path: '/forms/:formKey', screen: NewRequestScreen },
  { key: 'my_requests', path: '/requests/mine', screen: MyRequestsScreen },
  // Its owner, or anyone who may view or review its form: the server decides
  { key: 'my_requests', path: '/requests/:requestId', screen: RequestScreen, open: true },
  { key: 'my_requests', path: '/requests/:requestId/edit', screen: EditRequestScreen, open: true },
  { key: 'review', path: '/review', screen: ReviewScreen },
  { key: 'review', path: '/review/:requestId', screen: ReviewRequestScreen },
  { key: 'admin.users', path: '/admin/users', screen: Users },
  { key: 'admin.roles', path: '/admin/roles', screen: Roles },
  { key: 'admin.audit', path: '/admin/audit', screen: AuditLog },
  { key: 'admin.catalog', path: '/admin/catalog', screen: Catalog },
  { key: 'admin.sync', path: '/admin/sync', screen: Sync },
  { key: 'admin.order_sources', path: '/admin/order-sources', screen: OrderSources },
  { key: 'admin.mail', path: '/admin/mail', screen: MailTest },
];

// The paths the portal used before. They redirect for good, because emails already sent and
// bookmarks already made link to them.
export const REDIRECTS = {
  '/sales/new_request': '/forms',
  '/sales/my_requests': '/requests/mine',
  '/sales/review': '/review',
  '/admin/permissions': '/admin/roles',
  '/admin/daftra_sync': '/admin/sync',
  '/admin/order_sources': '/admin/order-sources',
};
