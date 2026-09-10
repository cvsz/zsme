import { expect, test, type Page } from '@playwright/test';

const adminUser = {
  user_id: 'user-1',
  tenant_id: 'tenant-1',
  organization_id: 'org-1',
  email: 'admin@example.com',
  display_name: 'Demo Admin',
  roles: ['ADMIN'],
  permissions: ['dashboard:read'],
};

const summary = {
  organization_id: 'org-1',
  as_of: '2026-09-08',
  currency_code: 'THB',
  cash_position: '1070.00',
  receivables: '2500.00',
  payables: '800.00',
  open_invoices: 2,
  open_bills: 1,
  customer_count: 4,
  vendor_count: 3,
  unmatched_bank_transactions: 1,
  recent_activity: [{
    id: 'event-1',
    action: 'journal.post',
    entity_type: 'journal_entry',
    entity_id: 'entry-1',
    correlation_id: 'corr-1',
    created_at: '2026-09-08T10:00:00Z',
  }],
};

async function configureConnectedWorkspace(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem('zsme-api-base-url', 'http://127.0.0.1:8000');
    window.sessionStorage.setItem('zsme-access-token', 'session-token');
  });
  await page.route('**/v1/auth/me', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(adminUser) });
  });
}

test('dashboard renders server-derived executive metrics and activity', async ({ page }) => {
  await configureConnectedWorkspace(page);
  await page.route('**/v1/dashboard/summary**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(summary) });
  });

  await page.goto('/dashboard');

  await expect(page.getByRole('heading', { name: 'Business control center', exact: true })).toBeVisible();
  await expect(page.getByText('THB 1,070.00', { exact: true })).toBeVisible();
  await expect(page.getByText('THB 2,500.00', { exact: true })).toBeVisible();
  await expect(page.getByText('journal.post', { exact: true })).toBeVisible();
  await expect(page.getByText('1 unmatched', { exact: true })).toBeVisible();
});

test('dashboard keeps financial values unavailable when the summary API fails', async ({ page }) => {
  await configureConnectedWorkspace(page);
  await page.route('**/v1/dashboard/summary**', async (route) => {
    await route.fulfill({ status: 503, contentType: 'application/problem+json', body: JSON.stringify({ status: 503, code: 'service_unavailable', detail: 'temporary outage' }) });
  });

  await page.goto('/dashboard');

  await expect(page.getByRole('alert', { name: 'Dashboard data needs attention' })).toContainText('Dashboard data is unavailable');
  await expect(page.getByText('THB 1,070.00', { exact: true })).toHaveCount(0);
});
