// Where each page lives and how it looks in the menus.

// Each menu entry carries its own path now (GET /api/auth/me), so there is no mapping here.
// Kept for the few places that still link to a page by key.
export const pagePath = (key) => '/' + key.replace('.', '/');

// Sidebar and bottom-bar icon for each page (from the design system's icon set)
export const PAGE_ICONS = {
  forms: 'grid',
  my_requests: 'inbox',
  review: 'check-circle',
  'admin.users': 'users',
  'admin.roles': 'shield',
  'admin.audit': 'history',
  'admin.catalog': 'package',
  'admin.sync': 'refresh',
  'admin.order_sources': 'link',
  'admin.mail': 'mail',
};
