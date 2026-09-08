import { expect, test, type Page } from '@playwright/test';

const adminUser = {
  user_id: 'user-1',
  tenant_id: 'tenant-1',
  organization_id: 'org-1',
  email: 'admin@example.com',
  display_name: 'Demo Admin',
  roles: ['ADMIN'],
  permissions: ['accounting:read', 'accounting:write'],
};

const account = {
  id: 'account-1',
  tenant_id: 'tenant-1',
  organization_id: 'org-1',
  code: '1001',
  name: 'Operating bank',
  account_type: 'asset',
  parent_id: null,
  is_control: false,
  is_active: true,
  version: 1,
};

const period = {
  id: 'period-1',
  tenant_id: 'tenant-1',
  organization_id: 'org-1',
  name: 'FY2026',
  start_date: '2026-01-01',
  end_date: '2026-12-31',
  status: 'open',
  locked_at: null,
  version: 1,
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

test('chart of accounts loads live tenant records and filters locally', async ({ page }) => {
  await configureConnectedWorkspace(page);
  await page.route('**/v1/accounting/accounts**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([account, { ...account, id: 'account-2', code: '4000', name: 'Revenue', account_type: 'revenue' }]) });
  });

  await page.goto('/accounting/chart-of-accounts');

  await expect(page.getByRole('heading', { name: 'Chart of accounts', exact: true })).toBeVisible();
  await expect(page.getByRole('cell', { name: '1001', exact: true })).toBeVisible();
  await expect(page.getByRole('cell', { name: /Operating bank/ })).toBeVisible();
  await page.getByLabel('Search Chart of accounts').fill('Revenue');
  await expect(page.getByRole('cell', { name: '4000', exact: true })).toBeVisible();
  await expect(page.getByRole('cell', { name: '1001', exact: true })).toHaveCount(0);
});

test('chart of accounts creation sends an idempotent organization-scoped request', async ({ page }) => {
  await configureConnectedWorkspace(page);
  let requestBody: Record<string, unknown> | undefined;
  let idempotencyKey = '';
  await page.route('**/v1/accounting/accounts**', async (route) => {
    if (route.request().method() === 'POST') {
      requestBody = JSON.parse(route.request().postData() || '{}') as Record<string, unknown>;
      idempotencyKey = route.request().headers()['idempotency-key'] || '';
      await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify({ ...account, id: 'account-2', code: '4000', name: 'Revenue', account_type: 'revenue' }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });

  await page.goto('/accounting/chart-of-accounts');
  await page.getByRole('button', { name: 'Add account' }).click();
  await page.getByLabel('Account code').fill('4000');
  await page.getByLabel('Account name').fill('Revenue');
  await page.getByLabel('Account type', { exact: true }).selectOption('revenue');
  await page.locator('section[aria-labelledby="create-account-title"]').getByRole('button', { name: 'Create account', exact: true }).click();

  await expect(page.getByText('Account created')).toBeVisible();
  await expect(page.getByRole('cell', { name: '4000', exact: true })).toBeVisible();
  expect(requestBody).toMatchObject({ code: '4000', name: 'Revenue', account_type: 'revenue', is_control: false });
  expect(idempotencyKey).toMatch(/^accounting-account-create-/);
});

test('fiscal periods load and expose an explicit lock control', async ({ page }) => {
  await configureConnectedWorkspace(page);
  await page.route('**/v1/accounting/periods**', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...period, status: 'locked', locked_at: '2026-09-08T10:00:00Z', version: 2 }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([period]) });
  });

  await page.goto('/accounting/periods');

  await expect(page.getByRole('heading', { name: 'Fiscal periods', exact: true })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'FY2026', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Lock FY2026' })).toBeVisible();
});

test('locking a fiscal period is a separate idempotent control action', async ({ page }) => {
  await configureConnectedWorkspace(page);
  let lockKey = '';
  await page.route('**/v1/accounting/periods**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([period]) });
  });
  await page.route('**/v1/accounting/periods/period-1/lock', async (route) => {
    lockKey = route.request().headers()['idempotency-key'] || '';
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...period, status: 'locked', locked_at: '2026-09-08T10:00:00Z', version: 2 }) });
  });

  await page.goto('/accounting/periods');
  await page.getByRole('button', { name: 'Lock FY2026' }).click();

  await expect(page.getByText('Fiscal period locked')).toBeVisible();
  expect(lockKey).toMatch(/^accounting-period-lock-/);
});
