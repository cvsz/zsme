import { expect, test, type Page } from '@playwright/test';

const adminUser = {
  user_id: 'user-1',
  tenant_id: 'tenant-1',
  organization_id: 'org-1',
  email: 'admin@example.com',
  display_name: 'Demo Admin',
  roles: ['ADMIN'],
  permissions: ['ar:read', 'partner:read'],
};

const partner = {
  id: 'partner-1',
  tenant_id: 'tenant-1',
  organization_id: 'org-1',
  partner_code: 'CUS-0001',
  partner_type: 'customer',
  display_name: 'Siam Craft Co., Ltd.',
  legal_name: null,
  tax_id: null,
  tax_branch: '00000',
  email: null,
  phone: null,
  payment_terms_days: 30,
  credit_limit: '0.00',
  is_active: true,
  version: 1,
  tags: [],
  addresses: [],
};

const invoice = {
  id: 'document-1',
  tenant_id: 'tenant-1',
  organization_id: 'org-1',
  document_type: 'sales_invoice',
  document_number: 'INV-0001',
  partner_id: 'partner-1',
  issue_date: '2026-09-08',
  due_date: '2026-10-08',
  currency_code: 'THB',
  control_account_code: '1100',
  tax_account_code: '2101',
  memo: null,
  subtotal: '1000.00',
  tax_total: '70.00',
  total: '1070.00',
  status: 'posted',
  ledger_entry_id: 'entry-1',
  posted_at: '2026-09-08T10:00:00Z',
  version: 2,
  lines: [],
};

async function configureConnectedWorkspace(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem('zsme-api-base-url', 'http://api.test');
    window.sessionStorage.setItem('zsme-access-token', 'session-token');
  });
  await page.route('**/v1/auth/me', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(adminUser) });
  });
}

test('sales control center loads customer and invoice data from live contracts', async ({ page }) => {
  await configureConnectedWorkspace(page);
  await page.route('**/v1/partners*', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([partner]) });
  });
  await page.route('**/v1/ar/invoices**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([invoice]) });
  });

  await page.goto('/sales');

  await expect(page.getByRole('heading', { name: 'Sales & billing', exact: true })).toBeVisible();
  await expect(page.getByText('Siam Craft Co., Ltd.', { exact: true })).toBeVisible();
  await expect(page.getByRole('cell', { name: /INV-0001/ })).toBeVisible();
  await expect(page.getByText('THB 1,070.00', { exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Create invoice' })).toHaveAttribute('href', '/invoices?create=1');
  await page.getByRole('link', { name: 'Create invoice' }).click();
  await expect(page.getByRole('heading', { name: 'Create invoice', exact: true })).toBeVisible();
});

test('sales control center reports a safe API failure without financial values', async ({ page }) => {
  await configureConnectedWorkspace(page);
  await page.route('**/v1/partners*', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });
  await page.route('**/v1/ar/invoices**', async (route) => {
    await route.fulfill({ status: 503, contentType: 'application/problem+json', body: JSON.stringify({ status: 503, detail: 'temporary outage' }) });
  });

  await page.goto('/sales');

  await expect(page.getByRole('alert', { name: 'Sales data needs attention' })).toContainText('Sales data is unavailable');
  await expect(page.getByText('THB 1,070.00', { exact: true })).toHaveCount(0);
});
