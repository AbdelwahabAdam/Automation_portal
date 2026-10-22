import AuditLog from './admin/AuditLog.jsx';
import Catalog from './admin/Catalog.jsx';
import DaftraSync from './admin/DaftraSync.jsx';
import MailTest from './admin/MailTest.jsx';
import Permissions from './admin/Permissions.jsx';
import Users from './admin/Users.jsx';
import { MyRequestsPage, NewRequestPage } from './Sales.jsx';
import Review from './Review.jsx';

// The screen for each page key in backend/app/pages.py.
// A page without an entry here shows as a blank page with its label.
export const PAGE_COMPONENTS = {
  'sales.new_request': NewRequestPage,
  'sales.my_requests': MyRequestsPage,
  'sales.review': Review,
  'admin.users': Users,
  'admin.permissions': Permissions,
  'admin.audit': AuditLog,
  'admin.catalog': Catalog,
  'admin.daftra_sync': DaftraSync,
  'admin.mail': MailTest,
};

// Sidebar and bottom-bar icon for each page (from the design system's icon set)
export const PAGE_ICONS = {
  'sales.new_request': 'grid',
  'sales.my_requests': 'inbox',
  'sales.review': 'check-circle',
  'data_entry.home': 'file-text',
  'accounting.home': 'receipt',
  'operations.home': 'tool',
  'admin.users': 'users',
  'admin.permissions': 'shield',
  'admin.audit': 'history',
  'admin.catalog': 'package',
  'admin.daftra_sync': 'refresh',
  'admin.mail': 'mail',
};
