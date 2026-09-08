import { expect, test, type Page } from '@playwright/test';

const adminUser = {
  user_id: 'user-1',
  tenant_id: 'tenant-1',
  organization_id: 'org-1',
  email: 'admin@example.com',
  display_name: 'Demo Admin',
  roles: ['ADMIN'],
  permissions: ['reports:read'],
};

const report = {
  from_date: '2026-01-01',
  to_date: '2026-12-31',
  rows: [
    { account_code: '1001', account_name: 'Operating bank', account_type: 'asset', debit: '1070.00', credit: '0.00', balance: '1070.00' },
    { account_code: '4000', account_name: 'Revenue', account_type: 'revenue', debit: '0.00', credit: '1070.00', balance: '-1070.00' },
  ],
  total_debit: '1070.00',
  total_credit: '1070.00',
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

test('trial balance loads posted ledger data with date scope and totals', async ({ page }) => {
  await configureConnectedWorkspace(page);
  let requestedUrl = '';
  await page.route('**/v1/reports/trial-balance**', async (route) => {
    requestedUrl = route.request().url();
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(report) });
  });

  await page.goto('/reports/trial-balance');

  await expect(page.getByRole('heading', { name: 'Reports & insights', exact: true })).toBeVisible();
  await expect(page.getByText('Operating bank', { exact: true })).toBeVisible();
  await expect(page.getByText('THB 1,070.00', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Balanced', { exact: true })).toBeVisible();
  expect(requestedUrl).toContain('from_date=2026-01-01');
  expect(requestedUrl).toContain('to_date=2026-12-31');
});

test('trial balance date controls reload the server report contract', async ({ page }) => {
  await configureConnectedWorkspace(page);
  const requestedUrls: string[] = [];
  await page.route('**/v1/reports/trial-balance**', async (route) => {
    requestedUrls.push(route.request().url());
    const url = new URL(route.request().url());
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...report, from_date: url.searchParams.get('from_date'), to_date: url.searchParams.get('to_date') }) });
  });

  await page.goto('/reports/trial-balance');
  await page.getByLabel('From date').fill('2026-04-01');
  await page.getByLabel('To date').fill('2026-06-30');
  await page.getByRole('button', { name: 'Run report' }).click();

  await expect.poll(() => requestedUrls.at(-1) || '').toContain('from_date=2026-04-01');
  expect(requestedUrls.at(-1)).toContain('to_date=2026-06-30');
});

test('unsupported report pages stay explicit about the backend contract', async ({ page }) => {
  await configureConnectedWorkspace(page);
  await page.goto('/reports/profit-loss');

  await expect(page.getByRole('heading', { name: 'Profit & loss', exact: true })).toBeVisible();
  await expect(page.getByText('Report contract pending', { exact: true }).last()).toBeVisible();
  await expect(page.getByText('No unsupported financial values are fabricated.', { exact: true })).toBeVisible();
});
